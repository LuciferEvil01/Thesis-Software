"""F1: alerta.variables sobre OULAD reproduce exactamente el conjunto de datos del entrenamiento."""

import numpy as np
import pandas as pd
import pytest

from alerta import variables

pytestmark = pytest.mark.slow

RAW_VALUES = variables.VLE + ["submission_rate", "mean_score_with_zeros", "last_score", "repeated_course",
                              "cutoff_day"]


@pytest.fixture(scope="module")
def both(oulad_data, proposal_dataset):
    _, labels, ours = oulad_data
    ours, ref = ours.copy(), proposal_dataset.copy()
    ref["course_id"] = ref["code_module"] + "_" + ref["code_presentation"]
    ref = ref.rename(columns={"id_student": "student_id", "anchor_tma": "anchor_k"})
    ref["cut"] = ref["cut"].astype(str)
    ours["cut"] = ours["cut"].astype(str)
    return ours, ref, labels


def test_same_rows(both):
    ours, ref, _ = both
    key = variables.ROW
    assert len(ours) == len(ref)
    merged = ours[key].merge(ref[key], on=key, how="outer", indicator=True)
    assert (merged["_merge"] == "both").all()


@pytest.mark.parametrize("col", variables.FEATURES + RAW_VALUES + ["anchor_k"])
def test_same_values(both, col):
    ours, ref, _ = both
    m = ours.merge(ref, on=variables.ROW, suffixes=("", "_ref"))
    a, b = m[col].astype(float).to_numpy(), m[f"{col}_ref"].astype(float).to_numpy()
    np.testing.assert_allclose(a, b, rtol=0, atol=1e-12, equal_nan=True, err_msg=col)


def test_same_target(both):
    ours, ref, labels = both
    m = ours.merge(labels, on=variables.KEYS).merge(ref, on=variables.ROW, suffixes=("", "_ref"))
    assert (m["at_risk"] == m["at_risk_ref"]).all()
