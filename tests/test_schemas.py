"""
Unit tests for analysis schemas (Pydantic v2 models)
Tests validation, field constraints, and schema compliance.
"""
import pytest
from pydantic import ValidationError
from app.schemas.analysis import (
    AnalyzeRequest,
    AnalyzeResponse,
    ConfidenceScores,
    SentimentEnum,
    EmotionEnum,
    CategoryEnum,
    ANALYSIS_JSON_SCHEMA
)


class TestAnalyzeRequest:
    """Tests for AnalyzeRequest schema"""
    
    def test_valid_request(self):
        """Test valid analyze request creation"""
        request = AnalyzeRequest(
            message="I'm feeling overwhelmed with the current workload",
            user_id="user123",
            channel_id="channel456"
        )
        assert request.message == "I'm feeling overwhelmed with the current workload"
        assert request.user_id == "user123"
        assert request.channel_id == "channel456"
        assert request.context is None
    
    def test_valid_request_with_context(self):
        """Test valid request with context"""
        request = AnalyzeRequest(
            message="Need help with this task",
            user_id="user123",
            channel_id="channel456",
            context={"project": "Q4-Initiative"}
        )
        assert request.context == {"project": "Q4-Initiative"}
    
    def test_empty_message_fails(self):
        """Test that empty message raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            AnalyzeRequest(
                message="",
                user_id="user123",
                channel_id="channel456"
            )
        assert "message" in str(exc_info.value).lower()
    
    def test_whitespace_only_message_fails(self):
        """Test that whitespace-only message raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            AnalyzeRequest(
                message="   \n\t  ",
                user_id="user123",
                channel_id="channel456"
            )
        assert "whitespace" in str(exc_info.value).lower()
    
    def test_message_too_long_fails(self):
        """Test that message exceeding max length fails"""
        with pytest.raises(ValidationError):
            AnalyzeRequest(
                message="x" * 5001,
                user_id="user123",
                channel_id="channel456"
            )
    
    def test_missing_required_fields_fails(self):
        """Test that missing required message field raises validation error"""
        with pytest.raises(ValidationError):
            AnalyzeRequest(user_id="user123", channel_id="channel456")  # missing message
        
        # user_id and channel_id are now optional
        request = AnalyzeRequest(message="test")
        assert request.message == "test"
        assert request.user_id is None
        assert request.channel_id is None
    
    def test_extra_fields_rejected(self):
        """Test that extra fields are rejected"""
        with pytest.raises(ValidationError):
            AnalyzeRequest(
                message="test message",
                user_id="user123",
                channel_id="channel456",
                extra_field="should fail"
            )
    
    def test_message_stripped(self):
        """Test that message whitespace is stripped"""
        request = AnalyzeRequest(
            message="  test message  ",
            user_id="user123",
            channel_id="channel456"
        )
        assert request.message == "test message"


class TestConfidenceScores:
    """Tests for ConfidenceScores schema"""
    
    def test_valid_confidence_scores(self):
        """Test valid confidence scores"""
        scores = ConfidenceScores(
            sentiment=0.95,
            emotion=0.87,
            category=0.76,
            stress=0.89
        )
        assert scores.sentiment == 0.95
        assert scores.emotion == 0.87
    
    def test_confidence_out_of_range_fails(self):
        """Test that confidence scores outside 0-1 range fail"""
        with pytest.raises(ValidationError):
            ConfidenceScores(
                sentiment=1.5,
                emotion=0.87,
                category=0.76,
                stress=0.89
            )
        
        with pytest.raises(ValidationError):
            ConfidenceScores(
                sentiment=0.95,
                emotion=-0.1,
                category=0.76,
                stress=0.89
            )


class TestAnalyzeResponse:
    """Tests for AnalyzeResponse schema"""
    
    def test_valid_response(self):
        """Test valid analyze response creation"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEGATIVE,
            emotion=EmotionEnum.FRUSTRATION,
            stress_score=7,
            category=CategoryEnum.WORKLOAD,
            key_phrases=["overwhelmed", "too much work"],
            suggested_reply="I understand you're feeling overwhelmed. Let's prioritize together.",
            action_items=["Schedule 1:1 meeting", "Review task priorities"],
            confidence_scores=ConfidenceScores(
                sentiment=0.92,
                emotion=0.88,
                category=0.85,
                stress=0.90
            ),
            urgency=True,
            model_debug={"model": "gpt-4", "tokens": 150, "latency_ms": 823}
        )
        assert response.sentiment == SentimentEnum.NEGATIVE
        assert response.stress_score == 7
        assert response.urgency is True
        assert len(response.key_phrases) == 2
        assert len(response.action_items) == 2
    
    def test_minimal_valid_response(self):
        """Test minimal valid response with only required fields"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.UPDATE,
            confidence_scores=ConfidenceScores(
                sentiment=0.85,
                emotion=0.82,
                category=0.88,
                stress=0.80
            ),
            urgency=False
        )
        assert response.key_phrases == []
        assert response.action_items == []
        assert response.suggested_reply is None
        assert response.model_debug is None
    
    def test_stress_score_out_of_range_fails(self):
        """Test that stress_score outside 0-10 range fails"""
        with pytest.raises(ValidationError):
            AnalyzeResponse(
                sentiment=SentimentEnum.NEGATIVE,
                emotion=EmotionEnum.ANGER,
                stress_score=11,
                category=CategoryEnum.CONFLICT,
                confidence_scores=ConfidenceScores(
                    sentiment=0.9, emotion=0.9, category=0.9, stress=0.9
                ),
                urgency=True
            )
    
    def test_invalid_enum_value_fails(self):
        """Test that invalid enum values fail"""
        with pytest.raises(ValidationError):
            AnalyzeResponse(
                sentiment="invalid_sentiment",
                emotion=EmotionEnum.JOY,
                stress_score=5,
                category=CategoryEnum.GENERAL,
                confidence_scores=ConfidenceScores(
                    sentiment=0.9, emotion=0.9, category=0.9, stress=0.9
                ),
                urgency=False
            )
    
    def test_key_phrases_empty_strings_filtered(self):
        """Test that empty strings in key_phrases are filtered"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.POSITIVE,
            emotion=EmotionEnum.JOY,
            stress_score=2,
            category=CategoryEnum.PRAISE,
            key_phrases=["great work", "", "  ", "excellent"],
            confidence_scores=ConfidenceScores(
                sentiment=0.9, emotion=0.9, category=0.9, stress=0.9
            ),
            urgency=False
        )
        assert response.key_phrases == ["great work", "excellent"]
    
    def test_action_items_empty_strings_filtered(self):
        """Test that empty strings in action_items are filtered"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEGATIVE,
            emotion=EmotionEnum.ANXIETY,
            stress_score=8,
            category=CategoryEnum.BLOCKER,
            action_items=["Immediate meeting", "", "  ", "Escalate to senior"],
            confidence_scores=ConfidenceScores(
                sentiment=0.9, emotion=0.9, category=0.9, stress=0.9
            ),
            urgency=True
        )
        assert response.action_items == ["Immediate meeting", "Escalate to senior"]
    
    def test_too_many_key_phrases_fails(self):
        """Test that exceeding max key_phrases fails"""
        with pytest.raises(ValidationError):
            AnalyzeResponse(
                sentiment=SentimentEnum.NEUTRAL,
                emotion=EmotionEnum.NEUTRAL,
                stress_score=5,
                category=CategoryEnum.GENERAL,
                key_phrases=["phrase" + str(i) for i in range(11)],  # 11 phrases, max is 10
                confidence_scores=ConfidenceScores(
                    sentiment=0.9, emotion=0.9, category=0.9, stress=0.9
                ),
                urgency=False
            )
    
    def test_suggested_reply_too_long_fails(self):
        """Test that suggested_reply exceeding max length fails"""
        with pytest.raises(ValidationError):
            AnalyzeResponse(
                sentiment=SentimentEnum.POSITIVE,
                emotion=EmotionEnum.JOY,
                stress_score=1,
                category=CategoryEnum.PRAISE,
                suggested_reply="x" * 1001,
                confidence_scores=ConfidenceScores(
                    sentiment=0.9, emotion=0.9, category=0.9, stress=0.9
                ),
                urgency=False
            )


class TestAnalysisJsonSchema:
    """Tests for exported JSON schema"""
    
    def test_schema_structure(self):
        """Test that JSON schema has required structure"""
        assert "type" in ANALYSIS_JSON_SCHEMA
        assert ANALYSIS_JSON_SCHEMA["type"] == "object"
        assert "properties" in ANALYSIS_JSON_SCHEMA
        assert "required" in ANALYSIS_JSON_SCHEMA
    
    def test_schema_required_fields(self):
        """Test that schema includes all required fields"""
        required = ANALYSIS_JSON_SCHEMA["required"]
        assert "sentiment" in required
        assert "emotion" in required
        assert "stress_score" in required
        assert "category" in required
        assert "confidence_scores" in required
        assert "urgency" in required
    
    def test_schema_enum_values(self):
        """Test that schema includes correct enum values"""
        props = ANALYSIS_JSON_SCHEMA["properties"]
        assert "positive" in props["sentiment"]["enum"]
        assert "negative" in props["sentiment"]["enum"]
        assert "frustration" in props["emotion"]["enum"]
        assert "workload" in props["category"]["enum"]
    
    def test_schema_stress_score_constraints(self):
        """Test that stress_score has correct constraints in schema"""
        stress_prop = ANALYSIS_JSON_SCHEMA["properties"]["stress_score"]
        assert stress_prop["type"] == "integer"
        assert stress_prop["minimum"] == 0
        assert stress_prop["maximum"] == 10
