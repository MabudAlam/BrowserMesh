# Operator image (uv-managed): reconciles Browser objects into Pods.
FROM python:3.12-slim

WORKDIR /srv

RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY controller.py ./controller.py

# kopf connects to the in-cluster API and reconciles Browser resources.
CMD [".venv/bin/kopf", "run", "/srv/controller.py", "--verbose"]
