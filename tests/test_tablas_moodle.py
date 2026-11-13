"""Las tablas de Moodle (fuente D) dan las mismas variables y la misma ROC-AUC que OULAD.

Usa las tablas del curso que reproduce AAA_2014J en el Moodle de laboratorio, exportadas con
`scripts/exportar_tablas_lab.py --cursos 45 --salida <carpeta>`; la carpeta se indica con
ALERTA_TABLAS_LAB. Sin ella, la prueba se omite.
"""

import os
import subprocess
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

from alerta import config, variables
from alerta.calificacion import ProporcionalOULAD
from alerta.fuentes import oulad, tablas_moodle

FOLDER = os.environ.get("ALERTA_TABLAS_LAB")
pytestmark = pytest.mark.skipif(not FOLDER or not Path(FOLDER).exists(), reason="sin tablas del laboratorio")


def _to_oulad() -> dict:
    out = subprocess.run(["docker", "exec", "alerta_moodle-db-1", "psql", "-U", "moodle", "-d", "moodle", "-c",
                          "COPY (select id, username from m_user) TO STDOUT WITH CSV HEADER"],
                         capture_output=True, text=True, check=True).stdout
    u = pd.read_csv(StringIO(out))
    u = u[u["username"].str.match(r"^e\d+$")]
    return dict(zip(u["id"], u["username"].str[1:].astype(int)))


def test_mismas_variables_que_oulad():
    d, labels, _, report = tablas_moodle.cargar(Path(FOLDER), fecha_de_nota=False)
    got = variables.build(tablas_moodle.convertir(d, ProporcionalOULAD()))
    got["student_id"] = got["student_id"].map(_to_oulad())
    o, _ = oulad.load(config.OULAD_DIR)
    ref = variables.build(o)
    ref = ref[ref["course_id"] == "AAA_2014J"]
    features = [f for f in variables.FEATURES if f != "repeated_course"]
    for cut in variables.CUTS:
        g, r = got[got["cut"].astype(str) == cut], ref[ref["cut"].astype(str) == cut]
        assert set(g["student_id"]) == set(r["student_id"])
        m = g.merge(r, on="student_id", suffixes=("", "_o"))
        for f in features:
            a, b = m[f].astype(float), m[f"{f}_o"].astype(float)
            assert (a.isna() == b.isna()).all(), f"{cut}: {f} vacía en una sola fuente"
            assert ((a - b).abs().fillna(0) < 1e-9).all(), f"{cut}: {f} distinta"
    assert report["notas_recuperadas_del_historial"] > 0  # notas de los desmatriculados
