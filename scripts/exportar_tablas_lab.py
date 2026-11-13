"""Exporta del Moodle de laboratorio las tablas de unos cursos en el formato de la solicitud a EVEA.

Sirve para probar `alerta.fuentes.tablas_moodle` y `alerta.validacion_evea` antes de recibir los
datos reales: un CSV por tabla, con el nombre estándar sin prefijo, encabezado y tiempo Unix. Para
los cursos que reproducen OULAD (idnumber `OULAD-<curso>`), escribe además `resultado_final.csv`
(sección 3.6 de la solicitud) con el resultado final de OULAD, porque el laboratorio no tiene nota
final en el libro de calificaciones.

Uso (con el contenedor de la base de datos en marcha):
    .venv/bin/python scripts/exportar_tablas_lab.py --cursos 45 --salida /ruta/carpeta
"""

from __future__ import annotations

import argparse
import io
import subprocess
from pathlib import Path

import pandas as pd

from alerta import config

CONTAINER, DB, USER, PREFIX = "alerta_moodle-db-1", "moodle", "moodle", "m_"
ENROL = ("'\\core\\event\\user_enrolment_created','\\core\\event\\user_enrolment_deleted',"
         "'\\core\\event\\user_enrolment_updated','\\core\\event\\role_assigned','\\core\\event\\role_unassigned'")


def query(sql: str) -> pd.DataFrame:
    out = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", USER, "-d", DB, "-c",
                          f"COPY ({sql}) TO STDOUT WITH CSV HEADER"], capture_output=True, text=True, check=True)
    return pd.read_csv(io.StringIO(out.stdout), low_memory=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cursos", type=int, nargs="+", required=True)
    ap.add_argument("--salida", type=Path, required=True)
    args = ap.parse_args()
    c = ",".join(map(str, args.cursos))
    p = PREFIX
    tables = {
        "course": f"select * from {p}course where id in ({c})",
        "context": f"select * from {p}context",
        "role": f"select * from {p}role",
        "role_assignments": f"select * from {p}role_assignments",
        "modules": f"select * from {p}modules",
        "course_modules": f"select * from {p}course_modules where course in ({c})",
        "assign": f"select * from {p}assign where course in ({c})",
        "assign_submission": f"select s.* from {p}assign_submission s join {p}assign a on a.id = s.assignment where a.course in ({c})",
        "quiz": f"select * from {p}quiz where course in ({c})",
        "grade_items": f"select * from {p}grade_items where courseid in ({c})",
        "grade_grades": f"select g.* from {p}grade_grades g join {p}grade_items i on i.id = g.itemid where i.courseid in ({c})",
        "grade_grades_history": f"select h.* from {p}grade_grades_history h join {p}grade_items i on i.id = h.itemid where i.courseid in ({c})",
        "scale": f"select * from {p}scale",
        "logstore_standard_log": f"select * from {p}logstore_standard_log where courseid in ({c}) and (edulevel = 2 or eventname in ({ENROL}))",
    }
    args.salida.mkdir(parents=True, exist_ok=True)
    for name, sql in tables.items():
        df = query(sql)
        df.to_csv(args.salida / f"{name}.csv", index=False)
        print(f"{name}: {len(df)} filas")

    # Resultado final de OULAD para los cursos que lo reproducen (usuarios `e<id_student>`)
    courses = query(f"select id, idnumber, startdate from {p}course where id in ({c})")
    users = query(f"select id, username from {p}user where username like 'e%'")
    users = users[users["username"].str[1:].str.isdigit()].assign(id_student=lambda u: u["username"].str[1:].astype(int))
    info = pd.read_csv(config.OULAD_DIR / "studentInfo.csv").merge(
        pd.read_csv(config.OULAD_DIR / "studentRegistration.csv"),
        on=["code_module", "code_presentation", "id_student"], how="left")
    info["date_unregistration"] = pd.to_numeric(info["date_unregistration"], errors="coerce")  # OULAD: «?»
    rows = []
    for r in courses.itertuples():
        if not str(r.idnumber).startswith("OULAD-"):
            continue
        module, presentation = str(r.idnumber)[6:].split("_")
        si = info[(info["code_module"] == module) & (info["code_presentation"] == presentation)]
        m = si.merge(users, on="id_student")
        for s in m.itertuples():
            baja = s.final_result == "Withdrawn"
            nota = {"Fail": 2, "Pass": 4, "Distinction": 5}.get(s.final_result)
            rows.append({"course_id": r.id, "student_id": s.id, "nota_final": nota,
                         "condicion": "baja" if baja else ("desaprobado" if nota == 2 else "aprobado"),
                         "fecha_baja": (int(r.startdate + s.date_unregistration * 86400)
                                        if pd.notna(s.date_unregistration) else None)})
    if rows:
        pd.DataFrame(rows).to_csv(args.salida / "resultado_final.csv", index=False)
        print(f"resultado_final: {len(rows)} filas")


if __name__ == "__main__":
    main()
