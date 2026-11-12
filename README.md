# Qu-16 Control

Control web completo para la mesa **Allen & Heath Qu-16**, con interfaz tipo
Mixing Station y un asistente de IA para ecualizar.

El canal de control es el **protocolo nativo CMNet** (TCP 51326) que usan
Qu-Pad y Mixing Station. No se depende de ninguna app de terceros.

---

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Codec CMNet: handshake, volcado de estado, ley de fader | ✅ |
| 1 | Monorepo, esqueletos de backend y frontend, Compose, CI | ✅ |
| 2 | `MixerLink` + espejo de estado + reconexión (solo lectura) | ✅ |
| 3 | UI de mezcla real y medidores | ⏳ |
| 4 | EQ, GEQ y dinámica | ⏳ |
| 5 | Audio USB-B: RTA y LUFS | ⏳ |
| 6 | Asistente de IA de ecualización | ⏳ |
| 7 | PWA y despliegue final | ⏳ |

## Estructura

```
backend/                 API y protocolo (Python 3.12)
  src/qu16/              codec CMNet: tramas, volcado, ley de fader
  src/qu16_api/          FastAPI: /api/health, /api/mixer/status, WS /ws
  tests/                 pytest
frontend/                SPA (React 19 + TS + Vite + Tailwind v4)
  src/store/             Zustand
  src/components/        faders y medidores
docker-compose.yml       backend + frontend (nginx)
deploy/                  guía de despliegue en la laptop de la mesa
docs/                    hallazgos de protocolo y diseño
```

## Arranque rápido

```bash
make install   # venv de backend + dependencias de frontend
make test      # pytest + vitest
make dev       # backend en :8000 y frontend en :5173
```

Sin `make`:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cd backend && .venv/bin/python -m pytest -q
cd frontend && npm install && npx vitest run && npm run build
```

## Sonda contra la mesa real

```bash
cd backend && .venv/bin/python scripts/probe.py --host 192.168.100.67 --show 20
```

Si tu equipo no está en la red de la mesa, usa un túnel SSH contra la laptop
que sí lo está:

```bash
ssh -N -L 51326:192.168.100.67:51326 usuario@laptop
cd backend && .venv/bin/python scripts/probe.py --host 127.0.0.1
```

## Despliegue

Ver [deploy/README.md](deploy/README.md). Resumen:

```bash
docker network create qu16-lan   # red con acceso a la mesa
docker compose up -d --build     # UI en http://<host>:8080
```

## El protocolo en una línea

- **TCP 51326** — canal real. Tramas de sistema `7F · grupo · len(LE16) · datos`
  y comandos DSP `F7` + 8 bytes.
- **UDP 49152** — medidores.
- **TCP 51325** — MIDI documentado, útil solo para faders, mutes, pans y
  escenas: **no toca la EQ**.
- **UDP 51320** — descubrimiento (`QU Find` → `Qu-16`).

Detalles medidos sobre la mesa real en
[docs/fase0-hallazgos.md](docs/fase0-hallazgos.md).
