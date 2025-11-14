#!/bin/bash

SCRIPT="server.app:app"
PID_FILE="uvicorn.pid"
LOG_FILE="uvicorn.log"

set -a
source .env
set +a

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

start() {
  if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "Uvicorn is already running with PID $(cat "$PID_FILE")"
    exit 1
  fi

  nohup uvicorn "$SCRIPT" --host "$HOST" --port "$PORT" --reload > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "Started Uvicorn ($SCRIPT) with PID $(cat "$PID_FILE"). Logs: $LOG_FILE"
}

stop() {
  if [ ! -f "$PID_FILE" ]; then
    echo "No PID file found for Uvicorn"
    exit 1
  fi

  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "Stopped Uvicorn (PID $PID)"
    rm "$PID_FILE"
  else
    echo "Process $PID not running"
    rm "$PID_FILE"
  fi
}

status() {
  if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "Uvicorn is running with PID $(cat "$PID_FILE")"
  else
    echo "Uvicorn is not running"
  fi
}

case "$1" in
  start) start ;;
  stop) stop ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|status}" ;;
esac
