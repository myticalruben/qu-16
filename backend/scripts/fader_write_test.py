#!/usr/bin/env python3
"""Ensayo de escritura de nivel por el protocolo CMNet (reversible).

Escribe el nivel del envío principal de un canal, comprueba con un volcado que
solo ese canal cambió y lo devuelve a su valor original.

La dirección se obtuvo observando a la mesa: al mover el fader del canal 1
emitió 2416 tramas ``ctrl=3 tgt=0x04 vid=0x0a p1=0 p2=0`` cuyo valor coincidía
con el nivel de ese canal en el volcado.

Uso:
    python scripts/fader_write_test.py --host 192.168.100.67 --channel 1 --delta 300
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from qu16.client import QuClient
from qu16.protocol import constants as C
from qu16.protocol import dump as dump_mod
from qu16.protocol import fader_law
from qu16.protocol.framing import DspCommand, SystemPacket

#: Grupo de destino de los niveles de mezcla.
TARGET_MIX = 0x04
#: Identificador del parámetro "nivel del envío principal".
VALUE_ID_MAIN_LEVEL = 0x0A
#: Identificador de cliente con el que se firma el cambio.
CLIENT_ID = 4


def level_command(channel: int, value: int, client_id: int = CLIENT_ID) -> DspCommand:
    """Comando de escritura del nivel principal de un canal."""
    return DspCommand(
        control_id=0x04,
        target_group=TARGET_MIX,
        value_id=VALUE_ID_MAIN_LEVEL,
        client_id=client_id,
        param1=channel,
        param2=0x00,
        value=value,
    )


async def snapshot(client: QuClient) -> dict[int, int]:
    parsed = dump_mod.parse(await client.request_state_dump(timeout=10))
    return {channel.index: channel.main_send_level for channel in parsed.channels}


def describe(channels: dict[int, int], base: dict[int, int]) -> list[tuple[int, int, int]]:
    return [
        (index, base[index], value)
        for index, value in channels.items()
        if index in base and base[index] != value
    ]


async def run(args: argparse.Namespace) -> int:
    client = QuClient(args.host, timeout=8)
    await client.connect()
    try:
        version = await client.handshake()
        print(f"conectado a {version}")

        base = await snapshot(client)
        original = base[args.channel]
        target = max(0, original - args.delta)
        print(f"canal {args.channel}: raw actual={original} "
              f"({fader_law.format_db(fader_law.to_db(original))})")
        print(f"objetivo: raw={target} "
              f"({fader_law.format_db(fader_law.to_db(target))})")

        try:
            await client.send(level_command(args.channel, target))
            await asyncio.sleep(0.6)
            during = await snapshot(client)
            changed = describe(during, base)
            print("cambios detectados:", changed or "ninguno")

            if changed == [(args.channel, original, target)]:
                print("✅ escritura confirmada: solo cambió el canal pedido")
            elif not changed:
                print("⚠️  la mesa no aplicó el cambio (dirección o client_id)")
            else:
                print("❌ cambiaron canales inesperados:", changed)
        finally:
            print("restaurando…")
            await client.send(level_command(args.channel, original))
            await asyncio.sleep(0.6)
            after = await snapshot(client)
            remaining = describe(after, base)
            print("tras restaurar, diferencias con el estado inicial:",
                  remaining or "ninguna")
            if not remaining:
                print("✅ estado idéntico al inicial")
    finally:
        await client.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.100.67")
    parser.add_argument("--channel", type=int, default=0,
                        help="índice del canal (0 = canal 1 de la mesa)")
    parser.add_argument("--delta", type=int, default=300,
                        help="cuánto bajar el valor crudo (~0.5 dB)")
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
