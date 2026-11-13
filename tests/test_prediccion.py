"""P15, P16 y P17 sin Moodle: la petición con la tarea a medio calificar, la explicación respecto al
curso y las notas en la escala del curso.

Curso inventado de 10 estudiantes y 100 días calificado de 2 a 5, con dos tareas: la 1 (día 20) y
la 2 (día 60). El servicio se ejecuta con un cliente falso que guarda lo que se publicaría.
"""

import json

import numpy as np
import pandas as pd
import pytest

from alerta import config, servicio, variables
from alerta.calificacion import Anclada
from alerta.canonico import Canonico
from alerta.modelo.entrenamiento import SPEC_E18
from alerta.modelo.paquete import CUTS, Logistica, ModeloCorte, Paquete

CID, N = 7, 10
NOTAS_1 = [5, 4, 4, 3, 3, 2, 5, 4, 3, 2]  # tarea 1; la 2 tiene las mismas notas


def curso(sin_nota: int) -> Canonico:
    """`sin_nota` estudiantes entregaron la tarea 2 y aún no tienen nota."""
    conv = Anclada({"suspenso_media": 25.0})
    from alerta.calificacion import ItemCalificable
    item = ItemCalificable("assign", 0, 5)
    grades = []
    for k, (sid, g) in enumerate(zip(range(1, N + 1), NOTAS_1)):
        grades.append((CID, 1, sid, 18, conv.a_100(g, item), 22, float(g)))
        graded = k >= sin_nota
        grades.append((CID, 2, sid, 58, conv.a_100(g, item) if graded else np.nan, 62 if graded else np.nan,
                       float(g) if graded else np.nan))
    rng = np.random.default_rng(1)
    activity = [(CID, s, day, 1, int(rng.integers(1, 9))) for s in range(1, N + 1) for day in range(0, 64, 3)]
    return Canonico(
        courses=pd.DataFrame({"course_id": [CID], "length_days": [100], "start_ts": [0]}),
        students=pd.DataFrame({"course_id": CID, "student_id": range(1, N + 1), "unregistered_day": np.nan,
                               "repeated": np.nan}),
        assessments=pd.DataFrame({"course_id": CID, "item_id": [1, 2], "module_type": "assign", "due_day": [20, 60],
                                  "grademax": 5.0, "is_tma": True, "grademin": 0.0, "gradepass": 0.0}),
        grades=pd.DataFrame(grades, columns=["course_id", "item_id", "student_id", "submitted_day", "score",
                                             "graded_day", "grade"]),
        activity=pd.DataFrame(activity, columns=["course_id", "student_id", "day", "site_id", "events"]),
    ).validate()


def paquete() -> Paquete:
    """Un paquete con coeficientes como los del modelo de la tesis (no hace falta Proposal)."""
    cuts = {}
    for cut in CUTS:
        f = SPEC_E18["features"][cut]
        n = len(f)
        cuts[cut] = ModeloCorte(f, 0.4, Logistica(np.full(n, 0.5), np.full(n, 0.3), np.full(n, -0.5), -0.5))
    return Paquete("prueba", cuts, escala={"suspenso_media": 25.0})


class Cliente:
    def __init__(self):
        self.calls = []

    def call(self, name, **kw):
        self.calls.append((name, kw))
        if name == "local_alertatemprana_get_runs":
            return []
        if name == "local_alertatemprana_get_course_config":
            return {"types": ["assign"]}
        if name == "local_alertatemprana_save_predictions":
            return {"runid": len(self.calls), "predictions": len(kw["predictions"]),
                    "flagged": sum(p["flagged"] for p in kw["predictions"]), "notified": 0}
        return {}


def request(monkeypatch, tmp_path, d: Canonico, day: int = 70):
    monkeypatch.setattr(servicio.moodle, "extract_course", lambda c, cid, **kw: (d, {}))
    monkeypatch.setattr(config, "ROOT", tmp_path)
    c = Cliente()
    start = 1767225600  # 2026-01-01
    course = {"id": CID, "fullname": "Prueba", "startdate": start, "enddate": start + 100 * 86400}
    r = servicio.process_course(c, paquete(), course, start + day * 86400 + 3600, [{"id": 1, "reason": "profesor", "userid": 5}],
                                check_grades=False)
    return r, c


def test_request_with_less_than_90_percent_does_not_predict(monkeypatch, tmp_path):
    r, c = request(monkeypatch, tmp_path, curso(sin_nota=2))  # 8 de 10
    assert not r["publicadas"]
    closed = [kw for name, kw in c.calls if name == "local_alertatemprana_complete_requests"]
    assert "tiene 8 de 10 notas (80 %). Faltan 2" in closed[0]["message"]


def test_request_with_90_percent_predicts_without_counting_missing_grades(monkeypatch, tmp_path):
    r, c = request(monkeypatch, tmp_path, curso(sin_nota=1))  # 9 de 10
    assert [p["ancla"] for p in r["publicadas"]] == [2]
    saved = next(kw for name, kw in c.calls if name == "local_alertatemprana_save_predictions")
    calc = {p["userid"]: json.loads(p["calculations"]) for p in saved["predictions"]}
    # El estudiante 1 (5 y 5, la segunda sin nota): su nota media es la de la tarea 1, no baja por el 0
    assert calc[1]["valores"]["nota_media"] == 5 and calc[1]["valores"]["ultima_nota"] == 5
    assert calc[1]["valores"]["escala"] == {"tipo": "2-5", "max": 5}


def test_contributions_are_relative_to_the_course_average(monkeypatch, tmp_path):
    """La suma de los aportes de un estudiante es su logit menos el del estudiante promedio del curso."""
    d = curso(sin_nota=0)
    pq = paquete()
    rows = variables.build(d, at=variables.moment(variables.evaluations(d, 70).iloc[-1], 70))
    m = pq.cuts[str(rows["cut"].iloc[0])]
    calc = [json.loads(x) for x in servicio.calculations(pq, rows)]
    X = rows[m.features].to_numpy(dtype=float)
    logit = lambda x: ((x - m.model.mean) / m.model.scale * m.model.coef).sum(axis=-1) + m.model.intercept  # noqa: E731
    for c, x in zip(calc, X):
        assert sum(v["aporte"] for v in c["variables"]) == pytest.approx(logit(x) - logit(X.mean(axis=0)), abs=1e-5)
    assert calc[0]["referencia"] == "promedio_del_curso"
