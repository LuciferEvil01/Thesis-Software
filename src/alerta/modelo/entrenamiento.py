"""Entrenamiento de un paquete a partir de una especificación fija.

Reproduce el ajuste final de la tesis (Proposal, notebook 04, DECISIONES E14). En cada corte:
  1. predicciones fuera de pliegue dejando fuera cada periodo (grupo);
  2. umbral según la regla de la especificación (`THRESHOLDS`): la proporción de desaprobados de los
     datos de entrenamiento en ese corte (Cap. 2, sección 2.4.1; DECISIONES E18; PLAN.md, P13) o,
     en el paquete v1, el que maximiza F2 sobre las predicciones fuera de pliegue (E14);
  3. ajuste con todos los datos.

La especificación (familia, hiperparámetros, variables de cada corte) **no se elige aquí**: viene
del protocolo de validación de la tesis y viaja dentro del paquete. Reentrenar es volver a ajustar
la misma especificación con más datos. Cambiar la especificación (otras variables, otra familia)
exige repetir la validación anidada de la tesis y es una decisión manual.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import fbeta_score, precision_recall_curve, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from alerta.modelo.paquete import CUTS, Logistica, ModeloCorte, Paquete, Sklearn

TARGET = "at_risk"

# Especificación del modelo final de la tesis (E14)
SPEC_TESIS = {
    "family": "logistica_l2",
    "params": {"C": 0.001, "max_iter": 1000},
    "features": {
        "first": ["mean_score_with_zeros_raw", "mean_score_with_zeros_pct", "recent_clicks_28d_pct"],
        "mid": ["mean_score_with_zeros_raw", "last_score_raw", "mean_score_with_zeros_pct", "recent_clicks_28d_pct"],
        "last": ["mean_score_with_zeros_raw", "last_score_raw", "mean_score_with_zeros_pct", "recent_clicks_28d_pct"],
    },
    "threshold": "f2_fuera_de_pliegue_por_periodo",
    "origen": "Proposal, DECISIONES.md E14",
}
# El modelo de la tesis con el umbral del Cap. 2 actual (E18): mismas variables y mismo ajuste
SPEC_E18 = {**SPEC_TESIS, "threshold": "proporcion_desaprobados_por_corte",
            "origen": "Proposal, DECISIONES.md E14 (modelo) y E18 (umbral)"}


def make_estimator(spec: dict):
    if spec["family"] == "logistica_l2":
        return make_pipeline(StandardScaler(), LogisticRegression(**spec["params"]))
    raise ValueError(f"familia desconocida: {spec['family']}")


def wrap(spec: dict, fitted) -> Logistica | Sklearn:
    return Logistica.from_sklearn(fitted) if spec["family"] == "logistica_l2" else Sklearn(fitted)


def f2_threshold(y, prob) -> float:
    """Umbral que maximiza F2 (van Rijsbergen, 1979) en la clase en riesgo."""
    prec, rec, thr = precision_recall_curve(y, prob)
    f2 = 5 * prec[:-1] * rec[:-1] / np.maximum(4 * prec[:-1] + rec[:-1], 1e-12)
    return float(thr[np.argmax(f2)])


def failure_proportion(y, prob=None) -> float:
    """Proporción de desaprobados (clase en riesgo) entre los estudiantes del corte (E18)."""
    return float(np.mean(y))


# Regla del umbral → función (y, predicciones fuera de pliegue) → umbral
THRESHOLDS = {"f2_fuera_de_pliegue_por_periodo": f2_threshold,
              "proporcion_desaprobados_por_corte": failure_proportion}


def out_of_group(estimator, X: pd.DataFrame, y: pd.Series, groups: np.ndarray) -> np.ndarray:
    """Predicciones fuera de pliegue dejando fuera cada grupo (periodo)."""
    oof = np.full(len(X), np.nan)
    for g in sorted(set(groups)):
        tr, va = groups != g, groups == g
        oof[va] = clone(estimator).fit(X[tr], y[tr]).predict_proba(X[va])[:, 1]
    return oof


def scores(y, prob, threshold: float) -> dict:
    yhat = prob > threshold
    return {"n": int(len(y)), "prevalencia": float(np.mean(y)), "roc_auc": float(roc_auc_score(y, prob)),
            "sensibilidad": float(recall_score(y, yhat)), "precision": float(precision_score(y, yhat, zero_division=0)),
            "f2": float(fbeta_score(y, yhat, beta=2)), "marcados": float(np.mean(yhat))}


def train(df: pd.DataFrame, spec: dict, version: str, group_col: str = "period", meta: dict | None = None,
          escala: dict | None = None) -> Paquete:
    """Entrena un paquete con `df` (variables + `at_risk` + `group_col`; una fila por estudiante y corte).

    `escala`: la de las notas de entrenamiento (`alerta.calificacion.escala_entrenamiento`), que viaja
    con el paquete para convertir las notas de la plataforma.
    """
    cuts, info = {}, {}
    for cut in CUTS:
        d = df[df["cut"].astype(str) == cut].reset_index(drop=True)
        groups = d[group_col].astype(str).to_numpy()
        if len(set(groups)) < 2:
            raise ValueError(f"corte {cut}: hacen falta al menos dos periodos para elegir el umbral")
        feats, y = spec["features"][cut], d[TARGET]
        estimator = make_estimator(spec)
        oof = out_of_group(estimator, d[feats], y, groups)
        thr = THRESHOLDS[spec["threshold"]](y, oof)
        cuts[cut] = ModeloCorte(feats, thr, wrap(spec, clone(estimator).fit(d[feats], y)))
        info[cut] = {"filas": len(d), "fuera_de_pliegue": scores(y, oof, thr)}
    meta = {**(meta or {}), "creado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "periodos": sorted(df[group_col].astype(str).unique()), "entrenamiento": info}
    return Paquete(version, cuts, spec, meta, escala or {})


def evaluate(paquete: Paquete, df: pd.DataFrame) -> dict:
    """Métricas por corte en datos con `at_risk` (ROC-AUC y, con el umbral del paquete, el resto)."""
    pred = paquete.predict(df)
    return {cut: scores(g[TARGET], g["prob"].to_numpy(), float(g["umbral"].iloc[0]))
            for cut, g in pred.groupby(pred["cut"].astype(str)) if g[TARGET].nunique() == 2}
