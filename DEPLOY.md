# Deploying DubForge on an Ubuntu server

Tested on Ubuntu 24.04 (x86_64) with Docker Engine and the Compose plugin. Everything runs
in containers: web (nginx), api, pipeline (worker), Postgres and Redis.

## Sizing

| Setup | RAM | Disk |
| --- | --- | --- |
| Mock providers, or Whisper `small.en` only | 2 GB **plus a 2 GB swap file** | 20 GB |
| Real translation and voices (`PIPELINE_EXTRAS="nllb tts-mms"`) | 8 GB or more | 40 GB or more |
| Also keeping background sound (`PIPELINE_EXTRAS="nllb tts-mms background"`) | 8 GB or more | 40 GB or more |

One vCPU works but builds and transcription are slow.

## 1. Server setup (once)

```bash
apt-get update && apt-get install -y docker.io docker-compose-v2 docker-buildx
systemctl enable --now docker

# swap, so a 2 GB machine does not run out of memory while building or transcribing
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# firewall: SSH and the web port only (Postgres, Redis and the API are never published)
ufw allow OpenSSH && ufw allow 80/tcp && ufw --force enable
```

`docker-buildx` is required: the Dockerfiles use BuildKit cache mounts.

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env` (these are read by Compose):

```
WEB_PORT=80
POSTGRES_PASSWORD=<long random string>      # e.g. openssl rand -hex 24
COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
STT_PROVIDER=mock                            # mock | whisper
TRANSLATION_PROVIDER=mock                    # mock | nllb
TTS_PROVIDER=mock                            # mock | edge | mms
```

`COMPOSE_FILE` names both files explicitly, so the development-only
`docker-compose.override.yml` is never applied on the server.

Set a login for the site (the app has no accounts of its own):

```bash
mkdir -p deploy
printf 'admin:%s\n' "$(openssl passwd -apr1 'choose-a-password')" > deploy/htpasswd
chown 101:101 deploy/htpasswd && chmod 600 deploy/htpasswd   # the proxy runs as uid 101
```

Without the `chown`, every request with a password fails with a 500 ("Permission denied").

## 3. Start

```bash
docker compose up -d --build
docker compose ps          # every service should be Up / healthy
```

Open `http://<server-ip>/` and sign in.

## What is and is not exposed

- Public: the web app on `WEB_PORT`, behind the password.
- Blocked at the proxy: `/api/internal/*` (the worker's callbacks, which have no login of
  their own) and `/api/docs`, `/api/redoc`, `/api/openapi.json`.
- Local to the server only: the API on `127.0.0.1:8001`.
- Not published: Postgres and Redis.

## Operating

```bash
docker compose logs -f api pipeline     # logs (rotated: 3 x 10 MB per service)
docker compose up -d --build            # update after pulling new code
docker compose down                     # stop; add -v to also delete data
```

Data lives in the `postgres-data`, `redis-data` and `media-data` volumes. Back them up
before upgrading or deleting anything.

## HTTPS

This setup serves plain HTTP, so the password and uploads are not encrypted in transit.
For anything beyond a demo, put a TLS front in front of it (for example Caddy with a domain
name) and keep `WEB_PORT` bound to localhost.
