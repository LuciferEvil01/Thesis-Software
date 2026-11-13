"""Demostración en el Moodle local con un curso real de OULAD (AAA 2014J), avanzando el tiempo a mano.

    python -m alerta demo preparar [--con-servicio]   crea el curso (unos 4 minutos)
    python -m alerta demo notas K                      la docente termina de calificar la tarea K
    python -m alerta demo atender                      el servicio atiende las peticiones del botón
    python -m alerta demo estado                       qué hay publicado y adónde ir

El curso tiene los 365 estudiantes de AAA 2014J con sus notas, entregas y cada clic convertido en un
evento del registro. Los nombres son ficticios. Las tareas se califican de 2 a 5, como en la UH
(P16): cada nota de OULAD pasa a su categoría (2 por debajo de 40, el suspenso de OULAD; 3 de 40 a
59; 4 de 60 a 79; 5 de 80 en adelante). Los cursos anteriores de la plataforma, que forman el grupo
de referencia de la conversión, son los cursos de OULAD de los periodos de entrenamiento,
calificados igual. El curso empieza el 1 de octubre de 2014 y tiene
cinco tareas. OULAD no guarda cuándo se publicó cada nota: la demostración supone que la docente
termina de calificar cada tarea 14 días después de su fecha de entrega (o al recibir una entrega
tardía), como en la tesis.

`notas K` hace lo que en un curso real hace el paso del tiempo: avanza la fecha simulada hasta el
día en que la tarea K queda calificada, desmatricula a quien se había dado de baja hasta ese día y
ejecuta el servicio en esa fecha, que publica la predicción y avisa a la docente (PLAN.md, P12).
`atender` ejecuta el servicio en la fecha simulada actual para atender las peticiones que la docente
haya hecho con el botón «Calcular predicciones ahora» del informe.

Sin `--con-servicio`, el servicio no ve el curso hasta que la docente lo matricula, como en la
realidad (es un buen momento de la demostración).
"""

from __future__ import annotations

import json
import zlib
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from alerta import calificacion, config, servicio, variables
from alerta.canonico import Canonico
from alerta.fuentes import oulad
from alerta.modelo.importar import PERIODOS_TESIS
from alerta.moodle import sembrar
from alerta.moodle.cliente import Cliente, MoodleError
from alerta.validacion import START_2014J

COURSE = "AAA_2014J"
IDNUMBER = "DEMO-ALERTA"
FULLNAME = "Demostración · Alerta temprana (curso AAA de OULAD, 2014J)"
TEACHER = {"username": "docente.demo", "firstname": "Docente", "lastname": "Demostración"}
STATE = config.ROOT / "data" / "demo" / "estado.json"
DAY = 86400

NOMBRES = ["Ana", "Carlos", "Laura", "Javier", "María", "Daniel", "Lucía", "Pablo", "Elena", "Andrés", "Sofía",
           "Miguel", "Claudia", "Alejandro", "Paula", "Diego", "Carmen", "Raúl", "Isabel", "Jorge", "Marta", "Luis",
           "Beatriz", "Fernando", "Rosa", "Alberto", "Patricia", "Ernesto", "Yanet", "Osmani", "Dayana", "Yoel"]
APELLIDOS = ["García", "Rodríguez", "González", "Fernández", "López", "Martínez", "Sánchez", "Pérez", "Gómez",
             "Martín", "Jiménez", "Ruiz", "Hernández", "Díaz", "Moreno", "Álvarez", "Romero", "Alonso", "Gutiérrez",
             "Navarro", "Torres", "Domínguez", "Vázquez", "Ramos", "Gil", "Ramírez", "Serrano", "Blanco", "Suárez",
             "Molina", "Castro", "Ortiz", "Rubio", "Marín", "Sanz", "Iglesias", "Medina", "Garrido", "Cortés"]


def _name(student_id: int) -> tuple[str, str]:
    h = zlib.crc32(str(student_id).encode())
    return NOMBRES[h % len(NOMBRES)], f"{APELLIDOS[(h >> 8) % len(APELLIDOS)]} {APELLIDOS[(h >> 16) % len(APELLIDOS)]}"


BANDS_25 = [-1, 40, 60, 80, 101]  # 2 | 3 | 4 | 5 sobre las notas de OULAD (0–100)


def to_25(score: pd.Series) -> pd.Series:
    """Nota de OULAD → categoría de la escala 2–5."""
    return pd.cut(score, BANDS_25, right=False, labels=[2, 3, 4, 5]).astype(float)


def grade_25(d: Canonico, course_id: str) -> None:
    """Califica de 2 a 5 las TMA de un curso: nota máxima 5 y `score` = categoría / 5 · 100, de modo que
    el sembrador (nota = score · máxima / 100) deja en Moodle la categoría."""
    tma = d.assessments["is_tma"].astype(bool) & (d.assessments["course_id"] == course_id)
    d.assessments.loc[tma, "grademax"] = 5.0
    rows = d.grades["course_id"].eq(course_id) & d.grades["item_id"].isin(d.assessments.loc[tma, "item_id"])
    d.grades.loc[rows, "score"] = to_25(d.grades.loc[rows, "score"]) / 5 * 100


def reference_25(d: Canonico) -> dict:
    """Grupo de referencia: las TMA de los cursos de OULAD de los periodos de entrenamiento, de 2 a 5."""
    tma = d.assessments[d.assessments["is_tma"].astype(bool)][["course_id", "item_id"]]
    g = d.grades.merge(tma, on=["course_id", "item_id"])
    g = g[g["course_id"].str.split("_").str[-1].isin(PERIODOS_TESIS)]
    return calificacion.referencia(pd.DataFrame({"course_id": g["course_id"], "grade": to_25(g["score"]),
                                                 "grademin": 0.0, "grademax": 5.0, "gradepass": 0.0}))


def _date(day: int) -> str:
    return datetime.fromtimestamp(START_2014J + day * DAY, timezone.utc).strftime("%d/%m/%Y")


def prepare(with_service: bool = False, log=print) -> dict:
    d, _ = oulad.load(config.OULAD_DIR)
    path = calificacion.guardar_referencia(reference_25(d))
    log(f"Grupo de referencia de la escala 2–5 (cursos de OULAD de {', '.join(PERIODOS_TESIS)}): {path}")
    grade_25(d, COURSE)
    # Fecha de publicación de las notas: 14 días después de la entrega de la tarea, o el día de la
    # entrega si llega más tarde (OULAD no la tiene)
    due = d.assessments.set_index(["course_id", "item_id"])["due_day"]
    lag = due.reindex(pd.MultiIndex.from_frame(d.grades[["course_id", "item_id"]])).to_numpy() + variables.GRADE_LAG
    d.grades["graded_day"] = np.fmax(lag, d.grades["submitted_day"].to_numpy())
    spec = sembrar.spec_from_canonico(d, COURSE, START_2014J, IDNUMBER, FULLNAME,
                                      service_role="teacher" if with_service else None, unenrol_withdrawn=False)
    spec["teacher"] = TEACHER
    for s in spec["students"]:
        s["firstname"], s["lastname"] = _name(int(s["username"][1:]))
    log(f"Creando el curso en Moodle: {len(spec['students'])} estudiantes, "
        f"{sum(a['events'] for a in spec['activity'])} eventos… (unos 4 minutos)")
    seeded = sembrar.seed(spec)
    try:  # buzón de pruebas vacío: en la demostración solo deben verse los avisos de la alerta
        requests.delete(f"{config.MOODLE_URL}/_/mail/api/v1/messages", timeout=10)
    except requests.RequestException:
        pass
    tmas = d.assessments[(d.assessments["course_id"] == COURSE) & d.assessments["is_tma"]].sort_values("due_day")
    tasks = [{"tarea": k, "item": int(t.item_id), "entrega": int(t.due_day), "notas": int(t.due_day) + variables.GRADE_LAG}
             for k, t in enumerate(tmas.itertuples(), start=1)]
    students = d.students[(d.students["course_id"] == COURSE) & d.students["unregistered_day"].notna()]
    state = {"courseid": seeded["courseid"], "tareas": tasks, "dia": 0,
             "bajas": {f"e{r.student_id}": float(r.unregistered_day) for r in students.itertuples()}, "aplicadas": []}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1))
    log(f"Curso {seeded['courseid']} listo: {config.MOODLE_URL}/course/view.php?id={seeded['courseid']}")
    return state


def _load() -> dict:
    if not STATE.exists():
        raise SystemExit("Primero: python -m alerta demo preparar")
    return json.loads(STATE.read_text())


def _advance(state: dict, day: int, log) -> None:
    """Lleva la fecha simulada hasta `day` y desmatricula a quien se había dado de baja hasta entonces."""
    state["dia"] = max(state["dia"], day)
    withdraw = sorted(u for u, d in state["bajas"].items() if d <= state["dia"] and u not in state["aplicadas"])
    if withdraw:
        sembrar.unenrol(IDNUMBER, withdraw)
        state["aplicadas"] += withdraw
    STATE.write_text(json.dumps(state, indent=1))
    log(f"Día {state['dia']} del curso ({_date(state['dia'])}): {len(state['aplicadas'])} estudiantes "
        f"dados de baja hasta hoy.")


def _run(state: dict, everything: bool, log) -> list[dict]:
    as_of = datetime.fromtimestamp(START_2014J + state["dia"] * DAY + 12 * 3600, timezone.utc)
    results = servicio.run(as_of, [state["courseid"]], everything=everything, log=log)
    if everything and not results:
        log("El servicio no ve el curso: la docente debe matricular a «alerta_servicio» como "
            "profesor sin permiso de edición (Participantes → Matricular usuarios).")
    return results


def grades(k: int, log=print) -> list[dict]:
    """La docente termina de calificar la tarea `k`: el servicio predice y la avisa."""
    state = _load()
    task = next((t for t in state["tareas"] if t["tarea"] == k), None)
    if task is None:
        raise SystemExit(f"El curso tiene las tareas 1 a {len(state['tareas'])}")
    _advance(state, task["notas"], log)
    log(f"La docente ha terminado de calificar la tarea {k} (entrega el día {task['entrega']}).")
    return _run(state, everything=True, log=log)


def attend(log=print) -> list[dict]:
    """El servicio atiende las peticiones del botón en la fecha simulada actual."""
    state = _load()
    log(f"Día {state['dia']} del curso ({_date(state['dia'])}).")
    results = _run(state, everything=False, log=log)
    if not results:
        log("No hay peticiones pendientes: pulse «Calcular predicciones ahora» en el informe del curso.")
    return results


def status(log=print) -> None:
    state = _load()
    c = Cliente.desde_config()
    try:
        runs = c.call("local_alertatemprana_get_runs", courseid=state["courseid"])
        enrolled = True
    except MoodleError:  # el servicio todavía no está matriculado en el curso
        runs, enrolled = [], False
    base = config.MOODLE_URL
    log(f"Curso: {base}/course/view.php?id={state['courseid']}")
    log(f"Informe: {base}/local/alertatemprana/index.php?id={state['courseid']}")
    log(f"Correo (mailpit): {base}/_/mail/")
    log(f"Docente: {TEACHER['username']} · servicio matriculado en el curso: {'sí' if enrolled else 'todavía no'}")
    log(f"Fecha simulada: día {state['dia']} ({_date(state['dia'])})")
    for t in state["tareas"]:
        log(f"  tarea {t['tarea']}: entrega el día {t['entrega']:>3} ({_date(t['entrega'])}), "
            f"notas el día {t['notas']:>3} ({_date(t['notas'])})")
    for r in runs:
        log(f"  publicada ({r['reason']}, ajuste {r['cut']}, día {r['cutoffday']}): "
            f"{r['flagged']} de {r['predictions']} en riesgo")
