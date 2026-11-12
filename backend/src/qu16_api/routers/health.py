"""Endpoints de salud y de estado de la mesa."""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..state import state_mirror

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Comprobación básica de vida de la API."""
    return {"status": "ok", "version": __version__}


@router.get("/mixer/status")
async def mixer_status() -> dict[str, object]:
    """Instantánea completa del vínculo con la mesa."""
    return await state_mirror.snapshot()


@router.get("/mixer/channels")
async def mixer_channels() -> dict[str, object]:
    """Canales del último volcado y momento en que se recibió."""
    snapshot = await state_mirror.snapshot()
    return {
        "channels": snapshot["channels"],
        "updated_at": snapshot["updated_at"],
    }
