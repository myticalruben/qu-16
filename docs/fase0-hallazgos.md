# Fase 0 — Codec CMNet validado contra la Qu-16

**Fecha:** 2026-11-11 · **Mesa:** Allen & Heath Qu-16 fw 1.97 · `192.168.100.67`

## Objetivo

Tener certeza técnica del canal de control **antes** de escribir interfaz:
handshake completo, volcado de estado decodificado y ley de fader correcta.

## Resultado

Todo verificado contra la mesa real a través de un túnel SSH.

### Handshake

```
cliente → 7F 00 02 00 C1 D0   grupo 0x00 · puerto UDP del cliente
mesa    → 7F 00 02 00 00 C0   grupo 0x00 · puerto UDP de la mesa = 49152
cliente → 7F 04 02 00 00 01   grupo 0x04 · tipo de cliente = 256 (Qu-Pad)
mesa    → 7F 01 0C 00 01 01 61 01 DE 11 00 …  grupo 0x01 · versión
cliente → ráfaga de inicialización (3 blobs)
mesa    → 7F 06 20 65 + 25 888 bytes   grupo 0x06 · volcado de estado
```

La mesa responde `board = 0x01`, es decir **QU-16**, y `minor = 0x61 = 97` →
firmware **1.97**, build `0x11de`.

### Volcado de estado

| Medición | Valor |
|---|---|
| Tamaño | 25 888 bytes |
| Cabecera | 67 bytes (magia `B5 00 FE FF`) |
| Bloques de canal | **60**, de 192 bytes, contiguos |
| Datos de FX | 14 301 bytes al final |

Nombres reales leídos de la mesa, en orden:

```
00 inala1   03 coro1   06 coro 4
01 inala2   04 coro2   07 guitar
02 inala3   05 coro 3   08 piano
```

Los 51 bloques restantes no tienen nombre asignado en la mesa.

### Ley de fader

Se descartó la conversión lineal inicial y se implementó la tabla oficial
*Example Linear Taper Level Values* del PDF de A&H, con interpolación.
`0x765C` = 0 dB exacto; `0x7F7F` = +10 dB; `0x0000` = -infinito.

Ejemplo de lectura real: `coro1` = `31519` → **+4.9 dB**.

## Correcciones descubiertas durante la fase

Tres suposiciones de la implementación de referencia resultaron equivocadas:

1. **La firma `80 2E CB 0B` no es universal.** Solo aparece en 48 de los 60
   bloques; los 3 primeros usan otro encabezado. Detectar bloques por firma
   perdía canales y desplazaba todos los índices.
   *Solución:* recorrido contiguo con paso de 192 bytes desde la cabecera.
2. **El límite del área de canales no es evidente.** Los bloques de FX
   posteriores tienen la misma longitud. *Solución:* discriminador estructural
   (presencia del relleno repetido `00 80`, ≥10 veces), verificado sobre los
   60 bloques reales frente a los de FX.
3. **La versión no es `major.minor.patch` de 16 bits.** El byte 2 es el minor
   y el 3 una revisión interna; el *build* ocupa los bytes 4-5.

## Lo que queda para las siguientes fases

| Pendiente | Fase | Nota |
|---|---|---|
| Mapeo semántico de los 60 bloques (cuáles son mixes, FX, LR, DCA) | 2 | Los 19 primeros son entradas estéreo + 16 mono |
| Escritura de parámetros en vivo | 2 | Formato `F7` ya codificado; falta validar el direccionamiento en una ventana sin sonido |
| Offsets de EQ, gate y compresor dentro del bloque | 4 | Los datos están en los 192 B, aún sin mapear |
| Medidores | 3 | Van por **UDP 49152**, 20 bytes por canal |

> La escritura **no** se ha probado contra la mesa para no alterar una sesión
> en uso. El formato está verificado byte a byte contra la captura de Mixing
> Station, y `DspCommand.encode()` reproduce exactamente esos bytes.

## Reproducir

```bash
.venv/bin/python -m pytest -q            # 18 tests
.venv/bin/python scripts/probe.py --host 127.0.0.1 --save docs/qu16-state.bin
```
