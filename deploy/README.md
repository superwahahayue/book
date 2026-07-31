# Server upload package

This folder is a production-only deployment package. It pulls the published
`0.0.1` frontend and backend images from GHCR; it does not need the project
source, `Dockerfile`, or Node/Python tooling on the server.

## Prepare the upload

1. Copy the existing root `.env` file into this `deploy/` folder, or copy
   `.env.example` to `.env` and enter the real `GEMINI_API_KEY`.
2. Upload the **contents** of this folder to `/opt/novel-generator` on the
   server. The final server directory must be:

   ```text
   /opt/novel-generator/
   ├── docker-compose.yml
   └── .env
   ```

   Do not upload `.env` to GitHub or include it in a public archive.

## Start on the server

```sh
cd /opt/novel-generator
mkdir -p data
sudo chown 10001:10001 data

# Required only when the GHCR package is private.
docker login ghcr.io -u superwahahayue

docker compose pull
docker compose up -d
docker compose ps
```

Open `http://SERVER_IP:8000` after both services report healthy. View logs with
`docker compose logs -f --tail=100`.
