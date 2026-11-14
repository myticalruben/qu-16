"""Decodificación de los medidores (UDP).

La mesa envía los medidores por UDP al puerto que el cliente anunció en el
handshake, en paquetes con este formato observado en la Qu-16 (fw 1.97)::

    7F · banco · longitud(LE16) · registros de 20 bytes

Hay dos bancos que se reparten los canales de forma consecutiva:

===========  ==========================  ================
Banco        Registros                   Índices de canal
===========  ==========================  ================
``0x23``     32                          0 … 31
``0x24``     27                          32 … 58
===========  ==========================  ================

Cada registro son 10 enteros de 16 bits en little endian. El primero se
corresponde con el nivel del canal y se interpreta con la misma ley de fader
que el resto del protocolo (:mod:`qu16.protocol.fader_law`).

.. warning::
   El significado de los campos 1-9 del registro **no está confirmado**: en las
   capturas se comportan como valores de pico, retención y banderas (aparecen
   con el bit 15 puesto). Solo el campo 0 se usa para el nivel mostrado, y se
   ignora cualquier lectura con el bit 15 activo por considerarla no válida.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


#: Marcador de trama.
MARKER = 0x7F
#: Banco de los canales 0-31.
BANK_A = 0x23
#: Banco de los canales 32-58.
BANK_B = 0x24
#: Primer índice de canal que cubre cada banco.
BANK_FIRST_INDEX = {BANK_A: 0, BANK_B: 32}
#: Tamaño de un registro de medidor.
RECORD_SIZE = 20
#: Enteros de 16 bits por registro.
FIELDS_PER_RECORD = 10
#: Campo que se usa como nivel del canal.
LEVEL_FIELD = 0
#: Bit que marca lecturas no válidas (pico, retención o bandera).
INVALID_BIT = 0x8000
#: Número de canales publicados: los índices globales van de 0 a 58.
CHANNEL_COUNT = 59
#: Precisión con la que se publican los niveles (una décima de dB).
LEVEL_DECIMALS = 1

# --- Calibración empírica de la escala de medidores -------------------------
# Medida el 2026-11-14 sobre la Qu-16 real: con el canal 1 recibiendo voz, su
# registro pasó de 29646 a 32374 mientras el resto seguía en 4609. La escala es
# LINEAL EN dB (no usa la ley de fader: eso daba +8.6 dB, imposible en un
# medidor). Reposo = -60 dB, fondo de escala = 0 dBFS.
#
# Para recalibrar basta con cambiar estas tres constantes.
#: Valor crudo de reposo (canales sin señal).
METER_FLOOR_RAW = 4609
#: Valor crudo que corresponde a 0 dBFS.
METER_FULL_RAW = 32767
#: dB que representa el valor de reposo.
METER_FLOOR_DB = -60.0


@dataclass(frozen=True, slots=True)
class MeterBank:
    """Registros de medidor de un banco, ya decodificados."""

    bank: int
    records: tuple[tuple[int, ...], ...]

    def global_index(self, position: int) -> int:
        """Índice de canal global de un registro dentro del banco."""
        return BANK_FIRST_INDEX[self.bank] + position

    def levels_raw(self) -> dict[int, int]:
        """Nivel crudo por índice de canal, omitiendo lecturas no válidas."""
        result: dict[int, int] = {}
        for position, record in enumerate(self.records):
            value = record[LEVEL_FIELD]
            if value & INVALID_BIT:
                continue
            result[self.global_index(position)] = value
        return result


def decode_packet(data: bytes) -> MeterBank | None:
    """Decodifica un datagrama de medidores.

    Devuelve ``None`` si el paquete no es un banco de medidores conocido
    (por ejemplo, el latido de 22 bytes).
    """
    if len(data) < 4 or data[0] != MARKER:
        return None
    bank = data[1]
    if bank not in BANK_FIRST_INDEX:
        return None

    length = struct.unpack_from("<H", data, 2)[0]
    body = data[4 : 4 + length]
    count = len(body) // RECORD_SIZE
    records = tuple(
        tuple(
            struct.unpack_from("<H", body, position * RECORD_SIZE + field * 2)[0]
            for field in range(FIELDS_PER_RECORD)
        )
        for position in range(count)
    )
    return MeterBank(bank=bank, records=records)


def level_db(value: int) -> float | None:
    """Convierte un nivel crudo de medidor a dBFS.

    La escala es lineal en dB entre :data:`METER_FLOOR_RAW` (-60 dB) y
    :data:`METER_FULL_RAW` (0 dBFS). Los valores no válidos (bit 15) y los que
    no superan el reposo devuelven ``None``, que la interfaz muestra como
    silencio.
    """
    if value & INVALID_BIT:
        return None
    if value <= METER_FLOOR_RAW:
        return None
    clamped = min(value, METER_FULL_RAW)
    span = METER_FULL_RAW - METER_FLOOR_RAW
    return METER_FLOOR_DB + (clamped - METER_FLOOR_RAW) * (-METER_FLOOR_DB) / span


class MeterState:
    """Último nivel conocido de cada canal, a partir de los dos bancos.

    La instancia es compartida por el receptor UDP y quien difunde los niveles.
    ``revision`` solo aumenta cuando cambia algún nivel, de modo que el bucle de
    difusión puede saltarse los paquetes que no aportan nada nuevo.
    """

    __slots__ = ("_levels", "_revision", "_connected")

    def __init__(self) -> None:
        self._levels: dict[int, int] = {}
        self._revision = 0
        self._connected = False

    @property
    def connected(self) -> bool:
        """``True`` mientras la mesa esté conectada y los medidores activos."""
        return self._connected

    @property
    def revision(self) -> int:
        """Versión del contenido; cambia solo cuando un nivel varía."""
        return self._revision

    def mark_connected(self) -> None:
        """Marca la sesión como activa para permitir la difusión."""
        self._connected = True

    def mark_disconnected(self) -> None:
        """Marca la sesión como inactiva y olvida los niveles."""
        self._connected = False
        self.cleared()

    def update(self, packet: MeterBank) -> None:
        """Incorpora un banco si aporta algún nivel nuevo o distinto."""
        incoming = packet.levels_raw()
        if not incoming:
            return
        unchanged = all(
            self._levels.get(index) == value
            for index, value in incoming.items()
        )
        if unchanged:
            return
        self._levels.update(incoming)
        self._revision += 1

    def raw(self) -> dict[int, int]:
        """Niveles crudos por índice de canal."""
        return dict(self._levels)

    def db(self) -> dict[int, float | None]:
        """Niveles en dB por índice de canal, sin redondear."""
        return {index: level_db(value) for index, value in self._levels.items()}

    def levels(self) -> list[float | None]:
        """Niveles en dB por índice de canal (0-58), ``None`` si no hay lectura.

        La posición de cada elemento es el índice global del canal; los canales
        sin dato se rellenan con ``None`` para que la lista tenga siempre
        :data:`CHANNEL_COUNT` entradas.
        """
        result: list[float | None] = [None] * CHANNEL_COUNT
        for index, value in self._levels.items():
            if 0 <= index < CHANNEL_COUNT:
                db = level_db(value)
                result[index] = None if db is None else round(db, LEVEL_DECIMALS)
        return result

    def cleared(self) -> None:
        """Olvida los niveles y marca la revisión como cambiada."""
        if not self._levels:
            return
        self._levels.clear()
        self._revision += 1
