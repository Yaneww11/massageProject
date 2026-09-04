#!/bin/sh
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

VENV_DIR="${VENV_DIR:-$REPO_DIR/venv}"
GUNICORN_PID_FILE="${GUNICORN_PID_FILE:-$REPO_DIR/gunicorn.pid}"
GUNICORN_BIND="${GUNICORN_BIND:-127.0.0.1:8000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"

git pull origin main

. "$VENV_DIR/bin/activate"

pip install --no-cache-dir -r requirements.txt

python manage.py migrate --noinput
python manage.py compilemessages
python manage.py collectstatic --noinput

if [ -f "$GUNICORN_PID_FILE" ] && kill -0 "$(cat "$GUNICORN_PID_FILE")" 2>/dev/null; then
    kill "$(cat "$GUNICORN_PID_FILE")"
    while kill -0 "$(cat "$GUNICORN_PID_FILE")" 2>/dev/null; do
        sleep 1
    done
fi

nohup gunicorn massageProject.wsgi:application \
    --bind "$GUNICORN_BIND" \
    --workers "$GUNICORN_WORKERS" \
    --pid "$GUNICORN_PID_FILE" \
    --daemon \
    --log-file "$REPO_DIR/gunicorn.log"
