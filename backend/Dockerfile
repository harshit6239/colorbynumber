FROM python:3.11-slim

WORKDIR /app

# Copy project metadata first for layer caching
COPY pyproject.toml ./

# Install only the runtime (non-dev) dependencies from pyproject.toml
RUN pip install --no-cache-dir "fastapi" "uvicorn[standard]" "httpx" "PyJWT" "python-multipart"

# Copy application code
COPY app.py ./

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
