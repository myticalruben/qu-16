"""Comandos DSP de escritura (niveles).

Verificado contra la Qu-16 real el 2026-11-14. La mesa usa **dos identificadores
distintos para el mismo parámetro**:

==============  ==========  =========================================
Valor           Dirección   Significado
==============  ==========  =========================================
``0x07``        cliente →   nivel principal (escritura)
                mesa
``0x0A``        mesa →      nivel principal (notificación de cambio)
                cliente
==============  ==========  =========================================

La dirección completa es::

    F7 · control(0x04) · destino(0x04 = MIX) · valor_id(0x07) ·
       cliente(0x04) · canal · mezcla(0x00) · valor(u16 LE)

``canal`` es el índice del canal (0 = canal 1 de la mesa) y ``mezcla`` 0 = LR.
"""

from __future__ import annotations

import struct

from .protocol import fader_law
from .protocol.framing import DspCommand

#: Identificador de control para órdenes del cliente.
CONTROL_SET = 0x04
#: Grupo de destino de los niveles de mezcla.
TARGET_MIX = 0x04
#: Identificador del parámetro de nivel cuando **escribe** el cliente.
VALUE_ID_LEVEL_WRITE = 0x07
#: Identificador con el que la mesa **notifica** un cambio de nivel.
VALUE_ID_LEVEL_REPORT = 0x0A
#: Identificador de cliente con el que firmamos los cambios.
CLIENT_ID = 0x04
#: Destino LR.
MIX_LR = 0x00


def main_level(channel: int, value: int, client_id: int = CLIENT_ID) -> DspCommand:
    """Comando que fija el nivel principal de ``channel``.

    ``value`` usa la misma escala de 16 bits que el volcado de estado; se puede
    obtener con :func:`level_raw_from_db`.
    """
    if not 0 <= channel <= 0xFF:
        raise ValueError(f"canal fuera de rango: {channel}")
    return DspCommand(
        control_id=CONTROL_SET,
        target_group=TARGET_MIX,
        value_id=VALUE_ID_LEVEL_WRITE,
        client_id=client_id,
        param1=channel,
        param2=MIX_LR,
        value=max(0, min(0xFFFF, value)),
    )


def level_raw_from_db(db: float) -> int:
    """Convierte dB a valor crudo de nivel usando la ley de fader."""
    return fader_law.to_raw(db)


def level_db_from_raw(value: int) -> float | None:
    """Convierte un valor crudo de nivel a dB."""
    return fader_law.to_db(value)


def encode_main_level(channel: int, value: int) -> bytes:
    """Bytes del comando, listos para el socket."""
    return main_level(channel, value).encode()


__all__ = [
    "CONTROL_SET",
    "TARGET_MIX",
    "VALUE_ID_LEVEL_WRITE",
    "VALUE_ID_LEVEL_REPORT",
    "CLIENT_ID",
    "MIX_LR",
    "main_level",
    "level_raw_from_db",
    "level_db_from_raw",
    "encode_main_level",
]
