# Qu-16 Control — frontend

Interfaz web de la Fase 2 para la mesa **Allen & Heath Qu-16**, inspirada en
consolas tipo Mixing Station. Tema oscuro, rack alimentado por los canales
reales del backend, cliente HTTP/WebSocket con reconexión y PWA instalable.

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
siga abierto, y los medidores se detienen a cero.

El rack pinta por defecto solo los canales con nombre. El control «Mostrar
todos» revela el resto (hasta decenas de canales), atenuados y con el nombre
vacío. Los medidores siguen siendo una maqueta animada hasta la Fase 3; los
faders son de solo lectura porque aún no envían comandos.

### Contrato mínimo con el backend

- `GET /api/health` → `{ status, version?, mixer_connected?, uptime_s? }`
- `GET /api/mixer/status` → `{ connected, model?, firmware?, channels? }`
- `WS /ws` → `{ "type": "hello", "payload": { "version": "0.1.0" } }` marca el
  enlace como listo y `{ "type": "state", "payload": { connected, model,
  firmware, updated_at, channels } }` entrega el volcado. Cada canal llega como
  `{ index, name, level_db, kind }`, con `level_db: null` para −∞ y `kind` en
  `input | stereo | other`. La reconexión es exponencial (1 s → 30 s).

Los tipos viven en `src/lib/api.ts` y el cliente en `src/lib/ws.ts`.

## Estructura

```text
src/
  App.tsx                 cabecera, rack y pie de la consola
  index.css               Tailwind v4, tokens oscuros y piezas a medida
  lib/api.ts              fetch tipado a /api/health y /api/mixer/status
  lib/ws.ts               WebSocket con reconexión exponencial
  store/mixer.ts          Zustand: conexión, snapshot y canales normalizados
  components/
    ConnectionBadge.tsx
    ChannelRack.tsx
    ChannelStrip.tsx
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
