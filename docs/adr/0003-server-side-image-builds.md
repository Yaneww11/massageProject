# Build the Docker image on the server, no registry or CI

Deploys are: SSH in, `git pull`, `docker build`, stop/replace the running container. There is no image registry (Docker Hub/GHCR) and no CI pipeline building the image elsewhere. This means brief downtime during each deploy (a plain restart, not blue-green) and no build-once/deploy-anywhere image — an acceptable trade-off for a single-server deployment; revisit if we ever run multiple servers or need zero-downtime deploys.
