# Fase 3 — Medidores en tiempo real

**Fecha:** 2026-11-14 · **Mesa:** Allen & Heath Qu-16 fw 1.97

## Cómo se obtienen

La mesa envía los medidores por **UDP al puerto que el cliente anunció en el
handshake** (no hay que pedirlos). Formato observado:

```
7F · banco · longitud(LE16) · registros de 20 bytes
```

| Banco | Registros | Canales |
|---|---|---|
| `0x23` | 32 | 0 – 31 |
| `0x24` | 27 | 32 – 58 |

Cada registro son 10 enteros de 16 bits little endian. **El campo 0 es el
nivel**; los campos 1-9 se comportan como picos, retención y banderas (aparecen
con el bit 15 puesto y se descartan como lecturas no válidas).

## Calibración (hecha contra la mesa real)

Se pidió al operador hablar por el **canal 1** mientras se grababan 120 s de
medidores:

```
idx=00  pico=32374  reposo=29646  delta=+2728   ← el micrófono del canal 1
idx=07  pico=17338  reposo=15825  delta=+1513   ← guitarra
idx=08  pico=22592  reposo=22237  delta= +355   ← piano
idx=52  pico=26037  reposo=23232  delta=+2805   ← (mezcla o FX)
```

### Dos correcciones que salieron de ahí

**1. El índice del registro es el del canal.** Canal 1 de la mesa → índice 0.
Por tanto los índices **0-15 son las 16 entradas** (no 3-18 como se había
supuesto) y las estéreo son 16-18. Corregido en `channel_kind()`.

**2. La escala es lineal en dB, no la ley de fader.** Con la ley de fader la
voz daba **+8.6 dBFS**, imposible. La escala real va de `4609` (reposo, −60 dB)
a `32767` (0 dBFS):

```
dB = -60 + (raw - 4609) · 60 / (32767 - 4609)
```

Con eso: voz ≈ −0.8 dBFS, piano ≈ −22.4 dBFS, guitarra ≈ −32.9 dBFS. Las
constantes están juntas y documentadas en `qu16/meters.py` para poder
recalibrar con una sola línea.

## Verificación en vivo (laptop en la LAN de la mesa)

```
conectado: True
t= 3s  canales con señal >-40 dB: 2  top: [(8, -23.0), (7, -36.1)]
t=15s  canales con señal >-40 dB: 2  top: [(8, -22.4), (7, -36.1)]
```

Piano en −22.4 dB y guitarra en −36.1 dB, coherente con la calibración.

## Arquitectura

```
UDP 49152 ──▶ MeterReceiver (filtra por IP de la mesa)
                     │
                     ▼
              MeterState (59 niveles, revisión)
                     │        ▲
                     │        └── solo sube revisión si algo cambia
                     ▼
        meters_loop @ 20 Hz ──▶ StateHub ──▶ WS {"type":"meters", ...}
                     │
                     └── no emite sin suscriptores, sin conexión o sin cambios
```

En el cliente, cada tira se suscribe **solo a `levels[index]`**, de modo que a
20 Hz con 59 canales únicamente se repinta el canal cuyo nivel cambió.

## Pendiente

| Tema | Estado |
|---|---|
| Mapeo semántico de los canales 19-58 (mixes, FX, LR, DCA) | pendiente |
| Medidores de mezcla/auxiliares verificados | pendiente |
| Escritura de parámetros | Fase 4 (requiere autorización del operador) |
