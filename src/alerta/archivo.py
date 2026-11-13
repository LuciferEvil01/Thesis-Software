"""Archivo de cursos cerrados: los datos con los que se reentrena (PLAN.md, P7).

Cuando un curso termina y se conoce el resultado de cada estudiante, se guarda aquí su esquema
canónico completo (no las variables: así se pueden recalcular si cambia su definición) junto con
la etiqueta de cada estudiante.

    archivo/<course_id>/
      courses|students|assessments|grades|activity.parquet   esquema canónico del curso
      labels.parquet                                          student_id, at_risk, resultado
      meta.json   course_id, period, period_start, source, closed_at, types, label_rule

- `period` es el grupo de la validación (un periodo lectivo); `period_start` (fecha ISO) ordena los
  periodos: el más reciente es el que se reserva para comparar modelos al reentrenar.
- `types`: tipos de evaluación con que se calcularon las variables en ese curso (P4).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alerta.canonico import COLUMNS, Canonico
from alerta.variables import DEFAULT_TYPES

TABLES = list(COLUMNS)
META_KEYS = ["course_id", "period", "period_start", "source", "closed_at", "label_rule"]


class Archivo:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def courses(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if (p / "meta.json").exists())

    def add(self, d: Canonico, labels: pd.DataFrame, meta: dict, replace: bool = False) -> Path:
        """Archiva un curso. `d` y `labels` pueden traer más cursos: se toma el de `meta`."""
        missing = set(META_KEYS) - set(meta)
        if missing:
            raise ValueError(f"meta: faltan {sorted(missing)}")
        cid = meta["course_id"]
        folder = self.root / str(cid)
        if folder.exists() and not replace:
            raise FileExistsError(f"el curso {cid} ya está archivado")
        folder.mkdir(exist_ok=True)
        for t in TABLES:
            df = getattr(d, t)
            df[df["course_id"] == cid].to_parquet(folder / f"{t}.parquet", index=False)
        lab = labels[labels["course_id"] == cid]
        if lab.empty:
            raise ValueError(f"el curso {cid} no tiene etiquetas")
        lab.to_parquet(folder / "labels.parquet", index=False)
        meta = {**meta, "types": sorted(meta.get("types", DEFAULT_TYPES))}
        (folder / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=str))
        return folder

    def meta(self) -> pd.DataFrame:
        return pd.DataFrame([json.loads((self.root / c / "meta.json").read_text()) for c in self.courses()])

    def load(self, courses: list[str] | None = None) -> tuple[Canonico, pd.DataFrame]:
        courses = self.courses() if courses is None else courses
        if not courses:
            raise LookupError("el archivo está vacío")
        tables = {t: pd.concat([pd.read_parquet(self.root / c / f"{t}.parquet") for c in courses],
                               ignore_index=True) for t in TABLES}
        labels = pd.concat([pd.read_parquet(self.root / c / "labels.parquet") for c in courses], ignore_index=True)
        return Canonico(**tables).validate(), labels
