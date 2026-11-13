"""Reentrenamiento con el archivo, simulado con OULAD: el campeón es v1 (2013B, 2013J, 2014B) y el
archivo trae además 2014J, el periodo nuevo."""

import pytest

from alerta import config
from alerta.archivo import Archivo
from alerta.fuentes import oulad
from alerta.modelo import importar
from alerta.modelo.reentrenamiento import Politica, retrain
from alerta.modelo.registro import Registro

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def archivo(oulad_data, tmp_path_factory):
    a = Archivo(tmp_path_factory.mktemp("archivo"))
    d, labels, _ = oulad_data
    assert len(oulad.archive(a, d, labels)) == 22
    return a


def registro_v1(tmp_path):
    reg = Registro(tmp_path / "modelos")
    reg.register(importar.from_proposal(config.PROPOSAL_DIR / "artifacts"))
    reg.activate("v1", "modelo de la tesis")
    return reg


def test_retrain_promotes_and_then_waits(archivo, tmp_path):
    reg = registro_v1(tmp_path)
    report = retrain(archivo, reg)
    assert report["periodos_nuevos"] == ["2014J"] and report["reservado"] == "2014J"
    # El aspirante se entrena con los mismos periodos que v1: es el mismo modelo
    assert all(abs(v) < 1e-9 for v in report["caida_roc_auc"].values())
    assert report["decision"] == "activada v2"
    v2 = reg.active()
    assert v2.meta["periodos"] == ["2013B", "2013J", "2014B", "2014J"]
    assert v2.spec == reg.load("v1").spec
    assert retrain(archivo, reg)["decision"] == "sin datos nuevos"


def test_retrain_keeps_champion_when_rule_fails(archivo, tmp_path):
    reg = registro_v1(tmp_path)
    report = retrain(archivo, reg, Politica(max_caida=-1))  # regla imposible de cumplir
    assert report["decision"].startswith("se mantiene")
    assert reg.active_version() == "v1" and reg.versions() == ["v1"]


def test_retrain_registers_without_activating(archivo, tmp_path):
    reg = registro_v1(tmp_path)
    report = retrain(archivo, reg, Politica(activar=False))
    assert report["nueva_version"] == "v2" and reg.active_version() == "v1"
