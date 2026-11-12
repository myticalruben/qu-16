"""Tests del decodificador de tramas y del volcado de estado."""

from __future__ import annotations

import struct

import pytest

from qu16.protocol.constants import DSP_MARKER, SYSTEM_MARKER, ClientType, Group, Target
from qu16.protocol.dump import (
    BLOCK_SIGNATURE,
    BLOCK_SIZE,
    PREAMBLE_SIZE,
    parse,
)
from qu16.protocol.framing import DspCommand, FrameParser, MixerVersion, SystemPacket


def test_system_packet_roundtrip() -> None:
    original = SystemPacket(Group.CONTROL, struct.pack("<H", ClientType.QU_PAD))
    encoded = original.encode()
    assert encoded == bytes.fromhex("7f0402000001")
    frames = FrameParser().feed(encoded)
    assert frames == [original]


def test_dsp_command_roundtrip() -> None:
    command = DspCommand(0x04, Target.MIX, 0x07, 0x04, 0x00, 0x00, 0x2BC3)
    encoded = command.encode()
    assert encoded == bytes.fromhex("f7040407040000c32b")
    assert encoded[0] == DSP_MARKER
    assert FrameParser().feed(encoded) == [command]


def test_parser_handles_partial_frames() -> None:
    """El flujo llega troceado en segmentos TCP arbitrarios."""
    blob = SystemPacket(Group.UDP_PORT, b"\xc1\xd0").encode()
    parser = FrameParser()
    collected = []
    for byte in blob:
        collected.extend(parser.feed(bytes([byte])))
    assert collected == [SystemPacket(Group.UDP_PORT, b"\xc1\xd0")]


def test_parser_handles_several_frames_in_one_read() -> None:
    blob = bytes.fromhex(
        "7f0402000200"
        "7f0402000f00"
        "7f0402000700"
    )
    frames = FrameParser().feed(blob)
    assert [f.group for f in frames] == [Group.CONTROL] * 3
    assert [f.data for f in frames] == [b"\x02\x00", b"\x0f\x00", b"\x07\x00"]


def test_parser_skips_unknown_bytes() -> None:
    blob = b"\x00\xff" + SystemPacket(Group.VERSION, b"\x01" * 12).encode()
    frames = FrameParser().feed(blob)
    assert len(frames) == 1
    assert frames[0].group == Group.VERSION


def test_parser_waits_for_large_dump() -> None:
    payload = bytes(range(256)) * 100  # 25 600 bytes, como el volcado real
    blob = bytes((SYSTEM_MARKER, Group.STATE_DUMP)) + struct.pack("<H", len(payload)) + payload
    parser = FrameParser()
    frames: list = []
    for start in range(0, len(blob), 1400):
        frames.extend(parser.feed(blob[start : start + 1400]))
    assert len(frames) == 1
    assert frames[0].data == payload


def test_version_decodes_real_qu16_packet() -> None:
    """Bytes reales devueltos por la Qu-16 en el handshake."""
    version = MixerVersion.from_bytes(bytes.fromhex("01016101de11000000000000"))
    assert version.board == 0x01
    assert version.model == "QU-16"


def test_version_decodes_real_qu32_packet() -> None:
    version = MixerVersion.from_bytes(bytes.fromhex("03015f01d111000000000000"))
    assert version.model == "QU-32"


def test_version_rejects_short_packet() -> None:
    with pytest.raises(ValueError):
        MixerVersion.from_bytes(b"\x01\x01")


def _synthetic_dump(channels: int) -> bytes:
    header = b"\xb5\x00\xfe\xff" + b"\x00" * (PREAMBLE_SIZE - 4)
    body = bytearray()
    for index in range(channels):
        # Los bloques reales llevan un relleno repetido 00 80.
        block = bytearray(b"\x00\x80" * (BLOCK_SIZE // 2))
        block[0:4] = BLOCK_SIGNATURE
        struct.pack_into("<H", block, 0x6B, 1000 + index)
        struct.pack_into("<H", block, 0x6D, 200 + index)
        block[0x89 : 0x89 + 8] = f"CH{index+1}".encode().ljust(8, b"\x00")
        body += block
    return header + bytes(body)


def test_dump_finds_every_channel_block() -> None:
    state = parse(_synthetic_dump(16))
    assert len(state.channels) == 16
    assert state.channels[0].name == "CH1"
    assert state.channels[0].main_send_level == 1000
    assert state.channels[15].name == "CH16"
    assert state.channels[15].gain == 215


def test_dump_ignores_truncated_tail() -> None:
    dump = _synthetic_dump(4)
    state = parse(dump[:-40])
    assert len(state.channels) == 3
