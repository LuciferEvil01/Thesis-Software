"""Capturas del informe para la tesis (Cap. 3, sección 3.4), como PDF.

Requisitos: laboratorio arrancado (`make up`), curso de demostración con una predicción publicada
(`make demo` con el servicio matriculado y `make demo-notas2`), Chromium, chromedriver y Selenium.

Uso:
    python3 scripts/capturas_tesis.py CURSO_ID PREDICCION_DETALLE USUARIO_DETALLE [SALIDA]

Lista: seis filas repartidas de la primera a la última de la lista completa (no consecutivas),
sin la casilla, la columna «Estado» ni las acciones de respuesta a la alerta (aceptar, no aplicable,
marcado incorrectamente), que la tesis no describe. Detalle: la página de la
predicción de un estudiante. Petición (D6-07): la parte superior del informe, con el botón «Calcular
predicciones ahora», las evaluaciones que se analizan y el historial. Actividad (D6-07): el informe
de actividad de Moodle del estudiante del detalle, que el informe enlaza en cada fila. Se ocultan la
cabecera, los cajones y el pie de Moodle.
"""
import io
import os
import sys
import time
from pathlib import Path

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

BASE = "http://localhost:8100"
CSS_COMUN = """
nav.navbar, #page-header, .drawer, .drawer-toggles, footer, #page-footer, .secondary-navigation,
.activity-header, .breadcrumb, #topofscroll > .header-actions-container, .btn-footer-popover,
.moodle-has-zindex .popover-region, [data-region="footer-container-popover"] { display: none !important; }
#page, #page.drawers { margin: 0 !important; padding: 0 !important; }
#topofscroll { margin-top: 0 !important; }
body { background: #fff !important; }
"""


def driver():
    o = webdriver.ChromeOptions()
    o.binary_location = "/usr/bin/chromium"
    for a in ("--headless=new", "--no-sandbox", "--lang=es", "--hide-scrollbars"):
        o.add_argument(a)
    d = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=o)
    d.set_page_load_timeout(300)
    ancho(d, 1300)
    return d


def ancho(d, px):
    """Ventana de `px` píxeles CSS con escala 2 (unos 200 ppp al ancho de la página)."""
    d.execute_cdp_cmd("Emulation.setDeviceMetricsOverride",
                      {"width": px, "height": 1400, "deviceScaleFactor": 2, "mobile": False})


def login(d, user, password):
    d.get(f"{BASE}/login/index.php")
    d.find_element(By.ID, "username").send_keys(user)
    d.find_element(By.ID, "password").send_keys(password)
    d.find_element(By.ID, "loginbtn").click()


def css(d, text):
    d.execute_script("var s=document.createElement('style');s.textContent=arguments[0];"
                     "document.head.appendChild(s);", text)


def guardar(d, elemento, salida):
    d.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)  # que el estilo añadido termine de recolocar la página
    png = elemento.screenshot_as_png
    img = Image.open(io.BytesIO(png)).convert("RGB")
    img.save(salida, "PDF", resolution=200.0)
    return img.size


def main():
    curso, detalle, usuario = sys.argv[1], sys.argv[2], sys.argv[3]
    salida = Path(sys.argv[4] if len(sys.argv) > 4 else "capturas")
    salida.mkdir(parents=True, exist_ok=True)
    password = os.environ.get("MOODLE_DEMO_PASSWORD", "Demo-Alerta-2026!")
    d = driver()
    try:
        login(d, "docente.demo", password)
        d.get(f"{BASE}/local/alertatemprana/index.php?id={curso}&all=1")
        tablas = d.find_elements(By.CSS_SELECTOR, "form table.generaltable")
        tabla = tablas[0]
        filas = tabla.find_elements(By.CSS_SELECTOR, "tbody tr")
        n = len(filas)
        elegidas = sorted({round(i * (n - 1) / 5) for i in range(6)})
        d.execute_script(
            "const filas=arguments[0].querySelectorAll('tbody tr');"
            "filas.forEach((f,i)=>{if(!arguments[1].includes(i)) f.style.display='none';});",
            tabla, elegidas)
        css(d, CSS_COMUN + """
form table.generaltable .c0, form table.generaltable .c7 { display: none !important; }
a[href*="action=fixed"], a[href*="action=notapplicable"], a[href*="action=incorrectlyflagged"]
  { display: none !important; }
""")
        d.execute_script("arguments[0].scrollIntoView();", tabla)
        print("lista:", n, "filas; elegidas", elegidas, guardar(d, tabla, salida / "informe_lista.pdf"))

        ancho(d, 1000)
        d.get(f"{BASE}/local/alertatemprana/prediction.php?id={detalle}")
        css(d, CSS_COMUN + ".btn, .singlebutton { display: none !important; }")
        region = d.find_element(By.CSS_SELECTOR, "#region-main")
        print("detalle:", guardar(d, region, salida / "informe_detalle.pdf"))

        # Petición: el botón y las evaluaciones que se analizan; nada de lo que sigue
        ancho(d, 760)
        d.get(f"{BASE}/local/alertatemprana/index.php?id={curso}")
        css(d, CSS_COMUN)
        d.execute_script(
            "let x=document.querySelector('#region-main p.small.mb-3').nextElementSibling;"
            "while(x){x.style.display='none'; x=x.nextElementSibling;}")
        region = d.find_element(By.CSS_SELECTOR, "#region-main")
        print("petición:", guardar(d, region, salida / "informe_peticion.pdf"))

        # Actividad: el informe de actividad de Moodle (report/outline) del mismo estudiante
        # (las ocho primeras páginas con vistas y todas las tareas; sin el botón «Atrás» ni los de
        # mensajería)
        ancho(d, 1000)
        d.get(f"{BASE}/report/outline/user.php?id={usuario}&course={curso}&mode=outline")
        css(d, CSS_COMUN + "[role=main] > div.mb-3:first-of-type, .header-button-group { display: none !important; }")
        d.execute_script(
            "let n=0;"
            "document.querySelectorAll('#region-main .section tr').forEach(r=>{"
            "  const c=r.querySelectorAll('td'); const vistas=c.length>3 && c[3].textContent.trim()!=='-';"
            "  const tarea=!!r.querySelector('a[href*=\"/mod/assign/\"]');"
            "  if(tarea) return; if(!vistas || n>=8) r.style.display='none'; else n++;});"
            "document.querySelectorAll('#region-main .section').forEach(s=>{"
            "  if(![...s.querySelectorAll('tr')].some(r=>r.style.display!=='none')) s.style.display='none';});")
        region = d.find_element(By.CSS_SELECTOR, "#region-main")
        print("actividad:", usuario, guardar(d, region, salida / "actividad_estudiante.pdf"))
    finally:
        d.quit()


if __name__ == "__main__":
    main()
