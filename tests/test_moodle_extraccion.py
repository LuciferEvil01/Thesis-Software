"""F3: viaje de ida y vuelta canónico → Moodle → canónico con el Moodle local (`make up`).

Se crea en Moodle el curso inventado de `curso_sintetico`, se extrae por el web service y se
comprueba que las tablas y las variables del modelo coinciden con las originales. El estudiante
de baja no se puede extraer (Moodle deja de listarlo), así que se compara sin él.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from curso_sintetico import CID, curso  # noqa: E402

from alerta import config, variables  # noqa: E402
from alerta.calificacion import ProporcionalOULAD  # noqa: E402
from alerta.canonico import Canonico  # noqa: E402
from alerta.fuentes import moodle, registro_exportado  # noqa: E402
from alerta.moodle import sembrar  # noqa: E402
from alerta.moodle import cursos  # noqa: E402
from alerta.moodle.cliente import Cliente  # noqa: E402

pytestmark = pytest.mark.moodle
START = 1767225600  # 2026-01-01


@pytest.fixture(scope="module")
def roundtrip():
    try:
        client = Cliente.desde_config()
        client.site_info()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Moodle local no disponible ({e}); ejecuta `make up`")
    original = curso()
    seeded = sembrar.seed(sembrar.spec_from_canonico(original, CID, START, "ALERTA-PRUEBA-F3", "Curso de prueba F3"))
    # Notas del curso inventado en 0–100: sin conversión, para comparar con el original
    extracted, report = moodle.extract_course(client, seeded["courseid"], calificacion=ProporcionalOULAD())

    # Traducir los ids de Moodle a los del curso original
    users = {v: int(k[1:]) for k, v in seeded["users"].items()}
    sites = {v: int(k[1:]) for k, v in seeded["sites"].items()} | {0: 0}
    t = {name: getattr(extracted, name).copy() for name in ("courses", "students", "assessments", "grades", "activity")}
    for df in t.values():
        df["course_id"] = CID
        for col, mapping in (("student_id", users), ("item_id", sites), ("site_id", sites)):
            if col in df:
                df[col] = df[col].map(mapping)
    present = original.students.loc[original.students["unregistered_day"].isna(), "student_id"]
    keep = lambda df: df[df["student_id"].isin(present)] if "student_id" in df else df  # noqa: E731
    expected = Canonico(**{name: keep(getattr(original, name)) for name in t})
    return expected, Canonico(**t), report, client, seeded["courseid"], extracted


def sort(df, keys):
    return df.sort_values(keys).reset_index(drop=True)


def test_report(roundtrip):
    _, _, report, *_ = roundtrip
    assert report["students"] == 5 and report["tmas"] == 3 and report["warnings"] == []


def test_course(roundtrip):
    expected, got, *_ = roundtrip
    assert got.courses["length_days"].iloc[0] == expected.courses["length_days"].iloc[0]


def test_assessments(roundtrip):
    expected, got, *_ = roundtrip
    cols = ["item_id", "module_type", "due_day", "grademax", "is_tma"]
    pd.testing.assert_frame_equal(sort(got.assessments[cols], "item_id"), sort(expected.assessments[cols], "item_id"),
                                  check_dtype=False)


def test_grades(roundtrip):
    expected, got, *_ = roundtrip
    cols = ["item_id", "student_id", "submitted_day", "score", "graded_day"]
    pd.testing.assert_frame_equal(sort(got.grades[cols], ["student_id", "item_id"]),
                                  sort(expected.grades[cols], ["student_id", "item_id"]), check_dtype=False)


def test_activity(roundtrip):
    expected, got, *_ = roundtrip
    keys = ["student_id", "day", "site_id"]
    agg = lambda d: sort(d.activity.groupby(keys, as_index=False)["events"].sum(), keys)  # noqa: E731
    pd.testing.assert_frame_equal(agg(got), agg(expected), check_dtype=False)


@pytest.mark.parametrize("types", [variables.DEFAULT_TYPES, {"assign", "quiz"}])
def test_same_features(roundtrip, types):
    expected, got, *_ = roundtrip
    a = sort(variables.build(expected, types).drop(columns=["repeated_course"]), variables.ROW)
    b = sort(variables.build(got, types).drop(columns=["repeated_course"]), variables.ROW)
    for col in variables.FEATURES + ["cutoff_day", "anchor_k"]:
        if col == "repeated_course":
            continue
        np.testing.assert_allclose(b[col].astype(float), a[col].astype(float), atol=1e-12, equal_nan=True, err_msg=col)


@pytest.mark.parametrize("fmt", ["csv", "excel"])
def test_exported_log_equals_plugin(roundtrip, fmt, tmp_path):
    """Fuente C (registro exportado) = fuente A (plugin)."""
    *_, client, courseid, from_plugin = roundtrip
    path = sembrar.download_log(courseid, tmp_path / "registro", fmt)
    from_export, _ = moodle.extract_course(client, courseid, activity=registro_exportado.source(path),
                                           calificacion=ProporcionalOULAD())
    keys = ["student_id", "day", "site_id", "events"]
    pd.testing.assert_frame_equal(sort(from_export.activity[keys], keys), sort(from_plugin.activity[keys], keys),
                                  check_dtype=False)


class Mitad:
    """Calificación de prueba: la mitad de la proporcional."""
    nombre = "mitad"

    def a_100(self, nota, item):
        return nota / item.grademax * 50


def test_grading_is_pluggable(roundtrip):
    *_, client, courseid, from_default = roundtrip
    half, report = moodle.extract_course(client, courseid, calificacion=Mitad())
    assert report["calificacion"] == "mitad"
    keys = ["student_id", "item_id"]
    a, b = sort(from_default.grades, keys), sort(half.grades, keys)
    np.testing.assert_allclose(b["score"], a["score"] / 2, equal_nan=True)


def test_service_sees_only_courses_where_a_teacher_enrolled_it(roundtrip):
    *_, client, courseid, _ = roundtrip
    hidden = sembrar.seed(sembrar.spec_from_canonico(curso(), CID, START, "ALERTA-PRUEBA-SIN-ACCESO",
                                                     "Curso sin el servicio", service_role=None))
    found = {c["id"]: c for c in cursos.discover(client)}
    assert courseid in found and hidden["courseid"] not in found
    assert found[courseid]["rol_servicio"] == "teacher"
    assert [t["fullname"] for t in found[courseid]["profesores"]] == ["Profesor ALERTA-PRUEBA-F3"]
    with pytest.raises(PermissionError):
        moodle.extract_course(client, hidden["courseid"])


def test_in_person_assignment_and_pass_mark(roundtrip):
    """P16 y P17: en una tarea sin entregas en línea (examen presencial), el estudiante sin nota queda
    «sin calificar» y la tarea no está completa; la nota de aprobado del ítem llega a la extracción."""
    *_, client, _, _ = roundtrip
    d = curso()
    d.assessments["online"] = d.assessments["item_id"] != 11
    d.assessments["gradepass"] = np.where(d.assessments["item_id"] == 11, 6.0, 0.0)
    seeded = sembrar.seed(sembrar.spec_from_canonico(d, CID, START, "ALERTA-PRUEBA-PRESENCIAL", "Curso presencial"))
    got, report = moodle.extract_course(client, seeded["courseid"], calificacion=ProporcionalOULAD())
    cm11 = seeded["sites"]["i11"]
    assert report["tareas_sin_entrega_en_linea"] == [cm11]
    assert got.assessments.set_index("item_id").loc[cm11, "gradepass"] == 6
    g = got.grades[got.grades["item_id"] == cm11]
    # Los 4 calificados conservan su fecha; el 4, sin nota, queda presentado en la fecha y sin calificar
    ungraded = g[g["score"].isna()]
    assert len(g) == 5 and len(ungraded) == 1 and ungraded["submitted_day"].iloc[0] == 50
    e = variables.evaluations(got, 75).set_index("item_id").loc[cm11]
    assert (e["entregas"], e["calificadas"], e["completa"]) == (5, 4, False)
