"""Moodle → esquema canónico (PLAN.md, P2–P4), por el web service.

Un curso de Moodle es un `course_id` del esquema canónico; los días se cuentan desde su `startdate`.

| Canónico     | De dónde sale                                                                    |
|--------------|----------------------------------------------------------------------------------|
| courses      | core_course_get_courses_by_field: startdate, enddate                             |
| students     | core_enrol_get_enrolled_users: usuarios con rol `student`                        |
| assessments  | libro de calificaciones (ítems de módulo) + fecha propia de cada tipo de módulo  |
| grades       | gradereport_user_get_grade_items (nota, fechas) + mod_assign_get_submissions     |
| activity     | fuente A: local_alertatemprana_get_activity; fuente C: registro exportado        |

Reglas de traducción:
- `item_id` es el `cmid` del módulo; `module_type` es el nombre del módulo (`assign`, `quiz`, …).
- Fecha de cada tipo: `assign` → `duedate`; `quiz` → `timeclose`. Los demás tipos quedan sin
  fecha y no entran en ningún corte (P4) hasta que se añada su regla en `DUE_DATE`.
- TMA = `assign` calificable (nota máxima > 0) con fecha de entrega.
- Entrega: en `assign`, la fecha de la entrega con estado `submitted`; si la tarea tiene nota pero
  no hay entrega en Moodle (entrega en papel), se toma como entregada en su fecha. En los demás
  tipos, `gradedatesubmitted` del libro de calificaciones, o la fecha de la nota si falta.
- Tarea sin entregas en línea (ningún tipo de entrega activado: un examen presencial registrado como
  tarea; P17): todos los estudiantes cuentan como presentados en su fecha y el que todavía no tiene
  nota queda «sin calificar» (nota vacía), no como no entregado (0).
- Escala de Moodle (P21): la nota es la posición del elemento (desde 1) y se traduce a su valor con
  `calificacion.valores_escala` (elementos numéricos, o cuatro palabras → 2, 3, 4 y 5), con los
  elementos de la escala que da `local_alertatemprana_get_gradeitems`.
- Requisito de la escala de las tareas (P21): con una conversión de la institución (`exige_25`), las
  tareas que no se califican de 2 a 5 no entran (`calificacion.excluir_tareas_fuera_de_escala`); el
  informe las lista en `tareas_fuera_de_escala`.
- Nota de 0 a 100: la decide un objeto `alerta.calificacion.Calificacion` (P8 y P16; por defecto,
  la conversión equipercentil), con la nota de aprobado del ítem (`local_alertatemprana_get_gradeitems`).
  La nota en la escala del curso se conserva en `grades.grade` y el rango del ítem en
  `assessments.grademin` y `assessments.gradepass`, para mostrarla al profesor.
- El servicio solo puede extraer los cursos en que un profesor lo ha matriculado (P10).
- No se conoce la baja (`unregistered_day`) ni si repite (`repeated`): Moodle deja de listar a
  quien se da de baja. Las instantáneas sucesivas lo resolverán (PLAN.md, P7.1).
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pandas as pd

from alerta.calificacion import Calificacion, ItemCalificable, cargar, excluir_tareas_fuera_de_escala, valores_escala
from alerta.canonico import Canonico
from alerta.moodle.cliente import Cliente

DAY = 86400
STUDENT_ROLES = frozenset({"student"})
SCALE_TYPE = 2  # grade_items.gradetype de una escala de Moodle (1 = puntuación)


def to_day(ts, start: int) -> float:
    """Día del curso de una marca de tiempo; vacío si no hay fecha (0 o None)."""
    return math.floor((ts - start) / DAY) if ts else np.nan


def _online(assignment: dict) -> bool:
    """La tarea admite entregas en la plataforma (algún tipo de entrega activado)."""
    return any(cf["subtype"] == "assignsubmission" and cf["name"] == "enabled" and cf["plugin"] != "comments"
               and str(cf["value"]) == "1" for cf in assignment.get("configs", []))


def _due_dates(c: Cliente, courseid: int) -> dict[int, tuple[str, int]]:
    """cmid → (tipo, fecha) para los tipos con regla de fecha."""
    out = {}
    for course in c.call("mod_assign_get_assignments", courseids=[courseid], includenotenrolledcourses=True)["courses"]:
        for a in course["assignments"]:
            out[a["cmid"]] = ("assign", a["duedate"])
    for q in c.call("mod_quiz_get_quizzes_by_courses", courseids=[courseid])["quizzes"]:
        out[q["coursemodule"]] = ("quiz", q["timeclose"])
    return out


def _offline_assigns(c: Cliente, courseid: int) -> set[int]:
    """cmid de las tareas sin entregas en línea."""
    assigns = c.call("mod_assign_get_assignments", courseids=[courseid], includenotenrolledcourses=True)["courses"]
    return {a["cmid"] for course in assigns for a in course["assignments"] if not _online(a)}


def _assign_submissions(c: Cliente, courseid: int) -> dict[tuple[int, int], int]:
    """(cmid, userid) → fecha de la entrega con estado `submitted`."""
    assigns = c.call("mod_assign_get_assignments", courseids=[courseid], includenotenrolledcourses=True)["courses"]
    by_id = {a["id"]: a["cmid"] for course in assigns for a in course["assignments"]}
    if not by_id:
        return {}
    out = {}
    for a in c.call("mod_assign_get_submissions", assignmentids=list(by_id))["assignments"]:
        for s in a["submissions"]:
            if s["status"] == "submitted":
                out[(by_id[a["assignmentid"]], s["userid"])] = s["timemodified"]
    return out


def activity_ws(c: Cliente, courseid: int, start: int) -> pd.DataFrame:
    """Fuente A: eventos de participación agregados por el plugin (ya vienen en días del curso)."""
    r = c.call("local_alertatemprana_get_activity", courseid=courseid)
    if r["startdate"] != start:
        raise ValueError(f"curso {courseid}: startdate del plugin ({r['startdate']}) ≠ del curso ({start})")
    df = pd.DataFrame(r["events"], columns=["userid", "day", "cmid", "events"])
    return df.rename(columns={"userid": "student_id", "cmid": "site_id"}).assign(course_id=courseid)


def extract_course(c: Cliente, courseid: int,
                   activity: Callable[[Cliente, int, int], pd.DataFrame] = activity_ws,
                   calificacion: Calificacion | None = None,
                   student_roles=STUDENT_ROLES) -> tuple[Canonico, dict]:
    """Extrae un curso. Devuelve el esquema canónico y un informe (avisos, totales)."""
    found = c.call("core_course_get_courses_by_field", field="id", value=courseid)["courses"]
    if not found:
        raise ValueError(f"no existe el curso {courseid} (o el usuario de servicio no puede verlo)")
    course = found[0]
    if "startdate" not in course:  # Moodle solo devuelve los datos públicos de un curso al que no se tiene acceso
        raise PermissionError(f"curso {courseid}: el servicio no está matriculado en él como profesor (P10)")
    start, end = course["startdate"], course["enddate"]
    if not end or end <= start:
        raise ValueError(f"curso {courseid}: necesita fecha de fin posterior a la de inicio")
    warnings = []
    calificacion = calificacion or cargar()

    users = c.call("core_enrol_get_enrolled_users", courseid=courseid)
    students = [u["id"] for u in users if student_roles & {r["shortname"] for r in u.get("roles", [])}]

    due = _due_dates(c, courseid)
    offline = _offline_assigns(c, courseid)
    submissions = _assign_submissions(c, courseid)
    gradeinfo = {g["cmid"]: g for g in c.call("local_alertatemprana_get_gradeitems", courseid=courseid)}
    gradepass = {k: g["gradepass"] for k, g in gradeinfo.items()}
    scale = {k: valores_escala(g["scale"]) if g.get("gradetype") == SCALE_TYPE else None for k, g in gradeinfo.items()}
    items, grades = {}, []
    # userid=0: el libro de calificaciones de todos los usuarios en una sola llamada (unas 18 veces más
    # rápido que una por estudiante en un curso de 338)
    student_set = set(students)
    reports = c.call("gradereport_user_get_grade_items", courseid=courseid, userid=0)["usergrades"]
    for report in reports:
        userid = report["userid"]
        if userid not in student_set:
            continue
        for g in report["gradeitems"]:
            if g["itemtype"] != "mod" or not g.get("cmid"):
                continue
            cmid, module = g["cmid"], g["itemmodule"]
            if cmid not in items:
                due_ts = due.get(cmid, (module, 0))[1]
                values = scale.get(cmid)
                gmin, gmax, gpass = ((min(values), max(values), 0.0) if values else
                                     (float(g["grademin"]), float(g["grademax"]), float(gradepass.get(cmid, 0))))
                items[cmid] = {"course_id": courseid, "item_id": cmid, "module_type": module,
                               "due_day": to_day(due_ts, start), "grademax": gmax,
                               "grademin": gmin, "gradepass": gpass}
            submitted = submissions.get((cmid, userid))
            raw = g.get("graderaw")
            if raw is not None and gradeinfo.get(cmid, {}).get("gradetype") == SCALE_TYPE:
                values, i = scale.get(cmid), int(round(float(raw))) - 1
                raw = values[i] if values and 0 <= i < len(values) else None
            in_person = module == "assign" and cmid in offline and due.get(cmid, (module, 0))[1]
            if submitted is None and (raw is not None or in_person):
                submitted = g.get("gradedatesubmitted") or (due[cmid][1] if module == "assign" and cmid in due
                                                            else g.get("gradedategraded"))
            if submitted is None and raw is None:
                continue
            item = ItemCalificable(module, items[cmid]["grademin"], items[cmid]["grademax"], items[cmid]["gradepass"])
            score = calificacion.a_100(float(raw), item) if raw is not None else np.nan
            grades.append({"course_id": courseid, "item_id": cmid, "student_id": userid,
                           "submitted_day": to_day(submitted, start), "score": score,
                           "graded_day": to_day(g.get("gradedategraded"), start) if raw is not None else np.nan,
                           "grade": float(raw) if raw is not None else np.nan})

    assessments = pd.DataFrame(list(items.values()), columns=["course_id", "item_id", "module_type", "due_day",
                                                              "grademax", "grademin", "gradepass"])
    grades = pd.DataFrame(grades, columns=["course_id", "item_id", "student_id", "submitted_day", "score",
                                           "graded_day", "grade"])
    out_of_scale = []
    if getattr(calificacion, "exige_25", False):
        assessments, grades, out_of_scale = excluir_tareas_fuera_de_escala(assessments, grades)
        if out_of_scale:
            warnings.append(f"tareas que no se califican de 2 a 5 (no entran): {out_of_scale}")
    assessments["is_tma"] = ((assessments["module_type"] == "assign") & (assessments["grademax"] > 0)
                             & assessments["due_day"].notna())
    undated = assessments.loc[assessments["due_day"].isna(), "module_type"].value_counts().to_dict()
    if undated:
        warnings.append(f"evaluaciones sin fecha (no entran en los cortes): {undated}")

    act = activity(c, courseid, start)
    act = act[act["student_id"].isin(students)]
    d = Canonico(
        courses=pd.DataFrame({"course_id": [courseid], "length_days": [math.ceil((end - start) / DAY)],
                              "start_ts": [start]}),
        students=pd.DataFrame({"course_id": courseid, "student_id": students, "unregistered_day": np.nan,
                               "repeated": np.nan}),
        assessments=assessments,
        grades=grades,
        activity=act[["course_id", "student_id", "day", "site_id", "events"]].reset_index(drop=True),
    ).validate()
    report = {"courseid": courseid, "fullname": course["fullname"], "students": len(students),
              "items": len(assessments), "tmas": int(assessments["is_tma"].sum()), "grades": len(grades),
              "events": int(act["events"].sum()), "calificacion": calificacion.nombre,
              "tareas_sin_entrega_en_linea": sorted(offline & set(assessments["item_id"])),
              "tareas_fuera_de_escala": out_of_scale, "warnings": warnings}
    return d, report
