# Qu-16 Control — documento de diseño

**Fecha:** 2026-11-11
**Estado:** aprobado el enfoque; pendiente de aprobación final del documento

---

## 1. Intención

Sustituir la dependencia de Mixing Station (app de terceros, cerrada) por una
aplicación web propia que controle **toda** la Allen & Heath Qu-16 desde el
navegador de una laptop o una tablet, y que además incorpore un asistente de IA
capaz de proponer y aplicar ecualización basándose en el espectro real.

**Éxito significa:** abrir una URL en la tablet, ver los 16 canales con sus
medidores moviéndose, mover un fader y que la mesa responda, y pedirle al
asistente "la voz está nasal" y que proponga un corte concreto en la PEQ.

## 2. Objetivos y no-objetivos

### Objetivos
- Control completo del *channel strip*: niveles, mutes, pan, EQ paramétrico,
  GEQ, compuerta, compresor, envíos, escenas.
- Medidores por canal en tiempo real y analizador de espectro (RTA).
- Presets y snapshots persistidos.
- Asistente de IA de ecualización con confirmación humana antes de aplicar.
- Instalable como PWA; despliegue en un solo `docker compose up`.

### No-objetivos
- Multitrack recording (la Qu-16 ya lo hace por USB).
- Edición de escenas almacenadas en la mesa más allá de recargarlas.
- Soporte para otros modelos de la familia Qu en la v1 (el protocolo es
  compatible, pero el mapa de canales cambia).

### Anti-objetivos
- Que la app pueda dejar la mesa en un estado inservible sin que el operador
  lo sepa: toda escritura de la IA pasa por confirmación y auditoría.
- Depender de un servicio en la nube: la IA y el audio se procesan en local.

## 3. Restricciones (medidas, no supuestas)

| Restricción | Dato real |
|---|---|
| Canal de control | TCP 51326, protocolo CMNet, tramas `7F` y `F7` |
| Firmware probado | Qu-16 fw **1.97** (board `0x01`) |
| Clientes remotos | máximo **8** (firmware ≥1.95) → una sola conexión, repartida por WebSocket |
| Medidores | **UDP 49152**, 20 bytes por canal |
| MIDI (51325) | documentado pero **sin acceso a EQ** → solo plan B |
| Volcado de estado | 25 888 B, cabecera de 67 B, 60 bloques de 192 B |

## 4. Enfoques considerados

| Enfoque | Qué aporta | Por qué se descartó / eligió |
|---|---|---|
| **A. Solo MIDI (51325)** | Rápido, documentado | ❌ No toca EQ ni dinámica: mata el asistente |
| **B. Envolver Mixing Station** | Nada que programar | ❌ Es una app cerrada; no hay API |
| **C. Protocolo CMNet nativo (51326)** | Control total, medidores nativos | ✅ **Elegido**, ya validado en Fase 0 |
| **D. Automatizar Qu-Pad por UI** | Ninguna ventaja | ❌ Frágil e imposible de desplegar |

Dentro de C, dos variantes de topología:

| Variante | Descripción | Decisión |
|---|---|---|
| Proxy transparente | El navegador habla 51326 a través de un túnel | ❌ Expone el protocolo al cliente y multiplica conexiones |
| **Espejo de estado en el servidor** | Backend dueño de la conexión; el cliente solo manda *intents* | ✅ **Elegido**: una conexión, estado autoritativo, reconexión centralizada |

## 5. Arquitectura

```
navegador (PWA)
  React 19 · TS · Vite · Tailwind v4 · Zustand · uPlot
        │  WebSocket: estado y medidores (binario Float32)
        │  REST: presets, escenas, IA
        ▼
FastAPI + Uvicorn (un proceso)
  ├── MixerLink      conexión TCP 51326, handshake, heartbeat, reconexión
  ├── StateMirror    estado autoritativo en memoria (fuente de verdad)
  ├── MeterLink      UDP 49152 → buffers circulares
  ├── Broadcaster    coalescing ~16 ms, difunde deltas por WS
  ├── AudioEngine    sounddevice sobre USB-B → FFT/RTA/LUFS
  ├── Assistant      IA con herramientas: lee estado + RTA, propone, aplica
  └── SQLite         presets, snapshots, preferencias, auditoría de la IA
```

### Decisiones
- **El backend es el único cliente de la mesa.** El navegador nunca abre 51326.
- **`StateMirror` es la fuente de verdad.** La UI pinta el espejo; manda
  *intents* y espera confirmación del eco de la mesa (no hay UI optimista a
  ciegas).
- **Los medidores van por un WebSocket aparte en binario**, no en JSON.
- **La IA no escribe directamente**: emite una propuesta, se registra en
  auditoría y se aplica solo tras confirmación explícita.

## 6. Fases

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Codec CMNet: handshake, volcado, decodificación | ✅ hecha |
| 1 | Monorepo, backend y frontend esqueletos, Compose, CI | 🔄 en curso |
| 2 | `MixerLink` + `StateMirror` + reconexión + heartbeat | pendiente |
| 3 | UI de mezcla real + medidores por UDP | pendiente |
| 4 | EQ, GEQ y dinámica (mapeo de `ValueID`) | pendiente |
| 5 | Audio USB-B: RTA y LUFS | pendiente |
| 6 | Asistente de IA de ecualización | pendiente |
| 7 | PWA, despliegue y endurecimiento | pendiente |

## 7. Lo que queda abierto

- **Mapeo semántico de los 60 bloques** del volcado (qué bloque es mix, FX, LR,
  DCA). Los 19 primeros están identificados por sus nombres.
- **Offsets de EQ/gate/comp dentro del bloque de 192 B.** Los datos están,
  pero no se ha identificado cada parámetro.
- **Direccionamiento de escritura** (`F7`): el formato está verificado, la
  correspondencia parámetro↔canal se cerrará en la Fase 2 contra la mesa real.
- **Modelo de IA**: ¿API en la nube o modelo local? Afecta al despliegue y a
  la privacidad; se decide en la Fase 6.

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| Escritura errónea sobre la mesa en directo | Banco de pruebas con la mesa libre; escritura idempotente primero; auditoría de todo cambio |
| Cambios de firmware rompen offsets | Los offsets se validan con tests sobre volcados reales; el dump se re-detecta por estructura, no por firma fija |
| Límite de 8 clientes | Una única conexión del backend |
| Latencia de la LAN inalámbrica | Medidores con coalescing y sin JSON |
