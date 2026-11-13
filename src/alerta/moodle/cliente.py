"""Cliente del web service REST de Moodle (simplificado a partir del MoodleClient de SEGTI-Edu).

    c = Cliente(url, token)              # o Cliente.desde_config()
    c.call("core_course_get_courses_by_field", field="id", value=5)

Los parámetros anidados se aplanan como los espera Moodle: `courseids=[1, 2]` → `courseids[0]=1&...`;
`options=[{"name": "x", "value": 1}]` → `options[0][name]=x&options[0][value]=1`.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from alerta import config


class MoodleError(RuntimeError):
    """Moodle respondió con una excepción (`exception`, `errorcode`, `message`)."""

    def __init__(self, wsfunction: str, payload: dict):
        self.wsfunction, self.errorcode = wsfunction, payload.get("errorcode")
        super().__init__(f"{wsfunction}: {payload.get('errorcode')}: {payload.get('message')}")


def flatten(params: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out = {}
    for key, value in params.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            out.update(flatten(value, name))
        elif isinstance(value, (list, tuple)):
            out.update(flatten(dict(enumerate(value)), name))
        elif isinstance(value, bool):
            out[name] = int(value)
        elif value is not None:
            out[name] = value
    return out


class Cliente:
    def __init__(self, url: str, token: str, timeout: int = 60, retries: int = 2):
        if not url or not token:
            raise ValueError("faltan la URL o el token de Moodle (ver .runtime/generated/rest.env o .env)")
        self.endpoint = url.rstrip("/") + "/webservice/rest/server.php"
        self.token, self.timeout, self.retries = token, timeout, retries
        self.session = requests.Session()

    @classmethod
    def desde_config(cls) -> Cliente:
        return cls(config.MOODLE_URL, config.MOODLE_TOKEN)

    def call(self, wsfunction: str, **params) -> Any:
        data = {"wstoken": self.token, "wsfunction": wsfunction, "moodlewsrestformat": "json", **flatten(params)}
        for attempt in range(self.retries + 1):
            try:
                r = self.session.post(self.endpoint, data=data, timeout=self.timeout)
                r.raise_for_status()
                break
            except (requests.ConnectionError, requests.Timeout):
                if attempt == self.retries:
                    raise
                time.sleep(2 ** attempt)
        payload = r.json()
        if isinstance(payload, dict) and "exception" in payload:
            raise MoodleError(wsfunction, payload)
        return payload

    def site_info(self) -> dict:
        return self.call("core_webservice_get_site_info")
