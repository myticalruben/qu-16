"""Tests del enlace contra el mezclador falso: volcado, sondeo y escritura."""

from __future__ import annotations

import asyncio
import contextlib
import struct
from collections.abc import Callable
from pathlib import Path

from fake_mixer import FakeMixer
from qu16.link import WRITE_ENABLED, MixerLink
from qu16.mirror import StateMirror
from qu16.protocol import dump as dump_module

#: 60 bloques de canal en el volcado real de la Qu-16.
EXPECTED_CHANNELS = 60
#: Volcado real usado por el cliente lento del test de solapamiento.
DUMP_PATH = Path(__file__).parent / "data" / "qu16-state.bin"


def _with_level(dump: bytes, index: int, value: int) -> bytes:
    """Devuelve una copia del volcado con otro nivel en el canal indicado."""
    state = dump_module.parse(dump)
    offset = state.channels[index].offset + dump_module.OFF_MAIN_SEND
    data = bytearray(dump)
    struct.pack_into("<H", data, offset, value)
    return bytes(data)


async def wait_for(
    predicate: Callable[[], bool], *, timeout: float = 3.0, interval: float = 0.01
) -> bool:
    """Espera a que ``predicate()`` sea verdadero, con un límite de tiempo."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return predicate()


async def test_link_builds_mirror_from_fake_mixer() -> None:
    """El enlace completa handshake + volcado y el espejo queda poblado."""
    mixer = await FakeMixer(send_meters=False).start()
    mirror = StateMirror()
    snapshots: list[dict[str, object]] = []
    link = MixerLink(
        "127.0.0.1",
        mixer.port,
        mirror=mirror,
        on_state=snapshots.append,
        keepalive_interval=0.02,
        poll_interval=0,
        meters_enabled=False,
        reconnect_min=0.05,
        reconnect_max=0.2,
    )
    try:
        link.start()
        assert await wait_for(lambda: mirror.connected)
        assert await wait_for(lambda: mirror.channel_count == EXPECTED_CHANNELS)

        # El callback se invoca al conectar (sin canales) y al recibir el volcado.
        assert snapshots[0]["connected"] is True
        assert snapshots[0]["channels"] == []
        assert any(len(item["channels"]) == EXPECTED_CHANNELS for item in snapshots)

        snapshot = await mirror.snapshot()
        assert snapshot["connected"] is True
        assert snapshot["model"] == "QU-16"
        assert snapshot["firmware"] == "1.97"
        assert isinstance(snapshot["updated_at"], str)
        assert snapshot["updated_at"].endswith("+00:00")

        channels = snapshot["channels"]
        assert len(channels) == EXPECTED_CHANNELS
        assert channels[3] == {
            "index": 3,
            "name": "coro1",
            "level_db": 4.9,
            "kind": "input",
        }
        # Calibrado contra la mesa: canal 1 = índice 0, así que 0-15 son entradas.
        assert channels[0]["kind"] == "input"
        assert channels[16]["kind"] == "stereo"
        assert channels[19]["kind"] == "other"
        assert channels[0]["name"] == "inala1"

        # La capa de protocolo permite escribir, pero este enlace se creó en
        # solo lectura: no debe salir ningún comando DSP.
        assert WRITE_ENABLED is True
        assert link.write_enabled is False
        assert mixer.dsp_frames == 0

        # El keepalive se envía mientras la sesión está viva.
        assert await wait_for(lambda: mixer.keepalives >= 1)
    finally:
        await link.stop()
        await mixer.close()


async def test_link_marks_disconnected_when_mixer_closes() -> None:
    """Si la mesa cierra la conexión, el enlace publica ``connected=False``."""
    mixer = await FakeMixer(send_meters=False).start()
    mirror = StateMirror()
    snapshots: list[dict[str, object]] = []
    link = MixerLink(
        "127.0.0.1",
        mixer.port,
        mirror=mirror,
        on_state=snapshots.append,
        keepalive_interval=0.02,
        poll_interval=0,
        meters_enabled=False,
        reconnect_min=0.05,
        reconnect_max=0.2,
    )
    try:
        link.start()
        assert await wait_for(lambda: mirror.channel_count == EXPECTED_CHANNELS)

        mixer.drop_clients()

        def saw_disconnect() -> bool:
            return any(item["connected"] is False for item in snapshots)

        assert await wait_for(saw_disconnect)
        # El último estado conocido se conserva para que la UI pueda mostrarlo.
        disconnected = [
            item for item in snapshots if item["connected"] is False
        ][-1]
        assert len(disconnected["channels"]) == EXPECTED_CHANNELS
        assert disconnected["model"] == "QU-16"
    finally:
        await link.stop()
        await mixer.close()


async def test_poll_refreshes_mirror_when_mixer_stops_notifying() -> None:
    """El sondeo periódico trae los cambios que la mesa no notifica."""
    mixer = await FakeMixer(send_meters=False).start()
    mirror = StateMirror()
    snapshots: list[dict[str, object]] = []
    link = MixerLink(
        "127.0.0.1",
        mixer.port,
        mirror=mirror,
        on_state=snapshots.append,
        keepalive_interval=0.02,
        poll_interval=0.05,
        meters_enabled=False,
        reconnect_min=0.05,
        reconnect_max=0.2,
    )
    try:
        link.start()
        assert await wait_for(lambda: mirror.channel_count == EXPECTED_CHANNELS)
        assert mirror.channels[3].level_db == 4.9
        assert await wait_for(lambda: mixer.dumps_sent >= 2)

        # La mesa cambia el nivel del canal 3 y no manda aviso: solo el
        # siguiente volcado del sondeo puede reflejarlo.
        mixer.dump = _with_level(mixer.dump, 3, 0x765C)  # 0.0 dB

        assert await wait_for(lambda: mirror.channels[3].level_db == 0.0)
        assert any(
            item["channels"] and item["channels"][3]["level_db"] == 0.0
            for item in snapshots
        )
    finally:
        await link.stop()
        await mixer.close()


async def test_poll_waits_for_slow_dump_before_next_one() -> None:
    """Con un volcado más lento que el intervalo, el sondeo espera."""
    dump = DUMP_PATH.read_bytes()

    class SlowClient:
        """Cliente falso que tarda en devolver cada volcado."""

        connected = True
        version = None
        calls = 0
        active = 0
        max_active = 0

        async def request_state_dump(self) -> bytes:
            self.calls += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            try:
                await asyncio.sleep(0.05)
                return dump
            finally:
                self.active -= 1

    mirror = StateMirror()
    link = MixerLink("127.0.0.1", mirror=mirror, poll_interval=0.01)
    client = SlowClient()
    task = asyncio.create_task(link._poll(client))  # type: ignore[arg-type]
    try:
        await asyncio.sleep(0.23)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    # Hubo varios volcados, pero nunca dos en vuelo a la vez.
    assert client.calls >= 2
    assert client.max_active == 1
    assert mirror.channel_count == EXPECTED_CHANNELS
