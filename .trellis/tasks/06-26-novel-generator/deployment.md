# Container deployment addendum

## Requirements

- Deploy the application to a Linux server with Docker Compose through one HTTP
  port.
- Build the Vue SPA during image creation and serve it from an Nginx frontend
  container, which proxies `/api` to an internal FastAPI backend container.
- Persist SQLite data in a host-mounted `data/` directory.
- Load provider settings and secrets from a server-side `.env` file; never copy
  that file into the image or commit it.
- Document first launch, upgrades, log inspection, backup and restore, plus
  use of an Ollama instance running on the Docker host.

## Design

The Dockerfile has shared Node build stage plus two production targets: a slim
Python backend runtime and an Nginx frontend runtime containing `frontend/dist`.
Docker Compose publishes only the frontend, while the backend is available only
on the internal Compose network. It loads `.env` and mounts `./data` at
`/app/data` for the backend, restarts both services after a reboot, and maps
`host.docker.internal` to the Docker host for the backend. Ollama stays outside
this Compose stack because its models and accelerator configuration are
independently managed.

## Implementation and validation

1. Add `Dockerfile`, `.dockerignore`, `docker-compose.yml`, Nginx routing, and
   `DEPLOY.md`.
2. Validate Compose syntax.
3. Build both targets and start the services with an isolated test `.env`.
4. Confirm Nginx returns the SPA, proxies `GET /api/novels` successfully, and
   the SQLite file is created in the mounted data directory.
5. Provide a deployment-only Compose file with no build context, so a server
   deploying GHCR images needs only that file, `.env`, and `data/`.
6. Provide a self-contained upload directory with fixed, verified `0.0.1` GHCR
   image references and a minimal environment template.

## Configuration update (2026-07-31)

The Gemini proxy default and both environment templates use the externally
reachable Cloudflare Tunnel URL rather than a localhost-only endpoint. This
ensures a server-side container can reach the configured provider without a
host-network dependency.
