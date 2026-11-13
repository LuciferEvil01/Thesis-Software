"""OULAD → esquema canónico.

Sirve para comprobar que `alerta.variables` reproduce el conjunto de datos del entrenamiento y,
más adelante, para reproducir una presentación de OULAD dentro de Moodle (PLAN.md, F4).

- Curso = asignatura y presentación: `course_id = "<code_module>_<code_presentation>"`.
- Tipos de evaluación: TMA → `assign` (son las TMA); CMA → `quiz`; examen → `exam`.
- OULAD no tiene fecha de publicación de las notas: `graded_day` queda vacío.
"""

from pathlib import Path

import pandas as pd

from alerta.canonico import Canonico

MODULE_TYPE = {"TMA": "assign", "CMA": "quiz", "Exam": "exam"}
AT_RISK = {"Fail": 1, "Withdrawn": 1, "Pass": 0, "Distinction": 0}


def _read(raw: Path, name: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(raw / f"{name}.csv", na_values="?", **kwargs)


def _course_id(df: pd.DataFrame) -> pd.Series:
    return df["code_module"] + "_" + df["code_presentation"]


def load(raw: Path) -> tuple[Canonico, pd.DataFrame]:
    """Devuelve el esquema canónico y las etiquetas (course_id, student_id, final_result, at_risk)."""
    keys = ["id_student", "code_module", "code_presentation"]
    courses = _read(raw, "courses")
    info = _read(raw, "studentInfo", usecols=keys + ["final_result", "num_of_prev_attempts"])
    registration = _read(raw, "studentRegistration", usecols=keys + ["date_unregistration"])
    assessments = _read(raw, "assessments")
    student_assessment = _read(raw, "studentAssessment")
    student_vle = _read(raw, "studentVle", dtype={"id_student": "int32", "id_site": "int32",
                                                  "date": "int16", "sum_click": "int32"})

    students = info.merge(registration, on=keys, how="left")
    students["course_id"] = _course_id(students)
    students = students.rename(columns={"id_student": "student_id", "date_unregistration": "unregistered_day"})
    students["repeated"] = (students["num_of_prev_attempts"] > 0).astype("int8")
    labels = students[["course_id", "student_id", "final_result"]].copy()
    labels["at_risk"] = labels["final_result"].map(AT_RISK).astype("int8")

    assessments["course_id"] = _course_id(assessments)
    items = pd.DataFrame({
        "course_id": assessments["course_id"],
        "item_id": assessments["id_assessment"],
        "module_type": assessments["assessment_type"].map(MODULE_TYPE),
        "due_day": assessments["date"],
        "grademax": 100.0,
        "is_tma": assessments["assessment_type"] == "TMA",
    })

    grades = student_assessment.merge(items[["course_id", "item_id"]], left_on="id_assessment",
                                      right_on="item_id")
    grades = grades.rename(columns={"id_student": "student_id", "date_submitted": "submitted_day"})
    grades["graded_day"] = float("nan")

    student_vle["course_id"] = _course_id(student_vle)
    activity = student_vle.rename(columns={"id_student": "student_id", "date": "day", "id_site": "site_id",
                                        "sum_click": "events"})

    d = Canonico(
        courses=pd.DataFrame({"course_id": _course_id(courses),
                              "length_days": courses["module_presentation_length"],
                              "start_ts": float("nan")}),
        students=students[["course_id", "student_id", "unregistered_day", "repeated"]],
        assessments=items,
        grades=grades[["course_id", "item_id", "student_id", "submitted_day", "score", "graded_day"]],
        activity=activity[["course_id", "student_id", "day", "site_id", "events"]],
    )
    return d.validate(), labels


def period_start(code_presentation: str) -> str:
    """Fecha aproximada de inicio de una presentación: «B» empieza en febrero; «J», en octubre."""
    return f"{code_presentation[:4]}-{'02' if code_presentation[4] == 'B' else '10'}-01"


def archive(archivo, d: Canonico, labels: pd.DataFrame, periods: list[str] | None = None) -> list[str]:
    """Archiva los cursos de OULAD (de los periodos dados) como cursos cerrados con su resultado."""
    done = []
    for cid in d.courses["course_id"]:
        presentation = cid.split("_", 1)[1]
        if periods is not None and presentation not in periods:
            continue
        archivo.add(d, labels, {"course_id": cid, "period": presentation, "period_start": period_start(presentation),
                                "source": "oulad", "closed_at": None,
                                "label_rule": "at_risk = final_result en {Fail, Withdrawn}"})
        done.append(cid)
    return done
