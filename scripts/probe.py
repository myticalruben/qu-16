#!/usr/bin/env python3
"""Sonda de Fase 0: handshake real + volcado de estado de la Qu-16.

Uso:
    python scripts/probe.py --host 127.0.0.1 --save docs/qu16-state.bin
"""

from __future__ import annotations

import argparse
import asyncio
import binascii
import sys
from pathlib import Path

from qu16.client import QuClient
from qu16.protocol import dump as dump_mod


async def run(args: argparse.Namespace) -> int:
    client = QuClient(args.host, args.port, timeout=args.timeout)
    await client.connect()
    try:
        print(f"conectado a {args.host}:{args.port}")
        version = await client.handshake()
        print(f"modelo:   {version.model}  (board=0x{version.board:02x})")
        print(f"firmware: {version.major}.{version.minor:02d} (build 0x{version.build:04x})")
        print(f"puerto UDP de la mesa: {client.mixer_udp_port}")

        print("solicitando volcado de estado…")
        raw = await client.request_state_dump(timeout=args.timeout + 4)

        if args.save:
            path = Path(args.save)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            print(f"volcado guardado en {path} ({len(raw)} bytes)")

        if args.hexdump:
            print("cabecera:", binascii.hexlify(raw[:80]).decode())

        state = dump_mod.parse(raw)
        print(f"\nbloques de canal detectados: {len(state.channels)}")
        print(f"cabecera: {len(state.header)} bytes")
        print()
        limit = args.show if args.show >= 0 else len(state.channels)
        for channel in state.channels[:limit]:
            print(" ", channel)

        if args.block is not None:
            offset = state.channel_offsets[args.block]
            block = raw[offset : offset + dump_mod.BLOCK_SIZE]
            print(f"\nbloque {args.block} @0x{offset:x}:")
            for row in range(0, len(block), 16):
                chunk = block[row : row + 16]
                ascii_view = "".join(
                    chr(b) if 32 <= b < 127 else "." for b in chunk
                )
                print(f"  {row:04x}  {binascii.hexlify(chunk).decode():<32}  {ascii_view}")
        return 0
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=51326)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--save", default="")
    parser.add_argument("--show", type=int, default=16)
    parser.add_argument("--block", type=int, default=None)
    parser.add_argument("--hexdump", action="store_true")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - sonda de diagnóstico
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
