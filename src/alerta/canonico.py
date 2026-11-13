"""Esquema canónico: los datos de un Moodle (o de OULAD) con la semántica de OULAD (PLAN.md, P2).

Cinco tablas. Los días se cuentan desde el inicio del curso (día 0 = inicio; negativos = antes).

    courses      course_id, length_days, start_ts
    students     course_id, student_id, unregistered_day, repeated
    assessments  course_id, item_id, module_type, due_day, grademax, is_tma
    grades       course_id, item_id, student_id, submitted_day, score, graded_day
    activity     course_id, student_id, day, site_id, events

- `start_ts` (marca de tiempo Unix del inicio) solo existe en Moodle; en OULAD queda vacío.
- `unregistered_day`: día de la baja; vacío si sigue matriculado.
- `repeated`: 1 si ya cursó la asignatura antes; vacío si no se sabe (no lo usa el modelo final).
- `module_type`: tipo de módulo de Moodle (`assign`, `quiz`, …). Las TMA (`is_tma`) son las
  tareas calificables con fecha de entrega (P4).
- `score`: nota de 0 a 100 (ya normalizada con `grademax`); vacía si se entregó sin nota.
- `graded_day`: día en que se publicó la nota; vacío si no se sabe (OULAD). Una nota publicada
  después del día de corte no se ve en ese corte.
"""

from dataclasses import dataclass

import pandas as pd

COLUMNS = {
    "courses": ["course_id", "length_days", "start_ts"],
    "students": ["course_id", "student_id", "unregistered_day", "repeated"],
    "assessments": ["course_id", "item_id", "module_type", "due_day", "grademax", "is_tma"],
    "grades": ["course_id", "item_id", "student_id", "submitted_day", "score", "graded_day"],
    "activity": ["course_id", "student_id", "day", "site_id", "events"],
}
UNIQUE = {
    "courses": ["course_id"],
    "students": ["course_id", "student_id"],
    "assessments": ["course_id", "item_id"],
    "grades": ["course_id", "item_id", "student_id"],
}


@dataclass
class Canonico:
    courses: pd.DataFrame
    students: pd.DataFrame
    assessments: pd.DataFrame
    grades: pd.DataFrame
    activity: pd.DataFrame

    def validate(self) -> "Canonico":
        """Comprueba columnas, claves únicas y rangos; devuelve self para encadenar."""
        for name, cols in COLUMNS.items():
            df = getattr(self, name)
            missing = set(cols) - set(df.columns)
            if missing:
                raise ValueError(f"{name}: faltan columnas {sorted(missing)}")
            key = UNIQUE.get(name)
            if key and df.duplicated(key).any():
                raise ValueError(f"{name}: claves {key} repetidas")
        if (self.courses["length_days"] <= 0).any():
            raise ValueError("courses: length_days debe ser positivo")
        score = self.grades["score"].dropna()
        if ((score < 0) | (score > 100)).any():
            raise ValueError("grades: score fuera de [0, 100]")
        if (self.activity["events"] < 0).any():
            raise ValueError("activity: events negativo")
        return self
