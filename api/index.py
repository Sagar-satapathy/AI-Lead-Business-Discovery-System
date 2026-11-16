"""
api/index.py - Vercel Serverless Entrypoint for FastAPI Application

Exposes the ASGI FastAPI application instance to Vercel's Python runtime.
Ensures repository root is included in sys.path so modules like backend,
data_processor, and ai_analyzer resolve seamlessly.
"""

import os
import sys

# Ensure repository root is on sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.main import app

# Export app for Vercel
__all__ = ["app"]
