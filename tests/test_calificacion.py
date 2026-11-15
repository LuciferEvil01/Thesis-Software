"""P16: conversión de las notas de la plataforma a la escala del modelo (Cap. 3)."""

import numpy as np
import pytest

from alerta import calificacion
from alerta.calificacion import Anclada, Equipercentil, ItemCalificable, ProporcionalOULAD

ITEM_25 = ItemCalificable("assign", 0, 5)
ITEM_PTS = ItemCalificable("assign", 0, 20, gradepass=12)
RNG = np.random.default_rng(0)
TRAIN = np.clip(RNG.normal(68, 22, 5000).round(), 0, 100)  # notas de entrenamiento inventadas (0–100)
ESCALA = calificacion.escala_entrenamiento(TRAIN)


def referencia(cursos: int = 2) -> dict:
    """Grupo de referencia inventado: cursos calificados de 2 a 5 con muchos 4."""
    notas = RNG.choice([2, 3, 4, 5], size=600, p=[0.2, 0.25, 0.4, 0.15]).astype(float)
    import pandas as pd
    return calificacion.referencia(pd.DataFrame({"course_id": np.arange(600) % cursos, "grade": notas,
                                                 "grademin": 0.0, "grademax": 5.0, "gradepass": 0.0}))


def test_default_is_equipercentile(monkeypatch):
    monkeypatch.delenv("ALERTA_CALIFICACION", raising=False)
    assert isinstance(calificacion.cargar(escala=ESCALA), Equipercentil)


def test_choose_by_environment(monkeypatch):
    monkeypatch.setenv("ALERTA_CALIFICACION", "test_calificacion:Fija")
    assert calificacion.cargar(escala=ESCALA).a_100(1, ITEM_25) == 42


def test_scale_of_an_item():
    assert ITEM_25.escala == "2-5" and ITEM_25.aprobado == 3
    assert ITEM_PTS.escala == "puntos" and ITEM_PTS.aprobado == 12
    assert ItemCalificable("assign", 0, 20).aprobado == 12  # sin «calificación para aprobar»: 60 %


@pytest.mark.parametrize("conv", [Anclada(ESCALA), Equipercentil(ESCALA, referencia())])
def test_a_fail_is_never_read_as_a_pass(conv):
    assert conv.a_100(2, ITEM_25) == pytest.approx(ESCALA["suspenso_media"])
    assert ESCALA["suspenso_media"] < calificacion.PASS_100
    assert conv.a_100(11.5, ITEM_PTS) < calificacion.PASS_100
    assert all(conv.a_100(n, ITEM_25) >= calificacion.PASS_100 for n in (3, 4, 5))


@pytest.mark.parametrize("conv", [Anclada(ESCALA), Equipercentil(ESCALA, referencia())])
def test_conversions_keep_the_order(conv):
    for item, notas in ((ITEM_25, [2, 3, 3.5, 4, 5]), (ITEM_PTS, [0, 8, 12, 15, 18, 20])):
        v = [conv.a_100(n, item) for n in notas]
        assert v == sorted(v)


def test_proportional_reads_a_2_as_a_pass():
    """El motivo de la conversión: la proporcional lleva el 2 al aprobado de OULAD."""
    assert ProporcionalOULAD().a_100(2, ITEM_25) == calificacion.PASS_100


def test_anchored_values():
    a = Anclada(ESCALA)
    assert [a.a_100(n, ITEM_25) for n in (3, 4, 5)] == [50, 70, 90]
    assert a.a_100(12, ITEM_PTS) == 40 and a.a_100(20, ITEM_PTS) == 100


def test_equipercentile_reproduces_training_distribution():
    """Con el grupo de referencia calificado como el entrenamiento, la conversión es la identidad
    (salvo el suspenso, que pasa a la media de los suspensos)."""
    import pandas as pd
    item = ItemCalificable("assign", 0, 100, gradepass=40)
    ref = calificacion.referencia(pd.DataFrame({"course_id": np.arange(len(TRAIN)) % 3, "grade": TRAIN,
                                                "grademin": 0.0, "grademax": 100.0, "gradepass": 40.0}))
    q = Equipercentil(ESCALA, ref)
    passed = TRAIN[TRAIN >= 40]
    converted = np.array([q.a_100(n, item) for n in passed])
    assert np.abs(converted - passed).max() <= 0.5


def test_equipercentile_follows_the_reference_group():
    """Cada categoría ocupa en el entrenamiento los mismos percentiles que entre los aprobados de
    los cursos anteriores: con muchos 4, el 4 queda en el centro de los aprobados."""
    ref = referencia()
    q = Equipercentil(ESCALA, ref)
    grades = np.array(ref["2-5"]["aprobados"])
    lo, hi = np.mean(grades < 4), np.mean(grades <= 4)  # percentiles que ocupa el 4 entre los aprobados
    passed = np.sort(TRAIN[TRAIN >= 40])
    assert q.a_100(4, ITEM_25) == pytest.approx(passed[int(len(passed) * lo):int(len(passed) * hi)].mean(), abs=0.5)


def test_without_reference_group_it_is_anchored():
    assert Equipercentil(ESCALA, referencia(cursos=1)).a_100(4, ITEM_25) == 70  # un solo curso: no basta
    assert Equipercentil(ESCALA, {}).a_100(4, ITEM_25) == 70


class Fija:
    nombre = "fija"

    def a_100(self, nota, item):
        return 42


def test_scale_values():
    """P21: la escala cubana con palabras o con números se lee como 2, 3, 4 y 5; otra escala, no."""
    from alerta.calificacion import valores_escala
    assert valores_escala("Mal, Regular, Bien, Excelente") == [2.0, 3.0, 4.0, 5.0]
    assert valores_escala("2,3,4,5") == [2.0, 3.0, 4.0, 5.0]
    assert valores_escala("Bueno, Malo, Regular") is None
    assert valores_escala("1,2,3,4,5") == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_only_tasks_graded_two_to_five_enter():
    """P21: entran las tareas de 2 a 5 (puntuación o escala de cuatro elementos) y los cuestionarios en
    puntos; las tareas en otra escala quedan fuera con sus notas."""
    import pandas as pd
    from alerta.calificacion import Anclada, Equipercentil, ProporcionalOULAD, excluir_tareas_fuera_de_escala
    a = pd.DataFrame({"course_id": 1, "item_id": [1, 2, 3, 4, 5],
                      "module_type": ["assign", "assign", "assign", "assign", "quiz"],
                      "grademin": [2.0, 0.0, 0.0, 1.0, 0.0], "grademax": [5.0, 5.0, 100.0, 5.0, 10.0],
                      "gradepass": 0.0})
    g = pd.DataFrame({"course_id": 1, "item_id": [1, 2, 3, 4, 5], "student_id": 7, "grade": [4.0, 3.0, 80.0, 2.0, 6.0]})
    a2, g2, out = excluir_tareas_fuera_de_escala(a, g)
    assert out == [3, 4]
    assert list(a2["item_id"]) == [1, 2, 5] and list(g2["item_id"]) == [1, 2, 5]
    assert Anclada.exige_25 and Equipercentil.exige_25 and not ProporcionalOULAD.exige_25
