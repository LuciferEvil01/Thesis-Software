# Thesis-Software · alerta temprana en Moodle

Sistema del Capítulo 3 del trabajo de diploma *Detección temprana de estudiantes en riesgo académico:
un sistema basado en los registros de Moodle* (José Agustín del Toro González, Facultad de Matemática
y Computación, Universidad de La Habana, 2026).

Aplica el modelo final de la tesis ([Thesis-Training](https://github.com/LuciferEvil01/Thesis-Training)) a cursos de Moodle: extrae los datos de cada
estudiante, calcula las variables, predice el riesgo cuando el profesor termina de calificar una
tarea o cuando lo pide, y le entrega la lista.
Plan, decisiones y estado: [PLAN.md](PLAN.md). Operación y paso a EVEA: [docs/OPERACION.md](docs/OPERACION.md).
Demostración paso a paso: [docs/DEMOSTRACION.md](docs/DEMOSTRACION.md) (`make demo`).

## Puesta en marcha

Requisitos: Docker con `docker compose`, git, Python 3.14 y el repositorio hermano [Thesis-Training](https://github.com/LuciferEvil01/Thesis-Training), clonado junto a este
(modelo y OULAD).

```bash
python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt -e .
make up        # Moodle local: arranca, instala (la primera vez), configura y comprueba el WS
make test      # todas las pruebas (unos 2 minutos; lee OULAD)
```

`make up` se puede repetir siempre: solo hace lo que falte. Deja:

- Moodle 5.2.1 en <http://localhost:8100> (usuario `admin`; contraseñas en `.env.local`, que se
  crea a partir de `.env.local.example`);
- el usuario de servicio `alerta_servicio`, con un rol de lectura y el servicio web
  `alerta_connector`; su token queda en `.runtime/generated/rest.env`, que lee `alerta.config`.

Otras órdenes: `make down`, `make status`, `make logs`, `make shell`, `make audit`, y
`MOODLE_RESET_CONFIRM=YES make reset` (borra la base de datos y moodledata).

Los puertos (8100, 54322, 8082) son distintos de los de SEGTI-Edu, así que los dos laboratorios
pueden estar levantados a la vez.

**Idioma.** `download.moodle.org` responde 403 desde Cuba. Si existe `.runtime/langpacks/es`, el
paquete de español se copia desde ahí; si no, Moodle intenta descargarlo.

## El servicio

Un profesor que quiera usar la alerta temprana matricula al usuario `alerta_servicio` en su curso
como profesor sin permiso de edición. Desde entonces, el servicio:

```bash
python -m alerta cursos      # lista los cursos que regula
python -m alerta ejecutar    # atiende las solicitudes de predicción pendientes (make ejecutar)
```

`ejecutar` está pensado para cron, cada 5 minutos (ver [docs/OPERACION.md](docs/OPERACION.md)).
Moodle deja una solicitud cuando se califica a un estudiante o cuando el profesor pulsa «Calcular
predicciones ahora» en el informe. El servicio predice y avisa a los profesores cuando una tarea
queda completamente calificada, y predice sin avisar cuando lo pide el profesor (PLAN.md, P12).
Ellos ven la lista y el historial en *Alerta temprana*, dentro del curso. Para revisar todos los
cursos en otra fecha: `python -m alerta ejecutar --todos --fecha 2026-02-05`.

## Estructura

| Ruta | Qué es |
|---|---|
| `src/alerta/` | El sistema: esquema canónico, variables, fuentes (OULAD, Moodle, registro exportado), modelo, servicio |
| `moodle/local/alertatemprana/` | Plugin de Moodle: actividad, cola de solicitudes, predicciones, notificación, informe y acciones del profesor |
| `modelos/` | Registro de versiones del modelo (`ACTIVO` = la que se usa) |
| `infra/moodle/` | Laboratorio Moodle: versiones, `lab.sh`, ajustes de Docker y scripts PHP de configuración |
| `.runtime/` | Código de Moodle y moodle-docker, credenciales generadas, caché de idiomas (no se versiona) |
| `tests/` | Pruebas (`make test-fast` omite las que leen OULAD completo) |
