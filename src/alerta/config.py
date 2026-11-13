"""Rutas y parámetros por entorno. Todo lo que depende del servidor viene de variables de entorno."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # raíz de Thesis-Software
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".runtime" / "generated" / "rest.env")  # lo escribe `make up` (Moodle local)

MOODLE_URL = os.environ.get("MOODLE_URL")
MOODLE_TOKEN = os.environ.get("MOODLE_TOKEN")

_TRAINING_DEFAULT = next((ROOT.parent / n for n in ("Thesis-Training", "Training", "Proposal") if (ROOT.parent / n).exists()),
                         ROOT.parent / "Thesis-Training")  # repositorio publicado: Thesis-Training
PROPOSAL_DIR = Path(os.environ.get("PROPOSAL_DIR", _TRAINING_DEFAULT))
OULAD_DIR = Path(os.environ.get("OULAD_DIR", PROPOSAL_DIR / "data" / "raw" / "oulad"))
TRAIN_DATASET = PROPOSAL_DIR / "data" / "processed" / "dataset.parquet"
MODELOS_DIR = Path(os.environ.get("MODELOS_DIR", ROOT / "modelos"))  # registro de versiones (se versiona en git)
ARCHIVO_DIR = Path(os.environ.get("ARCHIVO_DIR", ROOT / "data" / "archivo"))  # cursos cerrados (no se versiona)
# Grupo de referencia de la conversión de las notas: notas de aprobado de cursos cerrados de la plataforma
ESCALA_REFERENCIA = Path(os.environ.get("ESCALA_REFERENCIA", ROOT / "data" / "escala" / "referencia.json"))
