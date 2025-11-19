"""
Pydantic v2 models for message analysis request/response.
Includes JSON schema export for LLM function-calling.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        ..., min_length=1, max_length=5000, description="The message text to analyze"
    )
    user_id: str = Field(
        ..., min_length=1, max_length=100, description="ID of the user who sent the message"
    )
    channel_id: str = Field(
        ..., min_length=1, max_length=100, description="ID of the channel where message was sent"
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

    model_config = ConfigDict(extra="forbid")

    sentiment: SentimentEnum = Field(..., description="Overall sentiment of the message")
    emotion: EmotionEnum = Field(..., description="Primary emotion detected")
    stress_score: int = Field(
        ..., ge=0, le=10, description="Stress level indicator (0=calm, 10=extreme stress)"
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
    model_debug: dict | None = Field(
        default=None, description="Debug info: model name, tokens, latency, fallback_used"
    )

    @field_validator("key_phrases")
    @classmethod
    def validate_key_phrases(cls, v: list[str]) -> list[str]:
        """Ensure key phrases are not empty strings"""
        return [phrase.strip() for phrase in v if phrase.strip()]

    @field_validator("action_items")
    @classmethod
    def validate_action_items(cls, v: list[str]) -> list[str]:
        """Ensure action items are not empty strings"""
        return [item.strip() for item in v if item.strip()]


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
            "description": "Stress level indicator (0=calm, 10=extreme stress)",
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
            "items": {"type": "string"},
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
            "items": {"type": "string"},
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
        },
        "urgency": {
            "type": "boolean",
            "description": "Whether message requires immediate attention",
        },
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
