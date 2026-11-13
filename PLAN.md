# Thesis-Software · Plan

> `Proposal/` es la carpeta de trabajo del repositorio publicado como
> [Thesis-Training](https://github.com/LuciferEvil01/Thesis-Training).

Sistema de alerta temprana que aplica el modelo final de la tesis (sección 2.2, `Proposal/`) a
cursos de Moodle: extrae los datos de cada estudiante y curso, construye las variables, predice el
riesgo en cada corte y entrega la lista al profesor dentro de Moodle, imitando los *insights* de
Moodle Analytics.

- Primer destino: el Moodle 5.2.1 local (`SEGTI-Edu/infra/moodle`, Docker, PostgreSQL 17).
- Destino final: EVEA (UH). No se sabe nada de él todavía; todo lo que dependa del servidor va por
  configuración (URL, token, roles) y nada se acopla a la instalación local.

## Decisiones

Cada decisión lleva número y fecha. Si una cambia, se añade otra que lo diga; no se borra.

### P1 · 22-10-2026 · El modelo en producción

Los tres `Proposal/artifacts/final_<corte>.joblib` son la fuente de verdad. Cada uno es
`{model, features, C, threshold}`, con `model = StandardScaler → LogisticRegression (L2), C = 0,001`.

| Corte | Variables | Umbral (F2) |
|---|---|---|
| first | `mean_score_with_zeros_raw`, `mean_score_with_zeros_pct`, `recent_clicks_28d_pct` | 0,213 |
| mid | las 3 anteriores + `last_score_raw` | 0,235 |
| last | ídem | 0,263 |

Se empaqueta como un **paquete de modelo**: los joblib, un `modelo.json` con las medias, escalas,
coeficientes, intercepto, variables y umbral de cada corte, y un manifiesto (hash, versiones de
Python y sklearn, fecha, decisión E14). La predicción usa el `modelo.json`, que es portable,
auditable y no depende de pickle; un test comprueba que da las mismas probabilidades que el joblib.

### P2 · 22-10-2026 · Esquema canónico con la semántica de OULAD

La extracción traduce Moodle a unas tablas canónicas. Sobre ellas corre **el mismo código de
variables** para OULAD y para Moodle (refactor de `Proposal/scripts/build_dataset.py`):

| Tabla | Columnas | Equivale en OULAD |
|---|---|---|
| `courses` | course_id, start (timestamp), length_days | courses |
| `students` | course_id, student_id | studentInfo + studentRegistration |
| `assessments` | course_id, item_id, module_type, due_day, grademax, is_tma | assessments |
| `grades` | course_id, item_id, student_id, submitted_day, score_0_100, graded_day | studentAssessment |
| `activity` | course_id, student_id, day, site_id, events | studentVle |

Los días se cuentan desde el inicio del curso: `day = floor((t − startdate) / 86 400)`.

### P3 · 22-10-2026 · Actividad («clics»): fuentes A + C

Moodle no expone `logstore_standard_log` por web service. La tesis de Soler (UH, 2024) usó el
archivo de registros exportado. La actividad se obtiene a través de una interfaz con dos
implementaciones, que producen la misma tabla `activity`:

- **A · Plugin** `local_alertatemprana`: la función WS `get_activity(courseid, desde, hasta)` agrega
  los eventos de los estudiantes del curso por estudiante, día y módulo. Es automática y es la de la
  demostración.
- **C · Importación** del registro exportado desde la interfaz de Moodle (CSV o XLSX). Sirve en
  cualquier Moodle sin permisos especiales y es el respaldo para EVEA.

Solo cuentan los usuarios con rol de estudiante (fuera profesores y administrador, como en Soler).
El modelo usa el percentil dentro del curso, así que la equivalencia exacta entre «clic» de OULAD y
«evento» de Moodle es secundaria. La limitación se documenta.

### P4 · 22-10-2026 · TMA y evaluaciones incluidas

- **Las TMA (anclas de los cortes) son siempre las tareas (`assign`) calificables con fecha de
  entrega.** Ancla first = la de fecha más próxima al 25 % del curso; mid = al 50 %; last = la
  última. Día de corte = fecha de entrega del ancla + 14 días. Es igual que en OULAD.
- **Las variables de evaluación** (`mean_score_with_zeros`, `submission_rate`) se calculan sobre un
  **conjunto configurable de tipos de evaluación** de Moodle (`assign`, `quiz`, `workshop`,
  `lesson`, ítems manuales…) **por curso**.
  - Por defecto, solo `assign`.
  - Todo tipo debe poder incluirse.
  - Cómo lo decide el profesor se define más adelante.
- Un ítem entra en un corte si su fecha (`duedate`, `timeclose`, etc.) es ≤ la del ancla. Los
  ítems sin fecha no entran, y se informa.
- `last_score` es la nota del ancla, igual que en OULAD.
- Las notas salen del libro de calificaciones, que es genérico para todos los tipos
  (`gradereport_user_get_grade_items`: `itemmodule`, `graderaw`, `grademax`, `gradedatesubmitted`,
  `gradedategraded`). Se normalizan a 0–100.

### P5 · 22-10-2026 · Entrega al profesor: réplica de los insights de Moodle

Se reproduce el diseño de Moodle Analytics (`core_analytics`, `report_insights`) dentro de
`local_alertatemprana`, sin usar su motor, que entrena sus propios modelos y no admite nuestros
cortes ni los percentiles por curso:

- **Tablas** que imitan `analytics_predictions` y `analytics_prediction_actions`:
  - una predicción por estudiante y corte, con `prediction`, `predictionscore` (probabilidad),
    `calculations` (las variables, en JSON), `timestart`/`timeend`, corte, umbral y versión del
    modelo;
  - las acciones del profesor, con usuario, acción y fecha.
- **Notificación** con la Message API (proveedor propio): «Estudiantes en riesgo en el curso X» y
  un enlace al informe.
- **Informe del curso**: la lista ordenada por probabilidad y, por estudiante:
  - *Ver detalles* (las variables, con su valor y su percentil en la clase);
  - *Informe de actividad* (`report/outline/user.php`).
- **Acciones en lote**: *Enviar mensaje*, *Aceptar*, *No aplicable*, *Marcado incorrectamente*,
  *Útil* / *No útil*. Son la base del futuro mecanismo de aceptación de recomendaciones.
- **WS** para el sistema Python:
  - `save_predictions`: publica un lote y dispara la notificación;
  - `get_actions`: lee lo que hizo el profesor;
  - `get_course_config`: tipos de evaluación incluidos.

### P6 · 22-10-2026 · Cuándo se predice

Con la fecha de ejecución D (parámetro `--as-of` para simular el tiempo), un corte de un curso está
listo si D ≥ su día de corte. Se predice el último corte listo que aún no se haya publicado. No
entran los estudiantes cuya matrícula ya no está activa.

### P7 · 23-10-2026 · Modelo intercambiable y reentrenamiento periódico

**Modelo intercambiable.** El sistema solo conoce el **paquete** (`alerta.modelo.paquete`): una
carpeta con `manifest.json` que lleva la especificación de entrenamiento, los datos con que se
entrenó, las métricas y, por corte, las variables, el umbral y los parámetros. Hay dos tipos:
`logistica` (números en JSON, el de la tesis) y `sklearn` (joblib, para un modelo futuro no
lineal). El **registro** (`modelos/`) guarda las versiones, cuál está activa (`ACTIVO`) y el
historial de activaciones. Cambiar de modelo, o volver atrás, es activar otra versión; ningún otro
módulo cambia. v1 = el modelo final de la tesis (E14), importado de `Proposal/artifacts`.

**Reentrenamiento — extra, fuera del alcance de la tesis** (decidido por Jose el 23-10-2026). Queda
implementado y probado con OULAD, pero en la tesis solo se menciona como aclaración y trabajo
futuro, y no se integra en la operación (F7). Diseño (`alerta.modelo.reentrenamiento`, orden
`python -m alerta reentrenar`, pensada para cron):
- Los cursos cerrados se guardan en el **archivo** (`alerta.archivo`) con su esquema canónico
  completo y la etiqueta de cada estudiante. Se guardan los datos, no las variables, para poder
  recalcularlas si cambia su definición.
- El proceso solo actúa cuando el archivo tiene un periodo lectivo que el modelo activo no ha
  visto. Entonces:
  1. reserva el periodo más reciente;
  2. entrena un aspirante con los demás y lo compara con el campeón en el periodo reservado;
  3. si el aspirante no pierde más de 0,01 de ROC-AUC en ningún corte (regla fijada de antemano),
     entrena la versión nueva con todo, la registra y la activa;
  4. deja un informe.
- **Se reajusta la especificación, no se rehace la selección.** Las variables, C y la regla del
  umbral F2 no cambian. Cambiar la especificación exige repetir la validación anidada de la tesis
  y es una decisión manual, que produce un paquete nuevo.

**Correcciones a la idea inicial** (descargar el curso al terminar):
1. **El curso se archiva poco a poco, no al final.** Al terminar, Moodle ya no lista a quien se dio
   de baja (y las bajas son parte de «en riesgo»). Además, los registros se pueden purgar según la
   retención configurada y las notas se pueden recalificar. Cada ejecución periódica guarda una
   instantánea del curso abierto; al cerrarse, la última se pasa al archivo con las etiquetas.
2. **Hace falta definir la etiqueta en Moodle**, que OULAD trae hecha: suspenso (nota final del
   curso por debajo del aprobado) o baja. Depende de la escala de la institución (pendiente).
3. **Bucle de intervención.** Los estudiantes avisados que reciben ayuda y aprueban figuran como
   «no en riesgo», aunque el modelo acertara. Por eso se archiva también qué alerta recibió cada
   estudiante y qué hizo el profesor; es una limitación que hay que declarar.
4. Al principio, el archivo se siembra con OULAD, así que los cursos locales se suman a él. Cuando
   haya bastantes datos locales se podrá valorar entrenar solo con ellos.

### P8 · 23-10-2026 · La etiqueta «en riesgo» en Moodle

La escala de calificación es de 2 a 5: 2 = desaprobado, 3 = aprobado justo, 4 = aprobado estable y
5 = aprobado sobresaliente. **En riesgo = nota final 2 o baja del curso**, el equivalente de
Fail/Withdrawn en OULAD. Con 3, 4 o 5, no está en riesgo.

La etiqueta solo hace falta para evaluar a posteriori y para el archivo; la predicción no la usa.

**Actualización (23-10-2026, Jose): la traducción de las notas queda desacoplada.** El método de
calificación de la institución aún no está claro. La extracción usa una interfaz
(`alerta.calificacion.Calificacion`, método `a_100(nota, ítem)`). La implementación por defecto
es la de OULAD (nota / máxima · 100). Cambiarla es escribir otra clase y elegirla con
`ALERTA_CALIFICACION=modulo:Clase`; nada más cambia.

**Lo que motivó la actualización:** cómo se normalizan a 0–100 las notas de cada evaluación. Con
`nota / máximo × 100`, un 2 sobre 5 vale 40, que es justo el aprobado de OULAD, y la variable más
importante del modelo (`mean_score_with_zeros_raw`) lo leería como «aprobado». Se decide al ver
cómo están configuradas las calificaciones en Moodle (escala 2–5, puntos, etc.).

### P9 · 23-10-2026 · Reglas de la extracción de Moodle (F3)

- `item_id` = `cmid`. Fecha de cada tipo: `assign` → `duedate`; `quiz` → `timeclose`. Los demás
  tipos quedan sin fecha (no entran en los cortes) hasta que se añada su regla.
- Entrega: en `assign`, la de estado `submitted`. Una tarea con nota y sin entrega en Moodle (en
  papel) cuenta como entregada en su fecha. En los demás tipos, `gradedatesubmitted`.
- Nota publicada = `gradedategraded` del libro de calificaciones.
- Hallazgos del laboratorio:
  - `mod_assign_get_assignments` exige matrícula salvo con `includenotenrolledcourses`;
  - los cuestionarios suelen estar ocultos en el libro hasta que cierran, así que el rol del
    servicio necesita `moodle/grade:viewhidden`.
- Fuente A: eventos de nivel «participación» de usuarios con rol de estudiante. Fuente C: el
  profesor exporta el registro con «Participación»; las columnas se leen por posición (los nombres
  dependen del idioma), los ids salen de la descripción (siempre en inglés) y la hora se convierte
  desde la zona de quien exporta (America/Havana por defecto).

### P10 · 23-10-2026 · El sistema entra en Moodle como un servicio que el profesor añade a su curso

Indicado por Jose. El usuario de servicio (`alerta_servicio`) no tiene ningún permiso de lectura a
nivel de sitio: su rol de sistema solo permite usar el protocolo REST. **Regula los cursos en que un
profesor lo matricula** con el rol de profesor o de profesor sin permiso de edición (solo
lectura), y lee cada curso con los permisos de ese rol.

- `alerta.moodle.cursos.discover` lista esos cursos (`core_enrol_get_users_courses` + su rol en
  cada uno) y sus profesores, que serán los destinatarios de las alertas (F6).
- Un curso sin el servicio matriculado no se puede extraer (`PermissionError`).
- Comprobado en el laboratorio: con el rol de profesor sin edición (`teacher`) por defecto de
  Moodle, la extracción completa funciona (registro, tareas, entregas, notas ocultas, informe de
  usuario). Esto sustituye al rol de lectura global de F3.

### P11 · 23-10-2026 · Tres predicciones por curso, una en cada corte

Indicado por Jose: se predice solo en los tres cortes de la tesis. El servicio se ejecuta una vez
al día (`python -m alerta ejecutar`, en cron) y en cada curso:
- calcula los días de corte con las fechas de las tareas (fecha de la TMA ancla + 14 días);
- si ya pasó un día de corte, toma el corte más reciente y lo publica si no se había publicado;
- los cortes anteriores que quedaron sin publicar (el servicio entró tarde en el curso o no se
  ejecutó) se omiten, para no avisar con datos viejos. Cada curso recibe como mucho tres
  publicaciones.

**Entrega (F6).** El plugin guarda cada publicación (`local_alertatemprana_run`), las
predicciones con sus variables y su aporte al riesgo (`_pred`, como `analytics_predictions`) y
las acciones de los profesores (`_act`, como `analytics_prediction_actions`). Avisa a los
profesores del curso con una notificación de Moodle (correo y aviso emergente). Muestra:
- un informe por corte, con la lista ordenada por probabilidad, la nota media, la última tarea,
  la actividad de las 4 últimas semanas y las entregas;
- los detalles de cada predicción: cada variable, su valor y si aumenta o reduce el riesgo;
- las acciones *Aceptar*, *No aplicable*, *Marcado incorrectamente*, *Útil*, *No útil*,
  *Enviar mensaje* (también a varios estudiantes a la vez) e *Informe de actividad*.

Las predicciones viven en Moodle. El sistema Python guarda además una copia en
`data/ejecuciones/`.

### P12 · 28-10-2026 · Se predice cuando hay notas nuevas o cuando el profesor lo pide (sustituye a P6 y P11)

Revisión de Davier (D2-01, D2-07, D2-10, D2-13, D2-14), aceptada por Jose. Los tres días de corte
calculados de antemano y la ejecución diaria eran inflexibles: dependían de que el curso tuviera la
estructura de OULAD y suponían que el profesor publica las notas 14 días después de cada tarea.
Ahora el sistema es agnóstico a la estructura del curso:

- **Dos disparadores.**
  - *Notas completas*: el plugin escucha `\core\event\user_graded` y deja una solicitud en una
    cola (`local_alertatemprana_req`). Una evaluación está **completa** en el momento T si su fecha
    de entrega ya pasó y todas las entregas recibidas hasta T tienen nota publicada. Si hay una
    evaluación completa más reciente que el ancla de la última predicción automática, se predice
    y se avisa a los profesores (notificación y correo).
  - *A petición del profesor*: botón «Calcular predicciones ahora» en el informe. Usa la evaluación
    más reciente con alguna nota publicada. No envía correo; el resultado aparece en el informe.
- **Requisito mínimo**: al menos una evaluación (tarea con fecha de entrega) con notas. Si no la
  hay, la solicitud se cierra con ese mensaje, que el profesor ve en el informe.
- **El momento de la predicción.** Ancla = la evaluación elegida; entran las evaluaciones con fecha
  ≤ la del ancla; la actividad se cuenta hasta el momento T. Se conserva la semántica del
  entrenamiento y el «ancla + 14 días» pasa a ser «cuando el profesor tiene las notas».
- **Qué ajuste del modelo se aplica** (el paquete tiene uno por corte, P1): si el ancla es la última
  tarea del curso, `last`; si no, `first` cuando el ancla cae antes del 37,5 % del curso y `mid`
  después (la regla de anclaje de la tesis, invertida). **Limitación que se declara**: en momentos
  intermedios se aplica el ajuste del corte más cercano, y esos momentos no se evaluaron en la
  tesis.
- **Operación.** El servicio procesa la cola cada 5 minutos (cron). `--todos` revisa todos los
  cursos aunque no tengan solicitudes (para simular fechas en las pruebas y la demostración, o como
  barrido de seguridad).
- **Entrega.** Cada predicción es una publicación más (`run`), con su motivo (`notas` o
  `profesor`), su ancla y el ajuste usado. El informe muestra la más reciente y el historial.
- Sin cambios: extracción, variables, modelo y acciones. La validación contra OULAD (`make validar`)
  sigue usando los cortes de la tesis, porque reproduce el Capítulo 2.

### P13 · 04-11-2026 · Umbral: proporción de desaprobados del entrenamiento en cada corte

Cap. 2 actual (sección 2.4.1; Proposal, DECISIONES E18), que sustituye al umbral F2 de P1. El
paquete **v2** tiene los mismos modelos que v1 y, en cada corte, el umbral = proporción de
desaprobados de los periodos de entrenamiento entre los estudiantes que siguen matriculados en ese
corte: 0,433 · 0,389 · 0,353. Lo calcula el código (`importar.from_proposal_e18`, regla
`proporcion_desaprobados_por_corte` en `entrenamiento.THRESHOLDS`), y la misma regla se aplica al
reentrenar con cursos cerrados de otra plataforma. Se marca en riesgo a quien **supera** el umbral
(`>`, como en la tesis). v1 queda registrado para volver atrás. `python -m alerta modelo importar-e18`.

### P14 · 04-11-2026 · La probabilidad que se muestra es la de desaprobar (D5-27; sustituida por P19)

El informe, los detalles, la notificación, el proveedor de privacidad y el WS dicen «probabilidad de
desaprobar» (término fijado de la tesis), no «probabilidad de riesgo». La etiqueta «en riesgo» no
cambia (P8): marca a quien tiene una probabilidad de desaprobar mayor que el umbral.

### P15 · 04-11-2026 · La explicación de cada predicción es respecto al estudiante promedio del curso (D5-34)

Aporte de la variable j del estudiante i = coef_j · (x_ij − media del curso_j) / escala_j, con la
media de los estudiantes del curso en esa predicción y la escala del entrenamiento. Su suma es
exactamente la diferencia entre el logit del estudiante y el del estudiante promedio del curso. La
probabilidad no cambia. Se mantiene «neutro» para |aporte| < 0,05 (mueve la probabilidad como mucho
en poco más de un punto, Cap. 3).

### P16 · 04-11-2026 · Conversión de las notas: equipercentil entre aprobados (sustituye a la pendiente de P8)

Decisión del autor del 03-11-2026 (Cap. 3; ECTS Users' Guide 2015, secc. 4.3–4.4; Kolen y Brennan,
2014). En `alerta.calificacion`:
- Suspenso (un 2 en la escala 2–5; en puntos, una nota por debajo de la «calificación para aprobar»
  del ítem en Moodle o, si no está fijada, del 60 % de la máxima) → media de las notas de suspenso
  del entrenamiento (26,5).
- `Equipercentil` (por defecto): una nota de aprobado → media de las notas de aprobado del
  entrenamiento que ocupan sus mismos percentiles entre los aprobados del grupo de referencia (cursos
  cerrados de la plataforma, al menos 2, por escala; `python -m alerta escala referencia CURSO…`,
  guardado en `data/escala/referencia.json`).
- `Anclada`, mientras no haya grupo de referencia: 3, 4 y 5 → 50, 70 y 90 (centros de 40–59, 60–79 y
  80–100); en puntos, lineal de [aprobado, máxima] a [40, 100].
- La escala de entrenamiento (media de los suspensos y 1001 cuantiles de los aprobados) viaja en el
  paquete (`manifest.json`, `escala`), calculada con las TMA de OULAD de los periodos de entrenamiento.
- La «calificación para aprobar» de cada ítem no la da ningún WS estándar: la da la función nueva
  del plugin `local_alertatemprana_get_gradeitems`.
- El informe muestra las notas en la escala del curso (2 a 5, puntos o, si las tareas no comparten
  escala, porcentaje de la máxima); la no entregada cuenta como la nota más baja y la entregada sin
  nota no cuenta.
- La validación F5 sigue usando `ProporcionalOULAD` (reproduce OULAD, notas en 0–100). La
  demostración califica AAA 2014J de 2 a 5 y toma como grupo de referencia los cursos de OULAD de los
  periodos de entrenamiento calificados igual.

### P17 · 04-11-2026 · Predicción a petición con la tarea más reciente a medio calificar (D5-22)

Si la tarea más reciente con notas tiene menos del 90 % de sus notas, la petición del profesor no
predice: se le dice cuántas faltan y se le pide completar la calificación (la predicción de la tarea
anterior sigue en el informe). Con el 90 % o más, se predice y las notas que faltan no cuentan (no
valen 0). Denominador: las entregas recibidas de los estudiantes con matrícula activa; en una tarea
**sin entregas en línea** (examen presencial registrado como tarea), todos los estudiantes activos.
Corrige un defecto: en esas tareas solo había fila para quien ya tenía nota, así que los demás
contaban como no entregados (0) y la tarea se daba por completa con la primera nota. Ahora el
estudiante sin nota queda «sin calificar» y la tarea está completa cuando todos tienen nota.

### P18 · 04-11-2026 · El ajuste del modelo es el del corte más próximo (D5-23, D5-38; sustituye a la regla de P12)

25, 50 y 75 % son las posiciones de los cortes; las fronteras son los puntos medios: `first` antes
del 37,5 % del curso, `mid` entre el 37,5 y el 62,5 %, `last` a partir del 62,5 % y siempre en la
última tarea (`variables.MID_BOUNDARY`, `LAST_BOUNDARY`). Simulación de la tesis: los tres ajustes
ordenan igual en cualquier posición; la regla decide sobre todo el umbral.

### P19 · 05-11-2026 · «Riesgo académico» en la interfaz y la notificación (RC-03; sustituye a P14)

Revisión conjunta de la tesis: «riesgo académico» (no aprueba o abandona) es la única expresión para
la clase, el resultado observado y la alerta. El informe, los detalles, la notificación, el
proveedor de privacidad y las descripciones del WS dicen «probabilidad de riesgo académico» y «en
riesgo académico» (también en `lang/en`: «academic risk»). Plugin 0.6. Los nombres internos
(`en_riesgo`, `proporcion_desaprobados_por_corte` del manifiesto) no cambian, para no romper los
paquetes registrados.

### P20 · 05-11-2026 · El profesor elige qué tipos de evaluación se analizan (D6; completa P4)

Revisión de Davier (D6-05, D6-08) y decisión del autor. P4 había dejado abierto «cómo lo decide el
profesor»:

- **Página «Evaluaciones que se analizan»** (`evaluations.php`, enlazada desde el informe): muestra
  los tipos de módulo calificables del curso (libro de calificaciones) con cuántas actividades tiene
  cada uno, y el profesor marca cuáles entran. Las tareas (`assign`) entran siempre. Solo pueden
  elegirse los tipos cuya fecha sabe leer la extracción (`assign`, `quiz`, P9); los demás aparecen
  sin poder marcarse. Se guarda en `local_alertatemprana_cfg` y lo lee el servicio con
  `local_alertatemprana_get_course_config`. Por defecto, solo tareas: el comportamiento anterior.
- **Disparadores**: la predicción automática sigue anclada a las tareas completas (equivalen a las
  TMA del entrenamiento). La **petición del profesor** toma como referencia la evaluación más reciente
  con notas de cualquiera de los tipos elegidos (`variables.evaluations(d, día, tipos)`, columna
  `is_tma`). Los tipos elegidos entran también en la nota media de todas las predicciones.
- **Fundamento** (simulación con las CMA de OULAD, 05/11/2026):
  en los cierres de CMA, tomar la CMA como referencia y en la nota media cambia la ROC-AUC según la
  asignatura: +0,044 a +0,046 en CCC (las CMA pesan el 25 % de la nota; +0,04 también en 2014J) y
  −0,002 a −0,022 en BBB (cuestionarios de práctica, 5 % en total). Por eso la página recomienda
  incluir solo las evaluaciones que cuentan para la nota final.
- Las cadenas de la interfaz dicen «evaluación de referencia» en lugar de «tarea de referencia».
  Plugin 0.7.

## Arquitectura

```
Moodle                                         Thesis-Software (Python)
┌───────────────────────────────┐   REST WS  ┌─────────────────────────────────────┐
│ core WS: cursos, matrícula,   │ ─────────▶ │ extraccion/  Moodle → canónico      │
│ tareas, libro de calificac.   │            │   actividad: A (WS) | C (exportado) │
│ local_alertatemprana:         │            │ variables/   canónico → variables   │
│  get_activity                 │            │   (mismo código para OULAD)         │
│  get_course_config            │            │ prediccion/  paquete de modelo      │
│  save_predictions ──▶ notif.  │ ◀───────── │ entrega/     publicar en Moodle     │
│  informe + acciones (insights)│            │ cli + cron (--as-of)                │
└───────────────────────────────┘            └─────────────────────────────────────┘
```

Se reutiliza de SEGTI-Edu el `MoodleClient`, limpio: URL y token por parámetro, sin importar
`src.segti_edu`. También el patrón de *checkpoint* del procesador.

## Fases

| Fase | Qué | Hecho cuando |
|---|---|---|
| F0 | Esqueleto: git, paquete, venv con las versiones de Proposal, `.env` | `pytest` vacío pasa |
| F1 | Esquema canónico, adaptador OULAD → canónico y módulo de variables | Reproduce `Proposal/data/processed/dataset.parquet` exactamente |
| F2 | Paquete de modelo (`modelo.json` + manifiesto) y predictor | Mismas probabilidades que el joblib; mismas ROC-AUC en 2014J que E15 |
| F3 | `MoodleClient` limpio, plugin (`get_activity`, `get_course_config`), extracción Moodle → canónico e importador C | Extrae el curso semilla por A y por C con el mismo resultado |
| F4 | Datos de demostración: reproducir una presentación de OULAD en el Moodle local (~200 estudiantes, tareas con fechas, entregas, notas y eventos de log) | Curso poblado |
| F5 | Validación de extremo a extremo: Moodle → variables → predicción frente a los mismos estudiantes calculados en OULAD | Diferencias nulas o explicadas una a una |
| F6 | Entrega: tablas, `save_predictions`, notificación, informe, detalles y acciones | El profesor recibe la alerta y actúa sobre ella en Moodle |
| F7 | Operación: cron, registro de ejecuciones, configuración por servidor, documentación para EVEA | Una ejecución programada completa |

## Estado

| Fase | Estado |
|---|---|
| F0 | Hecha (23-10-2026): git, `.venv` (Python 3.14, versiones de Proposal), `pyproject.toml` |
| F1 | Hecha (23-10-2026): `alerta.canonico`, `alerta.fuentes.oulad`, `alerta.variables`. Reproduce `dataset.parquet` exactamente (filas, 13 variables, valores originales, ancla y objetivo; `tests/test_variables_oulad.py`). Reglas que OULAD no ejercita (tipos configurables, nota publicada después del corte, ítems sin fecha, bajas) en `tests/test_variables_reglas.py` |
| F2 | Hecha (23-10-2026): paquete, registro (`modelos/`, v1 activo), entrenamiento, archivo y reentrenamiento (P7). v1 da las probabilidades del joblib (1e-12); el entrenamiento del sistema reproduce el de la tesis (coeficientes y umbrales a 1e-10); en 2014J, ROC-AUC 0,787 · 0,883 · 0,923 y sensibilidad 0,929 · 0,894 · 0,887 (E15), también desde OULAD crudo. Reentrenamiento simulado con OULAD (2014J como periodo nuevo): promueve, mantiene o solo registra según la política |
| Laboratorio | Hecho (23-10-2026): Moodle 5.2.1 propio en `infra/moodle` + `.runtime` (copiado de SEGTI-Edu, proyecto Docker `alerta_moodle`, puertos 8100/54322/8082). `make up` arranca, instala, pone el español, crea el usuario de servicio `alerta_servicio` (rol de lectura a nivel de sistema), el servicio `alerta_connector` (11 funciones) y el token, y comprueba el WS. Probado desde cero (3 min 49 s) y repetido (12 s) |
| F3 | Hecha (23-10-2026): cliente REST (`alerta.moodle.cliente`), plugin `local_alertatemprana` con `get_activity` (fuente A), extracción Moodle → canónico (`alerta.fuentes.moodle`), importador del registro exportado en CSV y Excel (`alerta.fuentes.registro_exportado`, fuente C), sembrador de cursos de prueba (`infra/moodle/fixtures/seed_course.php`, `alerta.moodle.sembrar`) y orden `python -m alerta extraer`. Viaje de ida y vuelta canónico → Moodle → canónico idéntico (tablas y variables, con y sin `quiz`), y fuente C = fuente A (`tests/test_moodle_extraccion.py`). Ver P9 y P10 |
| F4–F5 | Hechas (23-10-2026): `python -m alerta validar-oulad` (`make validar`, unos 6 min). Reproduce AAA_2014J completo en Moodle (365 estudiantes, 5 TMA, 598 158 eventos) y, corte a corte, desmatricula a quien ya se había dado de baja, extrae por el WS, calcula variables y predice con v1. Frente al cálculo directo sobre OULAD: mismos estudiantes (338 · 330 · 304), diferencia 0 en las 12 variables y en las probabilidades, mismas alertas (280 · 176 · 112). ROC-AUC del curso: 0,792 · 0,830 · 0,922. Correcciones que salieron: redondeo a 9 decimales antes de los percentiles (el ruido de coma flotante rompía empates) y libro de calificaciones en una sola llamada (`userid=0`): la extracción pasó de unos 6 min a unos 25 s por curso |
| F6 | Hecha (23-10-2026): plugin 0.2 (tablas, `save_predictions`, `get_runs`, `get_actions`, notificación, informe, detalles, acciones, mensaje en lote, enlace en el curso) y `alerta.servicio` (`python -m alerta ejecutar [--fecha]`, `make ejecutar`). `tests/test_servicio.py`: espera antes del primer corte, publica en su día, no duplica, si se ejecuta tarde publica solo el último corte; el profesor recibe la notificación, ve el informe y los detalles, y su acción queda registrada. Ver P11 |
| F7 | Hecha (23-10-2026): configuración portable en el plugin (`local_alertatemprana\setup`, `cli/setup.php`, la usa también el laboratorio); observador que borra los datos del plugin al borrar un curso; registro de ejecuciones (`data/servicio/ejecuciones.jsonl`); demostración (`alerta.demo`, `make demo`, `make demo-corte1..3`, `make demo-estado`) con AAA_2014J y nombres ficticios; `docs/OPERACION.md` y `docs/DEMOSTRACION.md`. Ensayo completo según la guía: los tres cortes publicados (280 · 176 · 112 en riesgo), sin duplicados y con 3 correos a la docente. Sin mensajes de bienvenida al matricular en el laboratorio |
| P12 | Hecha (28-10-2026): plugin 0.4 (cola `local_alertatemprana_req`, observador de `user_graded`, botón «Calcular predicciones ahora», `get_requests`, `complete_requests`, varias publicaciones por curso con motivo e historial en el informe); `variables.evaluations`, `variables.moment` y `build(at=…)`; servicio por cola (`ejecutar`, `--todos`); demostración por tareas (`make demo-notas1..5`, `make demo-atender`). `tests/test_momento.py`: en los días de corte de la tesis el cálculo nuevo reproduce las variables de la tesis. `tests/test_servicio.py`: la calificación deja una solicitud; sin tareas completas no predice; la petición del profesor predice sin correo; una tarea completa predice y avisa una sola vez; la última tarea usa el ajuste `last` |
| P13–P18 | Hechas (04-11-2026, `docs/ACTUALIZACION-TESIS.md`): paquete v2 activo (umbrales 0,433 · 0,389 · 0,353); conversión equipercentil/anclada y grupo de referencia; plugin 0.5 (`get_gradeitems`, «probabilidad de desaprobar», explicación respecto al curso, notas en la escala del curso); regla del 90 % y tareas presenciales; fronteras del 37,5 y el 62,5 %; demostración calificada de 2 a 5. Tests: `test_calificacion`, `test_prediccion`, `test_momento`, `test_modelo` (umbrales de la tesis), `test_moodle_extraccion` (tarea presencial y nota de aprobado), `test_servicio` (petición con el 80 % de las notas) |
| P19 | Hecha (05-11-2026): plugin 0.6 con «riesgo académico» y «probabilidad de riesgo académico» en todos los textos que ve el profesor (`lang/es`, `lang/en`) y en las descripciones del WS |
| Pendiente | Exportación y borrado de datos personales en el proveedor de privacidad; instantáneas de los cursos abiertos (solo para el archivo, extra) |

## Riesgos que hay que declarar

1. **Escala de notas.** `mean_score_with_zeros_raw` lleva la frontera de aprobado de OULAD (40).
   En la UH el aprobado es otro. No se cambia el modelo; el percentil lo amortigua en parte. Es
   una limitación de la transferencia.
2. **Evento ≠ clic.** Ver P3.
3. **La última TMA** solo se conoce si las tareas tienen sus fechas configuradas desde el inicio.
4. **Notas sin publicar en el día de corte.** Se tratan como en OULAD y se marcan en el informe.
5. **Incluir otros tipos de evaluación** (P4) cambia la distribución de la nota media respecto a
   la del entrenamiento. Por eso, por defecto solo se incluye `assign`.
