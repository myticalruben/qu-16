"""Estado en memoria del vínculo con la mesa.

En la Fase 1 es un stub: nadie abre todavía la conexión TCP, pero la API ya
puede consultar y reflejar el estado que la Fase 2 mantendrá actualizado.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class MixerState:
    """Reflejo del estado de conexión con la Qu-16."""

    connected: bool = False
    model: str | None = None
    firmware: str | None = None

    def snapshot(self) -> dict[str, bool | str | None]:
        """Copia serializable del estado, apta para una respuesta JSON."""
        return asdict(self)

    def mark_connected(self, *, model: str | None, firmware: str | None) -> None:
        """Marca la mesa como conectada y guarda su identidad."""
        self.connected = True
        self.model = model
        self.firmware = firmware

    def mark_disconnected(self) -> None:
        """Marca la mesa como desconectada y limpia su identidad."""
        self.connected = False
        self.model = None
        self.firmware = None


#: Instancia compartida por los routers y el WebSocket.
mixer_state = MixerState()
