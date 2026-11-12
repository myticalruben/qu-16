"""Fixtures compartidas por los tests del backend."""

from __future__ import annotations

import pytest

from qu16_api.state import state_mirror


@pytest.fixture(autouse=True)
async def reset_state_mirror() -> None:
    """Aísla los tests que comparten el espejo global de la API."""
    await state_mirror.reset()
    yield
    await state_mirror.reset()
