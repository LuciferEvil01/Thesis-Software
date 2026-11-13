# Laboratorio Moodle local y pruebas. `make up` deja Moodle arrancado, instalado y configurado.
.PHONY: up down status check configure audit logs shell reset test test-fast validar ejecutar demo demo-notas1 demo-notas2 demo-notas3 demo-notas4 demo-notas5 demo-atender demo-estado
LAB := ./infra/moodle/scripts/lab.sh

up: ; $(LAB) up
down: ; $(LAB) down
status: ; $(LAB) status
check: ; $(LAB) check
configure: ; $(LAB) configure
audit: ; $(LAB) audit
logs: ; $(LAB) logs
shell: ; $(LAB) shell
reset: ; $(LAB) reset

test: ; .venv/bin/python -m pytest -q
test-fast: ; .venv/bin/python -m pytest -q -m "not slow"

validar: ; .venv/bin/python -m alerta validar-oulad --curso AAA_2014J
ejecutar: ; .venv/bin/python -m alerta ejecutar

# Demostración (docs/DEMOSTRACION.md)
demo: ; .venv/bin/python -m alerta demo preparar
demo-notas1: ; .venv/bin/python -m alerta demo notas 1
demo-notas2: ; .venv/bin/python -m alerta demo notas 2
demo-notas3: ; .venv/bin/python -m alerta demo notas 3
demo-notas4: ; .venv/bin/python -m alerta demo notas 4
demo-notas5: ; .venv/bin/python -m alerta demo notas 5
demo-atender: ; .venv/bin/python -m alerta demo atender
demo-estado: ; .venv/bin/python -m alerta demo estado
