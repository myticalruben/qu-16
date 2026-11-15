"""Endpoints de escritura de canales y de configuración del mixer."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from qu16.client import QuError
from qu16.link import MixerLink, WriteDisabledError
from qu16.protocol import fader_law

from ..config import Settings, get_settings
from ..state import state_mirror

router = APIRouter(prefix="/api/mixer", tags=["channels"])

#: Precisión de los dB publicados, igual que en el espejo.
_DB_DECIMALS = 1


class LevelRequest(BaseModel):
    """Cuerpo de la escritura de nivel: valor crudo o dB, nunca ambos."""

    value: int | None = Field(default=None, ge=0, le=0xFFFF)
    db: float | None = None

    @model_validator(mode="after")
    def _validate_choice(self) -> "LevelRequest":
        """Exige exactamente uno de ``value`` o ``db`` y un dB finito."""
        if (self.value is None) == (self.db is None):
            raise ValueError("indica exactamente uno de value o db")
        if self.db is not None and not math.isfinite(self.db):
            raise ValueError("db debe ser un número finito")
        return self

    def raw_value(self) -> int:
        """Valor crudo de 16 bits; convierte con la ley de fader si hace falta."""
        if self.value is not None:
            return self.value
        assert self.db is not None
        return fader_law.to_raw(self.db)


def _db_of(value: int) -> float | None:
    """dB de presentación para un valor crudo (``None`` si es -infinito)."""
    db = fader_law.to_db(value)
    return None if db is None else round(db, _DB_DECIMALS)


@router.get("/config")
async def mixer_config(
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Informa a la interfaz de si puede escribir y del estado de la mesa."""
    snapshot = await state_mirror.snapshot()
    return {
        "write_enabled": settings.write_enabled,
        "model": snapshot["model"],
        "connected": snapshot["connected"],
    }


@router.post("/channels/{index}/level")
async def set_channel_level(
    index: int,
    body: LevelRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Escribe el nivel principal de un canal y actualiza el espejo al momento.

    El candado de configuración se comprueba antes que nada: con
    ``write_enabled=False`` no se llega a tocar el enlace. El índice se valida
    contra el último volcado, de modo que un canal inexistente devuelve 404.
    """
    if not settings.write_enabled:
        raise HTTPException(status_code=409, detail="escritura deshabilitada")

    link: MixerLink | None = getattr(request.app.state, "mixer_link", None)
    if link is None or not link.connected:
        raise HTTPException(status_code=422, detail="canal no conectado")

    snapshot = await state_mirror.snapshot()
    channels = snapshot["channels"]
    if not isinstance(channels, list) or not 0 <= index < len(channels):
        raise HTTPException(status_code=404, detail="el índice de canal no existe")

    value = body.raw_value()
    try:
        await link.set_level(index, value)
    except WriteDisabledError:
        # El enlace y la configuración deberían coincidir; si no, sigue siendo
        # una escritura deshabilitada de cara al cliente.
        raise HTTPException(status_code=409, detail="escritura deshabilitada") from None
    except QuError:
        # La conexión se cayó entre la comprobación y el envío.
        raise HTTPException(status_code=422, detail="canal no conectado") from None

    return {"index": index, "value": value, "db": _db_of(value)}
