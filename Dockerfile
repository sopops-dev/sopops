# Build the UI and native dependencies separately; runtime needs no Rust toolchain.
FROM node:22-slim AS web
RUN corepack enable
WORKDIR /web
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.12-slim-trixie AS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git build-essential \
    && rm -rf /var/lib/apt/lists/*
ARG RUST_VERSION=1.94.0
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain "$RUST_VERSION"
ENV PATH=/root/.cargo/bin:$PATH UV_PROJECT_ENVIRONMENT=/opt/venv
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv
WORKDIR /build
COPY pyproject.toml uv.lock ./
# uv verifies the registry hashes and exact Git revision in the frozen lockfile.
RUN uv sync --frozen --no-dev --no-install-project --extra postgres --extra hatchet --extra livekit

FROM python:3.12-slim-trixie
ARG SOP_REF=v0.1.2
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git \
    && git --version | python -c 'import sys; assert tuple(map(int, sys.stdin.read().split()[2].split(".")[:2])) >= (2,45)' \
    && curl -fsSL https://raw.githubusercontent.com/sopops-dev/sop/main/install.sh | SOP_REF=$SOP_REF SOP_INSTALL_DIR=/usr/local/bin sh \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
COPY --from=dependencies /opt/venv /opt/venv
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /app
COPY pyproject.toml README.md hatch_build.py ./
COPY src ./src
COPY skills ./skills
COPY --from=web /web/dist ./web/dist
RUN uv pip install --python /opt/venv/bin/python --no-cache --no-deps . && rm -rf web skills /usr/local/bin/uv

RUN mkdir -p /data/raad && chown -R nobody /data
VOLUME /data
ENV HOST=0.0.0.0 PORT=8484 SOP_BIN=/usr/local/bin/sop DATABASE_URL=sqlite:////data/sopops.db SOPOPS_RAAD_CACHE_DIR=/data/raad
EXPOSE 8484
USER nobody
CMD ["sopops"]
