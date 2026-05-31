"""
Configuration Module
Loads settings from environment variables (set by Docker Compose)
"""

import os
from dotenv import load_dotenv

# Load .env file if exists (for local development without Docker)
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://orchestrator:orchestrator_secret@localhost:5432/orchestrator_db"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # App
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

    # Worker polling interval (seconds)
    WORKER_POLL_INTERVAL: int = 2

    # Redis channels
    LOGS_CHANNEL_PREFIX: str = "logs:"
    JOBS_QUEUE: str = "jobs:queue"


# Global settings instance
settings = Settings()