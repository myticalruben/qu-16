# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Etapa 1: construir el entorno virtual con el paquete y sus dependencias.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Primero el manifiesto para aprovechar la caché de capas de Docker.
COPY pyproject.toml ./
COPY src ./src

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install .

# ---------------------------------------------------------------------------
# Etapa 2: imagen final mínima, con usuario sin privilegios.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# QU16_FRONTEND_DIST permite montar el frontend compilado en un solo proceso.
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    QU16_FRONTEND_DIST=/app/frontend/dist

RUN groupadd --system --gid 1001 qu16 \
    && useradd --system --uid 1001 --gid qu16 --create-home --shell /usr/sbin/nologin qu16

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
RUN mkdir -p /app/frontend && chown -R qu16:qu16 /app

USER qu16

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status == 200 else 1)"]

CMD ["uvicorn", "qu16_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
