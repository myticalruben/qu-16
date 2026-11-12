# Fase 2 — Enlace en solo lectura

**Fecha:** 2026-11-12 · **Mesa:** Allen & Heath Qu-16 fw 1.97

## Objetivo

Convertir el volcado de estado en datos vivos: una conexión persistente con la
mesa, un espejo de estado autoritativo en el backend y difusión por WebSocket.
**Sin escribir nada en la mesa.**

## Verificación contra la mesa real

Antes de escribir el enlace se comprobó la hipótesis del latido. Con la mesa
real, a través del túnel SSH:

```
conectado: QU-16 · firmware 1.97 · 60 canales · dump 25888B
tras 12 s: 32 tramas recibidas, conexión viva
grupos: 0x16, 0x0b, 0x0a, 0x22, 0x21, 0x20, 0x1a, 0x1b, 0x02 ×24
segundo volcado OK: 60 canales
canales con nivel cambiado: ninguno
```

La mesa responde al latido con el grupo `0x02` cada ~500 ms. Pedir un segundo
volcado sin reconectar funciona, y los 60 niveles salieron idénticos: el
enlace no altera nada.

Integración completa con `QU16_AUTO_CONNECT=true`:

```json
{"connected": true, "model": "QU-16", "firmware": "1.97",
 "updated_at": "2026-11-12T01:16:03+00:00",
 "channels": [{"index": 0, "name": "inala1", "level_db": 9.5, "kind": "stereo"},
              {"index": 3, "name": "coro1",  "level_db": 4.9, "kind": "input"}]}
```

## Piezas

| Módulo | Responsabilidad |
|---|---|
| `qu16/link.py` | Conexión, handshake, volcado, latido cada 500 ms y reconexión 1→30 s con jitter |
| `qu16/mirror.py` | `StateMirror`: fuente de verdad con 60 canales, protegida por `asyncio.Lock` |
| `qu16_api/ws.py` | `StateHub`: suscriptores y difusión del estado |
| `fake_mixer.py` | Mesa falsa que reproduce el protocolo para los tests |

## Garantía de solo lectura

```python
WRITE_ENABLED = False
```

Todo envío pasa por `_send()`, que lanza `WriteDisabledError` si recibe un
`DspCommand`. La mesa falsa de los tests **cuenta las tramas `0xF7` recibidas y
exige que sean cero**. La escritura se habilitará en la Fase 4, y solo tras
confirmación explícita del operador.

## Decisiones

- **`auto_connect` por defecto en `false`.** La API no abre ningún socket si no
  se le pide, para que tests y CI no dependan de la red. Se activa con
  `QU16_AUTO_CONNECT=true` (lo hace el compose y el `Makefile` en `dev`).
- **Al caer la conexión se conservan modelo, firmware y últimos canales** con
  `connected=false`, para que la interfaz muestre el último estado en gris en
  lugar de vaciarse.
- **`kind`**: los índices 3-18 son `"input"` (verificado por los nombres de la
  mesa), 0-2 `"stereo"` (convención observada) y el resto `"other"`. Es la
  única clasificación que se ha podido verificar; no se afirma más.
- **`level_db`** se redondea a una décima, como muestra la mesa.

## Pendiente

| Tema | Fase |
|---|---|
| Mapeo semántico de los 60 bloques (mixes, FX, LR, DCA) | 3-4 |
| Escritura de parámetros en vivo | 4 |
| Medidores por UDP 49152 | 3 |
| Offsets de EQ, gate y compresor | 4 |
