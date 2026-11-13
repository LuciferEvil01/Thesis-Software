# Operación y paso a otro Moodle (EVEA)

## Piezas

| Pieza | Dónde corre | Qué hace |
|---|---|---|
| Plugin `local_alertatemprana` | dentro de Moodle | agrega la actividad del registro; deja una solicitud en la cola cuando se califica a un estudiante o cuando el profesor pulsa «Calcular predicciones ahora»; guarda predicciones y acciones, avisa a los profesores, muestra el informe |
| Usuario `alerta_servicio` | Moodle | identidad del sistema; solo usa REST y entra en los cursos que los profesores le abren |
| Sistema `alerta` (Python) | un servidor con acceso a Moodle | cada 5 minutos: lee la cola, y en cada curso con solicitudes extrae, comprueba si hay una tarea completa o una petición del profesor, predice y publica (PLAN.md, P12) |
| Modelo | `modelos/` | paquete activo (`ACTIVO`); v2 = modelo final de la tesis con el umbral del Cap. 2 (proporción de desaprobados por corte, P13); v1 = el mismo con el umbral F2 anterior |

## Instalación en otro Moodle

Requisitos: Moodle 5.0 o posterior, permiso de administrador para instalar un plugin, y un servidor
con Python 3.11 o posterior que llegue a Moodle por HTTP(S).

1. **Plugin.** Copiar `moodle/local/alertatemprana` a `public/local/alertatemprana` (Moodle 5.1 o
   posterior) o a `local/alertatemprana` (Moodle 5.0), y completar la actualización desde
   *Administración del sitio → Notificaciones*. También se puede comprimir la carpeta e instalarla
   desde *Instalar plugins*.
2. **Acceso.** En el servidor de Moodle:
   ```bash
   php public/local/alertatemprana/cli/setup.php
   ```
   Crea (o actualiza) el usuario `alerta_servicio`, su rol de sitio (solo REST), el servicio externo
   `alerta_connector` con sus 19 funciones y el token. Muestra dos líneas, `MOODLE_URL=` y
   `MOODLE_TOKEN=`, que van al archivo `.env` del sistema. Es idempotente.
3. **Sistema.** En el servidor del sistema:
   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -e .
   cp .env.example .env    # y añadir MOODLE_URL y MOODLE_TOKEN del paso 2
   .venv/bin/python -m alerta cursos   # comprobación: lista los cursos abiertos al servicio (al principio, ninguno)
   ```
   La carpeta `modelos/` viaja con el código. `Thesis-Training/` y OULAD solo hacen falta para las pruebas
   y la validación, no para operar.
4. **Escala de las notas** (P16). Mientras no haya grupo de referencia, las notas se convierten con
   valores fijos (3, 4 y 5 → 50, 70 y 90; el 2 → la media de los suspensos del entrenamiento). En
   cuanto la plataforma tenga al menos dos cursos cerrados calificados en la misma escala, se crea el
   grupo de referencia (el servicio debe estar matriculado en ellos):
   ```bash
   .venv/bin/python -m alerta escala referencia CURSO1 CURSO2 …
   ```
   Queda en `data/escala/referencia.json` y se usa desde la siguiente predicción.
5. **Cron**: la cola cada 5 minutos y, como red de seguridad, un barrido diario de todos los cursos
   (por si alguna solicitud se perdiera):
   ```
   */5 * * * *  cd /ruta/Thesis-Software && .venv/bin/python -m alerta ejecutar >> data/servicio.log 2>&1
   0 6 * * *    cd /ruta/Thesis-Software && .venv/bin/python -m alerta ejecutar --todos >> data/servicio.log 2>&1
   ```
   Una pasada sin solicitudes no hace nada ni escribe en el registro.

## Lo que hace cada profesor

En su curso: *Participantes → Matricular usuarios →* **Servicio Alerta temprana**, con el rol
**Profesor sin permiso de edición**. Requisitos del curso:
- fecha de inicio y de fin;
- tareas (`assign`) calificables con fecha de entrega, porque las predicciones toman como
  referencia la última tarea calificada. Una evaluación presencial (un examen) se registra como una
  tarea sin entregas en línea: está completa cuando todos los estudiantes tienen nota (P17);
- en las tareas calificadas en puntos, conviene fijar la «calificación para aprobar» del ítem; si no,
  se toma el 60 % de la máxima (P16).

Desde entonces:
- cada vez que termina de calificar una tarea (todas las entregas recibidas con nota), recibe una
  predicción nueva con un aviso y un correo;
- en *Más → Alerta temprana* tiene el informe, el historial de predicciones y el botón **Calcular
  predicciones ahora**, que predice con las notas publicadas hasta ese momento (sin correo). Si
  todavía no hay ninguna tarea con notas, el informe se lo indica; si la tarea más reciente con notas
  tiene menos del 90 % de ellas, le dice cuántas faltan y le pide completarlas (P17).

## Qué se guarda y dónde

| Dato | Dónde |
|---|---|
| Publicaciones, predicciones (con sus variables), acciones de los profesores y solicitudes | tablas `local_alertatemprana_run`, `_pred`, `_act` y `_req` de Moodle; se borran con el curso |
| Copia de cada publicación | `data/ejecuciones/<curso>/<publicación>/` |
| Registro de ejecuciones del servicio | `data/servicio/ejecuciones.jsonl` (una línea por pasada con trabajo) |
| Acciones de los profesores, para analizarlas | `local_alertatemprana_get_actions` (WS) |
| Grupo de referencia de la conversión de las notas | `data/escala/referencia.json` (P16) |

## Cambios habituales

| Cambio | Cómo |
|---|---|
| Otro modelo | registrar un paquete nuevo en `modelos/` y `python -m alerta modelo activar vN` (se vuelve atrás igual) |
| Otra traducción de las notas a 0–100 | una clase con `a_100(nota, ítem)` y `ALERTA_CALIFICACION=modulo:Clase` en `.env` (PLAN.md, P8 y P16; por defecto, `alerta.calificacion:Equipercentil`) |
| Actualizar el plugin en un Moodle donde ya estaba | copiar la carpeta, completar la actualización y repetir `cli/setup.php` (añade al servicio las funciones nuevas, como `get_gradeitems` en la 0.5) |
| Contar también los cuestionarios en la nota media | `types={"assign", "quiz"}` en `alerta.servicio.process_course` (por curso, cuando se decida cómo lo elige el profesor, P4) |
| Actividad sin el plugin (registro exportado) | `python -m alerta extraer CURSO --registro archivo.csv` (fuente C) |

## Limitaciones conocidas

- La exportación y el borrado de datos personales a petición del usuario (API de privacidad de
  Moodle) aún no están implementados; el plugin solo declara qué datos guarda.
- La predicción automática se hace una vez por tarea: corregir después una nota de esa tarea no
  genera otra predicción automática (el profesor puede pedirla con el botón).
- El modelo tiene un ajuste por cada corte de la tesis (25 %, 50 % y última tarea, en torno al 75 %).
  Cada tarea recibe el del corte más próximo (fronteras en el 37,5 y el 62,5 % del curso, P18); en
  la tesis, los tres ajustes ordenan igual en cualquier posición, pero esos momentos intermedios no
  se evaluaron con sus propios umbrales.
- Cada solicitud de notas implica extraer el curso completo (unos 25 s en un curso de 365
  estudiantes). Con muchos cursos calificando a la vez habría que repartir la cola.
- El modelo se entrenó con OULAD. Ver los riesgos de transferencia en PLAN.md.
