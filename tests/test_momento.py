"""P12: predicción en un momento cualquiera (ancla elegida por las notas, ajuste por su posición).

Curso inventado de `curso_sintetico` (110 días). TMA: 10 (día 20, 18 % del curso), 11 (día 50, 45 %)
y 12 (día 90, 82 %). La 10 nunca queda completa: el estudiante 3 la entregó y no tiene nota. El
estudiante 6 se da de baja el día 30 y desde entonces no cuenta.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from curso_sintetico import curso  # noqa: E402

from alerta import variables  # noqa: E402


@pytest.fixture(scope="module")
def d():
    return curso()


def status(d, day: int) -> pd.DataFrame:
    return variables.evaluations(d, day).set_index("item_id")


def test_adjustment_by_position(d):
    assert status(d, 100)["ajuste"].to_dict() == {10: "first", 11: "mid", 12: "last"}


def test_ungraded_submission_keeps_evaluation_incomplete(d):
    e = status(d, 29).loc[10]
    assert e["con_notas"] and not e["completa"] and (e["entregas"], e["calificadas"]) == (6, 5)


def test_only_active_students_count(d):
    """El día 30 el estudiante 6 ya se dio de baja: su entrega calificada deja de contar (P17)."""
    e = status(d, 30).loc[10]
    assert (e["entregas"], e["calificadas"]) == (5, 4) and e["proporcion"] == pytest.approx(0.8)


@pytest.mark.parametrize("due, adjustment", [(41, "first"), (42, "mid"), (68, "mid"), (69, "last")])
def test_adjustment_of_the_nearest_cut(d, due, adjustment):
    """Fronteras en el 37,5 y el 62,5 % del curso (110 días: 41,25 y 68,75), puntos medios entre las
    posiciones de los cortes (25, 50 y 75 %; P18)."""
    a = d.assessments.copy()
    a.loc[a["item_id"] == 11, "due_day"] = due
    moved = type(d)(d.courses, d.students, a, d.grades, d.activity)
    assert status(moved, 100).loc[11, "ajuste"] == adjustment


def test_evaluation_not_due_yet_is_ignored(d):
    e = status(d, 45).loc[11]  # el estudiante 3 entregó el día 45, pero la fecha es el 50
    assert not e["con_notas"] and not e["completa"]


def test_completes_when_last_grade_is_published(d):
    assert not status(d, 69).loc[11, "completa"]  # la nota del estudiante 3 se publica el día 70
    assert status(d, 70).loc[11, "completa"]
    assert status(d, 95).loc[12, "completa"] and not status(d, 94).loc[12, "completa"]


@pytest.mark.parametrize("cut", ["first", "mid", "last"])
def test_moment_at_thesis_cut_reproduces_thesis_variables(d, cut):
    """En el día de corte de la tesis, con su ancla, el cálculo nuevo da lo mismo que el de la tesis."""
    thesis = variables.build(d)
    thesis = thesis[thesis["cut"] == cut].reset_index(drop=True)
    c = variables.cuts(d).set_index("cut").loc[cut]
    e = variables.evaluations(d, int(c["cutoff_day"]))
    anchor = e[e["item_id"] == c["anchor_item"]].iloc[0]
    assert anchor["ajuste"] == cut
    now = variables.build(d, at=variables.moment(anchor, int(c["cutoff_day"])))
    cols = ["student_id", "cutoff_day", *variables.FEATURES]
    pd.testing.assert_frame_equal(now[cols].astype(float), thesis[cols].astype(float))


# P20: el profesor elige qué otros tipos de evaluación entran; la petición toma la más reciente.
QUIZ = frozenset({"assign", "quiz"})


def test_other_types_enter_only_if_chosen(d):
    assert 20 not in status(d, 100).index
    e = variables.evaluations(d, 100, QUIZ).set_index("item_id")
    assert not e.loc[20, "is_tma"] and e.loc[20, "ajuste"] == "first"  # día 35 de 110: 32 %
    assert e.loc[[10, 11, 12], "is_tma"].all() and e.loc[12, "ultima"] and not e.loc[20, "ultima"]


def test_chosen_quiz_is_the_most_recent_reference(d):
    """El día 40 la evaluación más reciente con notas es el cuestionario (día 35), no la TMA del 20."""
    e = variables.evaluations(d, 40, QUIZ)
    ready = e[e["con_notas"]].sort_values("due_day")
    assert int(ready.iloc[-1]["item_id"]) == 20
    assert int(e[e["is_tma"] & e["completa"]].shape[0]) == 0  # la automática no tiene ancla nueva


def test_quiz_reference_gives_its_grade_and_enters_the_mean(d):
    e = variables.evaluations(d, 40, QUIZ).set_index("item_id", drop=False)
    rows = variables.build(d, types=QUIZ, at=variables.moment(e.loc[20], 40)).set_index("student_id")
    # Estudiante 1: TMA 10 = 80 y cuestionario = 75; la media incluye el cuestionario
    assert rows.loc[1, "mean_score_with_zeros"] == pytest.approx((80 + 75) / 2)
    # El ajuste first no usa last_score; con el del segundo corte sería la nota del cuestionario
    mid = e.loc[20].copy(); mid["ajuste"] = "mid"
    rows = variables.build(d, types=QUIZ, at=variables.moment(mid, 40)).set_index("student_id")
    assert rows.loc[1, "last_score"] == pytest.approx(75)
