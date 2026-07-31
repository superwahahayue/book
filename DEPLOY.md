# Docker deployment

This deployment runs the Vue frontend in an Nginx container and the FastAPI
backend in a separate internal container. Nginx serves the SPA and forwards
`/api` requests to FastAPI; only Nginx is exposed publicly. The SQLite database
is stored in `./data` beside `docker-compose.yml`, so it stays intact when the
backend container is recreated.

## What the server needs

- Docker Engine 24+ with the Docker Compose plugin
- At least 1 GB of free disk space for the application image, plus space for
  the database and any model service you run separately
- A reachable model provider: an online provider is easiest for a remote
  server; Ollama can run on the host or another machine

## First deployment

1. Upload the project directory to the server, excluding local `.venv`,
   `frontend/node_modules`, and any existing local `data` unless that is
   intentional.
2. Create the persistent data directory and grant it to the fixed non-root
   container user (UID/GID `10001`):

   ```sh
   mkdir -p data
   sudo chown 10001:10001 data
   ```

3. In the project directory, create the server configuration:

   ```sh
   cp .env.example .env
   ```

4. Edit `.env` and set the provider values you use. Keep API keys only in this
   server-side file; do not commit or upload it to a public repository.
5. Start the service:

   ```sh
   docker compose up -d --build
   ```

6. Open `http://SERVER_IP:8000`. To use a different public port, set
   `APP_PORT` before starting, for example `APP_PORT=8080 docker compose up -d`.

Check service status and logs:

```sh
docker compose ps
docker compose logs -f --tail=100
```

## Deploy images from a registry

The dual-container deployment uses two images. Tag and push both from the build
machine, replacing `YOUR_USERNAME` with your Docker Hub username:

```sh
docker tag novel-generator-backend:0.0.1 YOUR_USERNAME/novel-generator-backend:0.0.1
docker tag novel-generator-frontend:0.0.1 YOUR_USERNAME/novel-generator-frontend:0.0.1
docker push YOUR_USERNAME/novel-generator-backend:0.0.1
docker push YOUR_USERNAME/novel-generator-frontend:0.0.1
```

On the server, add these values to `.env`, log in if the repositories are
private, then pull and start without a local build:

```dotenv
BACKEND_IMAGE=YOUR_USERNAME/novel-generator-backend:0.0.1
FRONTEND_IMAGE=YOUR_USERNAME/novel-generator-frontend:0.0.1
```

```sh
docker login
docker compose pull
docker compose up -d --no-build
```

### Minimal server upload

When deploying the published GHCR images, the server does not need the source
code, Dockerfile, or frontend files. Upload only `docker-compose.prod.yml` and
the server-side `.env` file, then rename the Compose file to
`docker-compose.yml` on the server. Create a `data/` directory beside them and
start with the commands above.

## Provider configuration

### Online API provider

Set `DEFAULT_PROVIDER` and the associated API variables in `.env`. The
container needs normal outbound HTTPS access to the provider endpoint.

### Ollama running on the Docker host

Start Ollama on the server and configure:

```dotenv
DEFAULT_PROVIDER=ollama
OLLAMA_HOST=http://host.docker.internal:11434
OLLAMA_DEFAULT_MODEL=gemma4:12b
```

The Compose file maps `host.docker.internal` to the Docker host on Linux. The
Ollama service must listen on an address that Docker containers can reach; its
model files and accelerator setup remain managed by Ollama rather than this
application container.

For Ollama on a different machine, use its reachable address instead, such as
`OLLAMA_HOST=http://192.0.2.10:11434`.

## Upgrade and rollback

After uploading a new version of the project, rebuild and recreate the frontend
and backend containers:

```sh
docker compose up -d --build
```

The `data/` directory is retained. To return to an earlier application version,
restore the earlier source directory or image tag, then run the same command.

## Back up the database

Stop the service briefly so the SQLite database is consistent, then archive
the persistent directory:

```sh
docker compose stop
tar -czf novels-data-$(date +%F).tar.gz data/
docker compose start
```

To restore, stop the service, replace `data/` with the backed-up copy, and
start it again. Keep backups outside the deployment directory.

## Put it behind HTTPS

For a public deployment, place Caddy, Nginx, or your hosting panel's reverse
proxy in front of the frontend service. Proxy traffic to `127.0.0.1:8000` (or
the chosen `APP_PORT`) and let that proxy manage TLS certificates. The backend
is not published to the host and remains reachable only through the internal
Docker network. If the app is only for personal use, do not expose port 8000
directly to the internet without access controls.
