"""Constantes del protocolo CMNet de Allen & Heath Qu.

Fuentes: captura real de Mixing Station Pro y AHQUToolkit.
"""

from __future__ import annotations

#: Primer byte de una trama de sistema: ``7F · grupo · len(LE16) · datos``
SYSTEM_MARKER = 0x7F
#: Primer byte de un comando DSP: ``F7 · 8 bytes``
DSP_MARKER = 0xF7

#: Puerto TCP del protocolo de control remoto (Qu-Pad / Mixing Station)
CONTROL_PORT = 51326
#: Puerto UDP de descubrimiento ("QU Find")
DISCOVERY_PORT = 51320
#: Puerto UDP por defecto de heartbeat / medidores
METERS_PORT = 49152

DISCOVERY_PROBE = b"QU Find"


class Group:
    """Identificadores de grupo de las tramas de sistema."""

    UDP_PORT = 0x00
    VERSION = 0x01
    CONTROL = 0x04
    STATE_DUMP = 0x06
    SYSTEM_A = 0x0A
    SYSTEM_B = 0x0B
    CHANNELS_A = 0x16
    CHANNELS_B = 0x18
    CHANNELS_C = 0x1A
    CHANNELS_D = 0x1B
    INIT_A = 0x20
    INIT_B = 0x21
    INIT_C = 0x22


class Target:
    """Grupos de destino de los comandos DSP."""

    MIX = 0x04
    PEQ = 0x05
    GAIN = 0x06
    GATE = 0x07
    COMP = 0x08


class ClientType:
    """Tipo de cliente que se anuncia en el handshake."""

    QU_YOU = 0x0000
    QU_PAD = 0x0100


#: Tipo de placa que anuncia la mesa en su paquete de versión.
BOARD_NAMES = {
    0x01: "QU-16",
    0x02: "QU-24",
    0x03: "QU-32",
}
