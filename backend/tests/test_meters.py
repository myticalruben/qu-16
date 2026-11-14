"""Tests del decodificador de medidores UDP."""

from __future__ import annotations

from pathlib import Path

import pytest

from qu16.meters import (
    BANK_A,
    BANK_B,
    FIELDS_PER_RECORD,
    INVALID_BIT,
    METER_FLOOR_RAW,
    METER_FULL_RAW,
    MeterBank,
    MeterState,
    decode_packet,
    level_db,
)

DATA = Path(__file__).parent / "data"


def _load(name: str) -> bytes:
    return bytes.fromhex((DATA / name).read_text().strip())


@pytest.fixture(scope="module")
def bank_a() -> MeterBank:
    packet = decode_packet(_load("meter-bank-a.hex"))
    assert packet is not None
    return packet


@pytest.fixture(scope="module")
def bank_b() -> MeterBank:
    packet = decode_packet(_load("meter-bank-b.hex"))
    assert packet is not None
    return packet


def test_bank_a_has_32_records(bank_a: MeterBank) -> None:
    assert bank_a.bank == BANK_A
    assert len(bank_a.records) == 32


def test_bank_b_has_27_records(bank_b: MeterBank) -> None:
    assert bank_b.bank == BANK_B
    assert len(bank_b.records) == 27


def test_every_record_has_ten_fields(bank_a: MeterBank) -> None:
    assert all(len(record) == FIELDS_PER_RECORD for record in bank_a.records)


def test_global_index_continues_between_banks(bank_a: MeterBank, bank_b: MeterBank) -> None:
    assert bank_a.global_index(0) == 0
    assert bank_a.global_index(31) == 31
    assert bank_b.global_index(0) == 32
    assert bank_b.global_index(26) == 58


def test_packets_are_contiguous(bank_a: MeterBank, bank_b: MeterBank) -> None:
    """Los dos bancos cubren 59 canales sin huecos."""
    indices = sorted(bank_a.levels_raw()) + sorted(bank_b.levels_raw())
    assert min(indices) == 0
    assert max(indices) <= 58


def test_resting_value_is_reported_as_silence() -> None:
    """4609 es el reposo medido en la mesa: por debajo no hay señal."""
    assert level_db(METER_FLOOR_RAW) is None
    assert level_db(METER_FLOOR_RAW - 1) is None
    assert level_db(METER_FLOOR_RAW + 1) is not None


def test_active_piano_channel_level(bank_a: MeterBank) -> None:
    """El registro 8 (piano) tenía señal en la captura: ~-22 dBFS."""
    piano = bank_a.records[8][0]
    db = level_db(piano)
    assert db is not None
    assert -30 < db < -15


def test_full_scale_is_zero_db() -> None:
    assert level_db(METER_FULL_RAW) == pytest.approx(0.0)
    # Por encima del fondo de escala el bit 15 marca lectura no válida.
    assert level_db(METER_FULL_RAW + 10) is None


def test_calibration_from_measured_voice() -> None:
    """El canal 1 con voz midió 32374: debe quedar cerca de 0 dBFS."""
    db = level_db(32374)
    assert db is not None
    assert -2.0 < db < 0.0


def test_invalid_bit_is_ignored() -> None:
    assert level_db(INVALID_BIT | 0x1234) is None
    assert level_db(INVALID_BIT) is None


def test_zero_is_silence() -> None:
    assert level_db(0) is None


def test_rejects_heartbeat_packet() -> None:
    heartbeat = bytes.fromhex("7f261200000000000000000000000000000000000000")
    assert decode_packet(heartbeat) is None


def test_rejects_short_and_foreign_packets() -> None:
    assert decode_packet(b"") is None
    assert decode_packet(b"\x7f\x23") is None
    assert decode_packet(b"\x00\x23\x02\x00") is None


def test_meter_state_merges_both_banks(bank_a: MeterBank, bank_b: MeterBank) -> None:
    state = MeterState()
    state.update(bank_a)
    first = len(state.raw())
    assert first > 0
    state.update(bank_b)
    assert len(state.raw()) > first
    assert all(db is None or isinstance(db, float) for db in state.db().values())


def test_meter_state_can_be_cleared(bank_a: MeterBank) -> None:
    state = MeterState()
    state.update(bank_a)
    state.cleared()
    assert state.raw() == {}
