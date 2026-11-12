"""Codificación y decodificación de tramas del protocolo CMNet.

Dos familias de trama conviven en el mismo flujo TCP:

* **Sistema** — ``7F · grupo(u8) · longitud(u16 LE) · datos``
* **DSP**     — ``F7`` seguido de 8 bytes fijos

El mezclador entrega el flujo troceado en segmentos TCP arbitrarios, así que
el decodificador es incremental: se le puede pasar cualquier prefijo.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Union

from .constants import BOARD_NAMES, DSP_MARKER, SYSTEM_MARKER


@dataclass(frozen=True, slots=True)
class SystemPacket:
    """Trama de sistema: control, versiones y volcado de estado."""

    group: int
    data: bytes

    def encode(self) -> bytes:
        return (
            bytes((SYSTEM_MARKER, self.group))
            + struct.pack("<H", len(self.data))
            + self.data
        )

    @classmethod
    def decode_body(cls, group: int, data: bytes) -> "SystemPacket":
        return cls(group=group, data=data)


@dataclass(frozen=True, slots=True)
class DspCommand:
    """Comando de parámetro DSP: 9 bytes en total, contando el marcador.

    ``F7 · control · destino · valor_id · cliente · p1 · p2 · valor(u16 LE)``
    """

    control_id: int
    target_group: int
    value_id: int
    client_id: int
    param1: int
    param2: int
    value: int

    def encode(self) -> bytes:
        return bytes(
            (
                DSP_MARKER,
                self.control_id,
                self.target_group,
                self.value_id,
                self.client_id,
                self.param1,
                self.param2,
            )
        ) + struct.pack("<H", self.value)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "DspCommand":
        if len(raw) != 8:
            raise ValueError(f"se esperaban 8 bytes tras 0xF7, llegaron {len(raw)}")
        return cls(
            control_id=raw[0],
            target_group=raw[1],
            value_id=raw[2],
            client_id=raw[3],
            param1=raw[4],
            param2=raw[5],
            value=struct.unpack_from("<H", raw, 6)[0],
        )


Frame = Union[SystemPacket, DspCommand]


class FrameParser:
    """Decodificador incremental de tramas.

    >>> parser = FrameParser()
    >>> parser.feed(b"\\x7f\\x00\\x02\\x00\\x00\\xc0")
    [SystemPacket(group=0, data=b'\\x00\\xc0')]
    """

    __slots__ = ("_buf",)

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> list[Frame]:
        self._buf += chunk
        frames: list[Frame] = []
        while self._buf:
            marker = self._buf[0]
            if marker == SYSTEM_MARKER:
                if len(self._buf) < 4:
                    break
                group = self._buf[1]
                length = struct.unpack_from("<H", self._buf, 2)[0]
                end = 4 + length
                if len(self._buf) < end:
                    break
                frames.append(SystemPacket(group, bytes(self._buf[4:end])))
                del self._buf[:end]
            elif marker == DSP_MARKER:
                end = 9
                if len(self._buf) < end:
                    break
                frames.append(DspCommand.from_bytes(bytes(self._buf[1:end])))
                del self._buf[:end]
            else:
                # Byte de relleno o fuera de trama: se descarta.
                del self._buf[:1]
        return frames


@dataclass(frozen=True, slots=True)
class MixerVersion:
    """Contenido del paquete de versión (grupo ``0x01``).

    Disposición observada en capturas reales (Qu-16 fw 1.97 y Qu-32 fw 1.95)::

        01 01 61 01 de 11 00 00 00 00 00 00
        │  │  │  │  └─ build (u16 LE = 0x11de)
        │  │  │  └──── revisión interna (0x01)
        │  │  └─────── minor (0x61 = 97  →  firmware 1.97)
        │  └────────── major (0x01)
        └───────────── placa (0x01 = Qu-16)
    """

    board: int
    major: int
    minor: int
    revision: int
    build: int

    @property
    def model(self) -> str:
        return BOARD_NAMES.get(self.board, f"desconocido (0x{self.board:02x})")

    @classmethod
    def from_bytes(cls, data: bytes) -> "MixerVersion":
        if len(data) < 6:
            raise ValueError(f"paquete de versión demasiado corto: {len(data)} bytes")
        return cls(
            board=data[0],
            major=data[1],
            minor=data[2],
            revision=data[3],
            build=struct.unpack_from("<H", data, 4)[0],
        )

    def __str__(self) -> str:
        return f"{self.model} · firmware {self.major}.{self.minor:02d}"
