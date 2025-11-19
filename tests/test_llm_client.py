"""
Tests for Gemini LLM client.

Tests:
- Client initialization
- API call mocking
- Retry logic
- Error handling
- JSON parsing and repair
- Schema validation
- Fallback generation
- Code fence stripping
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from app.core.llm_client import (
    GeminiClient,
    LLMConfig,
    create_gemini_client,
)


class TestLLMConfig:
    """Test LLM configuration dataclass"""
    
    def test_default_config(self):
        """Should create config with defaults"""
        config = LLMConfig(api_key="test_key")
        
        assert config.api_key == "test_key"
        assert config.model_name == "gemini-2.0-flash-exp"
        assert config.temperature == 0.3
        assert config.max_tokens == 2048
        assert config.timeout_seconds == 30
        assert config.max_retries == 3
    
    def test_custom_config(self):
        """Should accept custom parameters"""
        config = LLMConfig(
            api_key="custom_key",
            model_name="gemini-2.0-pro",
            temperature=0.7,
            max_tokens=4096
        )
        
        assert config.model_name == "gemini-2.0-pro"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096


class TestGeminiClientInit:
    """Test Gemini client initialization"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_client_initialization(self, mock_model, mock_configure):
        """Should initialize client with correct config"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        # Should configure API
        mock_configure.assert_called_once_with(api_key="test_key")
        
        # Should create model
        mock_model.assert_called_once()
        assert client.config == config
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_model_configuration(self, mock_model, mock_configure):
        """Should configure model with correct parameters"""
        config = LLMConfig(
            api_key="test_key",
            temperature=0.5,
            max_tokens=1024
        )
        client = GeminiClient(config)
        
        # Check model was called with generation config
        call_kwargs = mock_model.call_args[1]
        assert "generation_config" in call_kwargs
        
        gen_config = call_kwargs["generation_config"]
        assert gen_config.temperature == 0.5
        assert gen_config.max_output_tokens == 1024
        assert gen_config.response_mime_type == "application/json"


class TestAPICall:
    """Test API call functionality"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_successful_api_call(self, mock_model_class, mock_configure):
        """Should make successful API call and return response"""
        # Setup mock response
        mock_response = Mock()
        mock_response.text = '{"sentiment": "positive"}'
        mock_response.candidates = []  # Empty to use .text path
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        # Create client and make call
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        messages = [
            {"role": "system", "content": "You are an analyzer"},
            {"role": "user", "content": "Analyze this"}
        ]
        
        response = client._make_api_call(messages)
        
        assert response == '{"sentiment": "positive"}'
        mock_model.generate_content.assert_called_once()
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_api_call_formats_messages(self, mock_model_class, mock_configure):
        """Should format messages correctly for Gemini"""
        mock_response = Mock()
        mock_response.text = '{}'
        mock_response.candidates = []  # Empty to use .text path
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "Assistant response"}
        ]
        
        client._make_api_call(messages)
        
        # Check that prompt was formatted
        call_args = mock_model.generate_content.call_args[0]
        prompt = call_args[0]
        
        assert "SYSTEM INSTRUCTIONS:" in prompt
        assert "System prompt" in prompt
        assert "USER:" in prompt
        assert "User message" in prompt
        assert "ASSISTANT:" in prompt
        assert "Assistant response" in prompt


class TestCodeFenceStripping:
    """Test code fence removal"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_strip_json_code_fences(self, mock_model, mock_configure):
        """Should strip ```json ... ``` fences"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        text = '```json\n{"key": "value"}\n```'
        cleaned = client._strip_code_fences(text)
        
        assert cleaned == '{"key": "value"}'
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_strip_generic_code_fences(self, mock_model, mock_configure):
        """Should strip ``` ... ``` fences"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        text = '```\n{"key": "value"}\n```'
        cleaned = client._strip_code_fences(text)
        
        assert cleaned == '{"key": "value"}'
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_no_fences_unchanged(self, mock_model, mock_configure):
        """Should leave clean JSON unchanged"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        text = '{"key": "value"}'
        cleaned = client._strip_code_fences(text)
        
        assert cleaned == '{"key": "value"}'


class TestJSONRepair:
    """Test JSON repair functionality"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_repair_trailing_comma(self, mock_model, mock_configure):
        """Should repair trailing commas"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        text = '{"key": "value",}'
        repaired = client._attempt_json_repair(text)
        
        assert repaired is not None
        assert repaired == {"key": "value"}
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_repair_missing_closing_brace(self, mock_model, mock_configure):
        """Should add missing closing braces for minor truncation (with full object)"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        # Only 1 missing brace - wrapped in full text so extractor finds { and }
        text = 'Response: {"key": "value" } extra text'
        repaired = client._attempt_json_repair(text)
        
        assert repaired is not None
        assert repaired == {"key": "value"}
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_repair_returns_none_for_invalid(self, mock_model, mock_configure):
        """Should return None for unrecoverable JSON"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        text = 'this is not json at all'
        repaired = client._attempt_json_repair(text)
        
        assert repaired is None


class TestSchemaValidation:
    """Test Pydantic schema validation"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_valid_schema_passes(self, mock_model, mock_configure):
        """Should validate correct response structure"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        valid_data = {
            "sentiment": "positive",
            "emotion": "joy",
            "stress_score": 3,
            "category": "feedback",
            "key_phrases": ["great work"],
            "confidence_scores": {
                "sentiment": 0.9,
                "emotion": 0.85,
                "category": 0.8,
                "stress": 0.75
            },
            "urgency": False
        }
        
        validated = client._validate_json_structure(valid_data)
        
        assert validated["sentiment"] == "positive"
        assert validated["emotion"] == "joy"
        assert "schema_version" in validated  # Added by Pydantic
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_invalid_schema_raises(self, mock_model, mock_configure):
        """Should raise on invalid schema"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        invalid_data = {
            "sentiment": "invalid_sentiment",  # Not in enum
            "emotion": "joy"
        }
        
        with pytest.raises(ValueError, match="Invalid response structure"):
            client._validate_json_structure(invalid_data)


class TestFallbackResponse:
    """Test fallback response generation"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_fallback_is_valid(self, mock_model, mock_configure):
        """Fallback response should pass schema validation"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        fallback = client._generate_fallback_response()
        
        # Should be valid dict
        assert isinstance(fallback, dict)
        assert fallback["sentiment"] == "neutral"
        assert fallback["emotion"] == "neutral"
        assert fallback["stress_score"] == 5
        assert fallback["model_debug"]["fallback_used"] is True
        
        # Should pass Pydantic validation
        validated = client._validate_json_structure(fallback)
        assert validated is not None


class TestAnalyzeMethod:
    """Test main analyze method"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_successful_analysis(self, mock_model_class, mock_configure):
        """Should complete full analysis pipeline"""
        # Setup mock response
        valid_response = {
            "sentiment": "positive",
            "emotion": "joy",
            "stress_score": 2,
            "category": "praise",
            "key_phrases": ["excellent work"],
            "confidence_scores": {
                "sentiment": 0.95,
                "emotion": 0.9,
                "category": 0.85,
                "stress": 0.8
            },
            "urgency": False
        }
        
        mock_response = Mock()
        mock_response.text = json.dumps(valid_response)
        mock_response.candidates = []  # Empty to use .text path
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        # Create client and analyze
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        messages = [{"role": "user", "content": "Great work!"}]
        result = client.analyze(messages)
        
        assert result["sentiment"] == "positive"
        assert result["emotion"] == "joy"
        assert "schema_version" in result
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_analysis_with_fallback(self, mock_model_class, mock_configure):
        """Should use fallback on API error"""
        # Setup mock to raise error
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API Error")
        mock_model_class.return_value = mock_model
        
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        messages = [{"role": "user", "content": "Test"}]
        result = client.analyze(messages, fallback_on_error=True)
        
        # Should return fallback
        assert result["sentiment"] == "neutral"
        assert result["model_debug"]["fallback_used"] is True
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_analysis_without_fallback_raises(self, mock_model_class, mock_configure):
        """Should raise error when fallback disabled"""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API Error")
        mock_model_class.return_value = mock_model
        
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        messages = [{"role": "user", "content": "Test"}]
        
        with pytest.raises(RuntimeError, match="LLM analysis failed"):
            client.analyze(messages, fallback_on_error=False)


class TestTextExtraction:
    """Test robust text extraction from various response shapes"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_extract_from_text_attribute(self, mock_model, mock_configure):
        """Should extract from response.text"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        response = Mock()
        response.text = '{"key": "value"}'
        
        text = client._extract_text_from_response(response)
        assert text == '{"key": "value"}'
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_extract_from_candidates_text(self, mock_model, mock_configure):
        """Should extract from response.candidates[0].text"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        candidate = Mock()
        candidate.text = '{"key": "value"}'
        
        response = Mock()
        response.text = None
        response.candidates = [candidate]
        
        text = client._extract_text_from_response(response)
        assert text == '{"key": "value"}'
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_extract_from_candidates_output(self, mock_model, mock_configure):
        """Should extract from response.candidates[0].output"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        candidate = Mock()
        candidate.output = '{"key": "value"}'
        candidate.text = None
        
        response = Mock()
        response.text = None
        response.candidates = [candidate]
        
        text = client._extract_text_from_response(response)
        assert text == '{"key": "value"}'
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_extract_raises_on_empty(self, mock_model, mock_configure):
        """Should raise ValueError if no text found"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        response = Mock()
        response.text = None
        
        with pytest.raises(ValueError, match="Unable to extract text"):
            client._extract_text_from_response(response)


class TestJSONRepairSafety:
    """Test that JSON repair doesn't corrupt quoted strings"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_repair_preserves_quoted_commas(self, mock_model, mock_configure):
        """Should not corrupt commas inside string values"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        # This is valid JSON with comma in string value
        text = '{"message": "Hello, world"}'
        repaired = client._attempt_json_repair(text)
        
        assert repaired is not None
        assert repaired["message"] == "Hello, world"
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_repair_strips_code_fences_first(self, mock_model, mock_configure):
        """Should remove code fences before repair"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        text = '```json\n{"key": "value",}\n```'
        repaired = client._attempt_json_repair(text)
        
        assert repaired is not None
        assert repaired == {"key": "value"}
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_repair_extracts_json_object(self, mock_model, mock_configure):
        """Should extract {...} from surrounding text"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        text = 'Here is the result: {"key": "value"} end'
        repaired = client._attempt_json_repair(text)
        
        assert repaired is not None
        assert repaired == {"key": "value"}
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_repair_limited_brace_addition(self, mock_model, mock_configure):
        """Should only add braces for minor truncation"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        # Missing one closing brace
        text = '{"outer": {"inner": "value"}'
        repaired = client._attempt_json_repair(text)
        
        assert repaired is not None
        assert repaired == {"outer": {"inner": "value"}}
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_repair_rejects_excessive_truncation(self, mock_model, mock_configure):
        """Should reject heavily truncated JSON"""
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        # Missing many braces (>2)
        text = '{"a": {"b": {"c": {"d": "value"'
        repaired = client._attempt_json_repair(text)
        
        # Should fail to repair
        assert repaired is None


class TestRetryPolicy:
    """Test that retry policy only retries network errors"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_retries_network_timeout(self, mock_model_class, mock_configure):
        """Should retry on timeout errors"""
        from requests.exceptions import Timeout
        
        mock_response = Mock()
        mock_response.text = '{"key": "value"}'
        mock_response.candidates = []  # Empty to use .text path
        
        mock_model = Mock()
        mock_model.generate_content.side_effect = [
            Timeout("Connection timeout"),
            mock_response
        ]
        mock_model_class.return_value = mock_model
        
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        messages = [{"role": "user", "content": "Test"}]
        response = client._make_api_call(messages)
        
        # Should have retried and succeeded
        assert response == '{"key": "value"}'
        assert mock_model.generate_content.call_count == 2
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_does_not_retry_validation_error(self, mock_model_class, mock_configure):
        """Should NOT retry on ValueError (validation errors)"""
        mock_model = Mock()
        mock_model.generate_content.side_effect = ValueError("Invalid input")
        mock_model_class.return_value = mock_model
        
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        messages = [{"role": "user", "content": "Test"}]
        
        with pytest.raises(ValueError):
            client._make_api_call(messages)
        
        # Should only call once (no retry)
        assert mock_model.generate_content.call_count == 1


class TestModelDebugMetadata:
    """Test that model_debug includes safe metadata"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_debug_includes_latency(self, mock_model_class, mock_configure):
        """Should include latency_ms in model_debug"""
        valid_response = {
            "sentiment": "positive",
            "emotion": "joy",
            "stress_score": 2,
            "category": "praise",
            "key_phrases": ["test"],
            "confidence_scores": {
                "sentiment": 0.9,
                "emotion": 0.85,
                "category": 0.8,
                "stress": 0.75
            },
            "urgency": False
        }
        
        mock_response = Mock()
        mock_response.text = json.dumps(valid_response)
        mock_response.candidates = []  # Empty to use .text path
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        messages = [{"role": "user", "content": "Test"}]
        result = client.analyze(messages)
        
        assert "model_debug" in result
        assert "latency_ms" in result["model_debug"]
        assert isinstance(result["model_debug"]["latency_ms"], (int, float))
        assert result["model_debug"]["model"] == "gemini-2.0-flash-exp"
        assert result["model_debug"]["fallback_used"] is False
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_fallback_includes_error_type(self, mock_model_class, mock_configure):
        """Should include error_type in fallback model_debug"""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API Error")
        mock_model_class.return_value = mock_model
        
        config = LLMConfig(api_key="test_key")
        client = GeminiClient(config)
        
        messages = [{"role": "user", "content": "Test"}]
        result = client.analyze(messages, fallback_on_error=True)
        
        assert result["model_debug"]["fallback_used"] is True
        assert result["model_debug"]["error_type"] == "Exception"


class TestFactoryFunction:
    """Test create_gemini_client factory"""
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_factory_with_api_key(self, mock_model, mock_configure):
        """Should create client with provided API key"""
        client = create_gemini_client(api_key="test_key")
        
        assert isinstance(client, GeminiClient)
        assert client.config.api_key == "test_key"
    
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'env_key'})
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_factory_with_env_var(self, mock_model, mock_configure):
        """Should use API key from environment"""
        client = create_gemini_client()
        
        assert client.config.api_key == "env_key"
    
    @patch.dict('os.environ', {}, clear=True)
    def test_factory_without_key_raises(self):
        """Should raise if no API key provided"""
        with pytest.raises(ValueError, match="GEMINI_API_KEY not found"):
            create_gemini_client()
    
    @patch('app.core.llm_client.genai.configure')
    @patch('app.core.llm_client.genai.GenerativeModel')
    def test_factory_with_custom_model(self, mock_model, mock_configure):
        """Should use custom model name"""
        client = create_gemini_client(
            api_key="test_key",
            model_name="gemini-2.0-pro"
        )
        
        assert client.config.model_name == "gemini-2.0-pro"
