"""Aplicación FastAPI de qu16-control.

La API sirve el estado del espejo en memoria y lo empuja por WebSocket. La
conexión con la mesa solo se abre si ``QU16_AUTO_CONNECT`` está activo; con el
valor por defecto (``false``) el proceso no abre ningún socket.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from qu16.link import MixerLink

from . import __version__
from .config import get_settings
from .routers import health
from .state import state_mirror
from .ws import StateHub

logger = logging.getLogger(__name__)

#: Reparte a los websockets cada instantánea que publica el enlace.
state_hub = StateHub(state_mirror)


def frontend_dist() -> Path | None:
    """Devuelve el primer directorio ``frontend/dist`` que exista, si hay alguno.

    Se admiten varias ubicaciones para cubrir tanto el arranque desde el
    repositorio (``backend/src/qu16_api/main.py``) como el despliegue en un
    único proceso. ``QU16_FRONTEND_DIST`` tiene prioridad.
    """
    module_path = Path(__file__).resolve()
    candidates: list[Path] = []

    override = os.environ.get("QU16_FRONTEND_DIST")
    if override:
        candidates.append(Path(override))

    candidates.extend(
        [
            # Repositorio: .../backend/src/qu16_api/main.py -> .../frontend/dist
            module_path.parents[3] / "frontend" / "dist",
            Path.cwd() / "frontend" / "dist",
            Path.cwd() / "dist",
            Path.cwd().parent / "frontend" / "dist",
        ]
    )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Arranca y detiene el enlace con la mesa según ``auto_connect``."""
    settings = get_settings()
    logger.info("Arrancando %s %s", app.title, __version__)

    link: MixerLink | None = None
    if settings.auto_connect:
        link = MixerLink(
            settings.mixer_host,
            settings.mixer_port,
            mirror=state_mirror,
            on_state=state_hub.on_state,
            reconnect_min=settings.reconnect_min,
            reconnect_max=settings.reconnect_max,
            keepalive_interval=settings.keepalive_interval,
        )
        link.start()
        logger.info(
            "Enlace con la mesa activado (%s:%d)",
            settings.mixer_host,
            settings.mixer_port,
        )
    else:
        logger.info(
            "Enlace con la mesa desactivado (QU16_AUTO_CONNECT=false)"
        )

    app.state.mixer_link = link
    try:
        yield
    finally:
        if link is not None:
            await link.stop()
        await state_mirror.mark_disconnected()
        logger.info("API detenida")


async def websocket_endpoint(websocket: WebSocket) -> None:
    """Canal de eventos en tiempo real.

    Al conectar envía el saludo con la versión y la instantánea actual, y a
    partir de ahí el :class:`StateHub` le empuja cada cambio de estado. Los
    mensajes entrantes se descartan a propósito (Fase 2 es de solo lectura).
    """
    await websocket.accept()
    await websocket.send_json(
        {"type": "hello", "payload": {"version": __version__}}
    )
    await state_hub.register(websocket)

    try:
        await websocket.send_json(
            {"type": "state", "payload": await state_mirror.snapshot()}
        )
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            # Fase 2: los mensajes entrantes se descartan a propósito.
    except WebSocketDisconnect:
        logger.debug("Cliente WebSocket desconectado")
    finally:
        await state_hub.unregister(websocket)


def create_app() -> FastAPI:
    """Construye la aplicación con CORS, routers, WebSocket y estáticos."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.add_api_websocket_route("/ws", websocket_endpoint)

    dist = frontend_dist()
    if dist is not None:
        # Se monta al final para que no tape las rutas de la API ni /ws.
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
        logger.info("Sirviendo frontend estático desde %s", dist)
    else:
        logger.info("frontend/dist no existe: solo se sirve la API")

    return app


app = create_app()
