FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_LOCKED=1 UV_NO_SYNC=1 UV_NO_DEV=1
# See https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project

COPY . /app

RUN --mount=type=cache,id=uv,target=/root/.cache/uv \
    uv sync --compile-bytecode

CMD ["uv", "run", "backup"]
