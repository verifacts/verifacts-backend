import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from dotenv import load_dotenv 


load_dotenv()  # Load environment variables from a .env file if present

class Config(BaseSettings):
    """
    Application configuration settings.
    Reads from environment variables by default.
    """
    PROJECT_NAME: str = "Verifacts Backend"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default_secret_key")
    
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "gemini-2.5-pro")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKEN: int = int(os.getenv("LLM_MAX_TOKEN", "1024"))
    FIRECRAWL_API_KEY: Optional[str] = os.getenv("FIRECRAWL_API_KEY")
    GOOGLE_FACTS_CHECK_API_KEY: Optional[str] = os.getenv("GOOGLE_FACTS_CHECK_API_KEY")
    SERPER_API_KEY: Optional[str] = os.getenv("SERPER_API_KEY")
    
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


config = Config()