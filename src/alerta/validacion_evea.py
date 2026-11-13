"""Validación del modelo con cursos cerrados de EVEA: el protocolo E26 de `Proposal/DECISIONES.md`.

El modelo y el umbral son los del paquete activo, sin cambios (no se reentrena). Pasos:

1. Se leen las tablas de Moodle (`fuentes.tablas_moodle`) y se agrupan los cursos por periodo.
2. El periodo más antiguo solo sirve de «cursos anteriores» para la conversión equipercentil de las
   notas; en cada periodo evaluado, la referencia son los cursos de todos los periodos previos.
3. Momentos de predicción: (a) principal, los tres equivalentes a los cortes del Cap. 2 (la tarea
   más próxima al 25 % y al 50 % del curso y la última), el primer día en que tiene publicadas el
   90 % de las notas de quienes la entregaron; (b) secundario, cada tarea el día en que queda completa.
   El ajuste del modelo es el del sistema según la posición de la tarea en el curso.
4. Cursos que entran en cada momento: al menos 20 estudiantes con resultado conocido, 5 en riesgo y
   5 que aprueban.
5. Métricas: ROC-AUC del modelo y de la regla de la nota (orden por la nota media con ceros en la
   escala del curso) por curso y su media; diferencia con IC del 95 % por bootstrap de cursos;
   calibración por deciles; marcados, sensibilidad, especificidad y precisión con el umbral.

Uso:
    python -m alerta validar-evea --tablas /ruta/csv --salida data/validacion_evea
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from alerta import calificacion, config, variables
from alerta.canonico import Canonico
from alerta.fuentes import tablas_moodle
from alerta.modelo.registro import Registro
from alerta.servicio import course_scale

MIN_STUDENTS, MIN_CLASS = 20, 5
MAX_WAIT = 90  # días tras la fecha de la tarea en que se busca el 90 % de notas publicadas
N_BOOT, SEED = 1000, 42
TYPES = variables.DEFAULT_TYPES


def subset(d: Canonico, courses) -> Canonico:
    keep = lambda df: df[df["course_id"].isin(set(courses))].reset_index(drop=True)
    return Canonico(courses=keep(d.courses), students=keep(d.students), assessments=keep(d.assessments),
                    grades=keep(d.grades), activity=keep(d.activity))


def reference_grades(d: Canonico) -> pd.DataFrame:
    """Notas en la escala del ítem de unos cursos, para `calificacion.referencia`."""
    a = d.assessments[d.assessments["module_type"].isin(TYPES)]
    return d.grades.merge(a[["course_id", "item_id", "grademin", "grademax", "gradepass"]], on=["course_id", "item_id"])


def moments(d: Canonico) -> list[dict]:
    """Momentos de predicción de un curso: los tres principales y uno por tarea completa."""
    out, first_day, complete_day = [], {}, {}
    due = d.assessments.set_index("item_id")["due_day"]
    for item in d.assessments.loc[d.assessments["is_tma"].astype(bool), "item_id"]:
        for day in range(int(due[item]), int(due[item]) + MAX_WAIT + 1):
            ev = variables.evaluations(d, day, TYPES)
            row = ev[ev["item_id"] == item].iloc[0]
            if item not in first_day and row["entregas"] > 0 and row["proporcion"] >= variables.MIN_GRADED:
                first_day[item] = (day, row)
            if row["completa"]:
                complete_day[item] = (day, row)
                break
    for c in variables.cuts(d).itertuples():
        if c.anchor_item in first_day:
            day, row = first_day[c.anchor_item]
            out.append({"momento": c.cut, "tipo": "principal", "day": day, "at": variables.moment(row, day)})
    for item, (day, row) in complete_day.items():
        out.append({"momento": f"tarea {int(row['k'])}", "tipo": "secundario", "day": day,
                    "at": variables.moment(row, day)})
    return out


def evaluate_course(d: Canonico, labels: pd.DataFrame, paquete) -> list[dict]:
    rows_out = []
    for m in moments(d):
        rows = variables.build(d, TYPES, at=m["at"])
        rows = rows.merge(labels, on=["course_id", "student_id"])
        rows = rows[rows["at_risk"].notna()]
        n, pos = len(rows), int(rows["at_risk"].sum())
        base = {"course_id": int(d.courses["course_id"].iloc[0]), "momento": m["momento"], "tipo": m["tipo"],
                "dia": int(m["day"]), "estudiantes": n, "en_riesgo": pos}
        if n < MIN_STUDENTS or pos < MIN_CLASS or n - pos < MIN_CLASS:
            rows_out.append({**base, "excluido": True})
            continue
        pred = paquete.predict(rows)
        scale, _ = course_scale(d, rows.assign(anchor_due=int(m["at"]["anchor_due"].iloc[0])), TYPES)
        rule = rows[["course_id", "student_id"]].merge(scale, on=["course_id", "student_id"], how="left")["nota_media"]
        y = rows["at_risk"].astype(int).to_numpy()
        rows_out.append({**base, "excluido": False,
                         "auc_modelo": float(roc_auc_score(y, pred["prob"])),
                         "auc_regla": float(roc_auc_score(y, -rule.fillna(rule.median()))),
                         "y": y.tolist(), "prob": pred["prob"].round(6).tolist(),
                         "alerta": pred["en_riesgo"].astype(int).tolist()})
    return rows_out


def summarize(results: pd.DataFrame) -> dict:
    rng = np.random.default_rng(SEED)
    out = {}
    for momento, g in results[~results["excluido"]].groupby("momento", sort=False):
        diff = (g["auc_modelo"] - g["auc_regla"]).to_numpy()
        boot = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(N_BOOT)] if len(diff) > 1 else [np.nan]
        y = np.concatenate(g["y"].to_list()); p = np.concatenate(g["prob"].to_list())
        a = np.concatenate(g["alerta"].to_list()).astype(bool)
        dec = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False)
        cal = pd.DataFrame({"p": p, "y": y, "d": dec}).groupby("d").agg(prob_media=("p", "mean"), observado=("y", "mean"))
        tp, fp = int((a & (y == 1)).sum()), int((a & (y == 0)).sum())
        out[momento] = {
            "tipo": g["tipo"].iloc[0], "cursos": len(g), "estudiantes": int(g["estudiantes"].sum()),
            "proporcion_en_riesgo": float(y.mean()),
            "auc_modelo_media": float(g["auc_modelo"].mean()), "auc_regla_media": float(g["auc_regla"].mean()),
            "diferencia_media": float(diff.mean()),
            "ic95_diferencia": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "cursos_con_ventaja": int((diff > 0).sum()),
            "marcados": float(a.mean()), "sensibilidad": tp / max(int((y == 1).sum()), 1),
            "especificidad": float(((~a) & (y == 0)).sum() / max(int((y == 0).sum()), 1)),
            "precision": tp / max(tp + fp, 1),
            "calibracion": cal.round(4).to_dict("records"),
        }
    return out


def run(tablas: Path, salida: Path, log=print, conversion=None, **cargar_kw) -> dict:
    """`conversion`: solo para la prueba con el laboratorio; si se da, se evalúan todos los periodos con
    ella en lugar de reservar el primero como referencia de la equipercentil (E26, punto 2)."""
    d, labels, courses, info = tablas_moodle.cargar(tablas, **cargar_kw)
    log(f"tablas: {info}")
    paquete = Registro(config.MODELOS_DIR).active()
    periods = sorted(courses["periodo"].unique())
    evaluated = periods if conversion is not None else periods[1:]
    log(f"periodos: {periods}; evaluados: {evaluated}")
    results = []
    for p in evaluated:
        if conversion is not None:
            conv = conversion
        else:
            previous = courses.loc[courses["periodo"] < p, "course_id"]
            ref = calificacion.referencia(reference_grades(subset(d, previous)))
            conv = calificacion.Equipercentil(escala=paquete.escala, referencia=ref)
        for cid in courses.loc[courses["periodo"] == p, "course_id"]:
            dc = tablas_moodle.convertir(subset(d, [cid]), conv)
            if not dc.assessments["is_tma"].astype(bool).any():
                results.append({"course_id": int(cid), "momento": None, "excluido": True, "motivo": "sin tareas con fecha"})
                continue
            for r in evaluate_course(dc, labels, paquete):
                results.append({**r, "periodo": p})
        log(f"{p}: {len(courses[courses['periodo'] == p])} cursos; conversión: {conv.nombre}")
    res = pd.DataFrame(results)
    summary = summarize(res.dropna(subset=["momento"]))
    report = {"protocolo": "E26 (Proposal/DECISIONES.md)", "modelo": paquete.version, "tablas": info,
              "periodos": periods, "excluidos": int(res["excluido"].sum()), "resumen": summary}
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "resumen.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    res.drop(columns=[c for c in ["y", "prob", "alerta"] if c in res]).to_csv(salida / "por_curso.csv", index=False)
    for momento, s in summary.items():
        log(f"{momento:9s} ({s['tipo']}): {s['cursos']} cursos, {s['estudiantes']} estudiantes | modelo "
            f"{s['auc_modelo_media']:.3f} · regla {s['auc_regla_media']:.3f} · diferencia {s['diferencia_media']:+.3f} "
            f"[{s['ic95_diferencia'][0]:+.3f}; {s['ic95_diferencia'][1]:+.3f}] · marcados {s['marcados']:.0%}")
    return report
