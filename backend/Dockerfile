FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.6.14@sha256:3362a526af7eca2fcd8604e6a07e873fb6e4286d8837cb753503558ce1213664 /uv /usr/local/bin/uv

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --no-create-home app \
    && chown app:app /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen \
    && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH"

USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
