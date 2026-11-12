FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# WeasyPrint runtime libraries (reports extra) and OpenMP for LightGBM (ml extra)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ src/
RUN uv sync --frozen --no-dev --extra agents --extra gemini --extra ml --extra reports --extra observability

COPY migrations/ migrations/
COPY alembic.ini ./
COPY demo_data/ demo_data/
COPY scripts/ scripts/

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8080
CMD ["sh", "-c", "alembic upgrade head && uvicorn reic.bootstrap.app:create_app --factory --host 0.0.0.0 --port 8080"]
