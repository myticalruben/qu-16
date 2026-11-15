#!/bin/bash
set -u
cd "$(dirname "$0")" || exit 1
if [ -f run/app.pid ] && kill -0 "$(cat run/app.pid)" 2>/dev/null; then
  kill "$(cat run/app.pid)" && echo "detenido (pid $(cat run/app.pid))"
  rm -f run/app.pid
else
  echo "no estaba corriendo"
fi
