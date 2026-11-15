"""Enlace con la mesa Qu-16.

Gestiona el ciclo de vida de la conexión TCP: handshake, volcado de estado,
keepalive y reconexión exponencial con jitter. Todo ocurre en una tarea de
fondo para no bloquear el arranque de la API. Mientras la sesión está viva
también escucha los medidores por UDP en el puerto anunciado y actualiza un
:class:`~qu16.meters.MeterState` compartido; si ese socket no se puede abrir,
el enlace de control sigue funcionando sin medidores.

La mesa puede dejar de enviar avisos de cambio DSP aunque siga respondiendo al
volcado. Por eso, si ``poll_interval`` es positivo, un bucle de fondo pide un
volcado periódico y refresca el espejo; sin ese sondeo la interfaz se quedaría
congelada tras una escritura.

Las escrituras DSP (``DspCommand``, marcador ``0xF7``) están protegidas por dos
interruptores: :data:`WRITE_ENABLED`, permiso de la capa de protocolo, y
``write_enabled`` de cada enlace. El interruptor real y por defecto es
``QU16_WRITE_ENABLED`` de la API (apagado).
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import random
import socket
from collections.abc import Awaitable, Callable

from . import dsp
from .client import QuClient, QuError
from .meters import MeterState, decode_packet
from .mirror import StateMirror
from .protocol import constants as C
from .protocol.framing import DspCommand, SystemPacket

logger = logging.getLogger(__name__)

#: Permiso de la capa de protocolo para enviar comandos DSP. El interruptor
#: real y por defecto es ``QU16_WRITE_ENABLED`` (apagado): la API lo lee y lo
#: pasa como ``write_enabled`` al crear el enlace. Además, cada enlace debe
#: crearse con ``write_enabled=True``. Con cualquiera de los dos en ``False`` el
#: enlace rechaza cualquier ``DspCommand`` antes de llegar al socket.
WRITE_ENABLED = True

#: Latido que espera la mesa para no dar la sesión por perdida. No es un
#: comando DSP: es una trama de sistema del grupo CONTROL.
KEEPALIVE_PAYLOAD = b"\x01\x00"

#: Callback que recibe cada instantánea del espejo.
SnapshotCallback = Callable[[dict[str, object]], Awaitable[None] | None]


class WriteDisabledError(RuntimeError):
    """Se intentó enviar un comando DSP con la escritura deshabilitada."""


class _MeterProtocol(asyncio.DatagramProtocol):
    """Protocolo UDP mínimo que reenvía cada datagrama a un receptor."""

    def __init__(self, receiver: "MeterReceiver") -> None:
        self._receiver = receiver

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._receiver.datagram_received(data, addr)

    def error_received(self, exc: Exception) -> None:
        # Un ICMP de puerto cerrado no debe afectar a la sesión de control.
        logger.debug("medidores: error en el socket UDP: %s", exc)


class MeterReceiver:
    """Receptor UDP de medidores ligado al ciclo de vida de una sesión.

    Escucha en ``0.0.0.0:<meters_port>`` y descarta los datagramas que no
    procedan de la IP de la mesa. La apertura es tolerante a fallos: si el
    puerto está ocupado, ``open()`` devuelve ``False`` y el enlace de control
    sigue funcionando sin medidores.
    """

    def __init__(self, mixer_host: str, port: int, meters: MeterState) -> None:
        self.mixer_host = mixer_host
        self.port = port
        self.meters = meters
        self._transport: asyncio.DatagramTransport | None = None
        self._sources: frozenset[str] = frozenset({mixer_host})

    @property
    def bound_port(self) -> int | None:
        """Puerto local realmente abierto (útil si se pidió el puerto 0)."""
        if self._transport is None:
            return None
        sockname = self._transport.get_extra_info("sockname")
        return None if sockname is None else int(sockname[1])

    async def open(self) -> bool:
        """Abre el socket UDP; devuelve ``False`` si no se pudo enlazar."""
        loop = asyncio.get_running_loop()
        self._sources = await self._resolve_sources(loop)
        try:
            transport, _ = await loop.create_datagram_endpoint(
                lambda: _MeterProtocol(self),
                local_addr=("0.0.0.0", self.port),
            )
        except OSError as exc:
            logger.warning(
                "medidores: no se pudo abrir 0.0.0.0:%d (%s); "
                "el enlace sigue sin medidores",
                self.port,
                exc,
            )
            return False

        self._transport = transport
        logger.info(
            "medidores: escuchando en 0.0.0.0:%d",
            self.bound_port if self.bound_port is not None else self.port,
        )
        return True

    def close(self) -> None:
        """Cierra el socket UDP (idempotente)."""
        transport, self._transport = self._transport, None
        if transport is not None:
            transport.close()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Decodifica un datagrama del banco y actualiza el estado compartido."""
        if addr[0] not in self._sources:
            logger.debug("medidores: datagrama ignorado de %s", addr[0])
            return
        packet = decode_packet(data)
        if packet is not None:
            self.meters.update(packet)

    async def _resolve_sources(self, loop: asyncio.AbstractEventLoop) -> frozenset[str]:
        """Resuelve la IP de la mesa para filtrar por origen del datagrama."""
        try:
            infos = await loop.getaddrinfo(
                self.mixer_host,
                None,
                family=socket.AF_INET,
                type=socket.SOCK_DGRAM,
            )
        except OSError:
            return frozenset({self.mixer_host})
        return frozenset(info[4][0] for info in infos)


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
        meters: MeterState | None = None,
        meters_enabled: bool = True,
        write_enabled: bool = False,
        meters_port: int = 53441,
        reconnect_min: float = 1.0,
        reconnect_max: float = 30.0,
        keepalive_interval: float = 0.5,
        poll_interval: float = 2.0,
        timeout: float = 6.0,
        jitter: float = 0.1,
    ) -> None:
        self.write_enabled = write_enabled
        if reconnect_min <= 0 or reconnect_max < reconnect_min:
            raise ValueError("rango de reconexión inválido")
        if keepalive_interval <= 0:
            raise ValueError("keepalive_interval debe ser positivo")
        if poll_interval < 0:
            raise ValueError("poll_interval no puede ser negativo")
        if not 0 <= meters_port <= 65535:
            raise ValueError("meters_port fuera de rango")

        self.host = host
        self.port = port
        self.mirror = mirror if mirror is not None else StateMirror()
        self.meters = meters if meters is not None else MeterState()
        self.meters_enabled = meters_enabled
        self.meters_port = meters_port
        self.reconnect_min = reconnect_min
        self.reconnect_max = reconnect_max
        self.keepalive_interval = keepalive_interval
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.jitter = jitter

        self._on_state = on_state
        self._task: asyncio.Task[None] | None = None
        self._client: QuClient | None = None
        self._meter_receiver: MeterReceiver | None = None

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
        self._close_meter_receiver()
        self.meters.mark_disconnected()
        await self.mirror.mark_disconnected()
        await self._publish()

    @property
    def running(self) -> bool:
        """``True`` mientras la tarea de fondo siga viva."""
        return self._task is not None and not self._task.done()

    @property
    def connected(self) -> bool:
        """``True`` si hay una sesión TCP viva con la mesa."""
        client = self._client
        return client is not None and client.connected

    @property
    def meters_open(self) -> bool:
        """``True`` si el receptor UDP de medidores está abierto."""
        return self._meter_receiver is not None

    @property
    def udp_port(self) -> int:
        """Puerto UDP que se anuncia en el handshake.

        Coincide con ``meters_port`` salvo que se haya pedido el puerto 0: en
        ese caso devuelve el puerto efímero que asignó el sistema.
        """
        return self._announced_meters_port()

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
                    udp_port=self.meters_port,
                    timeout=self.timeout,
                )
                self._client = client
                await client.connect()

                # El receptor UDP se abre al conectar y se cierra en el
                # finally; si falla el enlace sigue sin medidores.
                if self.meters_enabled and await self._open_meter_receiver():
                    client.udp_port = self._announced_meters_port()
                    self.meters.mark_connected()

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
                # El sondeo convive con el latido: cada uno en su tarea. El
                # finally cancela el sondeo también si el latido falla o si
                # ``stop()`` cancela el bucle de conexión.
                poll_task = self._start_polling(client)
                try:
                    await self._keepalive(client)
                finally:
                    await self._stop_polling(poll_task)
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
                # Se limpia primero el UDP (síncrono) para que una cancelación
                # durante el cierre del cliente no deje el socket abierto.
                self._close_meter_receiver()
                self.meters.mark_disconnected()
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

    # ------------------------------------------------------------- medidores

    async def _open_meter_receiver(self) -> bool:
        """Abre el receptor UDP de medidores; ``False`` si no se pudo enlazar."""
        if self._meter_receiver is not None:
            return True
        receiver = MeterReceiver(self.host, self.meters_port, self.meters)
        if not await receiver.open():
            return False
        self._meter_receiver = receiver
        return True

    def _close_meter_receiver(self) -> None:
        """Cierra el receptor UDP de medidores, si estaba abierto."""
        receiver, self._meter_receiver = self._meter_receiver, None
        if receiver is not None:
            receiver.close()

    def _announced_meters_port(self) -> int:
        """Puerto que se anuncia en el handshake (el real si se pidió 0)."""
        receiver = self._meter_receiver
        if receiver is not None and receiver.bound_port is not None:
            return receiver.bound_port
        return self.meters_port

    # ------------------------------------------------------------- sesión

    def _start_polling(self, client: QuClient) -> asyncio.Task[None] | None:
        """Lanza el sondeo periódico del estado si está configurado."""
        if self.poll_interval <= 0:
            return None
        return asyncio.create_task(self._poll(client), name="qu16-poll")

    async def _stop_polling(self, task: asyncio.Task[None] | None) -> None:
        """Cancela y espera el sondeo; tolera que ya haya terminado."""
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def _poll(self, client: QuClient) -> None:
        """Pide un volcado cada ``poll_interval`` y refresca el espejo.

        El bucle es estrictamente secuencial: espera el intervalo, espera a que
        termine el volcado, actualiza el espejo y solo entonces vuelve a
        esperar. Por eso un volcado más lento que el intervalo no se solapa con
        el siguiente. Un error puntual se registra y el bucle continúa: el
        sondeo no debe tumbar la sesión ni la reconexión.
        """
        while self.poll_interval > 0:
            await asyncio.sleep(self.poll_interval)
            if not client.connected:
                return
            try:
                raw = await client.request_state_dump()
                await self.mirror.update_from_dump(client.version, raw)
                await self._publish()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - el bucle no debe morir
                logger.warning(
                    "enlace: fallo en el sondeo de estado: %s: %s",
                    type(exc).__name__,
                    exc,
                )

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
        """Único punto de salida hacia la mesa; filtra los comandos DSP."""
        if isinstance(packet, DspCommand) and not (
            WRITE_ENABLED and self.write_enabled
        ):
            raise WriteDisabledError(
                "escritura deshabilitada: requiere WRITE_ENABLED y write_enabled"
            )
        await client.send(packet)

    async def set_level(self, channel: int, raw: int) -> None:
        """Fija el nivel principal de un canal (escritura en la mesa).

        Requiere que el enlace se haya creado con ``write_enabled=True``. El
        valor es el crudo de 16 bits de la misma escala que el volcado.

        Tras enviar el comando aplica el valor al espejo y publica el estado,
        para que la interfaz no espere al siguiente sondeo. No hay confirmación
        por eco: si la mesa ajusta el valor, el sondeo lo corregirá.
        """
        if not self.write_enabled:
            raise WriteDisabledError(
                "el enlace se creó en solo lectura; pasa write_enabled=True"
            )
        client = self._client
        if client is None or not client.connected:
            raise QuError("sin conexión con la mesa")
        value = max(0, min(0xFFFF, raw))
        await self._send(client, dsp.main_level(channel, value))
        await self.mirror.apply_level(channel, value)
        await self._publish()

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
