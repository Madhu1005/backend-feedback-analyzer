"""
Analysis endpoints for message sentiment and emotion analysis.

Endpoints:
- POST /api/v1/analyze - Analyze a single message

Request validation, sanitization, and LLM-powered analysis with
comprehensive error handling and rate limiting.

Version: 1.0.0
"""
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.schemas.analysis import AnalyzeRequest
from app.services.analyzer import create_analyzer

logger = logging.getLogger(__name__)
router = APIRouter()


# Helper to get limiter from app state at runtime
def _get_limiter():
    """
    Get rate limiter from app state.

    Falls back to in-memory limiter if app not available (e.g., during testing).
    """
    try:
        from app.main import app
        return app.state.limiter
    except (ImportError, AttributeError):
        # Fallback for testing or if app not yet initialized
        return Limiter(key_func=get_remote_address)


def _rate_limit(limit_spec: str = "60/minute"):
    """
    Decorator factory for rate limiting endpoints.

    Args:
        limit_spec: Rate limit specification (e.g., "60/minute")

    Returns:
        Rate limit decorator using app's configured limiter
    """
    return _get_limiter().limit(limit_spec)


class AnalysisResponseEnvelope(BaseModel):
    """
    Envelope for successful analysis response.

    Wraps the analysis result with metadata about the request processing.
    """
    success: bool = True
    analysis: dict[str, Any] = Field(..., description="Analysis results from LLM")
    sanitization: dict[str, Any] = Field(..., description="Input sanitization details")
    processing_time_ms: float = Field(..., description="Total processing time in milliseconds")
    llm_used: bool = Field(..., description="Whether LLM was used (vs fallback)")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "analysis": {
                    "sentiment": "positive",
                    "emotion": "joy",
                    "stress_score": 2,
                    "category": "praise",
                    "urgency": False
                },
                "sanitization": {
                    "is_safe": True,
                    "threat_level": "low",
                    "modifications_made": ["normalized_unicode"]
                },
                "processing_time_ms": 1234.56,
                "llm_used": True
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response format"""
    success: bool = False
    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(default=None, description="Additional error details")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "validation_error",
                "message": "Message is too long",
                "details": {
                    "field": "message",
                    "max_length": 10000
                }
            }
        }


@router.post(
    "/analyze",
    response_model=AnalysisResponseEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Analyze a message",
    description="Analyze a single message for sentiment, emotion, stress level, and more using LLM.",
    responses={
        200: {"description": "Analysis successful", "model": AnalysisResponseEnvelope},
        400: {"description": "Invalid request format", "model": ErrorResponse},
        422: {"description": "Validation error", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
        503: {"description": "LLM service unavailable", "model": ErrorResponse},
    },
    tags=["Analysis"]
)
@_rate_limit("60/minute")  # Use centralized rate limiter
async def analyze_message(
    request: Request,
    analyze_request: AnalyzeRequest
) -> AnalysisResponseEnvelope:
    """
    Analyze a message for sentiment, emotion, and stress level.

    This endpoint:
    1. Validates and sanitizes input
    2. Detects potential threats (prompt injection, PII, etc.)
    3. Uses LLM to analyze sentiment, emotion, stress
    4. Returns structured analysis with confidence scores

    **Rate Limit:** 60 requests per minute per IP address

    Args:
        request: FastAPI request object (for rate limiting)
        analyze_request: Message to analyze with optional metadata

    Returns:
        AnalysisResponseEnvelope with analysis results and metadata

    Raises:
        HTTPException: 400, 422, 429, 500, or 503 for various error conditions
    """
    start_time = time.time()

    try:
        # Create analyzer (with LLM client)
        try:
            analyzer = create_analyzer()
        except Exception as e:
            logger.error(f"Failed to initialize analyzer: {type(e).__name__}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "success": False,
                    "error": "service_unavailable",
                    "message": "Analysis service is temporarily unavailable",
                    "details": {"reason": "LLM service initialization failed"}
                }
            ) from e

        # Perform analysis
        try:
            result = analyzer.analyze(analyze_request)
        except ValueError as e:
            # Validation or parsing errors
            logger.warning(f"Analysis validation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "success": False,
                    "error": "validation_error",
                    "message": str(e),
                    "details": {"field": "message"}
                }
            ) from e
        except Exception as e:
            # Unexpected errors
            logger.error(f"Analysis failed: {type(e).__name__}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error": "internal_error",
                    "message": "An unexpected error occurred during analysis",
                    "details": {"error_type": type(e).__name__}
                }
            ) from e

        # Calculate total processing time
        processing_time_ms = (time.time() - start_time) * 1000

        # Extract analysis result
        analysis_dict = result.analysis

        # Check if LLM was used or fallback
        llm_used = not analysis_dict.get("model_debug", {}).get("fallback_used", False)

        # Build response
        response = AnalysisResponseEnvelope(
            success=True,
            analysis=analysis_dict,
            sanitization={
                "is_safe": result.threat_level != "critical",
                "threat_level": result.threat_level,
                "modifications_made": [] if not result.sanitization_applied else ["sanitized"]
            },
            processing_time_ms=round(processing_time_ms, 2),
            llm_used=llm_used
        )

        # Log successful analysis (metadata only, no user content)
        logger.info(
            f"Analysis completed: "
            f"sentiment={analysis_dict.get('sentiment')}, "
            f"stress={analysis_dict.get('stress_score')}, "
            f"llm_used={llm_used}, "
            f"time={processing_time_ms:.2f}ms"
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unhandled error in analyze endpoint: {type(e).__name__}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "internal_error",
                "message": "An unexpected error occurred",
                "details": {"error_type": type(e).__name__}
            }
        ) from e
