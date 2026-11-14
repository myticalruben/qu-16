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
from qu16.meters import MeterState
from qu16.mirror import StateMirror

logger = logging.getLogger(__name__)

#: Tipo de los mensajes con los niveles de medidor.
METERS_MESSAGE_TYPE = "meters"
#: Tope de espera por suscriptor al entregar medidores: un cliente lento se
#: descarta en lugar de frenar el bucle.
_METERS_SEND_TIMEOUT = 0.5


class StateHub:
    """Conjunto de websockets suscritos al estado de la mesa."""

    def __init__(self, mirror: StateMirror) -> None:
        self._mirror = mirror
        self._clients: set[WebSocket] = set()
        #: Protege el conjunto de suscriptores.
        self._clients_lock = asyncio.Lock()
        #: Serializa las entregas para que el orden de los mensajes sea estable.
        self._send_lock = asyncio.Lock()
        #: Última revisión de medidores difundida (``-1`` = ninguna).
        self._meters_revision = -1

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
        await self._deliver(payload)

    async def broadcast_meters(self, meters: MeterState) -> bool:
        """Difunde los medidores si hay novedad y suscriptores.

        Devuelve ``True`` solo si se envió el mensaje. No se emite nada si la
        mesa no está conectada, si no hay ningún nivel, si no hay suscriptores
        o si los niveles no han cambiado desde el último envío. Así el coste
        depende de los suscriptores y de los cambios reales, no del caudal de
        paquetes UDP.
        """
        if not meters.connected or meters.revision == self._meters_revision:
            return False
        if not meters.raw():
            return False
        if self.client_count == 0:
            return False

        # Se marca antes de entregar para no repetir el mismo estado si el
        # envío tarda y llega otro paquete UDP mientras tanto.
        self._meters_revision = meters.revision
        await self._deliver(
            {
                "type": METERS_MESSAGE_TYPE,
                "payload": {"levels": meters.levels()},
            },
            timeout=_METERS_SEND_TIMEOUT,
        )
        return True

    async def meters_loop(self, meters: MeterState, rate_hz: float) -> None:
        """Bucle que intenta difundir medidores ``rate_hz`` veces por segundo.

        El periodo se marca al terminar cada intento, así que un envío lento
        retrasa el siguiente en lugar de acumular ráfagas.
        """
        if rate_hz <= 0:
            raise ValueError("meters_rate_hz debe ser positivo")
        interval = 1.0 / rate_hz
        while True:
            await asyncio.sleep(interval)
            try:
                await self.broadcast_meters(meters)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - el bucle no debe morir
                logger.exception("WebSocket: fallo al difundir medidores")

    async def _deliver(
        self, message: dict[str, object], *, timeout: float | None = None
    ) -> None:
        """Entrega un mensaje a todos los suscriptores vivos.

        Los envíos son concurrentes para que un cliente lento no retrase al
        resto. El :class:`asyncio.Lock` mantiene el orden entre mensajes.
        """
        async with self._send_lock:
            async with self._clients_lock:
                clients = list(self._clients)
            if not clients:
                return

            delivered = await asyncio.gather(
                *(
                    self._send_one(websocket, message, timeout)
                    for websocket in clients
                )
            )
            failed = [
                websocket
                for websocket, ok in zip(clients, delivered)
                if not ok
            ]
            if failed:
                async with self._clients_lock:
                    for websocket in failed:
                        self._clients.discard(websocket)
                logger.info(
                    "WebSocket: %d suscriptor(es) descartados", len(failed)
                )

    @staticmethod
    async def _send_one(
        websocket: WebSocket,
        message: dict[str, object],
        timeout: float | None,
    ) -> bool:
        """Envía un mensaje a un suscriptor; ``False`` si falla o tarda de más."""
        try:
            if timeout is None:
                await websocket.send_json(message)
            else:
                await asyncio.wait_for(websocket.send_json(message), timeout)
            return True
        except Exception:  # noqa: BLE001 - cliente desconectado o lento
            return False

    async def on_state(self, snapshot: dict[str, object]) -> None:
        """Callback compatible con ``MixerLink.on_state``."""
        await self.broadcast(snapshot)
