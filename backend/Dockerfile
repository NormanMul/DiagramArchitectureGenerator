# syntax=docker/dockerfile:1.7
# =============================================================================
# archgen-api Dockerfile
# =============================================================================
# Multi-stage build:
#   1. builder: install deps with uv into a venv
#   2. runtime: python:3.12-slim + graphviz binary + the venv
#
# Distroless is NOT used here: graphviz needs system libs (libexpat, libpng,
# libfontconfig, fonts-dejavu-core) that are messy to assemble in a distroless
# image. python:3.12-slim is the pragmatic minimum.
# =============================================================================

ARG PYTHON_VERSION=3.12.10
ARG UV_VERSION=0.11.7

# -----------------------------------------------------------------------------
# Stage 1: builder
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# uv (pinned)
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml uv.lock* ./
COPY app ./app

# Install into .venv inside /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --compile-bytecode

# -----------------------------------------------------------------------------
# Stage 2: runtime
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000

# Graphviz binary + cairo (for cairosvg SVG→PNG icon rasterization)
# + minimal font set the diagrams library needs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        graphviz \
        fonts-dejavu-core \
        libexpat1 \
        libfontconfig1 \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home-dir /app --shell /sbin/nologin app

WORKDIR /app

# Copy venv + source from builder
COPY --from=builder --chown=app:app /app/.venv ./.venv
COPY --from=builder --chown=app:app /app/app ./app

# Bundle icons (read-only at runtime).
COPY --chown=app:app ../icons /opt/archgen/icons

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
