#!/bin/sh
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

git pull

docker build -t massageproject:latest .

docker stop massageproject 2>/dev/null || true
docker rm massageproject 2>/dev/null || true

docker run -d \
  --name massageproject \
  --restart unless-stopped \
  --add-host=host.docker.internal:host-gateway \
  --env-file "$REPO_DIR/.env" \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  -p 127.0.0.1:8000:8000 \
  massageproject:latest
