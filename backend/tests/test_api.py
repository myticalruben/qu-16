"""Tests de la API FastAPI: salud, estado y WebSocket."""

from __future__ import annotations

from fastapi.testclient import TestClient

from qu16_api import __version__
from qu16_api.main import app


def test_health_returns_ok_and_version() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_mixer_status_returns_initial_state() -> None:
    with TestClient(app) as client:
        response = client.get("/api/mixer/status")

    assert response.status_code == 200
    assert response.json() == {
        "connected": False,
        "model": None,
        "firmware": None,
        "updated_at": None,
        "channels": [],
    }


def test_websocket_receives_hello() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            message = websocket.receive_json()

    assert message == {"type": "hello", "payload": {"version": __version__}}


def test_websocket_discards_client_messages() -> None:
    """Enviar texto o binario no debe romper la conexión."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            assert websocket.receive_json()["type"] == "hello"
            websocket.send_text("ignórame")
            websocket.send_bytes(b"ignore-me")
            # La conexión sigue viva: cerrar sin excepciones es suficiente.
