#!/bin/sh
# Cron job: rotates gunicorn.log daily and keeps only the last 5 days.
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

GUNICORN_PID_FILE="${GUNICORN_PID_FILE:-$REPO_DIR/gunicorn.pid}"
LOG_FILE="$REPO_DIR/gunicorn.log"

if [ -s "$LOG_FILE" ]; then
    mv "$LOG_FILE" "$LOG_FILE.$(date '+%Y-%m-%d')"

    if [ -f "$GUNICORN_PID_FILE" ]; then
        OLD_PID="$(cat "$GUNICORN_PID_FILE" 2>/dev/null || true)"
        [ -n "$OLD_PID" ] && kill -USR1 "$OLD_PID" 2>/dev/null || true
    fi
fi

find "$REPO_DIR" -maxdepth 1 -name 'gunicorn.log.*' -mtime +5 -delete
