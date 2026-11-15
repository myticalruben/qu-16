"""Tests de la API de escritura de niveles y de la configuración del mixer."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx
import pytest
from fake_mixer import FakeMixer
from qu16 import dsp
from qu16.link import MixerLink
from qu16.protocol import fader_law
from qu16_api.config import Settings, get_settings
from qu16_api.main import app
from qu16_api.state import state_mirror

#: 60 bloques de canal en el volcado real de la Qu-16.
EXPECTED_CHANNELS = 60
#: Nivel de prueba: 32000 crudo equivale a 6.9 dB en la ley de fader.
TEST_VALUE = 32000
TEST_DB = 6.9


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


@pytest.fixture
async def api_client() -> httpx.AsyncClient:
    """Cliente HTTP con el ciclo de vida de la aplicación arrancado."""
    app.dependency_overrides.clear()
    app.state.mixer_link = None
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
    app.dependency_overrides.clear()
    app.state.mixer_link = None


def _enable_writes() -> None:
    """Sustituye los ajustes por unos con el candado de escritura abierto."""
    app.dependency_overrides[get_settings] = lambda: Settings(write_enabled=True)


async def _start_link(
    snapshots: list[dict[str, object]] | None = None,
) -> tuple[MixerLink, FakeMixer]:
    """Levanta la mesa falsa y un enlace de escritura ya sincronizado."""
    mixer = await FakeMixer(send_meters=False).start()
    link = MixerLink(
        "127.0.0.1",
        mixer.port,
        mirror=state_mirror,
        on_state=snapshots.append if snapshots is not None else None,
        write_enabled=True,
        poll_interval=0,
        keepalive_interval=0.02,
        meters_enabled=False,
        reconnect_min=0.05,
        reconnect_max=0.2,
    )
    link.start()
    try:
        assert await wait_for(
            lambda: state_mirror.channel_count == EXPECTED_CHANNELS
        )
    except BaseException:
        await link.stop()
        await mixer.close()
        raise
    return link, mixer


async def test_level_write_is_locked_by_default(api_client: httpx.AsyncClient) -> None:
    """Sin ``write_enabled`` la API responde 409 y no toca el enlace."""
    response = await api_client.post(
        "/api/mixer/channels/3/level", json={"value": TEST_VALUE}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "escritura deshabilitada"}


async def test_level_write_sends_command_and_updates_mirror(
    api_client: httpx.AsyncClient,
) -> None:
    """Con el candado abierto el comando F7 llega y el espejo se actualiza."""
    _enable_writes()
    snapshots: list[dict[str, object]] = []
    link, mixer = await _start_link(snapshots)
    app.state.mixer_link = link
    try:
        response = await api_client.post(
            "/api/mixer/channels/3/level", json={"value": TEST_VALUE}
        )

        assert response.status_code == 200
        assert response.json() == {"index": 3, "value": TEST_VALUE, "db": TEST_DB}

        # El comando llega a la mesa con el formato verificado (marcador F7).
        assert await wait_for(lambda: mixer.dsp_frames == 1)
        assert mixer.dsp_payloads == [dsp.encode_main_level(3, TEST_VALUE)]

        snapshot = await state_mirror.snapshot()
        assert snapshot["channels"][3]["level_db"] == TEST_DB
        assert any(
            item["channels"] and item["channels"][3]["level_db"] == TEST_DB
            for item in snapshots
        )
    finally:
        await link.stop()
        await mixer.close()


async def test_level_write_accepts_db(api_client: httpx.AsyncClient) -> None:
    """El cuerpo puede traer dB y la API responde con el crudo convertido."""
    _enable_writes()
    link, mixer = await _start_link()
    app.state.mixer_link = link
    try:
        response = await api_client.post(
            "/api/mixer/channels/3/level", json={"db": 4.9}
        )

        expected = fader_law.to_raw(4.9)
        assert response.status_code == 200
        assert response.json() == {"index": 3, "value": expected, "db": 4.9}
        expected_command = [dsp.encode_main_level(3, expected)]
        assert await wait_for(lambda: mixer.dsp_payloads == expected_command)
    finally:
        await link.stop()
        await mixer.close()


async def test_level_write_rejects_unknown_channel(
    api_client: httpx.AsyncClient,
) -> None:
    """Un índice fuera del último volcado devuelve 404 y no envía nada."""
    _enable_writes()
    link, mixer = await _start_link()
    app.state.mixer_link = link
    try:
        response = await api_client.post(
            "/api/mixer/channels/999/level", json={"value": TEST_VALUE}
        )

        assert response.status_code == 404
        assert mixer.dsp_frames == 0
    finally:
        await link.stop()
        await mixer.close()


@pytest.mark.parametrize("body", [{}, {"value": 1, "db": 0.0}, {"value": 70000}])
async def test_level_write_rejects_invalid_body(
    api_client: httpx.AsyncClient, body: dict[str, object]
) -> None:
    """Un cuerpo sin valor, con ambos o con un crudo fuera de rango da 422."""
    _enable_writes()
    response = await api_client.post("/api/mixer/channels/3/level", json=body)

    assert response.status_code == 422


async def test_level_write_requires_connected_mixer(
    api_client: httpx.AsyncClient,
) -> None:
    """Con el candado abierto pero sin sesión viva, la API responde 422."""
    _enable_writes()
    response = await api_client.post(
        "/api/mixer/channels/3/level", json={"value": TEST_VALUE}
    )

    assert response.status_code == 422


async def test_mixer_config_reports_lock_and_connection(
    api_client: httpx.AsyncClient,
) -> None:
    """``GET /api/mixer/config`` refleja el candado y el estado del espejo."""
    response = await api_client.get("/api/mixer/config")
    assert response.json() == {
        "write_enabled": False,
        "model": None,
        "connected": False,
    }

    _enable_writes()
    link, mixer = await _start_link()
    app.state.mixer_link = link
    try:
        response = await api_client.get("/api/mixer/config")
        assert response.json() == {
            "write_enabled": True,
            "model": "QU-16",
            "connected": True,
        }
    finally:
        await link.stop()
        await mixer.close()
