# Cómo hacer la demostración

Guía para presentar el sistema de alerta temprana funcionando en el Moodle del portátil. La
demostración dura unos 20 minutos y tiene cinco partes:

1. un curso real (AAA de OULAD, 2014J) dentro de Moodle;
2. la docente añade el servicio a su curso;
3. la docente termina de calificar una tarea y llega la alerta;
4. la docente revisa la lista, los detalles de cada estudiante y actúa;
5. las pruebas de que el sistema calcula lo mismo que el modelo de la tesis.

## Qué se va a ver

| Qué | Dónde |
|---|---|
| Moodle | <http://localhost:8100> |
| Docente del curso | usuario `docente.demo`, contraseña `MOODLE_DEMO_PASSWORD` de `.env.local` (por defecto `Demo-Alerta-2026!`) |
| Administrador | usuario `admin`, contraseña `MOODLE_ADMIN_PASSWORD` de `.env.local` |
| Correo que reciben los profesores | <http://localhost:8100/_/mail/> (buzón de pruebas) |
| Terminal | en `Thesis-Software/`, para avanzar el tiempo |

**El curso.** Tiene los **365 estudiantes reales** del módulo AAA de OULAD en 2014J, con sus 5
tareas, entregas y notas. Cada uno de sus **598 158 clics** está convertido en un evento del
registro de Moodle. Los nombres son ficticios. Las tareas están **calificadas de 2 a 5**, como en la
UH: cada nota de OULAD pasa a su categoría (2 por debajo de 40, el suspenso de OULAD; 3 de 40 a 59;
4 de 60 a 79; 5 de 80 en adelante), y el sistema las convierte a la escala del modelo con la
conversión equipercentil de la tesis, tomando como cursos anteriores de la plataforma los cursos de
OULAD de los periodos de entrenamiento, calificados igual. El curso empieza el 1 de octubre de 2014. OULAD no
guarda cuándo se publicó cada nota, así que la demostración supone que la docente termina de
calificar cada tarea dos semanas después de su entrega: las notas de las tareas 1 a 5 quedan
completas los días 33, 68, 131, 180 y 229 del curso.

## Antes de la demostración

**El día antes** (o una hora antes):

```bash
cd Thesis-Software
make up          # Moodle arrancado, instalado y configurado (1–4 min)
make test-fast   # comprobación rápida (opcional)
make demo        # crea el curso de la demostración (unos 4 minutos)
make demo-estado # debe decir «servicio matriculado: todavía no» y ninguna predicción publicada
```

`make demo` borra y vuelve a crear el curso. Se puede repetir para ensayar todas las veces que haga
falta.

**Ensayo recomendado.** Una vez, completo: los pasos 2 a 4 de abajo, y después `make demo` para
dejarlo limpio. Cada paso tarda algo menos de un minuto.

**Justo antes.** Dos ventanas del navegador: una con la sesión de `docente.demo`, en el curso
«Demostración · Alerta temprana…», y otra con el buzón de correo. Una terminal en
`Thesis-Software/`.

## Guion

### 1. El problema y el curso (2 min)

Con la sesión de la docente, abrir el curso. Enseñar **Participantes** (365 estudiantes) y
**Calificaciones** (las 5 tareas, de 2 a 5).

> «Es un curso real de la Open University: los mismos datos con los que se validó el modelo, pero
> ahora dentro de un Moodle. Lo que vamos a ver es lo que pasaría si este curso se impartiera en
> EVEA con el servicio activado.»

### 2. La docente añade el servicio a su curso (2 min)

El sistema no ve ningún curso por su cuenta. **Lo incorpora cada profesor**, como incorporaría a
un profesor asistente:

1. *Participantes* → **Matricular usuarios**.
2. Buscar «Servicio» y elegir **Servicio Alerta temprana**.
3. *Asignar rol*: **Profesor sin permiso de edición** (solo puede leer).
4. **Matricular usuarios**.

En la terminal:

```bash
make demo-estado   # ahora: «servicio matriculado en el curso: sí»
```

> «A partir de aquí, el servicio lee este curso con los permisos de un profesor que no puede
> editar nada, y solo este curso.»

### 3. La docente termina de calificar una tarea (3 min)

```bash
make demo-notas2
```

Mientras corre, explicar qué pasa:

- se **simula que es el 8 de diciembre de 2014**: la docente acaba de calificar todas las entregas de la tarea 2.
  Cada calificación deja en Moodle una solicitud para el servicio, que la revisa cada pocos
  minutos;
- el servicio comprueba que la tarea 2 quedó completa (todas las entregas recibidas tienen nota),
  extrae las notas, las entregas y la actividad de cada estudiante **hasta ese día**;
- convierte las notas de 2 a 5 a la escala del modelo, calcula las variables y predice con el
  modelo de la tesis (versión v2), tomando la tarea 2 como referencia;
- publica las predicciones en Moodle y avisa a la docente.

> «No hay fechas fijas: el sistema reacciona cuando el profesor tiene las notas. Sirve para
> cualquier curso, tenga las tareas que tenga.»

Cuando termine:

- **La campana de notificaciones** de la docente: «Estudiantes en riesgo académico en … (notas de …)».
- **El buzón de correo**: el mismo aviso por correo.

### 4. La lista de la docente (5 min)

Desde la notificación, o desde el curso en **Más → Alerta temprana**:

- **Resumen:** 143 de 338 estudiantes en riesgo académico con los datos hasta el día 68, con la tarea 2 como referencia.
  > «Se marca en riesgo académico a quien tiene una probabilidad de riesgo académico mayor que la
  > proporción de estudiantes en riesgo académico que había en este punto del curso en los cursos de entrenamiento (43 %). La lista va ordenada por
  > probabilidad: la docente empieza por arriba.»
- **La tabla:** probabilidad de riesgo académico, nota media y nota de la tarea de referencia (de 2 a 5),
  actividad de las últimas 4 semanas (y su percentil en el curso) y entregas.
- **Ver detalles** (icono del ojo) de un estudiante de arriba: cada variable del modelo, su valor y
  si **aumenta o reduce la probabilidad de riesgo académico respecto al estudiante promedio del curso**.
- **Acciones**, iguales que las de los *insights* de Moodle: *Aceptar*, *No aplicable*, *Marcado
  incorrectamente*, *Enviar mensaje*, *Informe de actividad*. Pulsar *Aceptar* en uno: queda
  registrado y se ve en la columna *Estado*.
- **Enviar un mensaje** a varios a la vez: marcar dos o tres casillas → *Enviar un mensaje a los
  seleccionados*.

### 5. Más tareas y la petición de la docente (4 min)

```bash
make demo-notas3   # 9/2/2015: 110 de 330 en riesgo
make demo-notas5   # 18/5/2015: 85 de 304 en riesgo
```

En el informe, el **historial** muestra cada predicción con su fecha, su motivo y su tarea de
referencia.

> «Con más información, la lista se acorta y se afina. Los estudiantes que se dieron de baja
> desaparecen, como en Moodle.»

**La docente pide una predicción.** En el informe, pulsar **Calcular predicciones ahora**. Aparece
«Solicitud registrada». En la terminal:

```bash
make demo-atender
```

Al recargar el informe, hay una predicción nueva con motivo «pedida por el profesor», sin correo.
Si la tarea más reciente con notas tuviera menos del 90 % de ellas, el informe diría cuántas faltan
y pediría completarlas, sin predecir.

> «En los días de las tareas 2, 3 y 5, el ancla y la fecha coinciden con las de los tres cortes de
> la tesis. Las cifras no son exactamente las de la tesis porque aquí las notas están de 2 a 5.»

Si se repite `make demo-notas5`, no hay aviso nuevo: «sin evaluaciones completas nuevas».

### 6. Por qué fiarse de lo que calcula (3 min)

Lo que más interesa saber es si el software calcula **exactamente** lo que el modelo
aprendió. Tres pruebas, todas automáticas:

1. **Las variables.** Calculadas por el sistema sobre OULAD, reproducen el conjunto de datos de
   entrenamiento de la tesis sin una sola diferencia (49 101 filas, 13 variables).
2. **El modelo.** El paquete v2 da las mismas probabilidades que el modelo de la tesis, y en 2014J
   las mismas ROC-AUC (0,787 · 0,883 · 0,923). Su umbral, la proporción de estudiantes en riesgo académico del
   entrenamiento en cada corte (0,433 · 0,389 · 0,353), lo calcula el código con los datos.
3. **De extremo a extremo.** Este mismo curso, con sus notas originales de 0 a 100, metido en Moodle y leído por el servicio web, da
   **las mismas variables, probabilidades y alertas** que calculadas directamente sobre OULAD, en
   los tres cortes (`make validar`; informe en `data/validacion/AAA_2014J.json`). Y en los días de
   corte de la tesis, la predicción por tareas da exactamente las mismas variables que el cálculo
   por cortes (`tests/test_momento.py`).

```bash
make test-fast                              # en segundos
cat data/validacion/AAA_2014J.json          # resultado de la validación de extremo a extremo
```

### 7. Preguntas probables

- **¿Por qué tantos en riesgo académico al principio del curso?** El umbral es la proporción de
  estudiantes en riesgo académico que había en ese punto del curso en los cursos de entrenamiento (43 % en el primer corte), así
  que se marca más o menos a tantos como suelen terminar en riesgo académico. La lista ordenada por probabilidad
  permite priorizar.
- **¿Funciona con datos de EVEA?** El sistema está preparado: solo cambia la dirección y el token
  (`docs/OPERACION.md`). El modelo se entrenó con OULAD; trasladarlo tiene dos límites conocidos.
  Primero, la escala de notas: el 2 se lleva al suspenso del entrenamiento y los aprobados se
  equiparan por percentiles con los cursos anteriores de la plataforma (P16), de modo que un
  suspenso nunca se lee como aprobado. Segundo, la equivalencia entre un clic de OULAD y un evento de Moodle, que pesa
  poco porque el modelo usa el percentil dentro del curso.
- **¿Qué ve el servicio?** Solo los cursos donde un profesor lo matricula, con los permisos de un
  profesor sin edición.
- **¿Y si el modelo cambia?** Se registra una versión nueva y se activa; el resto del sistema no
  cambia. El reentrenamiento periódico está implementado como extra (trabajo futuro).

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| Moodle no abre | `make up` |
| `make demo-notas…` dice «El servicio no ve el curso» | Falta el paso 2 (matricular al servicio como profesor sin edición) |
| `make demo-atender` dice «No hay peticiones pendientes» | Pulsar antes «Calcular predicciones ahora» en el informe |
| Algo quedó a medias | `make demo` (recrea el curso; hay que repetir el paso 2) o `.venv/bin/python -m alerta demo preparar --con-servicio` (el servicio ya entra matriculado) |
| Ver qué hizo el servicio | `make demo-estado` y `data/servicio/ejecuciones.jsonl` |
