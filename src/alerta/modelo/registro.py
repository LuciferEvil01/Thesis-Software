"""Registro de versiones de modelo: qué paquetes hay y cuál está activo.

    modelos/
      <version>/manifest.json   un paquete por versión (no se modifica nunca)
      ACTIVO                    versión activa
      historial.jsonl           cada activación: fecha, versión, anterior y motivo
      informes/                 informes de los reentrenamientos

Volver a una versión anterior es activarla de nuevo.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from alerta.modelo.paquete import Paquete


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Registro:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def versions(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if (p / "manifest.json").exists())

    def register(self, paquete: Paquete) -> Path:
        if paquete.version in self.versions():
            raise ValueError(f"la versión {paquete.version} ya existe")
        return paquete.save(self.root / paquete.version)

    def load(self, version: str) -> Paquete:
        return Paquete.load(self.root / version)

    def active_version(self) -> str | None:
        f = self.root / "ACTIVO"
        return f.read_text().strip() if f.exists() else None

    def active(self) -> Paquete:
        version = self.active_version()
        if version is None:
            raise LookupError(f"no hay modelo activo en {self.root}")
        return self.load(version)

    def activate(self, version: str, reason: str) -> None:
        if version not in self.versions():
            raise ValueError(f"no existe la versión {version}")
        previous = self.active_version()
        (self.root / "ACTIVO").write_text(version + "\n")
        with open(self.root / "historial.jsonl", "a") as f:
            f.write(json.dumps({"fecha": now_iso(), "version": version, "anterior": previous,
                                "motivo": reason}, ensure_ascii=False) + "\n")

    def next_version(self) -> str:
        nums = [int(v[1:]) for v in self.versions() if v[:1] == "v" and v[1:].isdigit()]
        return f"v{max(nums, default=0) + 1}"

    def save_report(self, report: dict) -> Path:
        folder = self.root / "informes"
        folder.mkdir(exist_ok=True)
        path = folder / f"{report['fecha'].replace(':', '')}.json"
        path.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
        return path
