"""Fuente C de la actividad: el registro exportado desde la interfaz de Moodle (PLAN.md, P3).

Sirve en cualquier Moodle sin instalar el plugin (como en Soler, 2024). El profesor o el
administrador descarga el registro del curso en *Informes → Registros*, con «Todas las
actividades», «Participación» y todos los días, en CSV o en Excel.

El archivo tiene nueve columnas fijas, con los nombres traducidos al idioma de quien exporta:
hora, nombre completo, usuario afectado, contexto, componente, nombre del evento, descripción,
origen y dirección IP. Por eso las columnas se leen por posición y los ids se sacan de la
descripción, que Moodle escribe siempre en inglés:
    "The user with id '9' viewed the 'page' activity with course module id '12'."
La hora viene en la zona horaria de quien exporta (`tz`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from alerta.moodle.cliente import Cliente

COLUMNS = ["time", "fullname", "affected", "context", "component", "event", "description", "origin", "ip"]
USER = re.compile(r"The user with id '(\d+)'")
CMID = re.compile(r"course module id '(\d+)'")
TIME_FORMATS = ["%d/%m/%y, %H:%M:%S", "%d/%m/%y, %H:%M", "%d/%m/%Y, %H:%M:%S", "%d/%m/%Y, %H:%M"]
DAY = 86400


def read(path: Path) -> pd.DataFrame:
    """Lee el archivo exportado (CSV o Excel) a las nueve columnas estándar."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls", ".ods"):
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    if df.shape[1] != len(COLUMNS):
        raise ValueError(f"{path.name}: se esperaban {len(COLUMNS)} columnas y hay {df.shape[1]}")
    df.columns = COLUMNS
    return df


def _parse_time(s: pd.Series, tz: str) -> pd.Series:
    for fmt in TIME_FORMATS:
        t = pd.to_datetime(s, format=fmt, errors="coerce")
        if t.notna().all():
            return t.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    raise ValueError(f"formato de hora no reconocido, por ejemplo {s.iloc[0]!r}")


def to_activity(log: pd.DataFrame, course_id, start_ts: int, students, tz: str) -> pd.DataFrame:
    """Eventos de los estudiantes por día del curso y módulo (mismas columnas que la fuente A)."""
    user = log["description"].str.extract(USER, expand=False)
    df = pd.DataFrame({
        "student_id": pd.to_numeric(user),
        "site_id": pd.to_numeric(log["description"].str.extract(CMID, expand=False)).fillna(0).astype(int),
        "ts": (_parse_time(log["time"], tz) - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(seconds=1),
    }).dropna(subset=["student_id"])
    df = df[df["student_id"].isin(set(students))]
    df["day"] = ((df["ts"] - start_ts) // DAY).astype(int)
    out = df.groupby(["student_id", "day", "site_id"], as_index=False).size().rename(columns={"size": "events"})
    out["student_id"] = out["student_id"].astype(int)
    return out.assign(course_id=course_id)


def source(path: Path, tz: str = "America/Havana"):
    """Fuente de actividad para `alerta.fuentes.moodle.extract_course(..., activity=source(ruta))`."""
    log = read(path)

    def activity(c: Cliente, courseid: int, start: int) -> pd.DataFrame:
        users = c.call("core_enrol_get_enrolled_users", courseid=courseid)
        return to_activity(log, courseid, start, [u["id"] for u in users], tz)

    return activity

