# Single-container Docker deployment, no docker-compose

Production runs as one Docker container (a single `Dockerfile`, no `docker-compose.yml`) on our own server, deployed over SSH. Postgres and the reverse proxy already run directly on the host, outside Docker — the container joins Docker's default bridge network and reaches Postgres via `host.docker.internal`, while the reverse proxy forwards to the container's published `127.0.0.1:8000`. We considered `--network host` (simpler DB access, no extra DNS entry needed) but rejected it to keep the container network-isolated from the host.
