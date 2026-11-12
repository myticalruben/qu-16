"""Cliente asíncrono del protocolo de control CMNet de Allen & Heath Qu."""

from __future__ import annotations

import asyncio
import struct
from typing import Callable, Iterable

from .protocol import constants as C
from .protocol.framing import DspCommand, Frame, FrameParser, MixerVersion, SystemPacket

#: Secuencia de inicialización que envía Mixing Station tras el handshake.
#: El volcado de estado (grupo 0x06) llega justo después de esta ráfaga.
_INIT_HEX = (
    "7f04240013000000ffffffffffff9f0f0000000000000000000000000000000000e003c0ffffff7f",
    "7f04240015000000fac1230604000028d1041c000000000000000000000000000000000000000000",
    "7f04020002007f0402000f007f04020007007f04020006007f0404001b6400007f0404001a640000"
    "7f040400196400007f04020011007f0402001200",
)
INIT_SEQUENCE: tuple[bytes, ...] = tuple(bytes.fromhex(h) for h in _INIT_HEX)


class QuError(RuntimeError):
    """Error de protocolo o de conexión con la mesa."""


class QuClient:
    """Conexión TCP al puerto 51326 con handshake estilo Qu-Pad."""

    def __init__(
        self,
        host: str,
        port: int = C.CONTROL_PORT,
        *,
        udp_port: int = 53441,
        client_type: int = C.ClientType.QU_PAD,
        timeout: float = 6.0,
    ) -> None:
        self.host = host
        self.port = port
        self.udp_port = udp_port
        self.client_type = client_type
        self.timeout = timeout

        self.version: MixerVersion | None = None
        self.mixer_udp_port: int | None = None

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._parser = FrameParser()
        self._frames: asyncio.Queue[Frame] = asyncio.Queue()
        self._reader_task: asyncio.Task[None] | None = None
        self._closed = False

    # ------------------------------------------------------------------ ciclo

    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), self.timeout
        )
        self._reader_task = asyncio.create_task(self._pump())

    async def close(self) -> None:
        self._closed = True
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reader_task = None
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
        self._reader = None

    async def __aenter__(self) -> "QuClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ------------------------------------------------------------------- I/O

    async def _pump(self) -> None:
        assert self._reader is not None
        try:
            while not self._closed:
                chunk = await self._reader.read(65536)
                if not chunk:
                    break
                for frame in self._parser.feed(chunk):
                    self._frames.put_nowait(frame)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    async def send(self, packet: SystemPacket | DspCommand) -> None:
        if self._writer is None:
            raise QuError("cliente no conectado")
        self._writer.write(packet.encode())
        await self._writer.drain()

    async def send_raw(self, blob: bytes) -> None:
        if self._writer is None:
            raise QuError("cliente no conectado")
        self._writer.write(blob)
        await self._writer.drain()

    async def wait_for(
        self,
        predicate: Callable[[Frame], bool],
        *,
        timeout: float | None = None,
        description: str = "trama",
    ) -> Frame:
        """Espera la primera trama que cumpla ``predicate``; descarta el resto."""
        limit = self.timeout if timeout is None else timeout
        try:
            return await asyncio.wait_for(self._pull(predicate), limit)
        except asyncio.TimeoutError as exc:
            raise QuError(f"tiempo agotado esperando {description}") from exc

    async def _pull(self, predicate: Callable[[Frame], bool]) -> Frame:
        while True:
            frame = await self._frames.get()
            if predicate(frame):
                return frame

    async def collect(self, duration: float) -> list[Frame]:
        """Recoge todas las tramas recibidas durante ``duration`` segundos."""
        frames: list[Frame] = []
        loop = asyncio.get_running_loop()
        deadline = loop.time() + duration
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                frames.append(await asyncio.wait_for(self._frames.get(), remaining))
            except asyncio.TimeoutError:
                break
        return frames

    # -------------------------------------------------------------- handshake

    async def handshake(self) -> MixerVersion:
        """Ejecuta el handshake completo y devuelve la versión de la mesa."""
        await self.send(SystemPacket(C.Group.UDP_PORT, struct.pack("<H", self.udp_port)))

        port_packet = await self.wait_for(
            lambda f: isinstance(f, SystemPacket) and f.group == C.Group.UDP_PORT,
            description="puerto UDP de la mesa",
        )
        assert isinstance(port_packet, SystemPacket)
        self.mixer_udp_port = struct.unpack("<H", port_packet.data)[0]

        await self.send(
            SystemPacket(C.Group.CONTROL, struct.pack("<H", self.client_type))
        )

        version_packet = await self.wait_for(
            lambda f: isinstance(f, SystemPacket) and f.group == C.Group.VERSION,
            description="paquete de versión",
        )
        assert isinstance(version_packet, SystemPacket)
        self.version = MixerVersion.from_bytes(version_packet.data)
        return self.version

    async def request_state_dump(self, *, timeout: float = 8.0) -> bytes:
        """Envía la ráfaga de inicialización y devuelve el volcado de estado."""
        for blob in INIT_SEQUENCE:
            await self.send_raw(blob)

        dump = await self.wait_for(
            lambda f: isinstance(f, SystemPacket) and f.group == C.Group.STATE_DUMP,
            timeout=timeout,
            description="volcado de estado (grupo 0x06)",
        )
        assert isinstance(dump, SystemPacket)
        return dump.data

    async def read_frames(self, duration: float) -> Iterable[Frame]:
        return await self.collect(duration)
