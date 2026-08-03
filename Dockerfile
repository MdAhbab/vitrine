# syntax=docker/dockerfile:1

FROM node:20-alpine AS frontend
WORKDIR /src/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build


FROM python:3.11-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ENV=prod \
    DATABASE_URL=sqlite+aiosqlite:////data/vitrine.db \
    EVENT_BUS=memory \
    CACHE=memory \
    FRONTEND_ORIGIN=https://vitrine.ahbab.dev

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r /app/backend/requirements.txt

COPY backend /app/backend
COPY --from=frontend /src/frontend/dist /app/frontend/dist
COPY docker/entrypoint.sh /entrypoint.sh

# Ship the seeded database inside the image. The entrypoint copies it onto the
# /data volume on first boot, so a fresh VM comes up fully seeded with no extra
# step. An existing volume is left untouched.
COPY vitrine.db /app/seed/vitrine.db

RUN chmod +x /entrypoint.sh \
    && mkdir -p /data /app/files

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
# ONE worker, deliberately. With EVENT_BUS=memory and CACHE=memory (the settings
# baked in above) every piece of shared state lives in-process: the event bus,
# the AI result cache, the daily spend cap, and the rate limiter. A second
# worker does not scale those — it forks them, so the OPENAI_DAILY_LIMIT_USD
# kill-switch and every rate limit silently double, cache hits halve, and two
# processes contend for the same SQLite file. FastAPI is async, so one worker
# already serves concurrent requests. Raise this only after moving the bus and
# cache to Redis (EVENT_BUS=redis, CACHE=redis).
CMD ["gunicorn", "backend.gateway.app:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "1", "-b", "0.0.0.0:8000", "--timeout", "120", "--graceful-timeout", "30"]
