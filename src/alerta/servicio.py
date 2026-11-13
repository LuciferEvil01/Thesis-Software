"""El servicio: predice cuando una evaluación queda completa o cuando el profesor lo pide (PLAN.md, P12).

Moodle deja las solicitudes en una cola (`local_alertatemprana_req`): una de tipo `notas` cada vez que
se califica a un estudiante (observador de `user_graded`) y una de tipo `profesor` cuando el profesor
pulsa «Calcular predicciones ahora». Cada pocos minutos (cron), el servicio lee la cola y, en cada
curso con solicitudes (o en todos, con `todos=True`):

  1. Extrae el curso y calcula el estado de sus evaluaciones en el día de hoy (o el de `as_of`).
  2. Notas: si hay una tarea completa (todas sus entregas con nota) más reciente que el ancla de la
     última predicción automática, predice con ella como ancla, publica y avisa a los profesores. Si
     no, no hace nada. Solo las tareas disparan la predicción automática (P20).
  3. Profesor: predice con la evaluación más reciente que tenga alguna nota, de cualquiera de los
     tipos que el profesor eligió para su curso (P20), y publica sin correo.
     Si ninguna tiene notas, responde que todavía no se puede predecir; si esa evaluación tiene menos
     del 90 % de sus notas, no predice y le pide completar la calificación (P17).
  4. Marca las solicitudes como atendidas, con el resultado que verá el profesor en el informe.

El ajuste del modelo (first, mid o last) se elige por la posición del ancla en el curso
(`variables.evaluations`, P18). Los tipos de evaluación que entran en las variables los elige el
profesor en su curso (`local_alertatemprana_get_course_config`; por defecto, solo las tareas). Las notas se convierten a la escala del modelo con la escala de
entrenamiento del paquete (`alerta.calificacion`, P16). Cada predicción deja también una copia local
en `data/ejecuciones/`.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from alerta import calificacion, config, variables
from alerta.calificacion import ItemCalificable
from alerta.fuentes import moodle
from alerta.modelo.paquete import Logistica, Paquete
from alerta.modelo.registro import Registro
from alerta.moodle import cursos
from alerta.moodle.cliente import Cliente

DAY = 86400
GRADES, TEACHER = "notas", "profesor"
NO_GRADES = "Todavía no hay ninguna evaluación con notas publicadas, así que no se puede predecir."
NO_DATES = "El curso necesita fechas de inicio y de fin y tareas con fecha de entrega."
PARTIAL = ("La evaluación más reciente con notas tiene {graded} de {total} notas ({pct} %). Faltan {missing}: "
           "complete la calificación para predecir (hace falta al menos el {min} %). La predicción "
           "anterior, si la hay, sigue disponible en el informe.")


def course_types(c: Cliente, courseid: int) -> frozenset[str]:
    """Tipos de evaluación que el profesor eligió para su curso (P20); las tareas siempre entran."""
    return frozenset(c.call("local_alertatemprana_get_course_config", courseid=courseid)["types"]) | {"assign"}


def course_scale(d, rows: pd.DataFrame, types) -> tuple[pd.DataFrame, dict]:
    """Nota media y nota de la tarea de referencia de cada estudiante en la escala del curso.

    Como la nota media del modelo, pero con las notas de Moodle: la tarea no entregada cuenta como la
    nota más baja (2 en la escala 2–5) y la entregada sin nota no cuenta. Si las tareas no comparten
    escala, en porcentaje de la máxima. Sin las notas de Moodle (p. ej., OULAD), en la escala 0–100.
    """
    keys = ["course_id", "student_id"]
    a = d.assessments
    if "grade" not in d.grades.columns or "grademin" not in a.columns:
        out = rows[keys].assign(nota_media=rows["mean_score_with_zeros"], ultima_nota=rows["last_score"])
        return out, {"tipo": "0-100", "max": 100}
    r = rows.iloc[0]
    items = a[a["module_type"].isin(set(types)) & (a["due_day"] <= r["anchor_due"]) & (a["course_id"] == r["course_id"])]
    info = {i.item_id: ItemCalificable(i.module_type, i.grademin, i.grademax, i.gradepass) for i in items.itertuples()}
    scales = {(it.escala, it.grademax) for it in info.values()}
    if len(scales) == 1 and next(iter(scales))[0] == calificacion.SCALE_25:
        scale, factor = {"tipo": "2-5", "max": 5}, {k: 1.0 for k in info}
    elif len(scales) == 1:
        scale, factor = {"tipo": "puntos", "max": next(iter(scales))[1]}, {k: 1.0 for k in info}
    else:
        scale, factor = {"tipo": "porcentaje", "max": 100}, {k: 100 / it.grademax for k, it in info.items()}
    g = (rows[keys + ["cutoff_day"]].merge(items[["course_id", "item_id"]], on="course_id")
         .merge(d.grades, on=keys + ["item_id"], how="left"))
    submitted = g["submitted_day"] <= g["cutoff_day"]
    published = g["grade"].notna() & (g["graded_day"].isna() | (g["graded_day"] <= g["cutoff_day"]))
    lowest = g["item_id"].map({k: it.minima for k, it in info.items()})
    g["v"] = g["grade"].where(published).where(submitted, lowest) * g["item_id"].map(factor)
    out = rows[keys + ["anchor_item"]].merge(g.groupby(keys)["v"].mean().rename("nota_media").reset_index(), on=keys, how="left")
    last = g[g["item_id"] == r["anchor_item"]].set_index(keys)["v"].rename("ultima_nota")
    out = out.merge(last.reset_index(), on=keys, how="left")
    out["ultima_nota"] = out["ultima_nota"].fillna(out["nota_media"])
    return out[keys + ["nota_media", "ultima_nota"]], scale


def calculations(paquete: Paquete, rows: pd.DataFrame, shown: pd.DataFrame | None = None,
                 scale: dict | None = None) -> list[str]:
    """JSON por estudiante: valores legibles, variables del modelo y su aporte a la probabilidad.

    El aporte de cada variable se mide respecto al estudiante promedio del curso (P15): coeficiente ·
    (valor − media del curso) / escala del entrenamiento. Su suma es la diferencia entre el logit del
    estudiante y el del estudiante promedio del curso. `shown`: las notas en la escala del curso
    (`course_scale`).
    """
    cut = str(rows["cut"].iloc[0])
    m = paquete.cuts[cut]
    contrib = (m.model.contributions(rows[m.features], center=rows[m.features].to_numpy(dtype=float).mean(axis=0))
               if isinstance(m.model, Logistica) else np.zeros((len(rows), len(m.features))))
    if shown is None:
        shown = rows[["course_id", "student_id"]].assign(nota_media=rows["mean_score_with_zeros"],
                                                         ultima_nota=rows["last_score"])
        scale = {"tipo": "0-100", "max": 100}
    shown = rows[["course_id", "student_id"]].merge(shown, on=["course_id", "student_id"], how="left")
    in_course = {"mean_score_with_zeros_raw": "nota_media", "last_score_raw": "ultima_nota"}
    out = []
    for (_, r), ctr, (_, sh) in zip(rows.iterrows(), contrib, shown.iterrows()):
        valores = {"nota_media": round(float(sh["nota_media"]), 2), "escala": scale,
                   "nota_media_modelo": round(float(r["mean_score_with_zeros"]), 2),
                   "tasa_entrega": round(float(r["submission_rate"]), 4),
                   "eventos_28d": int(r["recent_clicks_28d"]),
                   "pct_nota_media": round(float(r["mean_score_with_zeros_pct"]), 4),
                   "pct_actividad_reciente": round(float(r["recent_clicks_28d_pct"]), 4),
                   "dias_sin_actividad": None if pd.isna(r["days_since_last_activity"]) else int(r["days_since_last_activity"])}
        if cut != "first":
            valores["ultima_nota"] = round(float(sh["ultima_nota"]), 2)
        variables_ = []
        for f, a in zip(m.features, ctr):
            v = {"nombre": f, "valor": round(float(r[f]), 6), "aporte": round(float(a), 6)}
            if f in in_course:
                v["curso"] = round(float(sh[in_course[f]]), 2)
            variables_.append(v)
        out.append(json.dumps({"corte": cut, "dia_de_corte": int(r["cutoff_day"]), "referencia": "promedio_del_curso",
                               "valores": valores, "variables": variables_}, ensure_ascii=False))
    return out


def _latest(evals: pd.DataFrame, column: str) -> pd.Series | None:
    ready = evals[evals[column]].sort_values("due_day")
    return None if ready.empty else ready.iloc[-1]


def _publish(c: Cliente, paquete: Paquete, course: dict, d, evals: pd.DataFrame, anchor: pd.Series, day: int,
             as_of: int, reason: str, notify: bool, requestedby: int, types, report: dict) -> dict:
    at = variables.moment(anchor, day)
    rows = variables.build(d, types=types, at=at)
    pred = paquete.predict(rows)
    shown, scale = course_scale(d, pred.assign(anchor_due=int(at["anchor_due"].iloc[0])), types)
    info = {"fecha_ejecucion": datetime.fromtimestamp(as_of, timezone.utc).isoformat(), "motivo": reason,
            "ancla": int(anchor["item_id"]), "ajuste": anchor["ajuste"], "extraccion": report,
            "tipos_evaluacion": sorted(types), "evaluaciones": evals.drop(columns="course_id").to_dict("records")}
    response = c.call("local_alertatemprana_save_predictions", courseid=course["id"], cut=anchor["ajuste"],
                      modelversion=paquete.version, threshold=float(pred["umbral"].iloc[0]), cutoffday=day,
                      timeend=int(course["startdate"] + (day + 1) * DAY), anchorcmid=int(anchor["item_id"]),
                      reason=reason, requestedby=requestedby, notify=notify,
                      info=json.dumps(info, ensure_ascii=False, default=str),
                      predictions=[{"userid": int(r.student_id), "score": float(r.prob), "flagged": bool(r.en_riesgo),
                                    "calculations": calc}
                                   for r, calc in zip(pred.itertuples(), calculations(paquete, pred, shown, scale))])
    out = config.ROOT / "data" / "ejecuciones" / str(course["id"]) / str(response["runid"])
    out.mkdir(parents=True, exist_ok=True)
    pred.to_parquet(out / "predicciones.parquet", index=False)
    (out / "informe.json").write_text(json.dumps(info | {"respuesta": response}, indent=1, ensure_ascii=False, default=str))
    return response


def process_course(c: Cliente, paquete: Paquete, course: dict, as_of: int, requests: list[dict] | None = None,
                   check_grades: bool = True, notify: bool = True, types=None) -> dict:
    """Atiende un curso. `requests`: sus solicitudes pendientes; `check_grades`: buscar evaluaciones
    completas aunque no haya solicitudes de tipo `notas` (revisión completa); `types`: tipos de
    evaluación (si no se dan, los que eligió el profesor en el curso)."""
    requests = requests or []
    by_reason = defaultdict(list)
    for r in requests:
        by_reason[r["reason"]].append(r)
    check_grades = check_grades or bool(by_reason[GRADES])
    result = {"curso": course["id"], "nombre": course["fullname"], "decisiones": [], "publicadas": []}

    def close(reason: str, message: str) -> None:
        if by_reason[reason]:
            c.call("local_alertatemprana_complete_requests", courseid=course["id"],
                   ids=[r["id"] for r in by_reason[reason]], message=message)

    if not course.get("startdate") or not course.get("enddate") or course["enddate"] <= course["startdate"]:
        for reason in (GRADES, TEACHER):
            close(reason, NO_DATES)
        return result | {"decision": NO_DATES}
    day = math.floor((as_of - course["startdate"]) / DAY)
    result["dia_del_curso"] = day
    d, report = moodle.extract_course(c, course["id"], calificacion=calificacion.cargar(escala=paquete.escala))
    types = course_types(c, course["id"]) if types is None else frozenset(types) | {"assign"}
    evals = variables.evaluations(d, day, types)
    if not evals["is_tma"].any():
        for reason in (GRADES, TEACHER):
            close(reason, NO_DATES)
        return result | {"decision": NO_DATES}
    result["evaluaciones"] = {int(e.item_id): ("completa" if e.completa else "con notas" if e.con_notas else "sin notas")
                              for e in evals.itertuples()}

    auto_published = False
    if check_grades:
        runs = c.call("local_alertatemprana_get_runs", courseid=course["id"])
        last_auto = next((r["anchorcmid"] for r in reversed(runs) if r["reason"] == GRADES), None)
        anchor = _latest(evals[evals["is_tma"]], "completa")
        if anchor is None:
            msg = "ninguna evaluación completa"
        elif int(anchor["item_id"]) == last_auto:
            msg = f"sin evaluaciones completas nuevas (la última, {int(anchor['item_id'])}, ya se usó)"
        else:
            resp = _publish(c, paquete, course, d, evals, anchor, day, as_of, GRADES, notify, 0, types, report)
            auto_published = True
            msg = f"publicada por notas completas (ancla {int(anchor['item_id'])}, ajuste {anchor['ajuste']})"
            result["publicadas"].append({"motivo": GRADES, "ancla": int(anchor["item_id"]), "ajuste": anchor["ajuste"],
                                         "estudiantes": resp["predictions"], "en_riesgo": resp["flagged"],
                                         "profesores_avisados": resp["notified"]})
        result["decisiones"].append(msg)
        close(GRADES, msg)

    if by_reason[TEACHER]:
        anchor = _latest(evals, "con_notas")
        if auto_published:
            msg = "Predicción publicada con las notas completas de la última tarea."
        elif anchor is None:
            msg = NO_GRADES
        elif anchor["proporcion"] < variables.MIN_GRADED:
            msg = PARTIAL.format(graded=int(anchor["calificadas"]), total=int(anchor["entregas"]),
                                 pct=int(anchor["proporcion"] * 100),
                                 missing=int(anchor["entregas"] - anchor["calificadas"]),
                                 min=int(variables.MIN_GRADED * 100))
        else:
            resp = _publish(c, paquete, course, d, evals, anchor, day, as_of, TEACHER, False,
                            int(by_reason[TEACHER][0].get("userid") or 0), types, report)
            msg = "Predicción publicada."
            result["publicadas"].append({"motivo": TEACHER, "ancla": int(anchor["item_id"]), "ajuste": anchor["ajuste"],
                                         "estudiantes": resp["predictions"], "en_riesgo": resp["flagged"],
                                         "profesores_avisados": resp["notified"]})
        result["decisiones"].append(f"profesor: {msg}")
        close(TEACHER, msg)

    return result | {"decision": "; ".join(result["decisiones"]) or "nada que hacer"}


def run(as_of: datetime | None = None, courses: list[int] | None = None, everything: bool = False,
        notify: bool = True, log=print) -> list[dict]:
    """Una pasada del servicio: los cursos con solicitudes pendientes (o todos, con `everything`)."""
    c = Cliente.desde_config()
    paquete = Registro(config.MODELOS_DIR).active()
    ts = int((as_of or datetime.now(timezone.utc)).timestamp())
    pending = defaultdict(list)
    for r in c.call("local_alertatemprana_get_requests"):
        pending[r["courseid"]].append(r)
    results = []
    for course in cursos.discover(c):
        if courses and course["id"] not in courses:
            continue
        if not everything and not pending[course["id"]]:
            continue
        try:
            r = process_course(c, paquete, course, ts, pending[course["id"]], check_grades=everything, notify=notify)
        except Exception as e:  # un curso con problemas no detiene a los demás
            r = {"curso": course["id"], "nombre": course["fullname"], "decision": f"error: {e}"}
        log(f"{r['curso']:>5} {r['nombre']}: {r['decision']}")
        results.append(r)
    # Registro de ejecuciones (una línea JSON por pasada con trabajo) para revisar la operación
    if results:
        path = config.ROOT / "data" / "servicio" / "ejecuciones.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps({"ejecutada": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "fecha_simulada": None if as_of is None else as_of.isoformat(),
                                "modelo": paquete.version, "cursos": results}, ensure_ascii=False, default=str) + "\n")
    return results
