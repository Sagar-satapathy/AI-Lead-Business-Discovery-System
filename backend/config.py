"""
backend/config.py - Application Configuration & Environment Settings

Loads configuration securely from environment variables and .env file.
Supports dual AI providers (OpenAI and Google Gemini) as well as fallback NLP,
PostgreSQL or SQLite database connection strings, and CORS configuration.
"""

import os
from typing import List, Optional
from dotenv import load_dotenv

# Load root .env file if available
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)


class Settings:
    # Application Info
    APP_NAME: str = "AI Lead Business Discovery System API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Database Configuration
    # Defaults to the existing SQLite leads.db in root workspace.
    # Set DATABASE_URL=postgresql://user:password@localhost:5432/leads_db to use PostgreSQL.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'leads.db')}"
    )

    # AI Configuration
    # Supports OpenAI and/or Google Gemini
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    # Preferred AI provider: 'auto', 'openai', 'gemini', 'fallback'
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "auto").lower()

    # External Search / Discovery Provider Keys (Free & Optional)
    # Tavily: Primary free external search provider (free 1,000 queries/month)
    TAVILY_API_KEY: Optional[str] = os.getenv("TAVILY_API_KEY")
    # Serper: Optional external provider (used only if explicitly configured)
    SERPER_API_KEY: Optional[str] = os.getenv("SERPER_API_KEY")
    SERPAPI_API_KEY: Optional[str] = os.getenv("SERPAPI_API_KEY")

    # Discovery Provider Selection: 'tavily', 'serper', 'mwmbl', 'static_benchmark', or 'auto'
    DISCOVERY_PROVIDER: str = os.getenv("DISCOVERY_PROVIDER", "auto").lower()

    # CORS Allowed Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ]


settings = Settings()
