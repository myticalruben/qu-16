#!/bin/bash
# Copia esta instancia a la laptop y la (re)arranca.
# Uso: deploy/instance.sh [usuario@host]
set -eu
DEST="${1:-deepseek@ruben-alexander-laptop-ubuntu}"
DIR=/opt/qu16-app

echo "==> empaquetando"
tar czf /tmp/qu16-app.tgz --exclude=.git --exclude=node_modules \
  --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache .

echo "==> copiando a $DEST"
cat /tmp/qu16-app.tgz | ssh "$DEST" "cat > /tmp/qu16-app.tgz"

echo "==> desplegando en $DIR"
ssh "$DEST" "set -e
  mkdir -p $DIR
  tar xzf /tmp/qu16-app.tgz -C $DIR
  [ -d $DIR/.venv ] || python3 -m venv $DIR/.venv
  $DIR/.venv/bin/pip -q install -e $DIR/backend
  [ -x $DIR/start.sh ] || { echo 'faltan start.sh/stop.sh/status.sh'; exit 1; }
  $DIR/stop.sh || true
  $DIR/start.sh
  sleep 2
  $DIR/status.sh"
