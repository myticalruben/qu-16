# Qu-16 Control — frontend

Interfaz web de la Fase 3 para la mesa **Allen & Heath Qu-16**, inspirada en
consolas tipo Mixing Station. Tema oscuro, rack alimentado por los canales
reales del backend, faders escribibles tras un candado de confirmación, cliente
HTTP/WebSocket con reconexión y PWA instalable.

## Stack

- React 19 + TypeScript + Vite 8
- Tailwind CSS v4 con `@tailwindcss/vite` (sin `tailwind.config.js` ni
  `postcss.config.js`)
- Zustand para el estado de la consola
- uPlot reservado para las gráficas de EQ de fases posteriores
- `vite-plugin-pwa` para el manifest, los iconos y el service worker
- Vitest + Testing Library + jsdom

## Uso

```bash
npm install
npm run dev        # http://localhost:5173
npm run test       # Vitest, una pasada
npm run build      # tsc -b && vite build -> dist/
npm run preview    # sirve dist/
```

En desarrollo, Vite hace proxy de `/api` y `/ws` a `http://localhost:8000`.
El frontend **no se conecta solo**: arranca en `disconnected` y la cabecera
ofrece el botón «Conectar». Así se puede abrir sin backend sin ruido de red.
Al recibir un mensaje `hello` el store pasa a `connected` y guarda la versión
del servidor; después, cada mensaje `state` sustituye el volcado de canales.
La insignia distingue el enlace con el backend del enlace con la mesa: si el
backend responde `connected: false`, muestra «Desconectado» aunque el socket
siga abierto, y dejan de llegar mensajes `meters`.

El rack pinta por defecto solo los canales con nombre. El control «Mostrar
todos» revela el resto (hasta decenas de canales), atenuados y con el nombre
vacío. Los medidores usan el nivel real de `meters` (−60 dB → 0 %, 0 dB →
100 %, lineal en dB) con umbrales verde/ámbar/rojo y pico con caída suave.

### Candado de escritura

El control **Control** de la cabecera arranca siempre apagado (no se persiste
entre recargas). Al pulsarlo aparece una confirmación explícita («Vas a poder
mover faders de la mesa real. El sonido cambiará.») con **Cancelar** y
**Activar control**. Solo se puede abrir si `GET /api/mixer/config` publica
`write_enabled: true`; en caso contrario el botón queda deshabilitado y muestra
«Bloqueado en el servidor». Con el candado apagado el rack indica «solo
lectura» y los faders no emiten peticiones.

Con el candado activo (y la mesa conectada), arrastrar un canal con nombre
actualiza la UI de forma optimista y envía el nivel al soltar. Durante los
primeros 400 ms de arrastre no se envía nada; a partir de ahí se manda como
máximo un POST cada 200 ms y siempre uno final al soltar. Mientras el dedo está
en el fader, los mensajes `state` del WebSocket no pisan ese canal. Si la API
responde 409/404/422 o falla la red, el nivel vuelve al valor anterior y aparece
un aviso que se retira solo a los 4 s.

### Contrato mínimo con el backend

- `GET /api/health` → `{ status, version?, mixer_connected?, uptime_s? }`
- `GET /api/mixer/status` → `{ connected, model?, firmware?, channels? }`
- `GET /api/mixer/config` → `{ write_enabled, model, connected }`; el candado
  solo se habilita con `write_enabled: true`.
- `POST /api/mixer/channels/{index}/level` con `{ "db": 4.9 }` →
  `{ index, value, db }`; 409 escritura deshabilitada, 404 índice inexistente,
  422 petición inválida.
- `WS /ws` → `{ "type": "hello", "payload": { "version": "0.1.0" } }` marca el
  enlace como listo y `{ "type": "state", "payload": { connected, model,
  firmware, updated_at, channels } }` entrega el volcado. Cada canal llega como
  `{ index, name, level_db, kind }`, con `level_db: null` para −∞ y `kind` en
  `input | stereo | other`. `{ "type": "meters", "payload": { "levels": [...] } }`
  llega hasta 20 veces por segundo; la posición es el índice de canal y cada
  valor es dB (`null` para silencio). La reconexión es exponencial (1 s → 30 s).

Los tipos viven en `src/lib/api.ts`, el cliente HTTP de escritura en
`writeChannelLevel` y el WebSocket en `src/lib/ws.ts`.

## Estructura

```text
src/
  App.tsx                 cabecera, rack y pie de la consola
  index.css               Tailwind v4, tokens oscuros y piezas a medida
  lib/api.ts              fetch tipado (salud, estado, config y nivel)
  lib/ws.ts               WebSocket con reconexión exponencial
  store/mixer.ts          Zustand: conexión, snapshot y canales normalizados
  components/
    ConnectionBadge.tsx
    ControlLock.tsx       candado, diálogo de confirmación y estados
    WriteErrorNotice.tsx  aviso efímero de fallo de escritura
    ChannelRack.tsx       escritura optimista y reversión
    ChannelStrip.tsx      fader arrastrable con freno
    MeterBar.tsx
  test/setup.ts
scripts/generate-icons.mjs  iconos PWA dibujados sin dependencias
```

## Docker

La imagen es multi-stage: compila con `node:22-alpine` y sirve estáticos con
`nginx:alpine`. `nginx.conf` incluye el fallback de SPA y el proxy de `/api` y
`/ws` a `backend:8000` (con `Upgrade`/`Connection` para WebSocket).

```bash
docker build -t qu16-frontend .
```

## Iconos

`npm run icons` regenera `public/icons/icon-{192,512}.png`,
`icon-maskable-512.png` y `apple-touch-icon.png` con el pequeño generador de
`scripts/generate-icons.mjs` (Node + zlib, sin dependencias).
