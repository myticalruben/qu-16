# qu16-control

Control web para la mesa **Allen & Heath Qu-16** sobre su protocolo nativo
CMNet (TCP 51326), con interfaz tipo Mixing Station y un asistente de IA para
ecualizar.

## Estado

**Fase 0 completada** — codec del protocolo validado contra la mesa real.

| Capacidad | Estado |
|---|---|
| Handshake CMNet (Qu-Pad) | ✅ verificado |
| Volcado de estado (25 888 B) | ✅ verificado |
| Decodificación de 60 bloques de canal | ✅ |
| Ley de fader oficial (valor crudo → dB) | ✅ |
| Escritura de parámetros | 🟡 codificada, pendiente de validar en vivo |
| EQ / GEQ / dinámica | 🟡 datos presentes en el volcado, offsets por mapear |

## Estructura

```
src/qu16/
  client.py              cliente asíncrono: handshake + volcado
  protocol/
    constants.py         puertos, grupos, destinos DSP
    framing.py           tramas de sistema (0x7F) y DSP (0xF7)
    dump.py              decodificación de canales del volcado
    fader_law.py         ley de fader oficial (14 bits ↔ dB)
scripts/probe.py         sonda contra la mesa real
tests/                   18 tests (pytest)
docs/                    hallazgos de la fase 0
```

## Uso

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/python scripts/probe.py --host 192.168.100.67 --show 20
```

Si la mesa no es alcanzable desde tu equipo, abre un túnel SSH contra la
laptop que sí está en su red:

```bash
ssh -N -L 51326:192.168.100.67:51326 usuario@laptop
.venv/bin/python scripts/probe.py --host 127.0.0.1
```

## Protocolo en una línea

El canal de control real es **TCP 51326**: tramas `7F · grupo · len(LE16) ·
datos` para estado y `F7` + 8 bytes para parámetros DSP. El puerto **51325 es
MIDI**, útil solo para faders, mutes, pans y escenas; no toca la EQ.
