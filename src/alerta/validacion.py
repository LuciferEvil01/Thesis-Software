"""F5: validación de extremo a extremo con un curso de OULAD reproducido en el Moodle local.

1. Se crea en Moodle el curso de OULAD completo (estudiantes, TMA, entregas, notas y cada clic
   como un evento del registro), con todos los estudiantes matriculados.
2. Para cada corte, en orden, se desmatricula a quien ya se había dado de baja el día del corte
   (así queda el curso como lo vería el servicio ese día), se extrae por el web service, se
   calculan las variables y se predice con el modelo activo.
3. Se compara con lo mismo calculado directamente sobre OULAD: mismos estudiantes, mismas
   variables y mismas probabilidades y alertas.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from alerta import config, variables
from alerta.calificacion import ProporcionalOULAD
from alerta.fuentes import moodle, oulad
from alerta.modelo.registro import Registro
from alerta.moodle import sembrar
from alerta.moodle.cliente import Cliente

START_2014J = 1412121600  # 2014-10-01 00:00 UTC, inicio aproximado de las presentaciones «J» de 2014
COMPARED = [f for f in variables.FEATURES if f != "repeated_course"]  # Moodle no sabe si repite


def replay_oulad(course_id: str = "AAA_2014J", start_ts: int = START_2014J, log=print) -> dict:
    d, labels = oulad.load(config.OULAD_DIR)
    reference = variables.build(d)  # OULAD completo: los percentiles por curso son los mismos
    reference = reference[reference["course_id"] == course_id]
    paquete = Registro(config.MODELOS_DIR).active()
    idnumber = f"OULAD-{course_id}"

    t0 = time.time()
    spec = sembrar.spec_from_canonico(d, course_id, start_ts, idnumber, f"OULAD {course_id} (reproducción)",
                                      unenrol_withdrawn=False)
    seeded = sembrar.seed(spec)
    seed_s = time.time() - t0
    log(f"sembrado {idnumber} (curso {seeded['courseid']}): {len(spec['students'])} estudiantes, "
        f"{sum(a['events'] for a in spec['activity'])} eventos, {seed_s:.0f} s")

    to_oulad = {mid: int(u[1:]) for u, mid in seeded["users"].items()}
    students = d.students[d.students["course_id"] == course_id].set_index("student_id")
    cuts = variables.cuts(d)
    cuts = cuts[cuts["course_id"] == course_id].set_index("cut")["cutoff_day"]
    client = Cliente.desde_config()
    report = {"curso": course_id, "moodle_courseid": seeded["courseid"], "modelo": paquete.version,
              "estudiantes": len(students), "eventos": int(sum(a["events"] for a in spec["activity"])),
              "segundos_sembrado": round(seed_s), "cortes": {}}

    gone: set[int] = set()
    for cut in variables.CUTS:
        cutoff = cuts[cut]
        withdrawn = set(students.index[students["unregistered_day"] <= cutoff]) - gone
        sembrar.unenrol(idnumber, [f"e{s}" for s in sorted(withdrawn)])
        gone |= withdrawn

        t0 = time.time()
        # Notas de OULAD (0–100) en Moodle: se traducen sin conversión para comparar con OULAD
        extracted, info = moodle.extract_course(client, seeded["courseid"], calificacion=ProporcionalOULAD())
        extract_s = time.time() - t0
        got = variables.build(extracted)
        got = got[got["cut"].astype(str) == cut].copy()
        got["student_id"] = got["student_id"].map(to_oulad)
        got["course_id"] = course_id
        ref = reference[reference["cut"].astype(str) == cut]

        same_rows = set(got["student_id"]) == set(ref["student_id"])
        m = got.merge(ref, on="student_id", suffixes=("", "_oulad"))
        diffs = {f: float(np.nanmax(np.abs(m[f].astype(float) - m[f"{f}_oulad"].astype(float)), initial=0))
                 for f in COMPARED if m[f].notna().any() or m[f"{f}_oulad"].notna().any()}
        p_got = paquete.predict(got).set_index("student_id")
        p_ref = paquete.predict(ref).set_index("student_id")
        common = p_ref.index
        y = labels[labels["course_id"] == course_id].set_index("student_id").loc[common, "at_risk"]
        report["cortes"][cut] = {
            "dia_de_corte": int(cutoff), "estudiantes_moodle": len(got), "estudiantes_oulad": len(ref),
            "mismos_estudiantes": same_rows, "max_dif_variables": max(diffs.values()),
            "max_dif_probabilidad": float(np.abs(p_got.loc[common, "prob"] - p_ref["prob"]).max()),
            "mismas_alertas": bool((p_got.loc[common, "en_riesgo"] == p_ref["en_riesgo"]).all()),
            "alertas": int(p_got["en_riesgo"].sum()),
            "roc_auc_curso": float(roc_auc_score(y, p_got.loc[common, "prob"])),
            "segundos_extraccion": round(extract_s, 1),
        }
        log(f"{cut}: {report['cortes'][cut]}")
    report["ok"] = all(c["mismos_estudiantes"] and c["max_dif_variables"] < 1e-9 and c["mismas_alertas"]
                       for c in report["cortes"].values())
    return report
