"""Reglas de alerta.variables que OULAD no ejercita: tipos de evaluación configurables (P4), fecha de
publicación de las notas y bajas. Un curso sintético de 100 días con tres TMA (días 20, 50, 90)."""

import numpy as np
import pandas as pd
import pytest

from alerta import variables
from alerta.canonico import Canonico

NAN = float("nan")


def course(grades, students=None, extra_items=()):
    items = [("c", 1, "assign", 20, 100, True), ("c", 2, "assign", 50, 100, True),
             ("c", 3, "assign", 90, 100, True), *extra_items]
    return Canonico(
        courses=pd.DataFrame({"course_id": ["c"], "length_days": [100], "start_ts": [NAN]}),
        students=students if students is not None else pd.DataFrame(
            {"course_id": "c", "student_id": [1, 2], "unregistered_day": NAN, "repeated": 0}),
        assessments=pd.DataFrame(items, columns=["course_id", "item_id", "module_type", "due_day",
                                                 "grademax", "is_tma"]),
        grades=pd.DataFrame(grades, columns=["course_id", "item_id", "student_id", "submitted_day",
                                             "score", "graded_day"]),
        activity=pd.DataFrame({"course_id": "c", "student_id": [1, 2], "day": [5, 6], "site_id": 1,
                               "events": [3, 4]}),
    )


def row(df, student, cut):
    return df[(df["student_id"] == student) & (df["cut"] == cut)].iloc[0]


def test_cuts_anchor_tmas():
    c = variables.cuts(course([]))
    assert c.set_index("cut")["anchor_item"].to_dict() == {"first": 1, "mid": 2, "last": 3}
    assert c.set_index("cut")["cutoff_day"].to_dict() == {"first": 34, "mid": 64, "last": 104}


def test_not_submitted_counts_zero():
    df = variables.build(course([("c", 1, 1, 18, 80, NAN), ("c", 2, 1, 49, 60, NAN)]))
    assert row(df, 1, "mid")["mean_score_with_zeros"] == 70
    assert row(df, 1, "mid")["last_score"] == 60
    assert row(df, 2, "mid")["mean_score_with_zeros"] == 0
    assert row(df, 2, "mid")["submission_rate"] == 0


def test_late_published_grade_is_not_seen():
    # Entregada a tiempo, nota publicada el día 70, después del corte mid (64): la nota media usa
    # las demás y la del corte toma la media del propio estudiante.
    df = variables.build(course([("c", 1, 1, 18, 80, 25), ("c", 2, 1, 49, 60, 70)]))
    r = row(df, 1, "mid")
    assert r["submission_rate"] == 1
    assert r["mean_score_with_zeros"] == 80 and r["last_score"] == 80
    # En el corte last (104) ya se ve; la TMA 3 no se entregó y cuenta 0
    assert row(df, 1, "last")["mean_score_with_zeros"] == pytest.approx((80 + 60 + 0) / 3)


def test_extra_types_only_when_included():
    quiz = [("c", 10, "quiz", 30, 100, False)]
    grades = [("c", 1, 1, 18, 80, NAN), ("c", 2, 1, 49, 60, NAN), ("c", 10, 1, 29, 100, NAN)]
    only_assign = variables.build(course(grades, extra_items=quiz))
    with_quiz = variables.build(course(grades, extra_items=quiz), types={"assign", "quiz"})
    assert row(only_assign, 1, "mid")["mean_score_with_zeros"] == 70
    assert row(with_quiz, 1, "mid")["mean_score_with_zeros"] == pytest.approx(80)
    assert row(with_quiz, 1, "first")["mean_score_with_zeros"] == 80  # el quiz (día 30) es posterior al ancla (20)
    assert row(with_quiz, 1, "mid")["last_score"] == 60  # last_score siempre es la TMA ancla


def test_undated_items_are_ignored():
    undated = [("c", 11, "quiz", NAN, 100, False)]
    grades = [("c", 1, 1, 18, 80, NAN), ("c", 11, 1, 5, 0, NAN)]
    df = variables.build(course(grades, extra_items=undated), types={"assign", "quiz"})
    assert row(df, 1, "first")["mean_score_with_zeros"] == 80


def test_unregistered_before_cutoff_is_excluded():
    students = pd.DataFrame({"course_id": "c", "student_id": [1, 2], "unregistered_day": [NAN, 40],
                             "repeated": 0})
    df = variables.build(course([], students=students))
    assert set(df.loc[df["student_id"] == 2, "cut"].astype(str)) == {"first"}


def test_percentiles_within_class():
    df = variables.build(course([("c", 1, 1, 18, 80, NAN)]))
    first = df[df["cut"] == "first"].set_index("student_id")
    assert first.loc[1, "mean_score_with_zeros_pct"] == 1.0
    assert first.loc[2, "mean_score_with_zeros_pct"] == 0.5
    assert np.isnan(first.loc[1, "last_score_pct"])
