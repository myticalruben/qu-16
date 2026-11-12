"""Configuración de la API leída de variables de entorno con prefijo ``QU16_``."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: Orígenes permitidos por defecto: Vite en desarrollo y nginx en despliegue.
_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]


class Settings(BaseSettings):
    """Ajustes de la aplicación y de la conexión con la mesa.

    Todos los campos se pueden sobrescribir con variables de entorno, por
    ejemplo ``QU16_MIXER_HOST=192.168.100.67``. Las listas se aceptan tanto en
    JSON (``["http://a"]``) como separadas por comas (``http://a,http://b``).
    """

    model_config = SettingsConfigDict(
        env_prefix="QU16_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Qu-16 Control API"
    mixer_host: str = "192.168.100.67"
    mixer_port: int = Field(default=51326, ge=1, le=65535)
    #: Si es ``False`` (por defecto) la API no abre ningún socket: los tests y
    #: el CI no dependen de que haya una mesa en la red.
    auto_connect: bool = False
    #: Rango del retroceso exponencial entre reintentos de conexión.
    reconnect_min: float = Field(default=1.0, gt=0)
    reconnect_max: float = Field(default=30.0, gt=0)
    #: Periodo del latido de control mientras la sesión está viva.
    keepalive_interval: float = Field(default=0.5, gt=0)
    #: ``NoDecode`` evita que pydantic-settings intente decodificar la lista
    #: como JSON antes de que se ejecute el validador de abajo.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(_DEFAULT_CORS_ORIGINS)
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        """Normaliza la lista de orígenes escrita en el entorno."""
        if not isinstance(value, str):
            return value

        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError("cors_origins debe ser una lista JSON")
            return parsed
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _check_reconnect_range(self) -> "Settings":
        """Impide un rango de reconexión incoherente."""
        if self.reconnect_max < self.reconnect_min:
            raise ValueError("reconnect_max no puede ser menor que reconnect_min")
        return self


@lru_cache
def get_settings() -> Settings:
    """Devuelve los ajustes cacheados para que el entorno se lea una sola vez."""
    return Settings()
