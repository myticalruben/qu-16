"""Tests del WebSocket de estado y del endpoint de canales."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from qu16.protocol.framing import MixerVersion
from qu16_api import __version__
from qu16_api.main import app, state_hub, state_mirror

DUMP_PATH = Path(__file__).parent / "data" / "qu16-state.bin"
VERSION = MixerVersion.from_bytes(bytes.fromhex("01016101de11000000000000"))


def test_websocket_sends_hello_then_state() -> None:
    """El saludo va primero; después llega la instantánea completa."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            hello = websocket.receive_json()
            state = websocket.receive_json()

        response = client.get("/api/mixer/channels")

    assert hello == {"type": "hello", "payload": {"version": __version__}}
    assert state["type"] == "state"
    assert state["payload"] == {
        "connected": False,
        "model": None,
        "firmware": None,
        "updated_at": None,
        "channels": [],
    }
    assert response.status_code == 200
    assert response.json() == {"channels": [], "updated_at": None}


def test_state_is_broadcast_to_subscribers_on_change() -> None:
    """Actualizar el espejo y difundir propaga el estado por el WebSocket."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            assert websocket.receive_json()["type"] == "hello"
            initial = websocket.receive_json()
            assert initial["payload"]["connected"] is False

            # Se ejecuta en el bucle de la aplicación, no en el del test.
            client.portal.call(
                state_mirror.update_from_dump, VERSION, DUMP_PATH.read_bytes()
            )
            client.portal.call(state_hub.broadcast)

            message = websocket.receive_json()

        response = client.get("/api/mixer/channels")

    assert message["type"] == "state"
    payload = message["payload"]
    assert payload["connected"] is True
    assert payload["model"] == "QU-16"
    assert payload["firmware"] == "1.97"
    assert len(payload["channels"]) == 60
    assert payload["channels"][3] == {
        "index": 3,
        "name": "coro1",
        "level_db": 4.9,
        "kind": "input",
    }

    body = response.json()
    assert [channel["name"] for channel in body["channels"][:4]] == [
        "inala1",
        "inala2",
        "inala3",
        "coro1",
    ]
    assert body["updated_at"] is not None
