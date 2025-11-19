"""
Message analysis orchestration service.

Responsibilities:
- Take user input (raw message)
- Sanitize input using InputSanitizer
- Build prompt using PromptBuilder
- Call LLM client for analysis
- Validate and normalize response
- Return final validated dict

Integration: Combines sanitizer, prompt_templates, and llm_client
Version: 1.0.0
"""
import logging
from dataclasses import dataclass
from typing import Any

from app.core.llm_client import GeminiClient, create_gemini_client
from app.core.prompt_templates import PromptBuilder, PromptContext
from app.core.sanitizer import InputSanitizer, ThreatLevel
from app.schemas.analysis import AnalyzeRequest

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """
    Complete analysis result with metadata.

    Attributes:
        analysis: Validated analysis dict matching AnalyzeResponse schema
        sanitization_applied: Whether input was sanitized
        threat_level: Detected threat level from sanitization
        llm_used: Whether LLM was called (vs fallback)
        processing_time_ms: Total processing time in milliseconds
    """
    analysis: dict[str, Any]
    sanitization_applied: bool
    threat_level: str
    llm_used: bool
    processing_time_ms: float


class MessageAnalyzer:
    """
    High-level service for analyzing workplace messages.

    Orchestrates the complete pipeline:
    1. Input sanitization (security)
    2. Prompt building (few-shot + schema)
    3. LLM inference (Gemini API)
    4. Response validation (Pydantic)
    5. Result normalization
    """

    def __init__(
        self,
        gemini_client: GeminiClient | None = None,
        sanitizer: InputSanitizer | None = None
    ):
        """
        Initialize analyzer with optional dependency injection.

        Args:
            gemini_client: Pre-configured Gemini client (creates default if None)
            sanitizer: Pre-configured sanitizer (creates default if None)
        """
        self.llm_client = gemini_client or create_gemini_client()
        self.sanitizer = sanitizer or InputSanitizer()

        logger.info("MessageAnalyzer initialized")

    def analyze(
        self,
        request: AnalyzeRequest,
        *,
        include_examples: bool = True,
        max_examples: int = 3,
        fallback_on_error: bool = True
    ) -> AnalysisResult:
        """
        Analyze a message through the complete pipeline.

        Args:
            request: Validated AnalyzeRequest with message and metadata
            include_examples: Whether to include few-shot examples in prompt
            max_examples: Maximum number of examples to include
            fallback_on_error: Whether to use fallback response on LLM errors

        Returns:
            AnalysisResult with validated analysis and metadata

        Raises:
            ValueError: If sanitization detects critical threat (optional)
            RuntimeError: If LLM fails and fallback disabled
        """
        import time
        start_time = time.time()

        # Step 1: Sanitize input
        logger.info(f"Analyzing message: length={len(request.message)} chars")

        sanitization_result = self.sanitizer.sanitize(
            request.message,
            html_escape=False,  # LLM doesn't need HTML escaping
            redact_pii=True,    # Protect user privacy
            strict=False        # Allow normal code mentions in workplace context
        )

        sanitized_message = sanitization_result.sanitized_text
        threat_level = sanitization_result.threat_level

        # Log sanitization results
        if sanitization_result.detected_threats:
            logger.warning(
                f"Threats detected: {sanitization_result.detected_threats}, "
                f"level={threat_level}"
            )

        # Optional: Block critical threats
        if threat_level == ThreatLevel.CRITICAL:
            logger.error("Critical threat detected, blocking analysis")
            # Could raise exception here, but for now use fallback
            return self._create_blocked_result(
                threat_level=threat_level,
                processing_time_ms=(time.time() - start_time) * 1000
            )

        # Step 2: Build prompt context
        context = PromptContext(
            message=sanitized_message,
            sender_id=request.user_id,
            metadata={
                "channel_id": request.channel_id,
                **(request.context or {})
            } if request.channel_id or request.context else None
        )

        # Step 3: Build prompt with schema and examples
        messages = PromptBuilder.build_analysis_prompt(
            context,
            include_schema=True,
            include_examples=include_examples,
            max_examples=max_examples
        )

        logger.info(
            f"Built prompt: messages={len(messages)}, "
            f"examples={max_examples if include_examples else 0}"
        )

        # Step 4: Call LLM
        try:
            analysis_dict = self.llm_client.analyze(
                messages,
                fallback_on_error=fallback_on_error
            )

            llm_used = not analysis_dict.get("model_debug", {}).get("fallback_used", False)

            # Add metadata to model_debug
            if "model_debug" not in analysis_dict:
                analysis_dict["model_debug"] = {}

            analysis_dict["model_debug"]["sanitization_applied"] = bool(
                sanitization_result.modifications_made
            )
            analysis_dict["model_debug"]["threat_level"] = threat_level.value

            logger.info(
                f"Analysis complete: llm_used={llm_used}, "
                f"sentiment={analysis_dict.get('sentiment')}"
            )

        except Exception as e:
            logger.error(f"Analysis pipeline failed: {str(e)}")

            if fallback_on_error:
                analysis_dict = self._generate_safe_fallback()
                llm_used = False
            else:
                raise

        # Step 5: Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000

        # Step 6: Return result
        return AnalysisResult(
            analysis=analysis_dict,
            sanitization_applied=bool(sanitization_result.modifications_made),
            threat_level=threat_level.value,
            llm_used=llm_used,
            processing_time_ms=processing_time_ms
        )

    def _create_blocked_result(
        self,
        threat_level: ThreatLevel,
        processing_time_ms: float
    ) -> AnalysisResult:
        """
        Create result for blocked/rejected messages.

        Args:
            threat_level: Detected threat level
            processing_time_ms: Processing time

        Returns:
            AnalysisResult indicating blocked content
        """
        blocked_analysis = {
            "sentiment": "neutral",
            "emotion": "neutral",
            "stress_score": 0,
            "category": "general",
            "key_phrases": ["Content flagged by security filter"],
            "suggested_reply": "This message has been flagged for review. Please contact support if you believe this is an error.",
            "action_items": ["Review flagged content", "Contact security team"],
            "confidence_scores": {
                "sentiment": 0.0,
                "emotion": 0.0,
                "category": 0.0,
                "stress": 0.0
            },
            "urgency": True,
            "model_debug": {
                "model": "security filter",
                "threat_level": threat_level.value,
                "blocked": True
            }
        }

        return AnalysisResult(
            analysis=blocked_analysis,
            sanitization_applied=True,
            threat_level=threat_level.value,
            llm_used=False,
            processing_time_ms=processing_time_ms
        )

    def _generate_safe_fallback(self) -> dict[str, Any]:
        """
        Generate safe fallback when both LLM and sanitizer fail.

        Returns:
            Dict matching AnalyzeResponse schema
        """
        return {
            "sentiment": "neutral",
            "emotion": "neutral",
            "stress_score": 5,
            "category": "general",
            "key_phrases": [],
            "suggested_reply": "Thank you for your message. I'll review this and get back to you shortly.",
            "action_items": ["Review message", "Follow up with sender"],
            "confidence_scores": {
                "sentiment": 0.5,
                "emotion": 0.5,
                "category": 0.5,
                "stress": 0.5
            },
            "urgency": False,
            "model_debug": {
                "model": "fallback",
                "fallback_used": True,
                "reason": "Pipeline failure"
            }
        }

    def analyze_batch(
        self,
        requests: list[AnalyzeRequest],
        **kwargs
    ) -> list[AnalysisResult]:
        """
        Analyze multiple messages in batch.

        Args:
            requests: List of AnalyzeRequest objects
            **kwargs: Additional arguments passed to analyze()

        Returns:
            List of AnalysisResult objects (same order as input)
        """
        results = []

        for i, request in enumerate(requests):
            logger.info(f"Processing batch item {i+1}/{len(requests)}")

            try:
                result = self.analyze(request, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch item {i+1} failed: {str(e)}")

                # Add error result
                error_result = AnalysisResult(
                    analysis=self._generate_safe_fallback(),
                    sanitization_applied=False,
                    threat_level="unknown",
                    llm_used=False,
                    processing_time_ms=0.0
                )
                results.append(error_result)

        logger.info(f"Batch processing complete: {len(results)}/{len(requests)} successful")
        return results


# Factory function for easy instantiation
def create_analyzer(
    api_key: str | None = None,
    model_name: str | None = None
) -> MessageAnalyzer:
    """
    Create configured MessageAnalyzer instance.

    Args:
        api_key: Gemini API key (defaults to env var)
        model_name: Model to use (defaults to gemini-2.0-flash-exp)

    Returns:
        Configured MessageAnalyzer
    """
    client = create_gemini_client(api_key=api_key, model_name=model_name)
    return MessageAnalyzer(gemini_client=client)
