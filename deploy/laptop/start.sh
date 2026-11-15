#!/bin/bash
# Arranca Qu-16 Control en la laptop.
set -u
cd "$(dirname "$0")" || exit 1
export QU16_AUTO_CONNECT="${QU16_AUTO_CONNECT:-true}"
export QU16_WRITE_ENABLED="${QU16_WRITE_ENABLED:-true}"
export QU16_MIXER_HOST="${QU16_MIXER_HOST:-192.168.100.67}"
export QU16_MIXER_PORT="${QU16_MIXER_PORT:-51326}"
export QU16_FRONTEND_DIST="${QU16_FRONTEND_DIST:-$(pwd)/frontend/dist}"
export QU16_POLL_INTERVAL="${QU16_POLL_INTERVAL:-2}"
PORT="${PORT:-8080}"
mkdir -p run
if [ -f run/app.pid ] && kill -0 "$(cat run/app.pid)" 2>/dev/null; then
  echo "ya está corriendo (pid $(cat run/app.pid))"
  exit 0
fi
setsid nohup .venv/bin/python -m uvicorn qu16_api.main:app --host 0.0.0.0 --port "$PORT" > run/app.log 2>&1 &
echo $! > run/app.pid
sleep 2
echo "arrancado: pid $(cat run/app.pid), puerto $PORT"
