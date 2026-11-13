import pandas as pd
import pytest

from alerta import config, variables
from alerta.fuentes import oulad


@pytest.fixture(scope="session")
def oulad_data():
    """(canónico, etiquetas, variables) de OULAD completo. Tarda unos 30 s."""
    if not config.OULAD_DIR.exists():
        pytest.skip("falta OULAD")
    d, labels = oulad.load(config.OULAD_DIR)
    return d, labels, variables.build(d)


@pytest.fixture(scope="session")
def proposal_dataset():
    if not config.TRAIN_DATASET.exists():
        pytest.skip("falta el dataset de Proposal")
    ref = pd.read_parquet(config.TRAIN_DATASET)
    ref["cut"] = ref["cut"].astype(str)
    return ref
