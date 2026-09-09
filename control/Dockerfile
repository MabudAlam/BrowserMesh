# Control plane image (uv-managed).
FROM python:3.12-slim

WORKDIR /srv

# Install uv (the package manager) and sync the locked environment.
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Ship the application code.
COPY app ./app

# Run the FastAPI app with the uv-managed virtualenv's uvicorn.
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
