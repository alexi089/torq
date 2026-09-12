FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
RUN uv sync --frozen --no-dev

# runtime CMD uses `uv run`; disable its automatic sync so the container
# provably never re-syncs (installs are already done above, at build time)
ENV UV_NO_SYNC=1

EXPOSE 8080
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
