"""Decodificación del volcado de estado de canales (grupo 0x06).

El blob está formado por una cabecera corta seguida de bloques de ``0xC0``
bytes, uno por canal, seguidos de los datos de FX.

Los desplazamientos de campo provienen de AHQUToolkit (implementación en Go
del mismo protocolo) y se validan contra el volcado real de la Qu-16.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from . import fader_law

#: Firma que aparece al inicio de muchos bloques de canal (no en todos).
BLOCK_SIGNATURE = b"\x80\x2e\xcb\x0b"
#: Longitud de un bloque de canal.
BLOCK_SIZE = 0xC0
#: Marca del volcado de estado.
HEADER_MAGIC = b"\xb5\x00\xfe\xff"
#: Cabecera observada antes del primer bloque (Qu-16 fw 1.97 y Qu-32 fw 1.95).
PREAMBLE_SIZE = 67
#: Los bloques de canal contienen un relleno repetido ``00 80``; los de FX no.
_MIN_FILLER_PAIRS = 10

# Desplazamientos relativos al inicio del bloque.
OFF_GATE_ATTACK = 0x17
OFF_GATE_RELEASE = 0x19
OFF_GATE_HOLD = 0x21
OFF_GATE_THRESHOLD = 0x23
OFF_GATE_DEPTH = 0x25
OFF_MAIN_SEND = 0x6B
OFF_GAIN = 0x6D
OFF_NAME = 0x89
NAME_LENGTH = 8


@dataclass(slots=True)
class ChannelState:
    """Estado decodificado de un canal del volcado."""

    index: int
    offset: int
    name: str
    main_send_level: int
    gain: int
    gate_attack: int
    gate_release: int
    gate_hold: int
    gate_threshold: int
    gate_depth: int

    @property
    def main_send_db(self) -> float | None:
        """Nivel del envío principal en dB según la ley de fader oficial."""
        return fader_law.to_db(self.main_send_level)

    def __str__(self) -> str:
        return (
            f"[{self.index:02d}] {self.name:<10} "
            f"send={self.main_send_level:5d} ({fader_law.format_db(self.main_send_db)}) "
            f"gain={self.gain:5d} "
            f"gate(th={self.gate_threshold}, d={self.gate_depth}, "
            f"a={self.gate_attack}, r={self.gate_release}, h={self.gate_hold})"
        )


@dataclass(slots=True)
class StateDump:
    """Volcado de estado ya interpretado."""

    raw: bytes
    header: bytes
    channel_offsets: list[int] = field(default_factory=list)
    channels: list[ChannelState] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.channels)


def _u16(block: bytes, offset: int) -> int:
    if offset + 2 > len(block):
        return 0
    return struct.unpack_from("<H", block, offset)[0]


def _decode_name(block: bytes, offset: int = OFF_NAME) -> str:
    raw = block[offset : offset + NAME_LENGTH]
    text = raw.split(b"\x00", 1)[0].decode("ascii", "replace").strip()
    return text


def _looks_like_channel(block: bytes) -> bool:
    """Heurística estructural: los canales llevan relleno ``00 80`` repetido."""
    return len(block) == BLOCK_SIZE and block.count(b"\x00\x80") >= _MIN_FILLER_PAIRS


def _locate_base(dump: bytes) -> int:
    """Desplazamiento del primer bloque de canal dentro del volcado."""
    if dump[:4] == HEADER_MAGIC:
        candidate = PREAMBLE_SIZE
        if candidate + BLOCK_SIZE <= len(dump) and _looks_like_channel(
            dump[candidate : candidate + BLOCK_SIZE]
        ):
            return candidate
    signature = dump.find(BLOCK_SIGNATURE)
    if signature < 0:
        return 0
    base = signature
    while base - BLOCK_SIZE >= 0 and _looks_like_channel(
        dump[base - BLOCK_SIZE : base]
    ):
        base -= BLOCK_SIZE
    return base


def find_blocks(dump: bytes) -> list[int]:
    """Devuelve los desplazamientos de cada bloque de canal.

    Los bloques son contiguos y de ``0xC0`` bytes. El recorrido se detiene en
    cuanto aparece un bloque que no tiene la estructura de un canal: después de
    los canales vienen los datos de FX, que no deben interpretarse como tales.
    """
    offsets: list[int] = []
    offset = _locate_base(dump)
    while offset + BLOCK_SIZE <= len(dump):
        if not _looks_like_channel(dump[offset : offset + BLOCK_SIZE]):
            break
        offsets.append(offset)
        offset += BLOCK_SIZE
    return offsets


def parse_channel(index: int, offset: int, block: bytes) -> ChannelState:
    return ChannelState(
        index=index,
        offset=offset,
        name=_decode_name(block),
        main_send_level=_u16(block, OFF_MAIN_SEND),
        gain=_u16(block, OFF_GAIN),
        gate_attack=_u16(block, OFF_GATE_ATTACK),
        gate_release=_u16(block, OFF_GATE_RELEASE),
        gate_hold=_u16(block, OFF_GATE_HOLD),
        gate_threshold=_u16(block, OFF_GATE_THRESHOLD),
        gate_depth=_u16(block, OFF_GATE_DEPTH),
    )


def parse(dump: bytes) -> StateDump:
    """Interpreta el volcado de estado completo."""
    offsets = find_blocks(dump)
    header_end = offsets[0] if offsets else len(dump)
    state = StateDump(raw=dump, header=dump[:header_end], channel_offsets=offsets)
    for index, offset in enumerate(offsets):
        block = dump[offset : offset + BLOCK_SIZE]
        state.channels.append(parse_channel(index, offset, block))
    return state


