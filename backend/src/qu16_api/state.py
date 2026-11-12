"""Instancia compartida del estado de la mesa en la API.

El espejo lo actualiza el enlace de solo lectura y lo consultan los routers y
el WebSocket, que deben ver siempre la misma copia.
"""

from __future__ import annotations

from qu16.mirror import StateMirror

#: Fuente de verdad que comparten enlace, routers y suscriptores del WebSocket.
state_mirror = StateMirror()
