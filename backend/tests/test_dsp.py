"""Tests de los comandos DSP de escritura y de su interruptor de seguridad."""

from __future__ import annotations

import asyncio

import pytest

from qu16 import dsp, link as link_module
from qu16.link import MixerLink, WriteDisabledError
from qu16.mirror import StateMirror
from qu16.protocol import fader_law


def test_encoder_reproduces_a_real_client_write() -> None:
    """Bytes exactos capturados de Mixing Station sobre una Qu real."""
    assert dsp.encode_main_level(0, 0x2BC3) == bytes.fromhex("f7040407040000c32b")


def test_channel_goes_in_param1() -> None:
    command = dsp.main_level(5, 30000)
    assert command.param1 == 5
    assert command.param2 == dsp.MIX_LR
    assert command.target_group == dsp.TARGET_MIX
    assert command.value_id == dsp.VALUE_ID_LEVEL_WRITE
    assert command.value == 30000


def test_write_and_report_use_different_value_ids() -> None:
    """La mesa reporta con 0x0A pero escribe con 0x07 (verificado en vivo)."""
    assert dsp.VALUE_ID_LEVEL_WRITE == 0x07
    assert dsp.VALUE_ID_LEVEL_REPORT == 0x0A
    assert dsp.VALUE_ID_LEVEL_WRITE != dsp.VALUE_ID_LEVEL_REPORT


def test_value_is_clamped() -> None:
    assert dsp.main_level(0, 70000).value == 0xFFFF
    assert dsp.main_level(0, -10).value == 0


def test_channel_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        dsp.main_level(300, 1)


def test_db_and_raw_roundtrip() -> None:
    raw = dsp.level_raw_from_db(0.0)
    assert raw == fader_law.UNITY_RAW
    assert dsp.level_db_from_raw(raw) == pytest.approx(0.0)


def test_set_level_requires_per_link_flag() -> None:
    link = MixerLink("127.0.0.1", write_enabled=False)
    with pytest.raises(WriteDisabledError):
        asyncio.run(link.set_level(0, 30000))


def test_set_level_requires_global_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con el interruptor global apagado, ni siquiera un enlace habilitado escribe."""
    monkeypatch.setattr(link_module, "WRITE_ENABLED", False)
    link = MixerLink("127.0.0.1", write_enabled=True)
    link._client = _StubClient()  # type: ignore[assignment]
    with pytest.raises(WriteDisabledError):
        asyncio.run(link.set_level(0, 30000))


def test_set_level_sends_command_when_fully_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(link_module, "WRITE_ENABLED", True)
    link = MixerLink("127.0.0.1", write_enabled=True)
    stub = _StubClient()
    link._client = stub  # type: ignore[assignment]
    asyncio.run(link.set_level(3, 0x2BC3))
    assert stub.sent == [bytes.fromhex("f7040407040300c32b")]


class _StubClient:
    """Cliente falso que solo apunta lo que se le envía."""

    connected = True

    def __init__(self) -> None:
        self.sent: list[bytes] = []

    async def send(self, packet: object) -> None:
        self.sent.append(packet.encode())  # type: ignore[attr-defined]
