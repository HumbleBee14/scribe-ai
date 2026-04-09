FROM python:3.14-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files first for layer caching
COPY pyproject.toml ./
RUN uv venv && uv pip install -e .

# Copy application code
COPY app/ app/
COPY scripts/ scripts/

# Copy knowledge data (pre-extracted JSON, chunks)
# Page images are mounted as a volume instead of baked into the image

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
