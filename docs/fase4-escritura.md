# Fase 4 (parte 1) — Escritura de niveles verificada

**Fecha:** 2026-11-14 · **Mesa:** Allen & Heath Qu-16 fw 1.97

## Resultado

La aplicación **ya puede mover faders de la mesa**, verificado en vivo y con
restauración exacta.

```
canal 1 raw=32308 -> objetivo 32008
  diff = {0: (32308, 32008)}     ✅ solo cambió el canal pedido
restaurado -> diferencias con el estado inicial: ninguna
```

## Cómo se descubrió

### 1. El MIDI no sirve para esto (en esta mesa)

Se probó el ensayo más conservador posible: NRPN relativo (`BN 63 40 · BN 62 00
· BN 61 00`) sobre el puerto 51325, que según el documento oficial baja el canal
exactamente 1 dB. **No hizo nada.** Tampoco respondió al comando `get` en
ninguno de los 16 canales MIDI.

La explicación más probable es que el documento que tenemos es de la generación
Qu-5/6/7 y esta Qu-16, de generación anterior, no comparte ese mapa. No se tocó
ningún ajuste de la consola para averiguarlo.

### 2. La mesa nos enseñó la dirección

Se pidió al operador mover el fader del canal 1 y se escuchó: llegaron **2416
tramas** a una única dirección.

```
ctrl=3 · tgt=0x04 · vid=0x0A · cli=12 · p1=0 · p2=0
valores 32210 … 35328  (nivel del canal 1 en el volcado: 32308)
```

### 3. El detalle que lo cambiaba todo

La mesa usa **dos identificadores distintos para el mismo parámetro**:

| Valor | Sentido | Significado |
|---|---|---|
| `0x0A` | mesa → cliente | notificación de cambio |
| `0x07` | cliente → mesa | **orden de escritura** |

Escribir con `0x0A` (lo que reporta la mesa) se ignora silenciosamente. Escribir
con `0x07` funciona a la primera.

Trama completa:

```
F7 · 04 (control) · 04 (destino MIX) · 07 (valor_id) ·
   04 (cliente) · canal · 00 (LR) · valor (u16 LE)
```

Nuestro codificador reproduce **byte a byte** la escritura real capturada de
Mixing Station (`f7040407040000c32b`), y hay un test que lo fija.

## Seguridad

La escritura está cerrada por **dos interruptores independientes**:

```python
WRITE_ENABLED = False            # global, en código
MixerLink(..., write_enabled=False)  # por enlace
```

Con cualquiera de los dos apagado, `set_level()` lanza `WriteDisabledError`
antes de tocar el socket. En los tests, la mesa falsa cuenta los comandos DSP y
exige que sean cero salvo en las pruebas explícitas de escritura.

## Lo que falta

| Tema | Estado |
|---|---|
| Faders en la interfaz conectados a `set_level` | pendiente de autorización |
| Mutes, pan y envíos | pendiente de decodificar sus direcciones |
| EQ paramétrico y GEQ | pendiente |
| Mapeo semántico de los canales 19-58 | pendiente |
