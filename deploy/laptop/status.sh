#!/bin/bash
set -u
cd "$(dirname "$0")" || exit 1
if [ -f run/app.pid ] && kill -0 "$(cat run/app.pid)" 2>/dev/null; then
  echo "activo (pid $(cat run/app.pid))"
  curl -s -m 5 "http://127.0.0.1:${PORT:-8080}/api/mixer/config" || echo "sin respuesta"
  echo
else
  echo "detenido"
fi
