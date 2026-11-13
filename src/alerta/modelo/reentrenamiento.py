"""Reentrenamiento periódico con los cursos archivados (PLAN.md, P7).

Se ejecuta de forma programada (por ejemplo, cada semana). Solo hace algo cuando el archivo tiene
algún periodo lectivo que el modelo activo (el «campeón») no ha visto:

  1. Calcula las variables de todos los cursos archivados y les une la etiqueta.
  2. Reserva el periodo más reciente. Entrena un «aspirante» con la especificación del campeón y los
     demás periodos, y compara a los dos en el periodo reservado, que ninguno ha visto.
  3. Si el aspirante no es peor que el campeón en ningún corte (regla fijada de antemano, en
     `Politica`), entrena la versión nueva con todos los periodos, la registra y, si la política lo
     permite, la activa. Si no, deja el campeón y lo anota.
  4. Guarda un informe en `modelos/informes/`.

La especificación (variables, hiperparámetros, regla del umbral) no cambia al reentrenar; ver
`alerta.modelo.entrenamiento`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from alerta import variables
from alerta.archivo import Archivo
from alerta.modelo.entrenamiento import TARGET, evaluate, train
from alerta.modelo.registro import Registro, now_iso


@dataclass
class Politica:
    min_filas: int = 200  # filas mínimas por corte en el periodo reservado para que la comparación valga
    max_caida: float = 0.01  # el aspirante no puede perder más que esto de ROC-AUC en ningún corte
    activar: bool = True  # activar la versión nueva si pasa la regla; si no, queda registrada y ya


def dataset(archivo: Archivo) -> pd.DataFrame:
    """Variables + `at_risk` + `period` de todos los cursos archivados."""
    meta = archivo.meta()
    parts = []
    for types, group in meta.groupby(meta["types"].map(tuple)):
        d, labels = archivo.load(group["course_id"].tolist())
        feats = variables.build(d, types=set(types))
        parts.append(feats.merge(labels[["course_id", "student_id", TARGET]], on=["course_id", "student_id"]))
    df = pd.concat(parts, ignore_index=True)
    return df.merge(meta[["course_id", "period"]], on="course_id")


def retrain(archivo: Archivo, registro: Registro, politica: Politica = Politica()) -> dict:
    champion = registro.active()
    meta = archivo.meta()
    order = meta.groupby("period")["period_start"].min().sort_values()
    new = [p for p in order.index if p not in set(champion.meta.get("periodos", []))]
    report = {"fecha": now_iso(), "campeon": champion.version, "politica": asdict(politica),
              "periodos_archivo": order.index.tolist(), "periodos_nuevos": new}

    if not new:
        report["decision"] = "sin datos nuevos"
        return report
    df = dataset(archivo)
    holdout = order.index[-1]
    train_df, test_df = df[df["period"] != holdout], df[df["period"] == holdout]
    report["reservado"] = holdout
    small = {c: int(n) for c, n in test_df.groupby(test_df["cut"].astype(str)).size().items() if n < politica.min_filas}
    if small or train_df["period"].nunique() < 2:
        report["decision"] = f"datos insuficientes (cortes con pocas filas: {small})"
        registro.save_report(report)
        return report

    challenger = train(train_df, champion.spec, "aspirante")
    report["comparacion"] = {"campeon": evaluate(champion, test_df), "aspirante": evaluate(challenger, test_df)}
    drops = {cut: report["comparacion"]["campeon"][cut]["roc_auc"] - m["roc_auc"]
             for cut, m in report["comparacion"]["aspirante"].items()}
    report["caida_roc_auc"] = drops
    if any(v > politica.max_caida for v in drops.values()):
        report["decision"] = "se mantiene el campeón: el aspirante es peor en algún corte"
        registro.save_report(report)
        return report

    version = registro.next_version()
    paquete = train(df, champion.spec, version,
                    meta={"origen": f"reentrenamiento desde {champion.version}", "fuente": "archivo",
                          "cursos": sorted(df["course_id"].unique().tolist()),
                          "comparacion": report["comparacion"]},
                    escala=champion.escala)  # las notas del archivo ya están en la escala del modelo
    registro.register(paquete)
    report["nueva_version"] = version
    if politica.activar:
        registro.activate(version, f"reentrenamiento: periodos nuevos {new}; reservado {holdout}")
        report["decision"] = f"activada {version}"
    else:
        report["decision"] = f"registrada {version}, pendiente de activar"
    registro.save_report(report)
    return report
