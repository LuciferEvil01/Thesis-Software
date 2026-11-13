"""Convierte el modelo final de la tesis (`Proposal/artifacts/final_<corte>.joblib`) en un paquete.

- `from_proposal` (v1): los joblib tal cual, con el umbral F2 de E14.
- `from_proposal_e18` (v2, P13): los mismos modelos con el umbral del Cap. 2 actual, la proporción de
  desaprobados de los periodos de entrenamiento en cada corte (E18), y la escala de las notas de
  entrenamiento para convertir las de la plataforma (P16). Los dos se calculan aquí con los datos.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import joblib

import pandas as pd

from alerta import calificacion
from alerta.canonico import Canonico
from alerta.modelo.entrenamiento import SPEC_E18, SPEC_TESIS, TARGET, THRESHOLDS
from alerta.modelo.paquete import CUTS, Logistica, ModeloCorte, Paquete

PERIODOS_TESIS = ["2013B", "2013J", "2014B"]  # periodos de OULAD con los que se ajustó (E14)


def from_proposal(artifacts: Path, version: str = "v1") -> Paquete:
    cuts, hashes = {}, {}
    for cut in CUTS:
        path = artifacts / f"final_{cut}.joblib"
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        final = joblib.load(path)
        if list(final["features"]) != SPEC_TESIS["features"][cut]:
            raise ValueError(f"{path.name}: las variables no coinciden con la especificación de E14")
        cuts[cut] = ModeloCorte(list(final["features"]), float(final["threshold"]), Logistica.from_sklearn(final["model"]))
    meta = {"origen": "Proposal (tesis, sección 2.2): modelo final de E14, evaluado en 2014J en E15",
            "periodos": PERIODOS_TESIS, "fuente": "oulad", "joblib_sha256": hashes}
    return Paquete(version, cuts, SPEC_TESIS, meta)


def training_scores(d: Canonico, periods: list[str] = PERIODOS_TESIS) -> pd.Series:
    """Notas (0–100) de las TMA de los cursos de OULAD de los periodos de entrenamiento."""
    tma = d.assessments[d.assessments["is_tma"].astype(bool)][["course_id", "item_id"]]
    g = d.grades.merge(tma, on=["course_id", "item_id"])
    return g.loc[g["course_id"].str.split("_").str[-1].isin(periods), "score"]


def from_proposal_e18(artifacts: Path, dataset: pd.DataFrame, d: Canonico, version: str = "v2",
                      period_col: str = "code_presentation") -> Paquete:
    """Paquete del modelo final con el umbral de E18 y la escala de las notas de entrenamiento.

    `dataset`: variables + `at_risk` + `period_col` (Proposal/data/processed/dataset.parquet);
    `d`: OULAD en el esquema canónico (`alerta.fuentes.oulad.load`).
    """
    v1 = from_proposal(artifacts, version)
    train = dataset[dataset[period_col].astype(str).isin(PERIODOS_TESIS)]
    rule = THRESHOLDS[SPEC_E18["threshold"]]
    cuts, info = {}, {}
    for cut in CUTS:
        y = train.loc[train["cut"].astype(str) == cut, TARGET]
        cuts[cut] = ModeloCorte(v1.cuts[cut].features, rule(y), v1.cuts[cut].model)
        info[cut] = {"filas": int(len(y)), "desaprobados": int(y.sum())}
    meta = {**v1.meta, "origen": "Proposal (tesis, Cap. 2): modelo final de E14 con el umbral de E18 "
                                 "(proporción de desaprobados del entrenamiento en cada corte)",
            "entrenamiento": info}
    return Paquete(version, cuts, SPEC_E18, meta, calificacion.escala_entrenamiento(training_scores(d)))
