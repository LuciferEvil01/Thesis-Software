"""F2: el paquete v1 es el modelo de la tesis, y el entrenamiento del sistema lo reproduce.

Usa 2014J solo para comprobar que el software da los mismos números que la evaluación ya hecha en
la tesis (E15); el modelo está fijado y aquí no se elige nada.
"""

import joblib
import numpy as np
import pytest

from alerta import config
from alerta.modelo import entrenamiento, importar
from alerta.modelo.paquete import CUTS, Paquete
from alerta.modelo.registro import Registro

pytestmark = pytest.mark.slow
ARTIFACTS = config.PROPOSAL_DIR / "artifacts"
E15_AUC = {"first": 0.787, "mid": 0.883, "last": 0.923}
E15_RECALL = {"first": 0.929, "mid": 0.894, "last": 0.887}


@pytest.fixture(scope="module")
def v1():
    if not ARTIFACTS.exists():
        pytest.skip("faltan los artefactos de Proposal")
    return importar.from_proposal(ARTIFACTS)


def test_same_probabilities_as_joblib(v1, proposal_dataset):
    for cut in CUTS:
        d = proposal_dataset[proposal_dataset["cut"] == cut]
        final = joblib.load(ARTIFACTS / f"final_{cut}.joblib")
        expected = final["model"].predict_proba(d[final["features"]])[:, 1]
        np.testing.assert_allclose(v1.predict(d)["prob"], expected, rtol=0, atol=1e-12)


def test_save_load_and_registry(v1, tmp_path, proposal_dataset):
    reg = Registro(tmp_path)
    reg.register(v1)
    reg.activate("v1", "prueba")
    loaded = reg.active()
    assert loaded.version == "v1" and reg.next_version() == "v2"
    d = proposal_dataset.head(500)
    np.testing.assert_array_equal(loaded.predict(d)["prob"], v1.predict(d)["prob"])


def test_training_reproduces_thesis_model(v1, proposal_dataset):
    train = proposal_dataset[proposal_dataset["code_presentation"].isin(importar.PERIODOS_TESIS)]
    new = entrenamiento.train(train, entrenamiento.SPEC_TESIS, "rep", group_col="code_presentation")
    for cut in CUTS:
        a, b = new.cuts[cut], v1.cuts[cut]
        assert a.features == b.features
        assert a.threshold == pytest.approx(b.threshold, abs=1e-10)
        np.testing.assert_allclose(a.model.coef, b.model.coef, atol=1e-10)
        assert a.model.intercept == pytest.approx(b.model.intercept, abs=1e-10)


def test_thesis_numbers_on_2014J(v1, proposal_dataset):
    test = proposal_dataset[proposal_dataset["code_presentation"] == "2014J"]
    m = entrenamiento.evaluate(v1, test)
    for cut in CUTS:
        assert round(m[cut]["roc_auc"], 3) == E15_AUC[cut]
        assert round(m[cut]["sensibilidad"], 3) == E15_RECALL[cut]


def test_pipeline_end_to_end_on_2014J(v1, oulad_data):
    """Desde OULAD crudo: esquema canónico → variables del sistema → paquete."""
    _, labels, feats = oulad_data
    df = feats[feats["course_id"].str.endswith("2014J")].merge(labels, on=["course_id", "student_id"])
    m = entrenamiento.evaluate(v1, df)
    assert {cut: round(m[cut]["roc_auc"], 3) for cut in CUTS} == E15_AUC


def test_missing_feature_is_an_error(v1, proposal_dataset):
    d = proposal_dataset[proposal_dataset["cut"] == "mid"].head(3).copy()
    d.loc[d.index[0], "last_score_raw"] = np.nan
    with pytest.raises(ValueError, match="variables vacías"):
        v1.predict(d)


def test_package_is_plain_json(v1, tmp_path):
    folder = v1.save(tmp_path / "v1")
    assert sorted(p.name for p in folder.iterdir()) == ["manifest.json"]
    assert Paquete.load(folder).cuts["mid"].threshold == v1.cuts["mid"].threshold


THESIS_THRESHOLDS = {"first": 0.433, "mid": 0.389, "last": 0.353}  # Cap. 2, sección 2.4.1 (E18)


def test_v2_thresholds_are_the_failure_proportion_of_training(v1, proposal_dataset, oulad_data):
    """P13: el umbral de cada corte es la proporción de desaprobados de los periodos de entrenamiento,
    calculada con los datos; el modelo es el mismo de v1."""
    d, *_ = oulad_data
    v2 = importar.from_proposal_e18(ARTIFACTS, proposal_dataset, d)
    assert v2.spec["threshold"] == "proporcion_desaprobados_por_corte"
    for cut in CUTS:
        assert round(v2.cuts[cut].threshold, 3) == THESIS_THRESHOLDS[cut]
        np.testing.assert_array_equal(v2.cuts[cut].model.coef, v1.cuts[cut].model.coef)
    assert v2.escala["suspenso_media"] < 40 and len(v2.escala["cuantiles_aprobado"]) == 1001
    assert Registro(config.MODELOS_DIR).load("v2").cuts["mid"].threshold == v2.cuts["mid"].threshold


def test_training_with_e18_rule(proposal_dataset):
    """Reentrenar con la especificación de v2 aplica la misma regla del umbral."""
    train = proposal_dataset[proposal_dataset["code_presentation"].isin(importar.PERIODOS_TESIS)]
    new = entrenamiento.train(train, entrenamiento.SPEC_E18, "rep", group_col="code_presentation")
    assert {cut: round(m.threshold, 3) for cut, m in new.cuts.items()} == THESIS_THRESHOLDS
