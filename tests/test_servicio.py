"""P12: el servicio predice cuando una evaluación queda completa o cuando el profesor lo pide.

Curso inventado de `curso_sintetico` en el Moodle local (110 días; TMA en los días 20, 50 y 90). La
TMA del día 20 nunca queda completa (una entrega sin nota; el día 30 tiene 4 de 5 notas, así que la
petición del profesor no predice, P17); la del 50 queda completa el día 70 y la del 90, el día 95.
Se simula la fecha de ejecución.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).parent))
from curso_sintetico import CID, curso  # noqa: E402

from alerta import calificacion, config, servicio, variables  # noqa: E402
from alerta.fuentes import moodle  # noqa: E402
from alerta.modelo.registro import Registro  # noqa: E402
from alerta.moodle import cursos, sembrar  # noqa: E402
from alerta.moodle.cliente import Cliente  # noqa: E402
from alerta.servicio import NO_GRADES, process_course  # noqa: E402

FEW_GRADES = "tiene 4 de 5 notas (80 %). Faltan 1"

pytestmark = pytest.mark.moodle
START = 1767225600  # 2026-01-01
IDNUMBER = "ALERTA-PRUEBA-F6"
DAY = 86400


def php(code: str) -> str:
    lab = config.ROOT / "infra" / "moodle" / "scripts" / "lab.sh"
    out = subprocess.run([str(lab), "php", "-r", f'define("CLI_SCRIPT",1); require "/var/www/html/config.php"; {code}'],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def at(day: float) -> int:
    return int(START + day * DAY + 12 * 3600)


VALIDATION = "alerta.calificacion:ProporcionalOULAD"


@pytest.fixture(scope="module", autouse=True)
def validation_grading():
    """El curso sintético tiene notas de 0 a 100: la lógica del servicio se prueba con la conversión de
    validación, sin el requisito de la escala de 2 a 5 (P21), que tiene su propia prueba."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ALERTA_CALIFICACION", VALIDATION)
        yield


@pytest.fixture(scope="module")
def setup():
    try:
        client = Cliente.desde_config()
        client.site_info()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Moodle local no disponible ({e}); ejecuta `make up`")
    seeded = sembrar.seed(sembrar.spec_from_canonico(curso(), CID, START, IDNUMBER, "Curso de prueba F6"))
    course = next(c for c in cursos.discover(client) if c["id"] == seeded["courseid"])
    teacher = int(php(f'global $DB; echo $DB->get_field("user", "id", ["username" => "prof_{IDNUMBER.lower()}"]);'))
    return client, Registro(config.MODELOS_DIR).active(), course, teacher


def pending(client, course) -> list[dict]:
    return [r for r in client.call("local_alertatemprana_get_requests") if r["courseid"] == course["id"]]


def notifications(teacher: int) -> int:
    return int(php(f'global $DB; echo $DB->count_records("notifications", ["useridto" => {teacher}, '
                   f'"component" => "local_alertatemprana"]);'))


def teacher_request(course, teacher) -> None:
    php(f'\\local_alertatemprana\\requests::enqueue({course["id"]}, "profesor", {teacher});')


@pytest.fixture(scope="module")
def sequence(setup):
    """Lo que pasa a lo largo del curso, en orden. Al sembrar, Moodle ya calificó: hay una solicitud
    de notas pendiente."""
    client, paquete, course, teacher = setup
    out = {"sembrado": pending(client, course), "avisos_antes": notifications(teacher)}
    out[30] = process_course(client, paquete, course, at(30), pending(client, course))
    teacher_request(course, teacher)
    out["peticion"] = pending(client, course)
    out["30p"] = process_course(client, paquete, course, at(30), pending(client, course), check_grades=False)
    for day in (70, 71):
        out[day] = process_course(client, paquete, course, at(day))
    teacher_request(course, teacher)
    out["75p"] = process_course(client, paquete, course, at(75), pending(client, course), check_grades=False)
    out[100] = process_course(client, paquete, course, at(100))
    return out


def test_grading_leaves_a_request(sequence):
    assert {r["reason"] for r in sequence["sembrado"]} == {"notas"}


def test_no_complete_evaluation_no_prediction(sequence):
    assert sequence[30]["decision"] == "ninguna evaluación completa" and not sequence[30]["publicadas"]


def test_request_with_too_few_grades_does_not_predict(setup, sequence):
    """Con menos del 90 % de las notas de la tarea más reciente, se pide completar la calificación."""
    client, _, course, _ = setup
    assert [r["reason"] for r in sequence["peticion"]] == ["profesor"]
    assert not sequence["30p"]["publicadas"] and FEW_GRADES in sequence["30p"]["decision"]
    msg = php(f'global $DB; $r = $DB->get_records("local_alertatemprana_req", ["courseid" => {course["id"]}, '
              f'"reason" => "profesor"], "id ASC", "*", 0, 1); echo reset($r)->message;')
    assert FEW_GRADES in msg


def test_teacher_request_predicts_without_email(setup, sequence):
    client, paquete, course, _ = setup
    p = sequence["75p"]["publicadas"]
    assert len(p) == 1 and p[0]["motivo"] == "profesor" and p[0]["ancla"] and p[0]["ajuste"] == "mid"
    assert p[0]["estudiantes"] == 5 and p[0]["profesores_avisados"] == 0
    # Mismo resultado que el cálculo local en ese momento
    d, _ = moodle.extract_course(client, course["id"], calificacion=calificacion.cargar(escala=paquete.escala))
    e = variables.evaluations(d, 75)
    anchor = e[e["con_notas"]].sort_values("due_day").iloc[-1]
    local = paquete.predict(variables.build(d, at=variables.moment(anchor, 75)))
    assert p[0]["en_riesgo"] == int(local["en_riesgo"].sum())


def test_complete_evaluation_predicts_and_notifies(sequence):
    p = sequence[70]["publicadas"]
    assert len(p) == 1 and p[0]["motivo"] == "notas" and p[0]["ajuste"] == "mid" and p[0]["profesores_avisados"] == 1


def test_same_evaluation_is_not_published_twice(sequence):
    assert not sequence[71]["publicadas"] and sequence[71]["decision"].startswith("sin evaluaciones completas nuevas")


def test_last_evaluation_uses_last_adjustment(setup, sequence):
    client, _, course, _ = setup
    assert [p["ajuste"] for p in sequence[100]["publicadas"]] == ["last"]
    runs = client.call("local_alertatemprana_get_runs", courseid=course["id"])
    assert [(r["reason"], r["cut"]) for r in runs] == [("notas", "mid"), ("profesor", "mid"), ("notas", "last")]
    assert pending(client, course) == []


def test_saved_predictions_carry_explanations(setup, sequence):
    _, _, course, _ = setup
    raw = php(f'global $DB; echo json_encode(array_values($DB->get_records("local_alertatemprana_pred", '
              f'["courseid" => {course["id"]}], "id", "id, calculations")));')
    preds = json.loads(raw)
    assert len(preds) == 15  # 5 estudiantes × 3 predicciones
    calc = json.loads(preds[-1]["calculations"])
    assert calc["corte"] == "last" and {v["nombre"] for v in calc["variables"]} == {
        "mean_score_with_zeros_raw", "last_score_raw", "mean_score_with_zeros_pct", "recent_clicks_28d_pct"}


def test_teacher_notified_only_for_complete_grades(setup, sequence):
    _, _, _, teacher = setup
    assert notifications(teacher) - sequence["avisos_antes"] == 2  # días 70 y 100, no la petición


def test_no_grades_answer(setup):
    """Una petición del profesor sin ninguna tarea con notas se cierra explicándolo."""
    client, paquete, course, teacher = setup
    teacher_request(course, teacher)
    r = process_course(client, paquete, course, at(5), pending(client, course), check_grades=False)
    assert not r["publicadas"] and r["decision"] == f"profesor: {NO_GRADES}"
    msg = php(f'global $DB; $r = $DB->get_records("local_alertatemprana_req", ["courseid" => {course["id"]}, '
              f'"reason" => "profesor"], "id DESC", "*", 0, 1); echo reset($r)->message;')
    assert msg == NO_GRADES


def test_teacher_sees_report_and_requests(setup, sequence):
    client, _, course, _ = setup
    env = {**dotenv_values(config.ROOT / ".env.local")}
    s, base = requests.Session(), config.MOODLE_URL.rstrip("/")
    token = re.search(r'name="logintoken" value="([^"]+)"', s.get(f"{base}/login/index.php").text).group(1)
    s.post(f"{base}/login/index.php", data={"username": f"prof_{IDNUMBER}".lower(),
                                            "password": env.get("MOODLE_DEMO_PASSWORD", "Demo-Alerta-2026!"), "logintoken": token})
    page = s.get(f"{base}/local/alertatemprana/index.php", params={"id": course["id"], "all": 1})
    assert page.status_code == 200 and "Predicciones publicadas" in page.text and "Estudiante 1" in page.text
    assert "Calcular predicciones ahora" in page.text
    sesskey = re.search(r'"sesskey":"([^"]+)"', page.text).group(1)
    predid = re.search(r"prediction\.php\?id=(\d+)", page.text).group(1)
    assert s.get(f"{base}/local/alertatemprana/prediction.php", params={"id": predid}).status_code == 200
    s.get(f"{base}/local/alertatemprana/action.php", params={"predictionid": predid, "action": "fixed", "sesskey": sesskey})
    actions = client.call("local_alertatemprana_get_actions", courseid=course["id"])
    assert {a["actionname"] for a in actions} >= {"predictiondetails", "fixed"}
    # El botón deja una solicitud del profesor
    s.post(f"{base}/local/alertatemprana/request.php", data={"id": course["id"], "sesskey": sesskey})
    assert [r["reason"] for r in pending(client, course)] == ["profesor"]


def test_tasks_not_graded_two_to_five_are_rejected(setup, monkeypatch):
    """P21: con la conversión de la institución, un curso cuyas tareas no se califican de 2 a 5 no se
    predice, y el profesor recibe el motivo."""
    client, paquete, _, _ = setup
    monkeypatch.delenv("ALERTA_CALIFICACION", raising=False)
    seeded = sembrar.seed(sembrar.spec_from_canonico(curso(), CID, START, IDNUMBER + "-ESCALA", "Curso en 0-100"))
    course = next(c for c in cursos.discover(client) if c["id"] == seeded["courseid"])
    r = process_course(client, paquete, course, at(75))
    assert r["decision"] == servicio.OUT_OF_SCALE and not r["publicadas"]
