"""Tests del flujo completo de medidores: enlace, mesa falsa y WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from collections.abc import Callable
from pathlib import Path

import pytest
from fake_mixer import FakeMixer
from fastapi.testclient import TestClient
from qu16.link import MeterReceiver, MixerLink
from qu16.meters import BANK_A, MeterBank, MeterState, decode_packet
from qu16.mirror import StateMirror
from qu16_api.main import app, state_hub
from qu16_api.state import state_meters
from qu16_api.ws import StateHub

DATA = Path(__file__).parent / "data"


def _load(name: str) -> bytes:
    return bytes.fromhex((DATA / name).read_text().strip())


def _free_udp_port() -> int:
    """Reserva y libera un puerto UDP libre para el receptor de medidores."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for(
    predicate: Callable[[], bool], *, timeout: float = 5.0, interval: float = 0.01
) -> bool:
    """Espera a que ``predicate()`` sea verdadero, con un límite de tiempo."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return predicate()


class _RecordingSocket:
    """Suscriptor mínimo que apunta los mensajes en lugar de enviarlos."""

    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send_json(self, message: dict[str, object]) -> None:
        self.messages.append(message)


def _bank(name: str) -> MeterBank:
    packet = decode_packet(_load(name))
    assert packet is not None
    return packet


# --------------------------------------------------------------- enlace real


def test_meter_receiver_ignores_foreign_sources() -> None:
    """Solo se aceptan datagramas cuya IP de origen sea la de la mesa."""
    meters = MeterState()
    receiver = MeterReceiver("192.168.1.10", 0, meters)
    packet = _load("meter-bank-a.hex")

    receiver.datagram_received(packet, ("192.168.1.99", 53441))
    assert meters.raw() == {}

    receiver.datagram_received(packet, ("192.168.1.10", 53441))
    assert len(meters.raw()) == 32


async def test_link_receives_meter_banks_from_fake_mixer() -> None:
    """El enlace abre el UDP anunciado y recibe los dos bancos de medidores."""
    port = _free_udp_port()
    mixer = await FakeMixer(send_meters=True).start()
    mirror = StateMirror()
    link = MixerLink(
        "127.0.0.1",
        mixer.port,
        mirror=mirror,
        meters_port=port,
        keepalive_interval=0.02,
        reconnect_min=0.05,
        reconnect_max=0.2,
    )
    try:
        link.start()
        assert await _wait_for(lambda: link.meters_open)
        assert await _wait_for(lambda: len(link.meters.raw()) >= 59)

        # El puerto anunciado en el handshake es el mismo que escucha el enlace.
        assert mixer.client_udp_port == port
        assert link.meters.connected is True
        assert mirror.connected is True

        levels = link.meters.levels()
        assert len(levels) == 59
        # Los canales con señal traen dB; los que están en reposo, None.
        assert all(level is None or isinstance(level, float) for level in levels)
        assert any(level is not None for level in levels)
        # El canal 8 (piano) tenía señal en la captura real.
        assert levels[8] is not None and -30 < levels[8] < -15
    finally:
        await link.stop()
        await mixer.close()


async def test_meters_disabled_keeps_link_without_udp_socket() -> None:
    """Con los medidores desactivados no se abre UDP y la sesión sigue viva."""
    port = _free_udp_port()
    mixer = await FakeMixer(send_meters=True).start()
    mirror = StateMirror()
    link = MixerLink(
        "127.0.0.1",
        mixer.port,
        mirror=mirror,
        meters_enabled=False,
        meters_port=port,
        keepalive_interval=0.02,
        reconnect_min=0.05,
        reconnect_max=0.2,
    )
    try:
        link.start()
        assert await _wait_for(lambda: mirror.connected)
        assert await _wait_for(lambda: mixer.client_udp_port == port)

        assert link.meters_open is False
        assert link.meters.connected is False
        # La mesa falsa insiste, pero no hay socket que reciba los datagramas.
        await asyncio.sleep(0.15)
        assert link.meters.raw() == {}
        assert await _wait_for(lambda: mixer.keepalives >= 1)
    finally:
        await link.stop()
        await mixer.close()


async def test_meter_port_in_use_keeps_link_without_meters(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Si el puerto está ocupado se avisa y la sesión de control continúa."""
    port = _free_udp_port()
    blocker = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    blocker.bind(("0.0.0.0", port))
    mixer = await FakeMixer(send_meters=False).start()
    mirror = StateMirror()
    link = MixerLink(
        "127.0.0.1",
        mixer.port,
        mirror=mirror,
        meters_port=port,
        keepalive_interval=0.02,
        reconnect_min=0.05,
        reconnect_max=0.2,
    )
    try:
        with caplog.at_level(logging.WARNING):
            link.start()
            assert await _wait_for(lambda: mirror.connected)
            assert await _wait_for(
                lambda: any("medidores" in record.message for record in caplog.records)
            )

        # El volcado sigue llegando: el fallo de UDP no tumba la conexión.
        assert await _wait_for(lambda: mirror.channel_count == 60)
        assert link.meters_open is False
        assert link.meters.connected is False
    finally:
        await link.stop()
        await mixer.close()
        blocker.close()


# ------------------------------------------------------------------ difusión


async def test_state_hub_broadcasts_meters_only_on_change() -> None:
    """Se difunde una lista de 59 niveles y se evita repetir la misma."""
    hub = StateHub(StateMirror())
    subscriber = _RecordingSocket()
    await hub.register(subscriber)  # type: ignore[arg-type]

    meters = MeterState()
    meters.mark_connected()
    meters.update(_bank("meter-bank-a.hex"))

    assert await hub.broadcast_meters(meters) is True
    assert len(subscriber.messages) == 1
    message = subscriber.messages[0]
    assert message["type"] == "meters"
    payload = message["payload"]
    assert isinstance(payload, dict)
    levels = payload["levels"]
    assert isinstance(levels, list)
    assert len(levels) == 59
    assert levels[0] is None  # canal en reposo
    assert levels[8] is not None and -30 < levels[8] < -15

    # El mismo contenido no genera otro mensaje.
    assert await hub.broadcast_meters(meters) is False
    assert len(subscriber.messages) == 1

    # Un nivel distinto sí lo genera.
    records = list(_bank("meter-bank-a.hex").records)
    first = records[8]
    records[8] = (first[0] + 512,) + first[1:]
    changed = MeterBank(bank=BANK_A, records=tuple(records))
    meters.update(changed)
    assert await hub.broadcast_meters(meters) is True
    assert len(subscriber.messages) == 2


async def test_meters_loop_rate_limits_emissions() -> None:
    """Aunque cambien más rápido, no se supera ``meters_rate_hz``."""
    hub = StateHub(StateMirror())
    subscriber = _RecordingSocket()
    await hub.register(subscriber)  # type: ignore[arg-type]

    base = _bank("meter-bank-a.hex")
    meters = MeterState()
    meters.mark_connected()
    meters.update(base)

    rate = 50.0
    task = asyncio.create_task(hub.meters_loop(meters, rate))
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 0.3
    step = 0
    try:
        while loop.time() < deadline:
            step += 1
            records = list(base.records)
            records[0] = (
                (base.records[0][0] + step) % 1000,
            ) + base.records[0][1:]
            meters.update(MeterBank(bank=base.bank, records=tuple(records)))
            await asyncio.sleep(0.002)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    # 0.3 s a 50 Hz son 15 mensajes como máximo; se deja holgura de uno.
    assert 1 <= len(subscriber.messages) <= 16


async def test_state_hub_skips_meters_without_subscribers_or_connection() -> None:
    """Sin suscriptores o sin mesa conectada no se emite nada."""
    bank = _bank("meter-bank-a.hex")
    meters = MeterState()
    meters.mark_connected()
    meters.update(bank)

    empty_hub = StateHub(StateMirror())
    assert await empty_hub.broadcast_meters(meters) is False

    hub = StateHub(StateMirror())
    subscriber = _RecordingSocket()
    await hub.register(subscriber)  # type: ignore[arg-type]
    meters.mark_disconnected()
    assert await hub.broadcast_meters(meters) is False
    assert subscriber.messages == []


# ------------------------------------------------------------- extremo a extremo


def _seed_global_meters() -> None:
    """Carga el banco A en el estado compartido que usa la aplicación."""
    state_meters.mark_connected()
    state_meters.update(_bank("meter-bank-a.hex"))


def test_websocket_receives_meters_message() -> None:
    """El WebSocket entrega ``{"type": "meters", ...}`` con 59 niveles."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            assert websocket.receive_json()["type"] == "hello"
            assert websocket.receive_json()["type"] == "state"

            client.portal.call(_seed_global_meters)
            client.portal.call(state_hub.broadcast_meters, state_meters)

            message = websocket.receive_json()

    assert message["type"] == "meters"
    payload = message["payload"]
    assert isinstance(payload, dict)
    assert isinstance(payload["levels"], list)
    assert len(payload["levels"]) == 59
