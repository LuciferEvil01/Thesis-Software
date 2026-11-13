"""Curso canónico inventado para probar la extracción de Moodle (viaje de ida y vuelta)."""

import numpy as np
import pandas as pd

from alerta.canonico import Canonico

NAN = np.nan
CID = "SINT"


def curso() -> Canonico:
    students = [1, 2, 3, 4, 5, 6]
    items = [(10, "assign", 20, 100), (11, "assign", 50, 10), (12, "assign", 90, 100), (20, "quiz", 35, 20)]
    grades = [
        # item, estudiante, entregado, nota 0-100, publicada
        (10, 1, 18, 80, 25), (11, 1, 49, 60, 60), (12, 1, 88, 90, 95), (20, 1, 30, 75, 30),
        (10, 2, 19, 55, 25), (11, 2, 52, 40, 60),                       (20, 2, 34, 50, 34),
        (10, 3, 20, NAN, NAN), (11, 3, 45, 100, 70),                                         # entregada sin nota; nota tardía
        (10, 4, 25, 30, 28),                                                                  # entrega tardía
        (10, 5, 15, 95, 20), (11, 5, 48, 85, 55), (12, 5, 80, 70, 92),
        (10, 6, 10, 20, 20),                                                                  # se da de baja
    ]
    rng = np.random.default_rng(0)
    activity = [(s, day, site, int(rng.integers(1, 6)))
                for s in students for day in range(-5, 100, 7) for site in (0, 101, 102, 103)
                if rng.random() < 0.5 + 0.08 * s - (0.4 if s == 2 and day > 40 else 0)]
    return Canonico(
        courses=pd.DataFrame({"course_id": [CID], "length_days": [110], "start_ts": [NAN]}),
        students=pd.DataFrame({"course_id": CID, "student_id": students,
                               "unregistered_day": [NAN] * 5 + [30.0], "repeated": NAN}),
        assessments=pd.DataFrame([(CID, i, t, d, m, t == "assign") for i, t, d, m in items],
                                 columns=["course_id", "item_id", "module_type", "due_day", "grademax", "is_tma"]),
        grades=pd.DataFrame([(CID, *g) for g in grades],
                            columns=["course_id", "item_id", "student_id", "submitted_day", "score", "graded_day"]),
        activity=pd.DataFrame([(CID, *a) for a in activity],
                              columns=["course_id", "student_id", "day", "site_id", "events"]),
    ).validate()
