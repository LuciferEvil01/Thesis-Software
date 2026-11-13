"""Paquete de modelo: lo único que el resto del sistema sabe del modelo (PLAN.md, P1 y P7).

Un paquete es una carpeta con `manifest.json` y, si su tipo lo necesita, archivos auxiliares:

    manifest.json   formato, versión, tipo, especificación de entrenamiento, datos con los que se
                    entrenó, métricas, la escala de las notas de entrenamiento (`escala`, para
                    convertir las notas de la plataforma; `alerta.calificacion`) y, por corte:
                    variables, umbral y parámetros del modelo.

El resto del sistema solo usa `Paquete.predict(df)`: recibe las variables (una fila por estudiante,
curso y corte) y devuelve la probabilidad y la alerta. Cambiar de modelo es registrar otro paquete
y activarlo (`alerta.modelo.registro`); ningún otro módulo cambia.

Tipos de modelo (`KINDS`):
- `logistica`: estandarización + regresión logística, guardada como números en el manifiesto
  (portable, auditable, sin pickle). Es el modelo de la tesis.
- `sklearn`: cualquier estimador de scikit-learn con `predict_proba`, guardado con joblib. Para
  un modelo futuro que no sea lineal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import joblib
import numpy as np
import pandas as pd

FORMAT = 1
CUTS = ["first", "mid", "last"]


class Modelo(Protocol):
    kind: str

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray: ...  # probabilidad de la clase en riesgo
    def to_dict(self, folder: Path, cut: str) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict, folder: Path, cut: str) -> Modelo: ...


@dataclass
class Logistica:
    """p = 1 / (1 + exp(−(Σ coef · (x − mean) / scale + intercept)))."""

    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray
    intercept: float
    kind: str = "logistica"

    @classmethod
    def from_sklearn(cls, pipeline) -> Logistica:
        scaler, lr = pipeline[0], pipeline[-1]
        return cls(scaler.mean_.copy(), scaler.scale_.copy(), lr.coef_[0].copy(), float(lr.intercept_[0]))

    def contributions(self, X: pd.DataFrame, center: np.ndarray | None = None) -> np.ndarray:
        """Aporte de cada variable al logit respecto a `center` (por defecto, la media del entrenamiento).

        Con `center` = la media de las variables en el curso, la suma de los aportes de un estudiante es
        la diferencia entre su logit y el del estudiante promedio del curso (explicación de una alerta).
        """
        center = self.mean if center is None else center
        return (X.to_numpy(dtype=float) - center) / self.scale * self.coef

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        z = self.contributions(X).sum(axis=1) + self.intercept
        return 1 / (1 + np.exp(-z))

    def to_dict(self, folder: Path, cut: str) -> dict:
        return {"mean": self.mean.tolist(), "scale": self.scale.tolist(), "coef": self.coef.tolist(),
                "intercept": self.intercept}

    @classmethod
    def from_dict(cls, data: dict, folder: Path, cut: str) -> Logistica:
        return cls(np.array(data["mean"]), np.array(data["scale"]), np.array(data["coef"]), data["intercept"])


@dataclass
class Sklearn:
    estimator: object
    kind: str = "sklearn"

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.estimator.predict_proba(X)[:, 1]

    def to_dict(self, folder: Path, cut: str) -> dict:
        name = f"{cut}.joblib"
        joblib.dump(self.estimator, folder / name)
        return {"file": name}

    @classmethod
    def from_dict(cls, data: dict, folder: Path, cut: str) -> Sklearn:
        return cls(joblib.load(folder / data["file"]))


KINDS: dict[str, type] = {"logistica": Logistica, "sklearn": Sklearn}


@dataclass
class ModeloCorte:
    features: list[str]
    threshold: float
    model: Modelo


@dataclass
class Paquete:
    version: str
    cuts: dict[str, ModeloCorte]
    spec: dict = field(default_factory=dict)  # especificación de entrenamiento (alerta.modelo.entrenamiento)
    meta: dict = field(default_factory=dict)  # creado, origen, datos de entrenamiento, métricas…
    escala: dict = field(default_factory=dict)  # notas de entrenamiento (alerta.calificacion.escala_entrenamiento)

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade `prob`, `en_riesgo`, `umbral` y `modelo` a cada fila según su corte.

        En riesgo = la probabilidad supera el umbral (estrictamente, como en la tesis).
        """
        out = df.copy()
        out["prob"], out["umbral"] = np.nan, np.nan
        cut_col = out["cut"].astype(str)
        for cut, m in self.cuts.items():
            rows = cut_col == cut
            if not rows.any():
                continue
            X = out.loc[rows, m.features]
            if X.isna().any().any():
                bad = X.columns[X.isna().any()].tolist()
                raise ValueError(f"corte {cut}: variables vacías {bad}")
            out.loc[rows, "prob"] = m.model.predict_proba(X)
            out.loc[rows, "umbral"] = m.threshold
        unknown = set(cut_col) - set(self.cuts)
        if unknown:
            raise ValueError(f"el paquete {self.version} no tiene modelo para los cortes {sorted(unknown)}")
        out["en_riesgo"] = out["prob"] > out["umbral"]
        out["modelo"] = self.version
        return out

    def save(self, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=False)
        manifest = {
            "format": FORMAT, "version": self.version, "spec": self.spec, "meta": self.meta,
            **({"escala": self.escala} if self.escala else {}),
            "cuts": {cut: {"features": m.features, "threshold": m.threshold, "kind": m.model.kind,
                           "params": m.model.to_dict(folder, cut)} for cut, m in self.cuts.items()},
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
        return folder

    @classmethod
    def load(cls, folder: Path) -> Paquete:
        manifest = json.loads((folder / "manifest.json").read_text())
        if manifest["format"] != FORMAT:
            raise ValueError(f"{folder}: formato {manifest['format']} no soportado")
        cuts = {cut: ModeloCorte(c["features"], c["threshold"], KINDS[c["kind"]].from_dict(c["params"], folder, cut))
                for cut, c in manifest["cuts"].items()}
        return cls(manifest["version"], cuts, manifest["spec"], manifest["meta"], manifest.get("escala", {}))
