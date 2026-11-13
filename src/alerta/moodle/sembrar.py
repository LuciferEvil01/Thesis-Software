"""Crear cursos de prueba en el Moodle local a partir del esquema canónico (PLAN.md, F3–F4).

`spec_from_canonico` convierte un curso canónico en la especificación JSON de
`infra/moodle/fixtures/seed_course.php`, y `seed` la ejecuta en el contenedor. Solo para el
laboratorio local: escribe directamente en la base de datos de Moodle.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from alerta import config
from alerta.canonico import Canonico

LAB = config.ROOT / "infra" / "moodle" / "scripts" / "lab.sh"
SEED_DIR = config.ROOT / ".runtime" / "generated" / "seed"  # visible en el contenedor como /opt/alerta-generated/seed


def _opt(x):
    return None if pd.isna(x) else float(x)


ITEM_NAMES = {"assign": "Tarea", "quiz": "Cuestionario"}


def _item_name(items: pd.DataFrame, r) -> str:
    """«Tarea 2», «Cuestionario 1»…: el tipo en español y su orden por fecha dentro del tipo."""
    same = items[(items["module_type"] == r.module_type) & items["due_day"].notna()].sort_values(["due_day", "item_id"])
    k = list(same["item_id"]).index(r.item_id) + 1
    return f"{ITEM_NAMES.get(r.module_type, r.module_type)} {k}"


def spec_from_canonico(d: Canonico, course_id, start_ts: int, idnumber: str, fullname: str | None = None,
                       service_role: str | None = "teacher", unenrol_withdrawn: bool = True) -> dict:
    """Especificación de un curso canónico. Los estudiantes con baja quedan desmatriculados.

    `service_role`: rol con que el profesor matricula al servicio (None = el servicio no entra).
    Columnas opcionales de `assessments`: `gradepass` (nota para aprobar) y `online` (False = tarea
    sin entregas en línea, como un examen presencial registrado como tarea).
    `unenrol_withdrawn`: desmatricular ya a los estudiantes con baja; con False se hace después con
    `unenrol`, para simular el curso tal como estaba en una fecha.
    """
    course = d.courses.set_index("course_id").loc[course_id]
    students = d.students[d.students["course_id"] == course_id]
    items = d.assessments[(d.assessments["course_id"] == course_id) & d.assessments["module_type"].isin(["assign", "quiz"])]
    grades = d.grades[(d.grades["course_id"] == course_id) & d.grades["item_id"].isin(items["item_id"])]
    activity = d.activity[d.activity["course_id"] == course_id]
    activity = activity.groupby(["student_id", "day", "site_id"], as_index=False)["events"].sum()
    grademax = items.set_index("item_id")["grademax"]
    user = lambda sid: f"e{sid}"  # noqa: E731
    sites = sorted(s for s in activity["site_id"].unique() if s != 0)
    return {
        "course": {"idnumber": idnumber, "shortname": idnumber, "fullname": fullname or idnumber,
                   "startdate": int(start_ts), "length_days": int(course["length_days"])},
        "teacher": {"username": f"prof_{idnumber}".lower(), "firstname": "Profesor", "lastname": idnumber},
        "service_role": service_role,
        "students": [{"username": user(s.student_id), "firstname": "Estudiante", "lastname": str(s.student_id),
                      "withdrawn": unenrol_withdrawn and bool(pd.notna(s.unregistered_day))}
                     for s in students.itertuples()],
        "resources": [{"key": f"s{s}", "name": f"Recurso {s}"} for s in sites],
        "items": [{"key": f"i{r.item_id}", "type": r.module_type, "name": _item_name(items, r),
                   "due_day": float(r.due_day), "grademax": float(r.grademax),
                   "gradepass": float(getattr(r, "gradepass", 0) or 0), "online": bool(getattr(r, "online", True))}
                  for r in items.itertuples() if pd.notna(r.due_day)],
        "grades": [{"username": user(g.student_id), "item": f"i{g.item_id}", "submitted_day": _opt(g.submitted_day),
                    "raw": None if pd.isna(g.score) else float(g.score) * grademax[g.item_id] / 100,
                    "graded_day": _opt(g.graded_day)} for g in grades.itertuples()],
        "activity": [{"username": user(a.student_id), "day": int(a.day), "site": None if a.site_id == 0 else f"s{a.site_id}",
                      "events": int(a.events)} for a in activity.itertuples()],
    }


def seed(spec: dict) -> dict:
    """Crea el curso en el Moodle local. Devuelve courseid, startdate y los ids de sitios y usuarios."""
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    path = SEED_DIR / f"{spec['course']['idnumber']}.json"
    path.write_text(json.dumps(spec, ensure_ascii=False, default=lambda x: x.item() if isinstance(x, np.generic) else x))
    out = subprocess.run([str(LAB), "php", "/opt/alerta/seed_course.php", f"/opt/alerta-generated/seed/{path.name}"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def unenrol(idnumber: str, usernames: list[str]) -> dict:
    """Desmatricula estudiantes del curso `idnumber` (simula bajas)."""
    out = subprocess.run([str(LAB), "php", "/opt/alerta/unenrol.php", idnumber, *usernames],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def download_log(courseid: int, dest: Path, fmt: str = "csv") -> Path:
    """Descarga el registro de un curso como lo haría un profesor (Informes → Registros, «Participación»).

    Entra como administrador con las credenciales de `.env.local`. `fmt`: "csv" o "excel".
    """
    import os
    import re

    import requests
    from dotenv import dotenv_values

    env = {**dotenv_values(config.ROOT / ".env.local"), **os.environ}
    base = config.MOODLE_URL.rstrip("/")
    s = requests.Session()
    token = re.search(r'name="logintoken" value="([^"]+)"', s.get(f"{base}/login/index.php").text).group(1)
    s.post(f"{base}/login/index.php", data={"username": env["MOODLE_ADMIN_USER"], "password": env["MOODLE_ADMIN_PASSWORD"],
                                            "logintoken": token}).raise_for_status()
    r = s.get(f"{base}/report/log/index.php", params={"id": courseid, "chooselog": 1, "logreader": "logstore_standard",
                                                      "edulevel": 2, "download": fmt})
    r.raise_for_status()
    if "attachment" not in r.headers.get("content-disposition", ""):
        raise RuntimeError("Moodle no devolvió un archivo: ¿credenciales de administrador correctas?")
    dest = Path(dest).with_suffix(".xlsx" if fmt == "excel" else ".csv")
    dest.write_bytes(r.content)
    return dest
