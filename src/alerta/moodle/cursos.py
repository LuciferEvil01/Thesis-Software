"""Cursos que regula el servicio (PLAN.md, P10).

El sistema entra en Moodle como un usuario más (`alerta_servicio`). Un profesor que quiere usarlo
lo matricula en su curso con el rol de profesor o de profesor sin permiso de edición (solo
lectura). Esos cursos, y solo esos, son los que el servicio ve y regula.
"""

from __future__ import annotations

from alerta.moodle.cliente import Cliente

SERVICE_ROLES = frozenset({"teacher", "editingteacher"})  # profesor sin edición y profesor
TEACHER_ROLES = frozenset({"teacher", "editingteacher"})


def _roles(user: dict) -> set[str]:
    return {r["shortname"] for r in user.get("roles", [])}


def discover(c: Cliente, service_roles=SERVICE_ROLES) -> list[dict]:
    """Cursos donde el usuario de servicio está matriculado con uno de `service_roles`.

    Devuelve, por curso: id, nombres, fechas, el rol del servicio y los profesores (destinatarios
    de las alertas: los demás usuarios con rol de profesor).
    """
    me = c.site_info()["userid"]
    out = []
    for course in c.call("core_enrol_get_users_courses", userid=me):
        users = c.call("core_enrol_get_enrolled_users", courseid=course["id"])
        mine = next((_roles(u) for u in users if u["id"] == me), set())
        role = sorted(mine & service_roles)
        if not role:
            continue
        teachers = [{"id": u["id"], "fullname": u["fullname"]} for u in users
                    if u["id"] != me and _roles(u) & TEACHER_ROLES]
        out.append({"id": course["id"], "shortname": course["shortname"], "fullname": course["fullname"],
                    "startdate": course.get("startdate"), "enddate": course.get("enddate"),
                    "rol_servicio": role[0], "profesores": teachers})
    return out
