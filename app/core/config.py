"""
Application configuration using Pydantic Settings.

Centralized configuration management with environment variable support.
All settings can be overridden via .env file or environment variables.

Environment Variables:
- GEMINI_API_KEY: Google Gemini API key (required)
- GEMINI_MODEL: Model name (default: gemini-2.0-flash-exp)
- ENVIRONMENT: dev/staging/prod (default: development)
- DEBUG: Enable debug mode (default: True)
- API_RATE_LIMIT: Requests per minute (default: 60)
- CORS_ORIGINS: Comma-separated allowed origins (default: *)
- LOG_LEVEL: Logging level (default: INFO)

Version: 1.0.0
"""
import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    Automatically loads from:
    1. Environment variables
    2. .env file in project root
    3. Default values
    """
    
    # Application Info
    app_name: str = "Zoho Feedback Analyzer API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    
    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=True, alias="DEBUG")
    
    # Gemini LLM Configuration
    # NOTE: Optional at config level; required in production (validated below)
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash-exp", alias="GEMINI_MODEL")
    llm_temperature: float = Field(default=0.3, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2048, alias="LLM_MAX_TOKENS")
    llm_timeout: int = Field(default=30, alias="LLM_TIMEOUT")
    
    # API Rate Limiting
    # WARNING: memory:// storage does NOT work with multiple workers!
    # In production with multiple workers, use Redis: "redis://localhost:6379/0"
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_storage_uri: str = Field(default="memory://", alias="RATE_LIMIT_STORAGE")
    
    # CORS Configuration
    cors_enabled: bool = Field(default=True, alias="CORS_ENABLED")
    cors_origins: List[str] = Field(
        default=["*"],
        alias="CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: List[str] = Field(default=["*"], alias="CORS_ALLOW_METHODS")
    cors_allow_headers: List[str] = Field(default=["*"], alias="CORS_ALLOW_HEADERS")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")  # json or text
    log_file: Optional[str] = Field(default=None, alias="LOG_FILE")
    
    # Request/Response Settings
    max_request_size: int = Field(default=1_048_576, alias="MAX_REQUEST_SIZE")  # 1 MB
    response_timeout: int = Field(default=60, alias="RESPONSE_TIMEOUT")  # seconds
    
    # Health Check Settings
    health_check_enabled: bool = Field(default=True, alias="HEALTH_CHECK_ENABLED")
    health_check_timeout: int = Field(default=5, alias="HEALTH_CHECK_TIMEOUT")
    
    # Feature Flags
    batch_analysis_enabled: bool = Field(default=False, alias="BATCH_ANALYSIS_ENABLED")
    async_processing_enabled: bool = Field(default=False, alias="ASYNC_PROCESSING_ENABLED")
    
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Ensure log level is valid"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Ensure environment is valid"""
        valid_envs = ["development", "staging", "production"]
        v_lower = v.lower()
        if v_lower not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v_lower
    
    @field_validator("rate_limit_per_minute")
    @classmethod
    def validate_rate_limit(cls, v):
        """Ensure rate limit is positive"""
        if v <= 0:
            raise ValueError("Rate limit must be positive")
        return v
    
    @field_validator("gemini_api_key", mode="after")
    @classmethod
    def validate_gemini_api_key_in_production(cls, v):
        """Require GEMINI_API_KEY in production environment"""
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env == "production" and not v:
            raise ValueError("GEMINI_API_KEY is required in production environment")
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == "production"
    
    class Config:
        """Pydantic settings configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # Allow extra fields for forward compatibility
        extra = "ignore"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get application settings singleton.
    
    Lazily loads settings from environment on first access.
    Subsequent calls return cached instance.
    
    Returns:
        Settings instance with loaded configuration
        
    Raises:
        ValidationError: If required settings are missing or invalid
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Force reload settings from environment.
    
    Useful for testing or runtime configuration changes.
    
    Returns:
        Fresh Settings instance
    """
    global _settings
    _settings = None
    return get_settings()


# NOTE: Do NOT instantiate settings at module import time
# Always call get_settings() explicitly when needed
# This prevents import-time failures when env vars are not set
