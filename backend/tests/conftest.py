"""
Set required environment variables before app.py is imported by any test.
This file is loaded by pytest before test collection begins.
"""
import os

os.environ.setdefault("PIPELINE_URL", "http://fake-pipeline")
os.environ.setdefault("PIPELINE_API_KEY", "fake-pipeline-key")
os.environ.setdefault("JWT_SECRET", "test-secret")
