"""Endpoints de salud y de estado de la mesa."""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..state import mixer_state

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Comprobación básica de vida de la API."""
    return {"status": "ok", "version": __version__}


@router.get("/mixer/status")
async def mixer_status() -> dict[str, bool | str | None]:
    """Estado en memoria del vínculo con la mesa (sin conectar todavía)."""
    return mixer_state.snapshot()
