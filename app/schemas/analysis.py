"""
Pydantic v2 models for message analysis request/response.
Implements strict validation and JSON schema export for LLM function-calling.

Security: All fields validated, model_debug sanitized, immutable models.
Version: 1.0.0
"""

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SentimentEnum(str, Enum):
    """Sentiment classification options"""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class EmotionEnum(str, Enum):
    """Primary emotion detected in message"""

    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    NEUTRAL = "neutral"
    FRUSTRATION = "frustration"
    ANXIETY = "anxiety"
    EXCITEMENT = "excitement"


class CategoryEnum(str, Enum):
    """Message category classification"""

    WORKLOAD = "workload"
    DEADLINE = "deadline"
    CONFLICT = "conflict"
    PRAISE = "praise"
    FEEDBACK = "feedback"
    QUESTION = "question"
    UPDATE = "update"
    BLOCKER = "blocker"
    SUPPORT_REQUEST = "support_request"
    GENERAL = "general"


class ConfidenceScores(BaseModel):
    """Confidence scores for each classification"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sentiment: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in sentiment classification"
    )
    emotion: float = Field(..., ge=0.0, le=1.0, description="Confidence in emotion detection")
    category: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in category classification"
    )
    stress: float = Field(..., ge=0.0, le=1.0, description="Confidence in stress score")


class AnalyzeRequest(BaseModel):
    """Request schema for message analysis endpoint"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str = Field(
        ..., min_length=1, max_length=5000, description="The message text to analyze"
    )
    user_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="ID of the user who sent the message",
    )
    channel_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="ID of the channel where message was sent",
    )
    context: dict[str, str] | None = Field(
        default=None, description="Optional contextual information"
    )

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        """Ensure message is not just whitespace"""
        if not v.strip():
            raise ValueError("Message cannot be empty or only whitespace")
        return v.strip()


class AnalyzeResponse(BaseModel):
    """Response schema for message analysis"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sentiment: SentimentEnum = Field(..., description="Overall sentiment of the message")
    emotion: EmotionEnum = Field(..., description="Primary emotion detected")
    stress_score: int = Field(
        ..., ge=0, le=10, description="Stress level (0=calm, 10=extreme stress)"
    )
    category: CategoryEnum = Field(..., description="Message category classification")
    key_phrases: list[str] = Field(
        default_factory=list, max_length=10, description="Important phrases extracted from message"
    )
    suggested_reply: str | None = Field(
        default=None, max_length=1000, description="AI-suggested reply for manager/team lead"
    )
    action_items: list[str] = Field(
        default_factory=list, max_length=5, description="Recommended action items"
    )
    confidence_scores: ConfidenceScores = Field(
        ..., description="Confidence scores for each classification"
    )
    urgency: bool = Field(default=False, description="Whether message requires immediate attention")
    model_debug: dict[str, Any] | None = Field(
        default=None, description="Debug info: model, tokens, latency, fallback_used"
    )
    schema_version: str = Field(
        default="1.0.0", description="Schema version for compatibility tracking"
    )

    @field_validator("key_phrases", "action_items")
    @classmethod
    def validate_list_items(cls, v: list[str]) -> list[str]:
        """Ensure list items are not empty and enforce max length"""
        MAX_ITEM_LENGTH = 200
        filtered = []
        for item in v:
            if item and item.strip():
                stripped = item.strip()
                if len(stripped) > MAX_ITEM_LENGTH:
                    raise ValueError(
                        f"Item too long: {len(stripped)} chars " f"(max {MAX_ITEM_LENGTH})"
                    )
                filtered.append(stripped)
        return filtered

    @field_validator("model_debug", mode="before")
    @classmethod
    def sanitize_model_debug(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Sanitize model_debug to prevent log injection and PII leaks"""
        if not v:
            return v

        sanitized = {}
        SAFE_KEYS = {
            "model",
            "tokens",
            "tokens_used",
            "latency_ms",
            "provider",
            "fallback_used",
            "temperature",
        }

        for key, value in v.items():
            # Only allow safe keys
            if key not in SAFE_KEYS:
                continue

            # Sanitize string values: remove newlines, limit length
            if isinstance(value, str):
                sanitized_val = value.replace("\n", " ").replace("\r", " ")
                # Remove potential code blocks or injection attempts
                sanitized_val = re.sub(r"[`{}\\\[\]]", "", sanitized_val)
                sanitized[key] = sanitized_val[:100]  # Limit length
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value  # Preserve native types for numbers and bools
            else:
                # Convert other types to string and sanitize
                sanitized[key] = str(value)[:50]

        return sanitized if sanitized else None

    @model_validator(mode="before")
    @classmethod
    def validate_attention_flag(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Set urgency based on stress score and emotion before freezing"""
        if isinstance(values, dict):
            stress_score = values.get("stress_score", 0)
            emotion = values.get("emotion")
            urgency = values.get("urgency", False)

            high_stress = stress_score >= 8
            critical_emotion = emotion in ["anger", "fear"]

            if (high_stress or critical_emotion) and not urgency:
                values["urgency"] = True

        return values


def _remove_titles_recursive(obj: Any) -> Any:
    """Recursively remove title fields from schema dict.

    Args:
        obj: Schema object (dict, list, or primitive)

    Returns:
        Cleaned object without title fields
    """
    if isinstance(obj, dict):
        return {k: _remove_titles_recursive(v) for k, v in obj.items() if k != "title"}
    elif isinstance(obj, list):
        return [_remove_titles_recursive(item) for item in obj]
    return obj


def get_clean_schema() -> dict[str, Any]:
    """Get JSON schema without title fields for cleaner LLM prompts.

    Returns:
        Simplified schema suitable for inclusion in system prompts
    """
    schema = AnalyzeResponse.model_json_schema()
    result = _remove_titles_recursive(schema)
    # Ensure we return a dict, not Any
    if not isinstance(result, dict):
        return {}
    return result


# JSON Schema export for LLM function-calling
ANALYSIS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "sentiment": {
            "type": "string",
            "enum": ["positive", "negative", "neutral", "mixed"],
            "description": "Overall sentiment of the message",
        },
        "emotion": {
            "type": "string",
            "enum": [
                "joy",
                "sadness",
                "anger",
                "fear",
                "surprise",
                "disgust",
                "neutral",
                "frustration",
                "anxiety",
                "excitement",
            ],
            "description": "Primary emotion detected",
        },
        "stress_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 10,
            "description": "Stress level (0=calm, 10=extreme stress)",
        },
        "category": {
            "type": "string",
            "enum": [
                "workload",
                "deadline",
                "conflict",
                "praise",
                "feedback",
                "question",
                "update",
                "blocker",
                "support_request",
                "general",
            ],
            "description": "Message category classification",
        },
        "key_phrases": {
            "type": "array",
            "items": {"type": "string", "maxLength": 200},
            "maxItems": 10,
            "description": "Important phrases extracted from message",
        },
        "suggested_reply": {
            "type": "string",
            "maxLength": 1000,
            "description": "AI-suggested reply for manager/team lead",
        },
        "action_items": {
            "type": "array",
            "items": {"type": "string", "maxLength": 200},
            "maxItems": 5,
            "description": "Recommended action items",
        },
        "confidence_scores": {
            "type": "object",
            "properties": {
                "sentiment": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "emotion": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "category": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "stress": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            },
            "required": ["sentiment", "emotion", "category", "stress"],
            "additionalProperties": False,
        },
        "urgency": {
            "type": "boolean",
            "description": "Whether message requires immediate attention",
        },
        "schema_version": {"type": "string", "description": "Schema version for compatibility"},
    },
    "required": [
        "sentiment",
        "emotion",
        "stress_score",
        "category",
        "confidence_scores",
        "urgency",
    ],
    "additionalProperties": False,
}
