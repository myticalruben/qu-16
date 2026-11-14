#!/usr/bin/env python3
"""Ensayo reversible de fader sobre el puerto MIDI (solo lectura salvo el salto).

Baja el nivel de un canal **1 dB**, espera, y lo vuelve a subir en el bloque
``finally`` aunque el proceso falle a medias. Usa los mensajes NRPN relativos
del protocolo oficial, así que no hace falta conocer el valor absoluto para
dejarlo exactamente como estaba.

Dirección (documento oficial, Ip1..Ip24 → LR):

    BN 63 40   BN 62 (canal-1)   BN 61 00   → −1 dB
    BN 63 40   BN 62 (canal-1)   BN 60 00   → +1 dB

Uso:
    python scripts/fader_bump.py --host 192.168.100.67 --channel 1
"""

from __future__ import annotations

import argparse
import socket
import sys
import time

MIDI_PORT = 51325
#: MSB del bloque de niveles de entrada (Ip1..Ip24 → LR).
LEVEL_MSB = 0x40
#: Sufijo NRPN de incremento y decremento relativos.
INCREMENT = 0x60
DECREMENT = 0x61


def nrpn(channel: int, msb: int, lsb: int, cc: int, value: int = 0x00,
         midi_channel: int = 0) -> bytes:
    """Construye un mensaje NRPN completo (4 mensajes CC)."""
    status = 0xB0 | midi_channel
    return bytes(
        (status, 0x63, msb, status, 0x62, lsb, status, cc, value)
    )


def run(args: argparse.Namespace) -> int:
    lsb = args.channel - 1
    down = nrpn(args.channel, LEVEL_MSB, lsb, DECREMENT, midi_channel=args.midi_channel)
    up = nrpn(args.channel, LEVEL_MSB, lsb, INCREMENT, midi_channel=args.midi_channel)

    sock = socket.create_connection((args.host, MIDI_PORT), timeout=5)
    try:
        print(f"canal {args.channel}: bajando 1 dB durante {args.hold:.1f} s")
        sock.sendall(down)
        time.sleep(args.hold)
    finally:
        # Restauración garantizada aunque haya una excepción.
        sock.sendall(up)
        sock.close()
        print("canal restaurado (+1 dB)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.100.67")
    parser.add_argument("--channel", type=int, default=1, choices=range(1, 25))
    parser.add_argument("--midi-channel", type=int, default=0,
                        help="canal MIDI de la mesa (0 = canal 1, por defecto)")
    parser.add_argument("--hold", type=float, default=2.5)
    args = parser.parse_args()
    try:
        return run(args)
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(f"sin conexión: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
