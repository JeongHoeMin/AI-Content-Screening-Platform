FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project

COPY app ./app
COPY main.py ./main.py
RUN uv sync --frozen

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD ["/app/.venv/bin/python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/health')"]

CMD ["/app/.venv/bin/uvicorn", "app.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
