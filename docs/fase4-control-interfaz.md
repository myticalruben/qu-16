# Fase 4 (parte 2) — Control real desde la interfaz, con candado

**Fecha:** 2026-11-15 · **Mesa:** Allen & Heath Qu-16 fw 1.97

## Qué se añade

Los faders de la web dejan de ser de solo lectura: con el candado activado
escriben el nivel del canal en **LR** sobre la mesa real.

## El candado, en dos niveles

| Nivel | Dónde | Efecto |
|---|---|---|
| `QU16_WRITE_ENABLED` | configuración del servidor | si es `false`, la API responde **409** y nada se escribe |
| Botón "Control" en la cabecera | interfaz | arranca apagado, pide confirmación explícita y no se recuerda entre recargas |

Hacen falta los dos. El servidor puede quedar bloqueado aunque la interfaz
esté abierta; la interfaz no puede activarse si el servidor no lo permite.

## Sondeo del estado

Se descubrió que la mesa **deja de empujar avisos DSP** a nuestra sesión
(probablemente porque la tabla de clientes remotos se llena con sesiones
anteriores). Sigue respondiendo al volcado, así que el espejo se refresca
pidiendo un volcado cada `QU16_POLL_INTERVAL` segundos (2 s por defecto).

Medido: un volcado tarda **0,23 s** y pesa **25 888 B**, o sea ~13 KB/s con
sondeo a 2 s. Sobra margen en una LAN.

Tras una escritura, el espejo se actualiza **al instante** con el valor
enviado, para que la interfaz no espere al siguiente sondeo; el sondeo corrige
cualquier desviación después.

## Comportamiento del fader

- Sin candado: solo lectura, etiqueta visible.
- Con candado: se arrastra y se envía al soltar; en arrastres largos, como
  mucho una petición cada 200 ms para que el cambio se oiga en vivo.
- Actualización optimista: el fader se mueve al instante; si la petición falla,
  vuelve a su valor anterior y se avisa.
- Mientras el usuario arrastra un canal, las actualizaciones por WebSocket de
  ese canal se ignoran para que no "peleen" con el valor que está moviendo.

## API

```
GET  /api/mixer/config
POST /api/mixer/channels/{index}/level   {"db": 4.9} | {"value": 32000}
```

## Lo que sigue sin resolverse

| Tema | Estado |
|---|---|
| Escritura de envíos a mixes | ❌ sin resolver (ver `fase4-escritura.md`) |
| Mutes, pans y EQ | pendiente |
| Avisos DSP en vivo | no funcionan; mitigado con sondeo |
