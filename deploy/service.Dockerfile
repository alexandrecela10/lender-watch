# Lender Watch hosted service: the connector for Claude and the Excel add-in, on one address.
# Public filings and the seed of automated answers only. No key, no .env, no AI judge.
# It refuses to start on a public address without sign-in settings (LW_AUTH_ISSUER and LW_AUTH_AUDIENCE).
FROM python:3.12-slim-bookworm

ARG GIT_COMMIT=dev
LABEL org.opencontainers.image.revision=$GIT_COMMIT

ENV UV_LINK_MODE=copy \
    ERM_BUILD_COMMIT=$GIT_COMMIT \
    ERM_METRICS_PATH=/data/metrics.sqlite \
    LW_HOST=0.0.0.0 \
    LW_PORT=8080 \
    LW_DATA_DIR=/data

RUN pip install --no-cache-dir uv==0.10.7

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

COPY erm/ erm/
COPY app/desk/excel/ app/desk/excel/
COPY data/public/ data/public/

RUN useradd --create-home --uid 1000 app && mkdir -p /data && chown -R app /app /data
USER app

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
  CMD ["/app/.venv/bin/python", "-c", "import urllib.request as u; u.urlopen('http://localhost:8080/health', timeout=4)"]

CMD ["/app/.venv/bin/python", "-m", "erm.service"]
