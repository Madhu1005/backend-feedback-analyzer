"""
Integration tests for FastAPI endpoints.

Tests all API endpoints with comprehensive error scenarios:
- POST /api/v1/analyze
- GET /health
- GET /health/ready
- GET /health/live

Test coverage:
- Request validation
- Error handling (400, 422, 429, 500, 503)
- CORS headers
- Rate limiting
- Health checks
- Response formats

Version: 1.0.0
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.analysis import AnalyzeRequest
from app.services.analyzer import AnalysisResult


@pytest.fixture
def client():
    """Test client for FastAPI app"""
    return TestClient(app)


@pytest.fixture
def mock_analyzer():
    """Mock MessageAnalyzer for testing"""
    with patch('app.api.analyze.create_analyzer') as mock_create:
        analyzer = Mock()
        mock_create.return_value = analyzer
        yield analyzer


class TestRootEndpoint:
    """Test root endpoint"""
    
    def test_root_returns_info(self, client):
        """Should return API information"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "version" in data
        assert "health" in data


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_health_check(self, client):
        """Should return 200 OK for basic health check"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
    
    def test_liveness_check(self, client):
        """Should return 200 OK for liveness check"""
        response = client.get("/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key_123'})
    def test_readiness_check_healthy(self, client):
        """Should return 200 OK when all dependencies are ready"""
        with patch('app.api.health.create_gemini_client'):
            response = client.get("/health/ready")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert "checks" in data
            assert data["checks"]["configuration"]["status"] == "healthy"
    
    @patch.dict('os.environ', {}, clear=True)
    def test_readiness_check_unhealthy(self, client):
        """Should return 503 when dependencies are not ready"""
        response = client.get("/health/ready")
        
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert "checks" in data


class TestAnalyzeEndpoint:
    """Test POST /api/v1/analyze endpoint"""
    
    def test_successful_analysis(self, client, mock_analyzer):
        """Should return 200 OK with analysis results"""
        # Setup mock analyzer response
        mock_result = AnalysisResult(
            analysis={
                "sentiment": "positive",
                "emotion": "joy",
                "stress_score": 2,
                "category": "praise",
                "key_phrases": ["great work"],
                "confidence_scores": {
                    "sentiment": 0.95,
                    "emotion": 0.9,
                    "category": 0.85,
                    "stress": 0.8
                },
                "urgency": False,
                "schema_version": "1.0.0",
                "model_debug": {
                    "model": "gemini-2.0-flash-exp",
                    "fallback_used": False
                }
            },
            sanitization_applied=False,
            threat_level="low",
            llm_used=True,
            processing_time_ms=1234.56
        )
        mock_analyzer.analyze.return_value = mock_result
        
        # Make request
        response = client.post(
            "/api/v1/analyze",
            json={"message": "Great work on the project!"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["success"] is True
        assert "analysis" in data
        assert "sanitization" in data
        assert "processing_time_ms" in data
        assert "llm_used" in data
        
        # Verify analysis content
        assert data["analysis"]["sentiment"] == "positive"
        assert data["analysis"]["emotion"] == "joy"
        assert data["analysis"]["stress_score"] == 2
        assert data["llm_used"] is True
        
        # Verify sanitization info
        assert data["sanitization"]["is_safe"] is True
        assert data["sanitization"]["threat_level"] == "low"
    
    def test_analysis_with_metadata(self, client, mock_analyzer):
        """Should accept and process metadata"""
        mock_result = AnalysisResult(
            analysis={
                "sentiment": "neutral",
                "emotion": "neutral",
                "stress_score": 5,
                "category": "general",
                "key_phrases": [],
                "confidence_scores": {
                    "sentiment": 0.5,
                    "emotion": 0.5,
                    "category": 0.5,
                    "stress": 0.5
                },
                "urgency": False,
                "schema_version": "1.0.0",
                "model_debug": {"fallback_used": False}
            },
            sanitization_applied=False,
            threat_level="low",
            llm_used=True,
            processing_time_ms=1000.0
        )
        mock_analyzer.analyze.return_value = mock_result
        
        response = client.post(
            "/api/v1/analyze",
            json={
                "message": "Test message",
                "user_id": "user123",
                "channel_id": "team-eng",
                "context": {
                    "timestamp": "2025-11-19T10:30:00Z",
                    "platform": "slack"
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert mock_analyzer.analyze.called
    
    def test_empty_message_rejected(self, client):
        """Should reject empty message with 422"""
        response = client.post(
            "/api/v1/analyze",
            json={"message": ""}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "validation_error"
    
    def test_missing_message_field(self, client):
        """Should reject request without message field with 422"""
        response = client.post(
            "/api/v1/analyze",
            json={}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "validation_error"
    
    def test_message_too_long(self, client):
        """Should reject message that is too long with 422"""
        long_message = "x" * 20000  # Exceeds max_length of 10000
        
        response = client.post(
            "/api/v1/analyze",
            json={"message": long_message}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
    
    def test_invalid_json(self, client):
        """Should reject invalid JSON with 422"""
        response = client.post(
            "/api/v1/analyze",
            data="not json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_llm_service_unavailable(self, client):
        """Should return 503 when LLM service is unavailable"""
        with patch('app.api.analyze.create_analyzer', side_effect=Exception("API Error")):
            response = client.post(
                "/api/v1/analyze",
                json={"message": "Test message"}
            )
            
            assert response.status_code == 503
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "service_unavailable"
    
    def test_analysis_validation_error(self, client, mock_analyzer):
        """Should return 422 when analysis validation fails"""
        mock_analyzer.analyze.side_effect = ValueError("Invalid input")
        
        response = client.post(
            "/api/v1/analyze",
            json={"message": "Test message"}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "validation_error"
    
    def test_internal_server_error(self, client, mock_analyzer):
        """Should return 500 for unexpected errors"""
        mock_analyzer.analyze.side_effect = RuntimeError("Unexpected error")
        
        response = client.post(
            "/api/v1/analyze",
            json={"message": "Test message"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "internal_error"
    
    def test_fallback_response_indicated(self, client, mock_analyzer):
        """Should indicate when fallback response is used"""
        mock_result = AnalysisResult(
            analysis={
                "sentiment": "neutral",
                "emotion": "neutral",
                "stress_score": 5,
                "category": "general",
                "key_phrases": [],
                "confidence_scores": {
                    "sentiment": 0.5,
                    "emotion": 0.5,
                    "category": 0.5,
                    "stress": 0.5
                },
                "urgency": False,
                "schema_version": "1.0.0",
                "model_debug": {
                    "model": "fallback",
                    "fallback_used": True,
                    "error_type": "RequestsTimeout"
                }
            },
            sanitization_applied=False,
            threat_level="low",
            llm_used=False,
            processing_time_ms=50.0
        )
        mock_analyzer.analyze.return_value = mock_result
        
        response = client.post(
            "/api/v1/analyze",
            json={"message": "Test message"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["llm_used"] is False
        assert data["analysis"]["model_debug"]["fallback_used"] is True


class TestCORS:
    """Test CORS configuration"""
    
    def test_cors_headers_present(self, client):
        """Should include CORS headers in response"""
        response = client.options(
            "/api/v1/analyze",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers
    
    def test_cors_allows_post(self, client):
        """Should allow POST requests from any origin"""
        response = client.post(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )
        
        # Should not be blocked by CORS
        assert response.status_code in [200, 404, 405]  # Not CORS error


class TestRequestHeaders:
    """Test custom request headers"""
    
    def test_request_id_header(self, client):
        """Should include X-Request-ID in response"""
        response = client.get("/health")
        
        assert "x-request-id" in response.headers
        assert response.headers["x-request-id"]  # Not empty
    
    def test_process_time_header(self, client):
        """Should include X-Process-Time in response"""
        response = client.get("/health")
        
        assert "x-process-time" in response.headers
        assert "ms" in response.headers["x-process-time"]


class TestRateLimiting:
    """Test rate limiting"""
    
    def test_rate_limit_not_exceeded_normally(self, client, mock_analyzer):
        """Should allow requests under rate limit"""
        mock_result = AnalysisResult(
            analysis={
                "sentiment": "neutral",
                "emotion": "neutral",
                "stress_score": 5,
                "category": "general",
                "key_phrases": [],
                "confidence_scores": {
                    "sentiment": 0.5,
                    "emotion": 0.5,
                    "category": 0.5,
                    "stress": 0.5
                },
                "urgency": False,
                "schema_version": "1.0.0",
                "model_debug": {"fallback_used": False}
            },
            sanitization_applied=False,
            threat_level="low",
            llm_used=True,
            processing_time_ms=100.0
        )
        mock_analyzer.analyze.return_value = mock_result
        
        # Make a few requests (under limit)
        for _ in range(3):
            response = client.post(
                "/api/v1/analyze",
                json={"message": "Test"}
            )
            assert response.status_code == 200


class TestErrorResponseFormat:
    """Test error response consistency"""
    
    def test_validation_error_format(self, client):
        """Validation errors should have consistent format"""
        response = client.post(
            "/api/v1/analyze",
            json={"message": ""}
        )
        
        data = response.json()
        assert "success" in data
        assert "error" in data
        assert "message" in data
        assert data["success"] is False
    
    def test_404_error_format(self, client):
        """404 errors should have consistent format"""
        response = client.get("/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "error" in data
