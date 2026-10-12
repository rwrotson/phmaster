FROM python:3.14-slim

# Debian's ffmpeg is older than the required 8.1.
COPY --from=mwader/static-ffmpeg:9.0.2@sha256:7d9bdaaf887f7e6ce6151f67325c344074b5ff1fb75316011c3376503e449a7b /ffmpeg /ffprobe /usr/local/bin/
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PHMASTER_LOG__DIR=/tmp/phmaster-logs

WORKDIR /media
ENTRYPOINT ["phmaster"]
CMD ["--help"]
