FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

COPY . .

EXPOSE 8000

# Shell-form CMD so `&&` runs via /bin/sh and ${PORT} (set by Render) expands at
# runtime. Migrations run at startup (idempotent) since the free web plan has no
# preDeployCommand. The worker service overrides this via its own dockerCommand.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
