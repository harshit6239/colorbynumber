# Set required env vars before any test module imports app.py
import os

os.environ.setdefault("PIPELINE_API_KEY", "test-key")
