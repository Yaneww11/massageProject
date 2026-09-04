#!/bin/sh
# Cron watchdog: restarts gunicorn if it was killed (e.g. by SiteGround resource limits).
# Silent when healthy; prints a message on restart so SiteGround's cron mailer only
# notifies on actual downtime.
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

VENV_DIR="${VENV_DIR:-$REPO_DIR/venv}"
GUNICORN_PID_FILE="${GUNICORN_PID_FILE:-$REPO_DIR/gunicorn.pid}"
GUNICORN_BIND="${GUNICORN_BIND:-127.0.0.1:8000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
WATCHDOG_LOG="$REPO_DIR/gunicorn-watchdog.log"

is_pid_alive() {
    [ -f "$GUNICORN_PID_FILE" ] && kill -0 "$(cat "$GUNICORN_PID_FILE" 2>/dev/null)" 2>/dev/null
}

is_port_responding() {
    curl -sf -o /dev/null "http://$GUNICORN_BIND/"
}

if is_pid_alive && is_port_responding; then
    exit 0
fi

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"
PID_STATE="dead"
is_pid_alive && PID_STATE="alive"
PORT_STATE="down"
is_port_responding && PORT_STATE="up"

{
    echo "[$TIMESTAMP] gunicorn appears down (pidfile: $PID_STATE, port: $PORT_STATE). Restarting."
    echo "--- last 30 lines of gunicorn.log ---"
    tail -n 30 "$REPO_DIR/gunicorn.log" 2>/dev/null
    echo "--------------------------------------"
} | tee -a "$WATCHDOG_LOG"

if [ -f "$GUNICORN_PID_FILE" ]; then
    OLD_PID="$(cat "$GUNICORN_PID_FILE" 2>/dev/null || true)"
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        while kill -0 "$OLD_PID" 2>/dev/null; do
            sleep 1
        done
    fi
fi

. "$VENV_DIR/bin/activate"

nohup gunicorn massageProject.wsgi:application \
    --bind "$GUNICORN_BIND" \
    --workers "$GUNICORN_WORKERS" \
    --pid "$GUNICORN_PID_FILE" \
    --daemon \
    --log-file "$REPO_DIR/gunicorn.log" \
    >/dev/null 2>&1

echo "[$TIMESTAMP] restart command issued." | tee -a "$WATCHDOG_LOG"
