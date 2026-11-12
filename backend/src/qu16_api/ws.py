"""Gestor de suscriptores del WebSocket y difusión del estado.

Un único :class:`StateHub` mantiene el conjunto de websockets conectados. El
enlace le entrega cada instantánea nueva mediante :meth:`StateHub.on_state`,
que la reparte a todos los suscriptores; los clientes que ya no responden se
descartan sin afectar al resto.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket
from qu16.mirror import StateMirror

logger = logging.getLogger(__name__)


class StateHub:
    """Conjunto de websockets suscritos al estado de la mesa."""

    def __init__(self, mirror: StateMirror) -> None:
        self._mirror = mirror
        self._clients: set[WebSocket] = set()
        #: Protege el conjunto de suscriptores.
        self._clients_lock = asyncio.Lock()
        #: Serializa las entregas para que el orden de los mensajes sea estable.
        self._send_lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        """Número de suscriptores registrados."""
        return len(self._clients)

    async def register(self, websocket: WebSocket) -> None:
        """Añade un suscriptor ya aceptado."""
        async with self._clients_lock:
            self._clients.add(websocket)

    async def unregister(self, websocket: WebSocket) -> None:
        """Quita un suscriptor (idempotente)."""
        async with self._clients_lock:
            self._clients.discard(websocket)

    async def broadcast(self, snapshot: dict[str, object] | None = None) -> None:
        """Envía ``{"type": "state", "payload": ...}`` a todos los suscriptores.

        Si no se pasa ``snapshot`` se lee del espejo en ese momento. Las
        desconexiones y los envíos fallidos se registran y se retiran del
        conjunto, de modo que un cliente caído no bloquea a los demás.
        """
        payload: dict[str, object] = {
            "type": "state",
            "payload": (
                snapshot if snapshot is not None else await self._mirror.snapshot()
            ),
        }

        async with self._send_lock:
            async with self._clients_lock:
                clients = list(self._clients)

            failed: list[WebSocket] = []
            for websocket in clients:
                try:
                    await websocket.send_json(payload)
                except Exception:  # noqa: BLE001 - cliente desconectado
                    failed.append(websocket)

            if failed:
                async with self._clients_lock:
                    for websocket in failed:
                        self._clients.discard(websocket)
                logger.info(
                    "WebSocket: %d suscriptor(es) descartados", len(failed)
                )

    async def on_state(self, snapshot: dict[str, object]) -> None:
        """Callback compatible con ``MixerLink.on_state``."""
        await self.broadcast(snapshot)
