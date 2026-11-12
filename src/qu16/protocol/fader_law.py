"""Ley de fader del protocolo.

El valor de nivel es de 14 bits (``0x0000`` a ``0x7FFF``) y su relación con los
decibelios NO es lineal. La tabla que sigue es la *Example Linear Taper Level
Values* del documento oficial ``Qu567_MIDI_Protocol``; el valor DSP se forma
como ``(VC << 8) | VF``, exactamente igual que el par coarse/fine del NRPN.

Esto permite mostrar dB reales y, más adelante, escribir niveles con precisión.
"""

from __future__ import annotations

from bisect import bisect_left

#: (valor crudo, dB). ``None`` representa -infinito.
_FADER_TABLE: tuple[tuple[int, float | None], ...] = (
    (0x0000, None),
    (0x2416, -89.0),
    (0x2771, -85.0),
    (0x2C42, -80.0),
    (0x3114, -75.0),
    (0x3565, -70.0),
    (0x3A37, -65.0),
    (0x3F09, -60.0),
    (0x435A, -55.0),
    (0x482C, -50.0),
    (0x4C7D, -45.0),
    (0x514F, -40.0),
    (0x533C, -38.0),
    (0x552A, -36.0),
    (0x5621, -35.0),
    (0x5717, -34.0),
    (0x580E, -33.0),
    (0x5905, -32.0),
    (0x597C, -31.0),
    (0x5A72, -30.0),
    (0x5B69, -29.0),
    (0x5C60, -28.0),
    (0x5D56, -27.0),
    (0x5E4D, -26.0),
    (0x5F44, -25.0),
    (0x603B, -24.0),
    (0x6131, -23.0),
    (0x6228, -22.0),
    (0x631F, -21.0),
    (0x6416, -20.0),
    (0x650C, -19.0),
    (0x6603, -18.0),
    (0x667A, -17.0),
    (0x6770, -16.0),
    (0x6867, -15.0),
    (0x695E, -14.0),
    (0x6A55, -13.0),
    (0x6B4B, -12.0),
    (0x6C42, -11.0),
    (0x6D39, -10.0),
    (0x6E2F, -9.0),
    (0x6F26, -8.0),
    (0x701D, -7.0),
    (0x7114, -6.0),
    (0x720A, -5.0),
    (0x7301, -4.0),
    (0x7378, -3.0),
    (0x746F, -2.0),
    (0x7565, -1.0),
    (0x765C, 0.0),
    (0x7753, 1.0),
    (0x7849, 2.0),
    (0x7940, 3.0),
    (0x7A37, 4.0),
    (0x7B2E, 5.0),
    (0x7C24, 6.0),
    (0x7D1B, 7.0),
    (0x7E12, 8.0),
    (0x7F08, 9.0),
    (0x7F7F, 10.0),
)

_RAW = tuple(raw for raw, _ in _FADER_TABLE)
_DB = tuple(db for _, db in _FADER_TABLE)
#: Valor crudo de 0 dB (unidad de ganancia).
UNITY_RAW = 0x765C


def to_db(raw: int) -> float | None:
    """Convierte un valor crudo de nivel a dB. ``None`` si es -infinito."""
    if raw <= 0:
        return None
    if raw >= _RAW[-1]:
        return _DB[-1]
    index = bisect_left(_RAW, raw)
    if _RAW[index] == raw:
        return _DB[index]
    lo_raw, lo_db = _FADER_TABLE[index - 1]
    hi_raw, hi_db = _FADER_TABLE[index]
    if lo_db is None:
        # Tramo entre -infinito y -89 dB: se interpola desde -120 dB.
        lo_db = -120.0
    ratio = (raw - lo_raw) / (hi_raw - lo_raw)
    return lo_db + ratio * (hi_db - lo_db)


def to_raw(db: float) -> int:
    """Convierte dB a valor crudo de nivel (inverso de :func:`to_db`)."""
    if db <= -120.0:
        return 0
    if db >= _DB[-1]:
        return _RAW[-1]
    index = bisect_left(_DB, db)
    lo_raw, lo_db = _FADER_TABLE[index - 1]
    hi_raw, hi_db = _FADER_TABLE[index]
    if lo_db is None:
        lo_db = -120.0
    ratio = (db - lo_db) / (hi_db - lo_db)
    return round(lo_raw + ratio * (hi_raw - lo_raw))


def format_db(db: float | None, *, signed: bool = True) -> str:
    """Formatea un nivel para mostrarlo al usuario."""
    if db is None:
        return "-inf"
    return f"{db:+.1f} dB" if signed else f"{db:.1f} dB"
