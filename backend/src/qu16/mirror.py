"""Espejo en memoria del estado de la mesa.

La Fase 2 es de solo lectura: el espejo se construye a partir del volcado de
estado que envía la mesa y nunca se escribe en ella. La escritura llegará en
la Fase 4.

Todas las mutaciones y lecturas pasan por un ``asyncio.Lock`` para que el
bucle de enlace (que actualiza) y la API/WebSocket (que leen) no observen un
estado a medio construir. Los métodos son ``async`` por ese motivo.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from .protocol import dump as dump_module
from .protocol.framing import MixerVersion

#: Índices 0-2: los tres primeros bloques del volcado. En la Qu-16 capturada
#: se llaman ``inala1``…, pero no hemos podido verificar que sean estéreo de
#: forma general; se etiquetan ``"stereo"`` porque es la convención del
#: volcado que sí hemos observado en esta fase.
STEREO_INDEXES = frozenset({0, 1, 2})
#: Índices 3-18: son los 16 canales de entrada de la Qu-16 (nombres reales
#: ``coro1``, ``guitar``, ``piano``… en la captura). Es la única clasificación
#: que hemos podido verificar contra la mesa real.
INPUT_INDEXES = frozenset(range(3, 19))

#: Precisión con la que se publican los niveles: los mostradores de la mesa
#: trabajan con una décima de dB.
_LEVEL_DECIMALS = 1


def channel_kind(index: int) -> str:
    """Clasifica un canal por su índice en el volcado.

    La clasificación es deliberadamente conservadora: solo los índices 3-18 se
    consideran entradas (verificado) y 0-2 estéreo (convención observada). El
    resto —mezclas, FX, grupos— queda como ``"other"`` hasta disponer de una
    captura que permita verificarlo.
    """
    if index in INPUT_INDEXES:
        return "input"
    if index in STEREO_INDEXES:
        return "stereo"
    return "other"


def _firmware_label(version: MixerVersion) -> str:
    """Texto de firmware con el mismo formato que usa la mesa (``1.97``)."""
    return f"{version.major}.{version.minor:02d}"


def _level(value: float | None) -> float | None:
    """Redondea un nivel en dB a la precisión de presentación."""
    return None if value is None else round(value, _LEVEL_DECIMALS)


def _iso(moment: datetime | None) -> str | None:
    """Serializa una marca de tiempo en ISO 8601 UTC."""
    if moment is None:
        return None
    return moment.isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class ChannelView:
    """Vista inmutable de un canal, apta para serializar a JSON."""

    index: int
    name: str
    level_db: float | None
    kind: str

    def as_dict(self) -> dict[str, object]:
        """Representación serializable del canal."""
        return {
            "index": self.index,
            "name": self.name,
            "level_db": self.level_db,
            "kind": self.kind,
        }


class StateMirror:
    """Fuente de verdad en memoria del estado de la mesa.

    Al desconectarse se conservan la identidad y los últimos canales conocidos
    (con ``connected=False``) para que la interfaz pueda mostrar el último
    estado en gris en lugar de vaciarse.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.connected = False
        self.model: str | None = None
        self.firmware: str | None = None
        self.channels: list[ChannelView] = []
        self.updated_at: datetime | None = None

    # ------------------------------------------------------------------ estado

    async def mark_connected(self, version: MixerVersion | None = None) -> None:
        """Marca la mesa como conectada; guarda modelo y firmware si se conocen."""
        async with self._lock:
            self.connected = True
            if version is not None:
                self.model = version.model
                self.firmware = _firmware_label(version)

    async def mark_disconnected(self) -> None:
        """Marca la mesa como desconectada sin borrar el último estado conocido."""
        async with self._lock:
            self.connected = False

    async def update_from_dump(
        self, version: MixerVersion | None, dump_bytes: bytes
    ) -> None:
        """Reconstruye el espejo a partir de un volcado de estado.

        ``version`` es el paquete de versión del handshake; puede ser ``None``
        si el espejo ya conocía la identidad de la mesa. El volcado se
        interpreta fuera del bloqueo para no retenerlo durante el parseo.
        """
        state = dump_module.parse(dump_bytes)
        channels = [
            ChannelView(
                index=channel.index,
                name=channel.name,
                level_db=_level(channel.main_send_db),
                kind=channel_kind(channel.index),
            )
            for channel in state.channels
        ]

        async with self._lock:
            self.connected = True
            if version is not None:
                self.model = version.model
                self.firmware = _firmware_label(version)
            self.channels = channels
            self.updated_at = datetime.now(UTC)

    async def reset(self) -> None:
        """Devuelve el espejo a su estado inicial (útil en tests)."""
        async with self._lock:
            self.connected = False
            self.model = None
            self.firmware = None
            self.channels = []
            self.updated_at = None

    # ----------------------------------------------------------------- lectura

    async def snapshot(self) -> dict[str, object]:
        """Copia serializable y coherente del estado completo."""
        async with self._lock:
            return {
                "connected": self.connected,
                "model": self.model,
                "firmware": self.firmware,
                "updated_at": _iso(self.updated_at),
                "channels": [channel.as_dict() for channel in self.channels],
            }

    @property
    def channel_count(self) -> int:
        """Número de canales del último volcado (lectura informativa)."""
        return len(self.channels)
