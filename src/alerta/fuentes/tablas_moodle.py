"""Fuente D: las tablas de la base de datos de Moodle → esquema canónico (validación con EVEA, E26).

Lee la entrega de `Solicitud_datos_EVEA.pdf`: un CSV por tabla con el nombre estándar de Moodle sin
prefijo (`course.csv`, `logstore_standard_log.csv`, …), en UTF-8, con encabezado, nulos vacíos y
marcas de tiempo Unix. Aplica las mismas reglas de traducción que `fuentes.moodle` (por el web
service), pero sobre cursos cerrados y con su historia completa:

| Canónico     | De dónde sale                                                                       |
|--------------|-------------------------------------------------------------------------------------|
| courses      | course: startdate, enddate                                                          |
| students     | role_assignments con el rol `student` en el contexto del curso, más los matriculados |
|              | que se dieron de baja (Moodle borra su rol al desmatricular; se recuperan del registro) |
| assessments  | grade_items de módulo + fecha propia de cada tipo (`assign.duedate`, `quiz.timeclose`) |
| grades       | grade_grades (nota final del ítem); entrega de `assign_submission`; fecha de         |
|              | publicación = la más antigua entre `grade_grades_history` y `grade_grades`         |
| activity     | logstore_standard_log con edulevel = 2 (participación), por usuario, día y módulo    |

Bajas: el último `\\core\\event\\user_enrolment_deleted` de cada estudiante, salvo que después vuelva
a matricularse. Resultado final: el ítem de curso del libro de calificaciones o, si la institución lo
registra fuera de EVEA, `resultado_final.csv` (sección 3.6 de la solicitud: course_id, student_id,
nota_final, condicion, fecha_baja). En riesgo académico = nota final de suspenso (2) o baja.

Las notas se dejan en la escala del ítem (`grades.grade`, con `grademin`, `grademax` y `gradepass` en
`assessments`); `score` (0–100) lo calcula después `convertir` con la conversión que se elija, porque
la equipercentil necesita como referencia los cursos de periodos anteriores (E26, punto 2).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from alerta.calificacion import Calificacion, ItemCalificable, excluir_tareas_fuera_de_escala, valores_escala
from alerta.canonico import Canonico

DAY = 86400
CONTEXT_COURSE, CONTEXT_MODULE = 50, 70
PARTICIPATION = 2
ENROL_CREATED = "\\core\\event\\user_enrolment_created"
ENROL_DELETED = "\\core\\event\\user_enrolment_deleted"
ROLE_ASSIGNED = "\\core\\event\\role_assigned"
DUE_FIELD = {"assign": "duedate", "quiz": "timeclose"}  # tipos con regla de fecha (como `fuentes.moodle`)


def leer(folder: Path, name: str, required: bool = True) -> pd.DataFrame | None:
    path = Path(folder) / f"{name}.csv"
    if not path.exists():
        if required:
            raise FileNotFoundError(f"falta la tabla {path.name} en {folder}")
        return None
    return pd.read_csv(path, low_memory=False)


def to_day(ts, start) -> float:
    return math.floor((ts - start) / DAY) if pd.notna(ts) and ts else np.nan


def _scale_values(scale: pd.DataFrame | None) -> dict[int, list[float]]:
    """scaleid → valores numéricos de sus elementos, en orden (`calificacion.valores_escala`)."""
    out = {}
    for s in ([] if scale is None else scale.itertuples()):
        values = valores_escala(s.scale)
        if values:
            out[int(s.id)] = values
    return out


def _item_value(gi, finalgrade, scales) -> float:
    """Nota de un ítem en su escala: el valor del elemento si el ítem usa una escala de Moodle."""
    if pd.isna(finalgrade):
        return np.nan
    if int(gi.gradetype) == 2:  # escala
        values = scales.get(int(gi.scaleid)) if pd.notna(gi.scaleid) else None
        if not values:
            return np.nan
        i = int(round(float(finalgrade))) - 1
        return values[i] if 0 <= i < len(values) else np.nan
    return float(finalgrade)


def _range(gi, scales) -> tuple[float, float, float]:
    """grademin, grademax y gradepass del ítem en la escala de sus notas."""
    if int(gi.gradetype) == 2 and pd.notna(gi.scaleid) and int(gi.scaleid) in scales:
        values = scales[int(gi.scaleid)]
        return min(values), max(values), 0.0
    return float(gi.grademin), float(gi.grademax), float(gi.gradepass or 0)


def cargar(folder: Path, courses: list[int] | None = None, student_role: str = "student",
           fecha_de_nota: bool = True):
    """Devuelve (Canonico sin `score`, etiquetas, cursos con su periodo, informe).

    `fecha_de_nota=False` da toda nota por publicada, como OULAD (solo para la prueba con el
    laboratorio, cuyo historial de notas tiene la fecha en que se sembró el curso).
    """
    t = {n: leer(folder, n) for n in ["course", "context", "role", "role_assignments", "modules",
                                      "course_modules", "grade_items", "grade_grades", "logstore_standard_log"]}
    for n in ["assign", "assign_submission", "quiz", "grade_grades_history", "scale", "resultado_final"]:
        t[n] = leer(folder, n, required=False)
    report: dict = {"avisos": []}

    course = t["course"][t["course"]["id"] != 1]  # el curso 1 es la portada del sitio
    course = course[(course["enddate"] > course["startdate"]) & (course["startdate"] > 0)]
    if courses is not None:
        course = course[course["id"].isin(courses)]
    start = course.set_index("id")["startdate"].to_dict()
    end = course.set_index("id")["enddate"].to_dict()
    ids = set(start)

    # Estudiantes: rol de estudiante en el contexto del curso, más quienes se matricularon y se dieron
    # de baja (sin rol al final) y no tienen otro rol en el curso
    ctx = t["context"][t["context"]["contextlevel"] == CONTEXT_COURSE].set_index("id")["instanceid"]
    ra = t["role_assignments"].assign(course_id=lambda r: r["contextid"].map(ctx)).dropna(subset=["course_id"])
    ra["course_id"] = ra["course_id"].astype(int)
    roles = t["role"].set_index("id")["shortname"]
    ra["rol"] = ra["roleid"].map(roles)
    student_ids = set(roles[roles == student_role].index)
    log = t["logstore_standard_log"]
    log = log[log["courseid"].isin(ids)]
    enrol = log[log["eventname"].isin([ENROL_CREATED, ENROL_DELETED])]
    assigned = log[(log["eventname"] == ROLE_ASSIGNED) & log["objectid"].isin(student_ids)]
    others = set(map(tuple, ra.loc[ra["rol"] != student_role, ["course_id", "userid"]].to_numpy()))
    pairs = (set(map(tuple, ra.loc[ra["rol"] == student_role, ["course_id", "userid"]].to_numpy()))
             | set(map(tuple, assigned[["courseid", "relateduserid"]].dropna().astype(int).to_numpy()))
             | {p for p in map(tuple, enrol[["courseid", "relateduserid"]].dropna().astype(int).to_numpy())
                if p not in others})
    students = pd.DataFrame(sorted(pairs), columns=["course_id", "student_id"])
    students = students[students["course_id"].isin(ids)]

    # Bajas: la última desmatriculación sin una matrícula posterior
    last = (enrol.sort_values("timecreated").groupby(["courseid", "relateduserid"])
            .agg(evento=("eventname", "last"), ts=("timecreated", "last")).reset_index())
    gone = last[last["evento"] == ENROL_DELETED].rename(columns={"courseid": "course_id", "relateduserid": "student_id"})
    students = students.merge(gone[["course_id", "student_id", "ts"]], on=["course_id", "student_id"], how="left")
    students["unregistered_day"] = [to_day(ts, start[c]) for c, ts in zip(students["course_id"], students["ts"])]
    students = students.drop(columns="ts").assign(repeated=np.nan)
    ext = t["resultado_final"]
    if ext is not None and "fecha_baja" in ext and ext["fecha_baja"].notna().any():
        # La fecha de baja oficial (sección 3.6) prevalece sobre la del registro de matrícula
        fb = ext.dropna(subset=["fecha_baja"])[["course_id", "student_id", "fecha_baja"]]
        students = students.merge(fb, on=["course_id", "student_id"], how="left")
        ts = students["fecha_baja"].map(_unix)
        official = [to_day(x, start[c]) for c, x in zip(students["course_id"], ts)]
        students["unregistered_day"] = np.where(ts.notna(), official, students["unregistered_day"])
        students = students.drop(columns="fecha_baja")
        report["avisos"].append(f"fecha de baja de resultado_final.csv en {int(ts.notna().sum())} estudiantes")

    # Evaluaciones: ítems de módulo del libro de calificaciones con la fecha propia de su tipo
    mods = t["modules"].set_index("id")["name"]
    cm = t["course_modules"].assign(module_type=lambda x: x["module"].map(mods))
    cm = cm[cm["course"].isin(ids)]
    due = {}
    for mtype, field in DUE_FIELD.items():
        if t[mtype] is not None:
            due.update({(mtype, int(i)): v for i, v in zip(t[mtype]["id"], t[mtype][field])})
    scales = _scale_values(t["scale"])
    gi = t["grade_items"]
    gi = gi[gi["courseid"].isin(ids)]
    mod_items = gi[(gi["itemtype"] == "mod") & gi["gradetype"].isin([1, 2])]
    cmid = {(r.module_type, int(r.instance)): int(r.id) for r in cm.itertuples()}
    items = []
    for g in mod_items.itertuples():
        key = (g.itemmodule, int(g.iteminstance))
        if key not in cmid:
            continue
        gmin, gmax, gpass = _range(g, scales)
        ts = due.get(key, 0)
        items.append({"course_id": int(g.courseid), "item_id": cmid[key], "gradeitem": int(g.id),
                      "module_type": g.itemmodule, "instance": int(g.iteminstance),
                      "due_day": to_day(ts, start[int(g.courseid)]) if ts else np.nan,
                      "grademin": gmin, "grademax": gmax, "gradepass": gpass})
    assessments = pd.DataFrame(items)
    assessments["is_tma"] = ((assessments["module_type"] == "assign") & (assessments["grademax"] > 0)
                             & assessments["due_day"].notna())

    # Notas: la final del ítem; publicada en la fecha más antigua entre el historial y grade_grades.
    # Moodle borra de grade_grades las notas de quien se desmatricula y solo las guarda en el historial:
    # las que faltan se recuperan de él (la última nota no vacía de cada estudiante e ítem).
    gg = t["grade_grades"].merge(assessments[["course_id", "item_id", "gradeitem"]], left_on="itemid", right_on="gradeitem")
    gg = gg[gg["finalgrade"].notna()]
    hist = t["grade_grades_history"]
    if hist is not None:
        h = hist[hist["finalgrade"].notna() & hist["itemid"].isin(assessments["gradeitem"])]
        first = h.groupby(["itemid", "userid"])["timemodified"].min().rename("hist_ts").reset_index()
        lost = (h.sort_values(["timemodified", "id"]).groupby(["itemid", "userid"]).last().reset_index()
                .merge(gg[["itemid", "userid"]], on=["itemid", "userid"], how="left", indicator=True))
        lost = lost[lost["_merge"] == "left_only"].drop(columns="_merge")
        lost = lost.merge(assessments[["course_id", "item_id", "gradeitem"]], left_on="itemid", right_on="gradeitem")
        report["notas_recuperadas_del_historial"] = len(lost)
        gg = pd.concat([gg, lost[gg.columns.intersection(lost.columns)]], ignore_index=True)
        gg = gg.merge(first, on=["itemid", "userid"], how="left")
        gg["graded_ts"] = gg[["timemodified", "hist_ts"]].min(axis=1)
    else:
        report["avisos"].append("sin grade_grades_history: la fecha de publicación es la última modificación")
        gg["graded_ts"] = gg["timemodified"]
    if not fecha_de_nota:
        gg["graded_ts"] = np.nan
    gi_by_id = gi.set_index("id")
    gg["grade"] = [_item_value(gi_by_id.loc[i], v, scales) for i, v in zip(gg["itemid"], gg["finalgrade"])]

    # Entregas de las tareas; una tarea sin ninguna entrega en línea es presencial (P17): se da por
    # presentado en su fecha a quien tiene nota, como en `fuentes.moodle`
    sub = {}
    if t["assign_submission"] is not None:
        s = t["assign_submission"]
        s = s[(s["status"] == "submitted") & (s.get("latest", 1) == 1)]
        sub = {(int(a), int(u)): ts for a, u, ts in zip(s["assignment"], s["userid"], s["timemodified"])}
    online = {a for a, _ in sub}
    rows = []
    a_by = assessments.set_index("gradeitem")
    for g in gg.itertuples():
        a = a_by.loc[g.itemid]
        st = start[int(a.course_id)]
        submitted = sub.get((int(a.instance), int(g.userid))) if a.module_type == "assign" else None
        if submitted is None:  # nota sin entrega en la plataforma: en la fecha de la evaluación, o de la nota
            submitted = due.get((a.module_type, int(a.instance))) or g.graded_ts
        rows.append({"course_id": int(a.course_id), "item_id": int(a.item_id), "student_id": int(g.userid),
                     "submitted_day": to_day(submitted, st), "score": np.nan,
                     "graded_day": to_day(g.graded_ts, st), "grade": g.grade})
    # Entregas sin nota (cuentan como entregadas y sin calificar)
    graded = {(r["item_id"], r["student_id"]) for r in rows}
    inst2 = {(int(r.instance)): r for r in assessments[assessments["module_type"] == "assign"].itertuples()}
    for (aid, uid), ts in sub.items():
        a = inst2.get(aid)
        if a is not None and (a.item_id, uid) not in graded:
            rows.append({"course_id": int(a.course_id), "item_id": int(a.item_id), "student_id": uid,
                         "submitted_day": to_day(ts, start[int(a.course_id)]), "score": np.nan,
                         "graded_day": np.nan, "grade": np.nan})
    grades = pd.DataFrame(rows, columns=["course_id", "item_id", "student_id", "submitted_day", "score", "graded_day", "grade"])
    grades = grades.merge(students[["course_id", "student_id"]], on=["course_id", "student_id"])
    offline = sorted(int(r.item_id) for r in assessments.itertuples() if r.module_type == "assign" and r.instance not in online)
    report["tareas_sin_entrega_en_linea"] = len(offline)

    # Actividad: eventos de participación de los estudiantes por día y módulo
    act = log[(log["edulevel"] == PARTICIPATION)].merge(
        students[["course_id", "student_id"]], left_on=["courseid", "userid"], right_on=["course_id", "student_id"])
    act["day"] = [to_day(ts, start[c]) for c, ts in zip(act["course_id"], act["timecreated"])]
    act["site_id"] = np.where(act["contextlevel"] == CONTEXT_MODULE, act["contextinstanceid"], 0)
    activity = (act.groupby(["course_id", "student_id", "day", "site_id"]).size().rename("events").reset_index())

    # Resultado final: ítem de curso o tabla externa (sección 3.6)
    labels = _labels(t, gi, scales, students, start)
    courses = pd.DataFrame({"course_id": list(start), "length_days": [math.ceil((end[c] - start[c]) / DAY) for c in start],
                            "start_ts": list(start.values())})
    courses["periodo"] = [periodo(s) for s in courses["start_ts"]]
    d = Canonico(courses=courses[["course_id", "length_days", "start_ts"]], students=students,
                 assessments=assessments.drop(columns=["gradeitem", "instance"]), grades=grades,
                 activity=activity).validate()
    report.update({"cursos": len(courses), "estudiantes": len(students), "evaluaciones": len(assessments),
                   "notas": len(grades), "eventos": int(activity["events"].sum()),
                   "con_resultado": int(labels["at_risk"].notna().sum())})
    return d, labels, courses, report


def _labels(t, gi, scales, students, start) -> pd.DataFrame:
    """at_risk por estudiante: baja, o nota final por debajo del aprobado; vacío si no se conoce."""
    out = students[["course_id", "student_id", "unregistered_day"]].copy()
    ext = t.get("resultado_final")
    if ext is not None:
        ext = ext.rename(columns={"nota_final": "final"})
        out = out.merge(ext[["course_id", "student_id", "final", "condicion"]], on=["course_id", "student_id"], how="left")
        baja = out["condicion"].astype(str).str.lower().str.startswith("baja") | out["unregistered_day"].notna()
        out["at_risk"] = np.where(baja, 1, np.where(out["final"].notna(), (out["final"] < 3).astype(float), np.nan))
        return out[["course_id", "student_id", "at_risk"]]
    ci = gi[gi["itemtype"] == "course"]
    gg = t["grade_grades"].merge(ci[["id", "courseid"]], left_on="itemid", right_on="id")
    by = ci.set_index("id")
    gg["final"] = [_item_value(by.loc[i], v, scales) for i, v in zip(gg["itemid"], gg["finalgrade"])]
    gg["pass"] = [ItemCalificable("course", *_range(by.loc[i], scales)).aprobado for i in gg["itemid"]]
    out = out.merge(gg.rename(columns={"courseid": "course_id", "userid": "student_id"})[
        ["course_id", "student_id", "final", "pass"]], on=["course_id", "student_id"], how="left")
    out["at_risk"] = np.where(out["unregistered_day"].notna(), 1,
                              np.where(out["final"].notna(), (out["final"] < out["pass"]).astype(float), np.nan))
    return out[["course_id", "student_id", "at_risk"]]


def _unix(v) -> float:
    """Fecha de baja como tiempo Unix: admite el número o una fecha ISO (AAAA-MM-DD)."""
    if pd.isna(v):
        return np.nan
    try:
        return float(v)
    except (TypeError, ValueError):
        return pd.Timestamp(str(v)).timestamp()


def periodo(start_ts: int) -> str:
    """Semestre de la UH por la fecha de inicio: el primero de septiembre a enero, el segundo de
    febrero a julio. Si la institución entrega su calendario, se sustituye por él."""
    t = pd.Timestamp(int(start_ts), unit="s")
    return f"{t.year}-{t.year + 1} S1" if t.month >= 8 else f"{t.year - 1}-{t.year} S2"


def convertir(d: Canonico, calificacion: Calificacion) -> Canonico:
    """Rellena `grades.score` (0–100) con la conversión dada, ítem a ítem. Con una conversión de la
    institución (`exige_25`), las tareas que no se califican de 2 a 5 quedan fuera (P21)."""
    assessments, grades = d.assessments, d.grades
    if getattr(calificacion, "exige_25", False):
        assessments, grades, _ = excluir_tareas_fuera_de_escala(assessments, grades)
    a = assessments.set_index(["course_id", "item_id"])
    g = grades.copy()
    g["score"] = [calificacion.a_100(v, ItemCalificable(a.loc[(c, i), "module_type"], a.loc[(c, i), "grademin"],
                                                        a.loc[(c, i), "grademax"], a.loc[(c, i), "gradepass"]))
                  if pd.notna(v) else np.nan for c, i, v in zip(g["course_id"], g["item_id"], g["grade"])]
    return Canonico(courses=d.courses, students=d.students, assessments=assessments, grades=g,
                    activity=d.activity).validate()
