"""
Additional security and validation tests for P0/P1 fixes.
Tests sanitization, immutability, and enhanced validation.
"""
import pytest
from pydantic import ValidationError

from app.schemas.analysis import (
    AnalyzeResponse,
    ConfidenceScores,
    SentimentEnum,
    EmotionEnum,
    CategoryEnum,
    _remove_titles_recursive,
    get_clean_schema
)


class TestModelDebugSanitization:
    """Tests for model_debug field sanitization (P0 fix)"""
    
    def test_model_debug_filters_unsafe_keys(self):
        """Test that only safe keys are allowed in model_debug"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            ),
            model_debug={
                "model": "gpt-4",
                "tokens": 100,
                "api_key": "sk-secret123",  # Unsafe key
                "user_input": "sensitive data"  # Unsafe key
            }
        )
        # Only safe keys should remain
        assert "model" in response.model_debug
        assert "tokens" in response.model_debug
        assert "api_key" not in response.model_debug
        assert "user_input" not in response.model_debug
    
    def test_model_debug_removes_newlines(self):
        """Test that newlines are removed from strings"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            ),
            model_debug={
                "model": "gpt-4\n\ninjection attempt"
            }
        )
        assert "\n" not in response.model_debug["model"]
        assert "injection attempt" in response.model_debug["model"]
    
    def test_model_debug_removes_code_blocks(self):
        """Test that code blocks and special chars are removed"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            ),
            model_debug={
                "provider": "```python\nmalicious_code()```"
            }
        )
        # Backticks and brackets should be removed
        assert "`" not in response.model_debug["provider"]
        assert "{" not in response.model_debug.get("provider", "")
    
    def test_model_debug_limits_string_length(self):
        """Test that string values are limited to 100 chars"""
        long_string = "x" * 200
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            ),
            model_debug={"model": long_string}
        )
        assert len(response.model_debug["model"]) <= 100
    
    def test_model_debug_allows_safe_types(self):
        """Test that int, float, bool are passed through"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            ),
            model_debug={
                "tokens": 150,
                "latency_ms": 234.5,
                "fallback_used": True
            }
        )
        assert response.model_debug["tokens"] == 150
        assert response.model_debug["latency_ms"] == 234.5
        assert response.model_debug["fallback_used"] is True
    
    def test_model_debug_empty_returns_none(self):
        """Test that empty dict after sanitization returns None"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            ),
            model_debug={"unsafe_key": "value"}
        )
        # All unsafe keys removed, should return None
        assert response.model_debug is None


class TestListItemValidation:
    """Tests for max length per list item (P1 fix)"""
    
    def test_key_phrases_rejects_too_long_items(self):
        """Test that key_phrases rejects items > 200 chars"""
        long_phrase = "x" * 201
        with pytest.raises(ValidationError) as exc_info:
            AnalyzeResponse(
                sentiment=SentimentEnum.NEUTRAL,
                emotion=EmotionEnum.NEUTRAL,
                stress_score=3,
                category=CategoryEnum.GENERAL,
                key_phrases=[long_phrase],
                suggested_reply="Noted.",
                confidence_scores=ConfidenceScores(
                    sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
                )
            )
        assert "too long" in str(exc_info.value).lower()
    
    def test_action_items_rejects_too_long_items(self):
        """Test that action_items rejects items > 200 chars"""
        long_action = "a" * 201
        with pytest.raises(ValidationError) as exc_info:
            AnalyzeResponse(
                sentiment=SentimentEnum.NEUTRAL,
                emotion=EmotionEnum.NEUTRAL,
                stress_score=3,
                category=CategoryEnum.GENERAL,
                action_items=[long_action],
                suggested_reply="Noted.",
                confidence_scores=ConfidenceScores(
                    sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
                )
            )
        assert "too long" in str(exc_info.value).lower()
    
    def test_list_items_at_boundary_accepted(self):
        """Test that items exactly 200 chars are accepted"""
        boundary_phrase = "x" * 200
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            key_phrases=[boundary_phrase],
            action_items=[boundary_phrase],
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            )
        )
        assert len(response.key_phrases[0]) == 200
        assert len(response.action_items[0]) == 200


class TestModelImmutability:
    """Tests for frozen model configuration (P0/P1 fix)"""
    
    def test_confidence_scores_immutable(self):
        """Test that ConfidenceScores cannot be mutated"""
        scores = ConfidenceScores(
            sentiment=0.8, emotion=0.8, category=0.8, stress=0.8
        )
        with pytest.raises(ValidationError):
            scores.sentiment = 0.9
    
    def test_analyze_request_immutable(self):
        """Test that AnalyzeRequest cannot be mutated"""
        from app.schemas.analysis import AnalyzeRequest
        
        request = AnalyzeRequest(
            message="Test",
            user_id="user1",
            channel_id="ch1"
        )
        with pytest.raises(ValidationError):
            request.message = "Changed"
    
    def test_analyze_response_immutable(self):
        """Test that AnalyzeResponse cannot be mutated"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            )
        )
        with pytest.raises(ValidationError):
            response.stress_score = 5


class TestUrgencyFlagValidation:
    """Tests for urgency flag model validator (P0 fix)"""
    
    def test_urgency_set_for_high_stress(self):
        """Test that urgency is set automatically for stress >= 8"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEGATIVE,
            emotion=EmotionEnum.FRUSTRATION,
            stress_score=8,
            category=CategoryEnum.WORKLOAD,
            suggested_reply="Let's address this.",
            confidence_scores=ConfidenceScores(
                sentiment=0.8, emotion=0.8, category=0.8, stress=0.8
            )
        )
        assert response.urgency is True
    
    def test_urgency_set_for_anger(self):
        """Test that urgency is set automatically for anger emotion"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEGATIVE,
            emotion=EmotionEnum.ANGER,
            stress_score=5,
            category=CategoryEnum.CONFLICT,
            suggested_reply="Let's discuss calmly.",
            confidence_scores=ConfidenceScores(
                sentiment=0.8, emotion=0.8, category=0.8, stress=0.8
            )
        )
        assert response.urgency is True
    
    def test_urgency_set_for_fear(self):
        """Test that urgency is set automatically for fear emotion"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEGATIVE,
            emotion=EmotionEnum.FEAR,
            stress_score=6,
            category=CategoryEnum.BLOCKER,
            suggested_reply="We'll work through this.",
            confidence_scores=ConfidenceScores(
                sentiment=0.8, emotion=0.8, category=0.8, stress=0.8
            )
        )
        assert response.urgency is True
    
    def test_urgency_not_set_for_low_stress(self):
        """Test that urgency is not set for low stress"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            )
        )
        assert response.urgency is False
    
    def test_manual_urgency_preserved_when_false(self):
        """Test that manually set urgency=False is preserved for low stress"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            urgency=False,
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            )
        )
        assert response.urgency is False


class TestCleanSchemaFunction:
    """Tests for _remove_titles_recursive and get_clean_schema (P0 fix)"""
    
    def test_remove_titles_from_dict(self):
        """Test that title keys are removed from dict"""
        test_obj = {
            "title": "Should be removed",
            "type": "object",
            "description": "Should remain"
        }
        result = _remove_titles_recursive(test_obj)
        assert "title" not in result
        assert "type" in result
        assert "description" in result
    
    def test_remove_titles_nested(self):
        """Test that title keys are removed from nested dicts"""
        test_obj = {
            "type": "object",
            "properties": {
                "field1": {
                    "title": "Remove this",
                    "type": "string"
                }
            }
        }
        result = _remove_titles_recursive(test_obj)
        assert "title" not in result["properties"]["field1"]
        assert "type" in result["properties"]["field1"]
    
    def test_remove_titles_from_list(self):
        """Test that title keys are removed from dicts in lists"""
        test_obj = [
            {"title": "Remove", "value": 1},
            {"title": "Remove", "value": 2}
        ]
        result = _remove_titles_recursive(test_obj)
        for item in result:
            assert "title" not in item
            assert "value" in item
    
    def test_get_clean_schema_returns_dict(self):
        """Test that get_clean_schema returns a dict"""
        schema = get_clean_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema or "$defs" in schema
    
    def test_get_clean_schema_no_titles(self):
        """Test that get_clean_schema removes all title fields"""
        schema = get_clean_schema()
        schema_str = str(schema)
        # Check deeply nested structure
        def has_title_key(obj):
            if isinstance(obj, dict):
                if "title" in obj:
                    return True
                return any(has_title_key(v) for v in obj.values())
            elif isinstance(obj, list):
                return any(has_title_key(item) for item in obj)
            return False
        
        assert not has_title_key(schema)


class TestSchemaVersion:
    """Tests for schema_version field (P2 requirement)"""
    
    def test_schema_version_default(self):
        """Test that schema_version has default value"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            )
        )
        assert response.schema_version == "1.0.0"
    
    def test_schema_version_included_in_dict(self):
        """Test that schema_version is included in model export"""
        response = AnalyzeResponse(
            sentiment=SentimentEnum.NEUTRAL,
            emotion=EmotionEnum.NEUTRAL,
            stress_score=3,
            category=CategoryEnum.GENERAL,
            suggested_reply="Noted.",
            confidence_scores=ConfidenceScores(
                sentiment=0.7, emotion=0.7, category=0.7, stress=0.7
            )
        )
        response_dict = response.model_dump()
        assert "schema_version" in response_dict
        assert response_dict["schema_version"] == "1.0.0"
