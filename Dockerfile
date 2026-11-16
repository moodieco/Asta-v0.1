# syntax=docker/dockerfile:1
#
# ASTA ships two runtimes in one image: the Vite dashboard is built with Node,
# the scanner engine + dashboard server run on Python. Render builds this file
# directly (see render.yaml), so a push to the branch is the whole deploy.

# --- 1. dashboard build ----------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- 2. runtime ------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install . && rm -rf /root/.cache

COPY config ./config
COPY --from=web /web/dist ./web/dist

# Runtime state: history db, scanner library, share tokens, alert log. Mount a
# volume at /var/data and set ASTA_DATA_DIR=/var/data to keep it across deploys.
RUN useradd --create-home --uid 10001 asta \
    && mkdir -p data/history data/logs data/scanners data/alerts data/cache /var/data \
    && chown -R asta:asta /app /var/data

# Render mounts the disk root-owned, so the container starts as root, fixes the
# mount's ownership and drops to `asta` (see docker/entrypoint.sh).
COPY docker/entrypoint.sh /usr/local/bin/asta-entrypoint
RUN chmod +x /usr/local/bin/asta-entrypoint
ENTRYPOINT ["/usr/local/bin/asta-entrypoint"]

EXPOSE 4310
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '4310'), timeout=4)"

# Hosting platforms inject PORT and route to 0.0.0.0. --no-browser matters:
# there is no browser in a container, and webbrowser.open would only log noise.
CMD asta serve --host 0.0.0.0 --port "${PORT:-4310}" --no-browser
