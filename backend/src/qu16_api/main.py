"""Aplicación FastAPI de qu16-control.

En la Fase 1 solo se sirve la API y el WebSocket de eventos. La conexión real
con la mesa llegará en la Fase 2; por eso el ``lifespan`` todavía no abre
ningún socket TCP.
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

from . import __version__
from .config import get_settings
from .routers import health
from .state import mixer_state

logger = logging.getLogger(__name__)


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
    """Ciclo de vida de la aplicación; sin conexión con la mesa en Fase 1."""
    logger.info("Arrancando %s %s", app.title, __version__)
    try:
        yield
    finally:
        mixer_state.mark_disconnected()
        logger.info("API detenida")


async def websocket_endpoint(websocket: WebSocket) -> None:
    """Canal de eventos en tiempo real.

    Al conectar envía el saludo con la versión y después descarta cualquier
    mensaje del cliente. En fases posteriores este canal empujará el estado
    de la mesa.
    """
    await websocket.accept()
    await websocket.send_json(
        {"type": "hello", "payload": {"version": __version__}}
    )

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            # Fase 1: los mensajes entrantes se descartan a propósito.
    except WebSocketDisconnect:
        logger.debug("Cliente WebSocket desconectado")


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
