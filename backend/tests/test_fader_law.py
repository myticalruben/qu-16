"""Tests de la ley de fader y del volcado capturado de la Qu-16 real."""

from __future__ import annotations

from pathlib import Path

import pytest

from qu16.protocol import fader_law
from qu16.protocol.dump import parse

FIXTURE = Path(__file__).parent / "data" / "qu16-state.bin"


def test_unity_gain_is_zero_db() -> None:
    assert fader_law.to_db(fader_law.UNITY_RAW) == pytest.approx(0.0, abs=1e-6)


def test_zero_is_minus_infinity() -> None:
    assert fader_law.to_db(0) is None


def test_max_is_ten_db() -> None:
    assert fader_law.to_db(0x7F7F) == pytest.approx(10.0)


def test_table_endpoints_are_exact() -> None:
    """Cada punto de la tabla oficial debe devolver su dB exacto."""
    for raw, db in fader_law._FADER_TABLE:
        if db is None:
            continue
        assert fader_law.to_db(raw) == pytest.approx(db, abs=1e-6)


def test_monotonic() -> None:
    previous = -1e9
    for raw in range(0x0100, 0x7F80, 0x40):
        db = fader_law.to_db(raw)
        assert db is not None and db >= previous
        previous = db


def test_roundtrip_db_raw() -> None:
    for db in (-60.0, -24.0, -12.0, -6.0, 0.0, 3.0, 10.0):
        raw = fader_law.to_raw(db)
        assert fader_law.to_db(raw) == pytest.approx(db, abs=0.05)


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture no disponible")
def test_real_dump_decodes_qu16_channels() -> None:
    state = parse(FIXTURE.read_bytes())
    assert len(state.channels) == 60
    assert len(state.header) == 67
    # Los tres primeros canales estaban nombrados en la mesa.
    assert [c.name for c in state.channels[:9]] == [
        "inala1", "inala2", "inala3", "coro1", "coro2", "coro 3", "coro 4", "guitar", "piano"
    ]
    # Niveles coherentes: 0 significa silencio, el resto dentro de rango.
    assert state.channels[20].main_send_level == 0
    assert state.channels[20].main_send_db is None
    assert state.channels[0].main_send_db is not None
    assert -60 < state.channels[0].main_send_db < 10
