"""Traducción de las calificaciones de Moodle a la escala del modelo (0–100), desacoplada (PLAN.md, P8 y P16).

El modelo aprendió con las notas de OULAD (0–100, aprobado en 40). La extracción no sabe cómo
califica la institución: recibe un objeto `Calificacion` y le pide `a_100(nota, ítem)`.

Conversión de la tesis (Cap. 3; ECTS Users' Guide 2015, secc. 4.3–4.4; Kolen y Brennan, 2014):

- Un suspenso (un 2, o una nota en puntos por debajo del aprobado del ítem) pasa a la media de las
  notas de suspenso del entrenamiento (por debajo de 40). Así nunca se lee como aprobado.
- `Equipercentil` (por defecto): cada nota de aprobado pasa a la media de las notas de aprobado del
  entrenamiento que ocupan sus mismos percentiles entre los aprobados de los cursos anteriores de
  la plataforma (el grupo de referencia, de al menos `MIN_CURSOS` cursos, en `config.ESCALA_REFERENCIA`).
- `Anclada`: mientras no haya grupo de referencia de esa escala, el 3, el 4 y el 5 van a valores
  fijos del tramo de aprobado (50, 70 y 90, los centros de 40–59, 60–79 y 80–100) y una nota en
  puntos de aprobado se lleva de forma lineal de [aprobado, máxima] a [40, 100].
- `ProporcionalOULAD`: nota / máxima · 100, como OULAD. Solo para reproducir OULAD en Moodle
  (validación F5); con la escala 2–5 leería un 2 como aprobado (40).

La escala de entrenamiento (media de los suspensos y cuantiles de los aprobados) la calcula
`escala_entrenamiento` y viaja en el paquete del modelo (`Paquete.escala`).

Para usar otra conversión: escribir una clase con `nombre` y `a_100` y elegirla con la variable de
entorno `ALERTA_CALIFICACION=paquete.modulo:Clase` (o pasarla a `extract_course`).
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

PASS_100 = 40  # aprobado de OULAD
PASS_POINTS = 0.6  # aprobado de un ítem en puntos que no lo fija en Moodle (fracción de la máxima)
ANCHORS_25 = {3: 50.0, 4: 70.0, 5: 90.0}  # `Anclada`: centros de 40–59, 60–79 y 80–100
FALLBACK_FAIL = 20.0  # media de los suspensos si el paquete no trae su escala (paquetes anteriores a v2)
MIN_CURSOS = 2  # tamaño mínimo del grupo de referencia (ECTS 2015: al menos dos cohortes)
GRID = np.linspace(0, 1, 1001)  # cuantiles guardados de las notas de aprobado del entrenamiento
SCALE_25, POINTS = "2-5", "puntos"


@dataclass(frozen=True)
class ItemCalificable:
    """Lo que Moodle dice de un ítem del libro de calificaciones."""

    module_type: str  # assign, quiz, …
    grademin: float
    grademax: float
    gradepass: float = 0.0  # «calificación para aprobar» del ítem en Moodle; 0 = sin fijar

    @property
    def escala(self) -> str:
        return SCALE_25 if self.grademax == 5 and self.grademin in (0, 2) else POINTS

    @property
    def aprobado(self) -> float:
        if self.escala == SCALE_25:
            return 3.0
        return self.gradepass if self.gradepass > 0 else PASS_POINTS * self.grademax

    @property
    def minima(self) -> float:
        """Nota con que se muestra una tarea no entregada en la escala del curso."""
        return 2.0 if self.escala == SCALE_25 else self.grademin

    def posicion(self, nota: float) -> float:
        """Valor comparable entre ítems de la misma escala (la nota, o la fracción de la máxima)."""
        return float(nota) if self.escala == SCALE_25 else float(nota) / self.grademax


class Calificacion(Protocol):
    nombre: str

    def a_100(self, nota: float, item: ItemCalificable) -> float:
        """Nota de Moodle → nota de 0 a 100 en la escala del modelo."""
        ...


def escala_entrenamiento(scores) -> dict:
    """Media de los suspensos y cuantiles de los aprobados de las notas de entrenamiento (0–100)."""
    s = pd.Series(scores, dtype=float).dropna()
    passed = np.sort(s[s >= PASS_100].to_numpy())
    return {"aprobado": PASS_100, "suspenso_media": float(s[s < PASS_100].mean()), "notas": int(len(s)),
            "aprobados": int(len(passed)), "cuantiles_aprobado": np.quantile(passed, GRID).round(4).tolist()}


class ProporcionalOULAD:
    nombre = "proporcional (nota / máxima · 100, como OULAD)"

    def a_100(self, nota: float, item: ItemCalificable) -> float:
        return nota / item.grademax * 100


class Anclada:
    nombre = "anclada (2 → media de los suspensos; 3, 4 y 5 en el tramo de aprobado)"

    def __init__(self, escala: dict | None = None):
        self.fail = float((escala or {}).get("suspenso_media", FALLBACK_FAIL))

    def a_100(self, nota: float, item: ItemCalificable) -> float:
        if nota < item.aprobado:
            return self.fail
        if item.escala == SCALE_25:  # interpolación entre los anclajes (por si hay notas como 3,5)
            return float(np.interp(nota, list(ANCHORS_25), list(ANCHORS_25.values())))
        span = item.grademax - item.aprobado
        return 100.0 if span <= 0 else PASS_100 + (100 - PASS_100) * (nota - item.aprobado) / span


class Equipercentil:
    """Equiparación entre aprobados con el grupo de referencia; `Anclada` en las escalas sin él."""

    def __init__(self, escala: dict | None = None, referencia: dict | None = None):
        self.anclada = Anclada(escala)
        self.fail = self.anclada.fail
        self.quantiles = np.array((escala or {}).get("cuantiles_aprobado") or [])
        referencia = cargar_referencia() if referencia is None else referencia
        self.reference = {k: np.sort(np.array(v["aprobados"], dtype=float)) for k, v in referencia.items()
                          if len(v.get("cursos", [])) >= MIN_CURSOS and v.get("aprobados")}
        self.nombre = ("equipercentil entre aprobados (grupo de referencia: "
                       + (", ".join(f"{k}: {len(referencia[k]['cursos'])} cursos" for k in self.reference) or "ninguno")
                       + "; sin él, anclada)")

    def a_100(self, nota: float, item: ItemCalificable) -> float:
        ref = self.reference.get(item.escala)
        if ref is None or not len(self.quantiles):
            return self.anclada.a_100(nota, item)
        if nota < item.aprobado:
            return self.fail
        v = item.posicion(nota)
        lo, hi = np.searchsorted(ref, v, "left") / len(ref), np.searchsorted(ref, v, "right") / len(ref)
        # Media de las notas de aprobado del entrenamiento entre los percentiles [lo, hi] de la nota
        # (una nota que no está en la referencia ocupa un solo percentil)
        return float(np.interp(np.linspace(lo, hi, 201), GRID, self.quantiles).mean())


def referencia(grades: pd.DataFrame) -> dict:
    """Grupo de referencia a partir de las notas de cursos cerrados de la plataforma.

    `grades`: course_id, grade (nota en la escala del ítem), grademin, grademax, gradepass. Guarda,
    por escala, los cursos y las notas de aprobado (en la escala 2–5, la nota; en puntos, la fracción
    de la máxima).
    """
    out: dict = {}
    for g in grades.dropna(subset=["grade"]).itertuples():
        item = ItemCalificable("assign", float(g.grademin), float(g.grademax), float(g.gradepass or 0))
        e = out.setdefault(item.escala, {"cursos": set(), "aprobados": []})
        e["cursos"].add(str(g.course_id))
        if g.grade >= item.aprobado:
            e["aprobados"].append(round(item.posicion(g.grade), 6))
    return {k: {"cursos": sorted(v["cursos"]), "aprobados": sorted(v["aprobados"])} for k, v in out.items()}


def ruta_referencia() -> Path:
    from alerta import config
    return config.ESCALA_REFERENCIA


def guardar_referencia(ref: dict, path: Path | None = None) -> Path:
    path = path or ruta_referencia()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ref, ensure_ascii=False))
    return path


def cargar_referencia(path: Path | None = None) -> dict:
    path = path or ruta_referencia()
    return json.loads(path.read_text()) if path.exists() else {}


DEFAULT = "alerta.calificacion:Equipercentil"


def cargar(ref: str | None = None, escala: dict | None = None) -> Calificacion:
    """Instancia la clase `paquete.modulo:Clase` (por defecto, la de `ALERTA_CALIFICACION`).

    `escala`: la de entrenamiento del paquete del modelo, si la clase la acepta.
    """
    module, _, name = (ref or os.environ.get("ALERTA_CALIFICACION") or DEFAULT).partition(":")
    cls = getattr(importlib.import_module(module), name)
    accepts = "escala" in inspect.signature(cls).parameters
    return cls(escala=escala) if accepts else cls()
