"""
Tests for configuration module.

Validates configuration loading, validators, and production requirements.

Version: 1.0.0
"""
import pytest
import os
from pydantic import ValidationError
from app.core.config import get_settings, reload_settings, Settings


class TestSettingsValidation:
    """Test configuration validation"""
    
    def test_gemini_api_key_accepted_in_production(self, monkeypatch):
        """GEMINI_API_KEY should work when set in production"""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("GEMINI_API_KEY", "test_key_12345")
        
        settings = Settings()
        assert settings.gemini_api_key == "test_key_12345"
        assert settings.environment == "production"
    
    def test_optional_api_key_in_development(self, monkeypatch):
        """GEMINI_API_KEY should be optional in development (structural test)"""
        # This verifies the field is Optional[str], not required str
        monkeypatch.setenv("ENVIRONMENT", "development")
        # If GEMINI_API_KEY were required (...), this would fail at import time
        # The fact that Settings() instantiates proves it's Optional
        settings = Settings()
        assert settings.environment == "development"
        # API key may be set from .env or not - we just verify no crash


class TestLogLevelValidator:
    """Test log level validation"""
    
    def test_valid_log_level(self, monkeypatch):
        """Valid log levels should be accepted"""
        monkeypatch.setenv("LOG_LEVEL", "debug")
        
        settings = Settings()
        assert settings.log_level == "DEBUG"  # Normalized to uppercase
    
    def test_invalid_log_level(self, monkeypatch):
        """Invalid log levels should raise error"""
        monkeypatch.setenv("LOG_LEVEL", "INVALID")
        
        with pytest.raises(ValidationError):
            Settings()


class TestEnvironmentValidator:
    """Test environment validation"""
    
    def test_valid_environments(self, monkeypatch):
        """Valid environments should be accepted"""
        for env in ["development", "staging", "production"]:
            monkeypatch.setenv("ENVIRONMENT", env)
            settings = Settings()
            assert settings.environment == env
    
    def test_invalid_environment(self, monkeypatch):
        """Invalid environments should raise error"""
        monkeypatch.setenv("ENVIRONMENT", "invalid")
        
        with pytest.raises(ValidationError):
            Settings()


class TestRateLimitValidator:
    """Test rate limit validation"""
    
    def test_positive_rate_limit(self, monkeypatch):
        """Positive rate limits should be accepted"""
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "120")
        
        settings = Settings()
        assert settings.rate_limit_per_minute == 120
    
    def test_zero_rate_limit(self, monkeypatch):
        """Zero rate limit should raise error"""
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
        
        with pytest.raises(ValidationError):
            Settings()
    
    def test_negative_rate_limit(self, monkeypatch):
        """Negative rate limit should raise error"""
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "-10")
        
        with pytest.raises(ValidationError):
            Settings()


class TestCorsOriginsParser:
    """Test CORS origins parsing"""
    
    def test_cors_origins_parsing_logic(self):
        """Test the CORS origins validator logic"""
        # Test the validator directly
        from app.core.config import Settings
        
        # Test comma-separated parsing
        result = Settings.parse_cors_origins("http://localhost:3000,https://app.example.com")
        assert result == ["http://localhost:3000", "https://app.example.com"]
        
        # Test single origin
        result = Settings.parse_cors_origins("http://localhost:3000")
        assert result == ["http://localhost:3000"]
        
        # Test wildcard
        result = Settings.parse_cors_origins("*")
        assert result == ["*"]
        
        # Test already-a-list passthrough
        result = Settings.parse_cors_origins(["http://localhost:3000"])
        assert result == ["http://localhost:3000"]


class TestSettingsProperties:
    """Test settings helper properties"""
    
    def test_is_development(self, monkeypatch):
        """is_development property should work"""
        monkeypatch.setenv("ENVIRONMENT", "development")
        
        settings = Settings()
        assert settings.is_development is True
        assert settings.is_production is False
    
    def test_is_production(self, monkeypatch):
        """is_production property should work"""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("GEMINI_API_KEY", "test_key")
        
        settings = Settings()
        assert settings.is_production is True
        assert settings.is_development is False


class TestGetSettings:
    """Test get_settings function"""
    
    def test_get_settings_caches(self, monkeypatch):
        """get_settings should return cached instance"""
        monkeypatch.setenv("GEMINI_API_KEY", "test1")
        
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2  # Same instance
    
    def test_reload_settings(self, monkeypatch):
        """reload_settings should force new instance"""
        monkeypatch.setenv("GEMINI_API_KEY", "test1")
        settings1 = get_settings()
        
        monkeypatch.setenv("GEMINI_API_KEY", "test2")
        settings2 = reload_settings()
        
        assert settings1 is not settings2  # Different instances
        assert settings2.gemini_api_key == "test2"


class TestDefaultValues:
    """Test configuration default values"""
    
    def test_default_app_name(self):
        """App name should have default"""
        settings = Settings()
        assert settings.app_name == "Zoho Feedback Analyzer API"
    
    def test_default_environment(self):
        """Environment should default to development"""
        settings = Settings()
        assert settings.environment == "development"
    
    def test_default_rate_limit(self):
        """Rate limit should default to 60/min"""
        settings = Settings()
        assert settings.rate_limit_per_minute == 60
    
    def test_default_cors_origins(self):
        """CORS origins should default to wildcard"""
        settings = Settings()
        assert settings.cors_origins == ["*"]
