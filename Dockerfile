# The review app in public mode. Holds public sample data only, and needs no key.
FROM python:3.12-slim-bookworm

ARG GIT_COMMIT=dev
LABEL org.opencontainers.image.revision=$GIT_COMMIT

ENV UV_LINK_MODE=copy \
    ERM_PUBLIC=1 \
    ERM_BUILD_COMMIT=$GIT_COMMIT \
    ERM_METRICS_PATH=/tmp/metrics.sqlite \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

RUN pip install --no-cache-dir uv==0.10.7

WORKDIR /app

# Dependencies first, so a code change reuses this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY .streamlit/ .streamlit/
COPY app/ app/
COPY erm/ erm/
COPY data/public/ data/public/
COPY data/sponsors/ data/sponsors/

RUN useradd --create-home --uid 1000 app && chown -R app /app
USER app

EXPOSE 8501
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD ["/app/.venv/bin/python", "-c", "import urllib.request as u; u.urlopen('http://localhost:8501/_stcore/health', timeout=4)"]

CMD ["/app/.venv/bin/streamlit", "run", "app/review.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
