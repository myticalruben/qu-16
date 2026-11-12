"""API HTTP y WebSocket de qu16-control."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

#: Nombre con el que se distribuye el paquete (pyproject.toml).
_DISTRIBUTION = "qu16-control"

try:
    #: Versión instalada del paquete, leída de sus metadatos.
    __version__ = version(_DISTRIBUTION)
except PackageNotFoundError:  # pragma: no cover - solo si se importa sin instalar
    __version__ = "0.1.0"

__all__ = ["__version__"]
