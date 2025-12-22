FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml /app/pyproject.toml

# V1：不强制 uv.lock；如你希望可重复构建，请在本地 `uv lock` 并提交 uv.lock，然后把它也 COPY 进来。
RUN uv sync --no-dev

COPY app /app/app

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


