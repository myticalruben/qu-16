"""Mezclador falso que habla el protocolo CMNet.

Permite probar el enlace de solo lectura sin la mesa real ni la red: escucha
en ``127.0.0.1``, responde al puerto UDP, al paquete de versión y devuelve el
volcado real de ``tests/data/qu16-state.bin`` cuando recibe la ráfaga de
inicialización.
"""

from __future__ import annotations

import asyncio
import contextlib
import struct
from pathlib import Path

from qu16.protocol.constants import Group
from qu16.protocol.framing import FrameParser, SystemPacket

#: Volcado real capturado a la Qu-16 de producción.
DEFAULT_DUMP_PATH = Path(__file__).parent / "data" / "qu16-state.bin"
#: Paquete de versión real: Qu-16, firmware 1.97, build 0x11de.
DEFAULT_VERSION_DATA = bytes.fromhex("01016101de11000000000000")
#: Puerto UDP que anuncia el mezclador falso en el handshake.
DEFAULT_MIXER_UDP_PORT = 53441


class FakeMixer:
    """Servidor asyncio mínimo con el comportamiento observable de la mesa.

    Solo implementa lo que necesita la Fase 2: handshake, volcado y conteo de
    latidos. Los comandos DSP recibidos se cuentan en :attr:`dsp_frames` para
    poder afirmar que el enlace no escribe.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        *,
        dump_path: Path | str | None = None,
        version_data: bytes = DEFAULT_VERSION_DATA,
        mixer_udp_port: int = DEFAULT_MIXER_UDP_PORT,
    ) -> None:
        self.host = host
        self.port = port
        self.dump = Path(dump_path or DEFAULT_DUMP_PATH).read_bytes()
        self.version_data = version_data
        self.mixer_udp_port = mixer_udp_port

        #: Contadores observables desde los tests.
        self.connections = 0
        self.dumps_sent = 0
        self.keepalives = 0
        self.dsp_frames = 0

        self._server: asyncio.AbstractServer | None = None
        self._clients: set[asyncio.StreamWriter] = set()

    async def start(self) -> "FakeMixer":
        """Levanta el servidor en el puerto indicado (0 = uno libre)."""
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        socket = self._server.sockets[0]
        self.port = socket.getsockname()[1]
        return self

    async def close(self) -> None:
        """Cierra el servidor y todas las conexiones activas."""
        server, self._server = self._server, None
        if server is not None:
            server.close()
            await server.wait_closed()
        for writer in list(self._clients):
            writer.close()
        self._clients.clear()

    async def __aenter__(self) -> "FakeMixer":
        return await self.start()

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def drop_clients(self) -> None:
        """Cierra las conexiones activas para simular un corte de la mesa."""
        for writer in list(self._clients):
            writer.close()

    # ------------------------------------------------------------------ interno

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.connections += 1
        self._clients.add(writer)
        parser = FrameParser()
        handshaken = False
        dump_sent = False
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                for frame in parser.feed(chunk):
                    if not isinstance(frame, SystemPacket):
                        # Cualquier 0xF7 es un comando DSP: no debe ocurrir.
                        self.dsp_frames += 1
                        continue

                    if frame.group == Group.UDP_PORT and not handshaken:
                        await self._write(
                            writer,
                            SystemPacket(
                                Group.UDP_PORT,
                                struct.pack("<H", self.mixer_udp_port),
                            ),
                        )
                    elif frame.group == Group.CONTROL and not handshaken:
                        await self._write(
                            writer,
                            SystemPacket(Group.VERSION, self.version_data),
                        )
                        handshaken = True
                    elif frame.group == Group.CONTROL:
                        if len(frame.data) >= 4 and not dump_sent:
                            # Ráfaga de init: responde con el volcado real.
                            dump_sent = True
                            self.dumps_sent += 1
                            await self._write(
                                writer,
                                SystemPacket(Group.STATE_DUMP, self.dump),
                            )
                        elif frame.data == b"\x01\x00":
                            self.keepalives += 1
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            self._clients.discard(writer)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    @staticmethod
    async def _write(writer: asyncio.StreamWriter, packet: SystemPacket) -> None:
        writer.write(packet.encode())
        await writer.drain()
