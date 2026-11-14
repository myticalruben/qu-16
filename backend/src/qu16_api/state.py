"""Instancia compartida del estado de la mesa en la API.

El espejo lo actualiza el enlace de solo lectura y lo consultan los routers y
el WebSocket, que deben ver siempre la misma copia.
"""

from __future__ import annotations

from qu16.meters import MeterState
from qu16.mirror import StateMirror

#: Fuente de verdad que comparten enlace, routers y suscriptores del WebSocket.
state_mirror = StateMirror()
#: Último nivel de cada canal que comparten el receptor UDP y la difusión.
state_meters = MeterState()
