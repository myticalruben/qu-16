"""Tests del enlace de solo lectura contra el mezclador falso."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from fake_mixer import FakeMixer
from qu16.link import WRITE_ENABLED, MixerLink
from qu16.mirror import StateMirror

#: 60 bloques de canal en el volcado real de la Qu-16.
EXPECTED_CHANNELS = 60


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
    mixer = await FakeMixer().start()
    mirror = StateMirror()
    snapshots: list[dict[str, object]] = []
    link = MixerLink(
        "127.0.0.1",
        mixer.port,
        mirror=mirror,
        on_state=snapshots.append,
        keepalive_interval=0.02,
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
        assert channels[0]["kind"] == "stereo"
        assert channels[19]["kind"] == "other"
        assert channels[0]["name"] == "inala1"

        # La Fase 2 no escribe: ni comandos DSP ni tráfico con marcador 0xF7.
        assert WRITE_ENABLED is False
        assert mixer.dsp_frames == 0

        # El keepalive se envía mientras la sesión está viva.
        assert await wait_for(lambda: mixer.keepalives >= 1)
    finally:
        await link.stop()
        await mixer.close()


async def test_link_marks_disconnected_when_mixer_closes() -> None:
    """Si la mesa cierra la conexión, el enlace publica ``connected=False``."""
    mixer = await FakeMixer().start()
    mirror = StateMirror()
    snapshots: list[dict[str, object]] = []
    link = MixerLink(
        "127.0.0.1",
        mixer.port,
        mirror=mirror,
        on_state=snapshots.append,
        keepalive_interval=0.02,
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
