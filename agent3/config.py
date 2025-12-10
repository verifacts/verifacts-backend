"""
Configuration for Agent 3 - Fact Checker
"""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Agent 3 configuration settings"""

    # API Configuration
    google_fact_check_api_key: str = ""
    fact_check_api_url: str = (
        "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    )

    # Performance Settings
    api_timeout: int = 2  # seconds
    max_batch_size: int = 20

    # Cache Settings (for future Redis integration)
    cache_enabled: bool = True
    redis_url: str = "redis://localhost:6379"
    cache_ttl: int = 86400  # 24 hours in seconds

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8003  # Agent 3 runs on port 8003

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
