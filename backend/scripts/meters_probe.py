#!/usr/bin/env python3
"""Sonda de medidores en vivo (solo lectura).

Conecta con la mesa, se anuncia como Qu-Pad, escucha los paquetes UDP de
medidores y muestra la tabla de registros crudos. No envía ningún comando de
control: sirve para calibrar el significado de cada campo.

Uso:
    python scripts/meters_probe.py --host 192.168.100.67 --seconds 10
"""

from __future__ import annotations

import argparse
import asyncio
import socket
import struct
import time

from qu16.client import INIT_SEQUENCE
from qu16.protocol import constants as C
from qu16.protocol.framing import SystemPacket

BANK_A = 0x23
BANK_B = 0x24
RECORD_SIZE = 20


def decode_meter_packet(data: bytes) -> tuple[int, list[list[int]]] | None:
    """Decodifica un paquete de medidores en su banco y sus registros.

    Formato observado: ``7F · banco · longitud(LE16) · registros de 20 bytes``,
    donde cada registro son 10 enteros de 16 bits en little endian.
    """
    if len(data) < 4 or data[0] != 0x7F:
        return None
    bank = data[1]
    if bank not in (BANK_A, BANK_B):
        return None
    length = struct.unpack_from("<H", data, 2)[0]
    body = data[4 : 4 + length]
    records = [
        [struct.unpack_from("<H", body, off + i * 2)[0] for i in range(10)]
        for off in range(0, len(body) - RECORD_SIZE + 1, RECORD_SIZE)
    ]
    return bank, records


async def run(args: argparse.Namespace) -> int:
    loop = asyncio.get_running_loop()
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind(("", args.udp_port))
    udp.setblocking(False)

    reader, writer = await asyncio.open_connection(args.host, C.CONTROL_PORT)
    writer.write(SystemPacket(C.Group.UDP_PORT, struct.pack("<H", args.udp_port)).encode())
    await writer.drain()
    await reader.read(64)

    writer.write(
        SystemPacket(C.Group.CONTROL, struct.pack("<H", C.ClientType.QU_PAD)).encode()
    )
    await writer.drain()
    await reader.read(64)

    for blob in INIT_SEQUENCE:
        writer.write(blob)
    await writer.drain()

    for _ in range(20):
        await reader.read(65536)

    banks: dict[int, list[list[int]]] = {}
    deadline = loop.time() + args.seconds
    next_print = 0.0
    while loop.time() < deadline:
        try:
            data, addr = udp.recvfrom(4096)
        except BlockingIOError:
            await asyncio.sleep(0.01)
            continue
        if addr[0] != args.host:
            continue
        decoded = decode_meter_packet(data)
        if decoded is None:
            continue
        banks[decoded[0]] = decoded[1]

        now = loop.time()
        if now >= next_print and banks:
            next_print = now + args.interval
            print(f"\n=== bancos: { {hex(k): len(v) for k, v in banks.items()} } ===")
            for bank in sorted(banks):
                rows = banks[bank]
                active = [
                    (record[0], index, record)
                    for index, record in enumerate(rows)
                    if record[0] > args.threshold
                ]
                active.sort(reverse=True)
                print(f"banco 0x{bank:02x}: {len(rows)} registros, "
                      f"{len(active)} por encima de {args.threshold}")
                for value, index, record in active[: args.top]:
                    print(f"   reg {index:02d}: pos0={value:5d}  "
                          + " ".join(f"{v:5d}" for v in record))

    writer.close()
    udp.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.100.67")
    parser.add_argument("--udp-port", type=int, default=53441)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--threshold", type=int, default=5000)
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
