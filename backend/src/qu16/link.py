"""Enlace de solo lectura con la mesa Qu-16.

Gestiona el ciclo de vida de la conexión TCP: handshake, volcado de estado,
keepalive y reconexión exponencial con jitter. Todo ocurre en una tarea de
fondo para no bloquear el arranque de la API.

La Fase 2 es estrictamente de lectura: el enlace puede hacer handshake, pedir
el volcado y mandar el latido, pero nunca comandos DSP (``DspCommand``,
marcador ``0xF7``). Ver :data:`WRITE_ENABLED`.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import random
from collections.abc import Awaitable, Callable

from .client import QuClient
from .mirror import StateMirror
from .protocol import constants as C
from .protocol.framing import DspCommand, SystemPacket

logger = logging.getLogger(__name__)

#: La escritura en la mesa se habilita en la Fase 4 y solo tras confirmación
#: explícita con el operador. Mientras esté en ``False`` el enlace rechaza
#: cualquier ``DspCommand`` antes de llegar al socket.
WRITE_ENABLED = False

#: Latido que espera la mesa para no dar la sesión por perdida. No es un
#: comando DSP: es una trama de sistema del grupo CONTROL.
KEEPALIVE_PAYLOAD = b"\x01\x00"

#: Callback que recibe cada instantánea del espejo.
SnapshotCallback = Callable[[dict[str, object]], Awaitable[None] | None]


class WriteDisabledError(RuntimeError):
    """Se intentó enviar un comando DSP con la escritura deshabilitada."""


class MixerLink:
    """Conexión persistente y de solo lectura con la mesa.

    ``start()`` no espera a que la mesa responda: lanza una tarea que intenta
    conectar y reintenta con retroceso exponencial. ``stop()`` la cancela y
    cierra el socket.
    """

    def __init__(
        self,
        host: str,
        port: int = C.CONTROL_PORT,
        *,
        mirror: StateMirror | None = None,
        on_state: SnapshotCallback | None = None,
        reconnect_min: float = 1.0,
        reconnect_max: float = 30.0,
        keepalive_interval: float = 0.5,
        udp_port: int = 53441,
        timeout: float = 6.0,
        jitter: float = 0.1,
    ) -> None:
        if reconnect_min <= 0 or reconnect_max < reconnect_min:
            raise ValueError("rango de reconexión inválido")
        if keepalive_interval <= 0:
            raise ValueError("keepalive_interval debe ser positivo")

        self.host = host
        self.port = port
        self.mirror = mirror if mirror is not None else StateMirror()
        self.reconnect_min = reconnect_min
        self.reconnect_max = reconnect_max
        self.keepalive_interval = keepalive_interval
        self.udp_port = udp_port
        self.timeout = timeout
        self.jitter = jitter

        self._on_state = on_state
        self._task: asyncio.Task[None] | None = None
        self._client: QuClient | None = None

    # ------------------------------------------------------------------ ciclo

    def start(self) -> None:
        """Lanza el bucle de conexión en segundo plano (idempotente)."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="qu16-link")

    async def stop(self) -> None:
        """Cancela el bucle, cierra la conexión y publica el estado final."""
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._discard_client()
        await self.mirror.mark_disconnected()
        await self._publish()

    @property
    def running(self) -> bool:
        """``True`` mientras la tarea de fondo siga viva."""
        return self._task is not None and not self._task.done()

    # ------------------------------------------------------------- bucle

    async def _run(self) -> None:
        """Conecta, mantiene la sesión y reintenta con retroceso exponencial."""
        delay = self.reconnect_min
        while True:
            connected = False
            try:
                client = QuClient(
                    self.host,
                    self.port,
                    udp_port=self.udp_port,
                    timeout=self.timeout,
                )
                self._client = client
                await client.connect()
                version = await client.handshake()

                # Conectado, aún sin volcado: la interfaz puede reaccionar ya.
                await self.mirror.mark_connected(version)
                await self._publish()
                connected = True

                raw = await client.request_state_dump()
                await self.mirror.update_from_dump(version, raw)
                await self._publish()

                # Sesión sana: el siguiente corte vuelve a reintentar en el
                # mínimo, no en el máximo acumulado.
                delay = self.reconnect_min
                await self._keepalive(client)
                logger.warning("enlace: la mesa cerró la conexión")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - el bucle no debe morir
                logger.warning(
                    "enlace: %s: %s (reintento en %.2f s)",
                    type(exc).__name__,
                    exc,
                    delay,
                )
            finally:
                await self._discard_client()

            if connected:
                await self.mirror.mark_disconnected()
                await self._publish()

            # Espera con jitter para no sincronizar reintentos entre clientes.
            await asyncio.sleep(self._retry_delay(delay))
            delay = min(delay * 2, self.reconnect_max)

    def _retry_delay(self, base: float) -> float:
        """Retardo de reintento con jitter uniforme en torno a ``base``."""
        spread = base * self.jitter
        return max(0.0, base + random.uniform(-spread, spread))

    # ------------------------------------------------------------- sesión

    async def _keepalive(self, client: QuClient) -> None:
        """Manda el latido cada ``keepalive_interval`` segundos.

        Termina —sin excepción— cuando el lector detecta que la conexión se
        cerró; si el envío falla, la excepción sube y el bucle de conexión
        cierra el cliente y reintenta.
        """
        while True:
            await asyncio.sleep(self.keepalive_interval)
            if not client.connected:
                logger.info("enlace: conexión cerrada por la mesa")
                return
            await self._send(
                client, SystemPacket(C.Group.CONTROL, KEEPALIVE_PAYLOAD)
            )

    async def _send(
        self, client: QuClient, packet: SystemPacket | DspCommand
    ) -> None:
        """Único punto de salida hacia la mesa; bloquea comandos DSP en Fase 2."""
        if isinstance(packet, DspCommand) and not WRITE_ENABLED:
            raise WriteDisabledError(
                "escritura deshabilitada: los comandos DSP se habilitan en la Fase 4"
            )
        await client.send(packet)

    async def _publish(self) -> None:
        """Entrega la instantánea actual al callback, sin romper el bucle."""
        if self._on_state is None:
            return
        snapshot = await self.mirror.snapshot()
        try:
            result = self._on_state(snapshot)
            if inspect.isawaitable(result):
                await result
        except Exception:  # noqa: BLE001 - un suscriptor no debe tumbar el enlace
            logger.exception("enlace: el callback on_state falló")

    async def _discard_client(self) -> None:
        """Cierra y olvida el cliente actual, ignorando errores de cierre."""
        client, self._client = self._client, None
        if client is None:
            return
        with contextlib.suppress(Exception):
            await client.close()
