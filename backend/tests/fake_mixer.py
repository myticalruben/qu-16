"""Mezclador falso que habla el protocolo CMNet.

Permite probar el enlace de solo lectura sin la mesa real ni la red: escucha
en ``127.0.0.1``, responde al puerto UDP, al paquete de versión, devuelve el
volcado real de ``tests/data/qu16-state.bin`` cuando recibe la ráfaga de
inicialización y, si se pide, envía por UDP los dos bancos de medidores de
``tests/data/meter-bank-*.hex``.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
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
#: Datagramas reales de los dos bancos de medidores.
METER_BANK_FILES = ("meter-bank-a.hex", "meter-bank-b.hex")


class FakeMixer:
    """Servidor asyncio mínimo con el comportamiento observable de la mesa.

    Implementa lo que necesita la Fase 2: handshake, volcado, conteo de
    latidos y, opcionalmente, el envío periódico de medidores al puerto UDP que
    el cliente anuncia. Los comandos DSP recibidos se cuentan en
    :attr:`dsp_frames` para poder afirmar que el enlace no escribe.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        *,
        dump_path: Path | str | None = None,
        version_data: bytes = DEFAULT_VERSION_DATA,
        mixer_udp_port: int = DEFAULT_MIXER_UDP_PORT,
        send_meters: bool = True,
        meter_interval: float = 0.02,
    ) -> None:
        self.host = host
        self.port = port
        self.dump = Path(dump_path or DEFAULT_DUMP_PATH).read_bytes()
        self.version_data = version_data
        self.mixer_udp_port = mixer_udp_port
        self.send_meters = send_meters
        self.meter_interval = meter_interval

        data_dir = Path(__file__).parent / "data"
        self.meter_packets = tuple(
            bytes.fromhex((data_dir / name).read_text().strip())
            for name in METER_BANK_FILES
        )

        #: Contadores observables desde los tests.
        self.connections = 0
        self.dumps_sent = 0
        self.keepalives = 0
        self.dsp_frames = 0
        #: Puerto UDP que anunció el cliente en el handshake.
        self.client_udp_port: int | None = None
        self.meter_packets_sent = 0

        self._server: asyncio.AbstractServer | None = None
        self._clients: set[asyncio.StreamWriter] = set()
        self._meter_tasks: set[asyncio.Task[None]] = set()

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
        await self._cancel_meter_tasks()
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
        meter_task: asyncio.Task[None] | None = None
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
                        if len(frame.data) >= 2:
                            self.client_udp_port = struct.unpack(
                                "<H", frame.data[:2]
                            )[0]
                            if self.send_meters and meter_task is None:
                                meter_task = asyncio.create_task(
                                    self._pump_meters()
                                )
                                self._meter_tasks.add(meter_task)
                                meter_task.add_done_callback(
                                    self._meter_tasks.discard
                                )
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
            if meter_task is not None:
                meter_task.cancel()
                self._meter_tasks.discard(meter_task)
                with contextlib.suppress(asyncio.CancelledError):
                    await meter_task
            self._clients.discard(writer)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _pump_meters(self) -> None:
        """Envía los bancos de medidores al puerto UDP que anunció el cliente.

        Usa los datagramas reales de ``tests/data`` y repite el par de bancos
        cada ``meter_interval`` segundos, como hace la mesa.
        """
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        try:
            while True:
                if self.client_udp_port is None:
                    return
                target = (self.host, self.client_udp_port)
                for packet in self.meter_packets:
                    try:
                        await loop.sock_sendto(sock, packet, target)
                    except OSError:
                        # El puerto del cliente aún no escucha: se reintenta.
                        break
                    self.meter_packets_sent += 1
                await asyncio.sleep(self.meter_interval)
        except asyncio.CancelledError:
            raise
        finally:
            sock.close()

    async def _cancel_meter_tasks(self) -> None:
        """Cancela y espera las tareas de envío de medidores."""
        tasks = list(self._meter_tasks)
        self._meter_tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def _write(writer: asyncio.StreamWriter, packet: SystemPacket) -> None:
        writer.write(packet.encode())
        await writer.drain()
