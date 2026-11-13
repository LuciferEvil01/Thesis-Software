"""Variables del modelo a partir del esquema canónico.

Es `Proposal/scripts/build_dataset.py` sobre el esquema canónico, con una sola generalización
(PLAN.md, P4): las variables de evaluación se calculan sobre un conjunto configurable de tipos de
módulo (por defecto, solo `assign`). Con OULAD y el conjunto por defecto reproduce exactamente
`Proposal/data/processed/dataset.parquet` (tests/test_variables_oulad.py).

Una fila por estudiante, curso y corte. En cada corte solo se usa la información con día <= día de
corte, y se excluye a quien ya se había dado de baja.

Cortes anclados a las TMA: en cada curso, la TMA de fecha más próxima al 25 % del curso (first),
la más próxima al 50 % (mid) y la última (last). Día de corte = fecha de esa TMA + 14 días. Son los
cortes de la tesis (entrenamiento y validación). El servicio predice en un momento cualquiera
(PLAN.md, P12 y P18): `evaluations` y `moment` eligen el ancla y el ajuste del modelo, y `build(at=…)`
calcula las variables en ese momento.

Evaluaciones de un corte: los ítems de los tipos incluidos con fecha <= la de la TMA ancla.
Entregado = entregado como muy tarde el día de corte; la nota de lo no entregado cuenta 0.
`last_score` es la nota de la TMA ancla (no existe en el primer corte).
"""

from collections.abc import Iterable

import numpy as np
import pandas as pd

from alerta.canonico import Canonico

CUTS = ["first", "mid", "last"]
TMA_TARGETS = {"first": 25, "mid": 50}  # % del curso al que se acercan los dos primeros cortes
GRADE_LAG = 14  # días entre la fecha de una TMA y la publicación de su nota
RECENT_DAYS = 28  # ventana de recent_clicks_28d
DEFAULT_TYPES = frozenset({"assign"})

KEYS = ["course_id", "student_id"]
ROW = KEYS + ["cut"]
CLASS = ["course_id", "cut"]  # clase = curso y corte: los percentiles se calculan dentro de ella

VLE = ["total_clicks", "active_days", "days_since_last_activity", "recent_clicks_28d",
       "n_unique_sites", "clicks_per_active_day", "pre_course_clicks"]
GRADES = ["mean_score_with_zeros", "last_score"]
FEATURES = ([f"{c}_pct" for c in VLE] + [f"{c}_raw" for c in GRADES] + [f"{c}_pct" for c in GRADES]
            + ["submission_rate", "repeated_course"])


def cuts(d: Canonico) -> pd.DataFrame:
    """TMA ancla y día de corte de cada curso y corte."""
    tmas = d.assessments[d.assessments["is_tma"].astype(bool) & d.assessments["due_day"].notna()]
    tmas = tmas.merge(d.courses[["course_id", "length_days"]], on="course_id")
    tmas = tmas.sort_values(["course_id", "due_day"])
    tmas["k"] = tmas.groupby("course_id").cumcount() + 1
    tmas["pct"] = tmas["due_day"] / tmas["length_days"] * 100
    rows = []
    for course, g in tmas.groupby("course_id", sort=False):
        anchors = {cut: g.iloc[(g["pct"] - target).abs().argmin()] for cut, target in TMA_TARGETS.items()}
        anchors["last"] = g.iloc[-1]
        for cut, a in anchors.items():
            due = int(a["due_day"])
            rows.append((course, cut, a["item_id"], int(a["k"]), due, due + GRADE_LAG))
    return pd.DataFrame(rows, columns=["course_id", "cut", "anchor_item", "anchor_k", "anchor_due",
                                       "cutoff_day"])


def vle_features(activity: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """Actividad hasta el día de corte, incluida la anterior al inicio del curso."""
    v = activity.merge(base[ROW + ["cutoff_day"]], on=KEYS)
    v = v[v["day"] <= v["cutoff_day"]]
    g = v.groupby(ROW)
    f = pd.DataFrame({
        "total_clicks": g["events"].sum(),
        "active_days": g["day"].nunique(),
        "n_unique_sites": g["site_id"].nunique(),
        "days_since_last_activity": g["cutoff_day"].first() - g["day"].max(),
    })
    f["clicks_per_active_day"] = f["total_clicks"] / f["active_days"]
    f["pre_course_clicks"] = v[v["day"] < 0].groupby(ROW)["events"].sum()
    f["recent_clicks_28d"] = v[v["day"] > v["cutoff_day"] - RECENT_DAYS].groupby(ROW)["events"].sum()

    # Sin actividad registrada: 0 eventos; la recencia queda vacía (no está definida)
    counts = [c for c in f.columns if c != "days_since_last_activity"]
    f = base[ROW].merge(f.reset_index(), on=ROW, how="left")
    f[counts] = f[counts].fillna(0)
    return f


def _graded(rows: pd.DataFrame) -> pd.DataFrame:
    """Añade `submitted` y `score0` (nota visible el día de corte; 0 si no se entregó a tiempo)."""
    rows = rows.copy()
    rows["submitted"] = rows["submitted_day"] <= rows["cutoff_day"]
    published = rows["graded_day"].isna() | (rows["graded_day"] <= rows["cutoff_day"])
    rows["score0"] = rows["score"].where(published).where(rows["submitted"], 0)
    return rows


def assessment_features(d: Canonico, base: pd.DataFrame, types: Iterable[str]) -> pd.DataFrame:
    grades = d.grades[["course_id", "item_id", "student_id", "submitted_day", "score", "graded_day"]]
    items = d.assessments[d.assessments["module_type"].isin(set(types)) & d.assessments["due_day"].notna()]
    due = base[ROW + ["cutoff_day", "anchor_due"]].merge(items[["course_id", "item_id", "due_day"]],
                                                          on="course_id")
    due = _graded(due[due["due_day"] <= due["anchor_due"]]
                  .merge(grades, on=["course_id", "item_id", "student_id"], how="left"))
    g = due.groupby(ROW)
    f = pd.DataFrame({"submission_rate": g["submitted"].mean(),
                      "mean_score_with_zeros": g["score0"].mean()})

    anchor = _graded(base[ROW + ["cutoff_day", "anchor_item"]]
                     .merge(grades, left_on=["course_id", "anchor_item", "student_id"],
                            right_on=["course_id", "item_id", "student_id"], how="left"))
    f["last_score"] = anchor.set_index(ROW)["score0"]
    f = base[ROW].merge(f.reset_index(), on=ROW, how="left")

    # Entregas sin nota: la nota media se calcula con las demás y la del corte toma la nota media
    # del propio estudiante. Si no queda ninguna nota, la media toma la mediana de su clase.
    class_median = f.groupby([f[c] for c in CLASS])["mean_score_with_zeros"].transform("median")
    f["mean_score_with_zeros"] = f["mean_score_with_zeros"].fillna(class_median)
    f["last_score"] = f["last_score"].fillna(f["mean_score_with_zeros"])
    f.loc[f["cut"] == "first", "last_score"] = np.nan  # no se usa en el primer corte
    return f


def class_percentile(df: pd.DataFrame, col: str, invert: bool = False) -> pd.Series:
    """Percentil dentro de la clase: rango promedio en los empates; 0,5 si la clase no varía."""
    # Redondeo a 9 decimales: el ruido de coma flotante (p. ej., una nota convertida de ida y vuelta
    # entre escalas, 78/100·100 = 78.00000000000001) no debe romper empates entre estudiantes.
    x = df[col].astype(float).round(9)
    if invert:  # más días sin actividad = menos actividad; sin ningún evento = el peor percentil
        x = -x.fillna(np.inf)
    by_class = x.groupby([df[c] for c in CLASS])
    pct = by_class.rank(pct=True, method="average")
    return pct.mask(by_class.transform("nunique") <= 1, 0.5)


# Posición de cada corte en el curso: las TMA más próximas al 25 y al 50 % y la última, que en OULAD
# cae en torno al 75 %. Cada tarea recibe el ajuste del corte más próximo (P18): las fronteras son
# los puntos medios.
CUT_POSITIONS = {"first": 25, "mid": 50, "last": 75}
MID_BOUNDARY = (CUT_POSITIONS["first"] + CUT_POSITIONS["mid"]) / 2  # 37,5 % del curso
LAST_BOUNDARY = (CUT_POSITIONS["mid"] + CUT_POSITIONS["last"]) / 2  # 62,5 % del curso
MIN_GRADED = 0.9  # proporción mínima de notas de la evaluación de referencia para predecir a petición (P17)


def evaluations(d: Canonico, day: int, types: Iterable[str] = DEFAULT_TYPES) -> pd.DataFrame:
    """Estado de cada evaluación de cada curso en el día `day` del curso (P12, P17 y P20).

    Entran las TMA (`is_tma`: tareas calificables con fecha) y las evaluaciones con fecha de los demás
    tipos que el profesor eligió para su curso (`types`). Las TMA disparan la predicción automática;
    la petición del profesor toma la más reciente con notas, sea del tipo que sea (P20).
    Solo cuentan los estudiantes con matrícula activa ese día.
    - `entregas`: las entregas recibidas hasta ese día; en una tarea sin entregas en línea, todos
      los estudiantes activos (la extracción los da por presentados en su fecha).
    - `calificadas`: cuántas de ellas tienen la nota publicada; `proporcion` = calificadas / entregas.
    - `con_notas`: su fecha ya pasó y tiene al menos una nota publicada.
    - `completa`: su fecha ya pasó, recibió alguna entrega y todas tienen la nota publicada.
    - `k`: número de TMA hasta ella, incluida (en una TMA, su orden).
    - `ajuste`: el ajuste del modelo que se aplica si es el ancla: el del corte más próximo según su
      posición en el curso (`first` antes del 37,5 %, `mid` hasta el 62,5 % y `last` después) y
      siempre `last` en la última TMA.
    """
    a = d.assessments
    others = a["module_type"].isin(set(types) - {"assign"})
    items = a[(a["is_tma"].astype(bool) | others) & a["due_day"].notna()].copy()
    items["is_tma"] = items["is_tma"].astype(bool)
    items = items.merge(d.courses[["course_id", "length_days"]], on="course_id").sort_values(["course_id", "due_day"])
    items["k"] = items["is_tma"].astype(int).groupby(items["course_id"]).cumsum()
    items["pct"] = items["due_day"] / items["length_days"] * 100
    last_tma = items[items["is_tma"]].groupby("course_id")["due_day"].max()
    items["ultima"] = items["is_tma"] & (items["due_day"] == items["course_id"].map(last_tma))

    active = d.students[~(d.students["unregistered_day"] <= day)][["course_id", "student_id"]]
    g = d.grades[d.grades["submitted_day"] <= day].merge(active, on=["course_id", "student_id"])
    g["publicada"] = g["score"].notna() & (g["graded_day"].isna() | (g["graded_day"] <= day))
    st = g.groupby(["course_id", "item_id"]).agg(entregas=("student_id", "size"), calificadas=("publicada", "sum"))
    items = items.merge(st.reset_index(), on=["course_id", "item_id"], how="left")
    items[["entregas", "calificadas"]] = items[["entregas", "calificadas"]].fillna(0).astype(int)

    past = items["due_day"] <= day
    items["con_notas"] = past & (items["calificadas"] > 0)
    items["completa"] = items["con_notas"] & (items["calificadas"] == items["entregas"])
    items["proporcion"] = (items["calificadas"] / items["entregas"].where(items["entregas"] > 0)).fillna(0.0)
    items["ajuste"] = np.select([items["ultima"] | (items["pct"] >= LAST_BOUNDARY), items["pct"] >= MID_BOUNDARY],
                                ["last", "mid"], "first")
    return items[["course_id", "item_id", "module_type", "is_tma", "k", "due_day", "pct", "ultima", "entregas",
                  "calificadas", "proporcion", "con_notas", "completa", "ajuste"]].reset_index(drop=True)


def moment(evaluation: pd.Series, day: int) -> pd.DataFrame:
    """El «corte» de una predicción en un momento cualquiera (P12): el ancla es `evaluation` y la
    actividad se cuenta hasta `day`. Tiene la forma de `cuts` para que `build` lo use igual."""
    return pd.DataFrame([{"course_id": evaluation["course_id"], "cut": evaluation["ajuste"],
                          "anchor_item": evaluation["item_id"], "anchor_k": int(evaluation["k"]),
                          "anchor_due": int(evaluation["due_day"]), "cutoff_day": int(day)}])


def build(d: Canonico, types: Iterable[str] = DEFAULT_TYPES, at: pd.DataFrame | None = None) -> pd.DataFrame:
    """Una fila por estudiante, curso y corte, con los valores originales y las variables.

    Sin `at`, los tres cortes de la tesis (`cuts`); con `at`, los momentos indicados (`moment`).
    """
    d.validate()
    base = d.students.merge(cuts(d) if at is None else at, on="course_id")
    base = base[~(base["unregistered_day"] <= base["cutoff_day"])].reset_index(drop=True)
    base["repeated_course"] = base["repeated"]

    df = (base[ROW + ["anchor_item", "anchor_k", "cutoff_day", "repeated_course"]]
          .merge(vle_features(d.activity, base), on=ROW)
          .merge(assessment_features(d, base, types), on=ROW))

    for c in VLE:
        df[f"{c}_pct"] = class_percentile(df, c, invert=(c == "days_since_last_activity"))
    for c in GRADES:
        df[f"{c}_raw"] = df[c] / 100
        df[f"{c}_pct"] = class_percentile(df, c)
    df.loc[df["cut"] == "first", "last_score_pct"] = np.nan

    df["cut"] = pd.Categorical(df["cut"], CUTS, ordered=True)
    return df.sort_values(CLASS + ["student_id"]).reset_index(drop=True)
