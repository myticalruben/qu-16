#!/bin/bash
# Copia el proyecto a la laptop y (re)arranca la instancia.
# Uso: deploy/instance.sh [usuario@host]
set -eu
DEST="${1:-deepseek@ruben-alexander-laptop-ubuntu}"
DIR=/opt/qu16-app
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> empaquetando"
tar czf /tmp/qu16-app.tgz -C "$HERE/.." --exclude=.git --exclude=node_modules \
  --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache .

echo "==> copiando a $DEST"
cat /tmp/qu16-app.tgz | ssh "$DEST" "cat > /tmp/qu16-app.tgz"

echo "==> desplegando en $DIR"
ssh "$DEST" "set -e
  mkdir -p $DIR
  tar xzf /tmp/qu16-app.tgz -C $DIR
  cp $DIR/deploy/laptop/*.sh $DIR/ && chmod +x $DIR/*.sh
  [ -d $DIR/.venv ] || python3 -m venv $DIR/.venv
  $DIR/.venv/bin/pip -q install -e $DIR/backend
  $DIR/stop.sh || true
  $DIR/start.sh
  sleep 2
  $DIR/status.sh"
