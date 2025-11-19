"""
LLM client for Gemini API integration.

Responsibilities:
- Configure Google Generative AI client
- Make API calls with retry logic
- Handle timeouts and errors
- Enforce JSON schema validation
- Strip code fences from malformed responses
- Return validated dict matching AnalyzeResponse schema

Provider: Gemini ONLY (gemini-2.0-pro or gemini-2.0-flash)
Version: 1.0.0
"""
import json
import logging
import os
import re
import socket
import time
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmBlockThreshold, HarmCategory
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.schemas.analysis import AnalyzeResponse

logger = logging.getLogger(__name__)


# Gemini API error types that should trigger retry (network/timeout only)
RETRIABLE_ERRORS = (
    RequestsTimeout,
    RequestsConnectionError,
    socket.timeout,
    # Add SDK-specific transient exceptions here if present, e.g. genai.TransportError
)


@dataclass
class LLMConfig:
    """Configuration for LLM client"""
    api_key: str
    model_name: str = "gemini-2.0-flash-exp"  # Default to flash for speed
    temperature: float = 0.3  # Low temperature for consistent JSON
    max_tokens: int = 2048
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_min_wait: int = 1  # seconds
    retry_max_wait: int = 10  # seconds


class GeminiClient:
    """
    Gemini API client with production-grade error handling.
    
    Features:
    - Exponential backoff retry logic
    - Timeout enforcement
    - JSON schema validation
    - Code fence stripping
    - Pydantic validation integration
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize Gemini client.
        
        Args:
            config: LLM configuration with API key and parameters
        """
        self.config = config

        # Configure Gemini API
        genai.configure(api_key=config.api_key)

        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=config.model_name,
            generation_config=GenerationConfig(
                temperature=config.temperature,
                max_output_tokens=config.max_tokens,
                response_mime_type="application/json",  # Force JSON output
            ),
            # Safety settings - allow all content for workplace analysis
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )

        logger.info(
            f"Initialized Gemini client: model={config.model_name}, "
            f"temp={config.temperature}, max_tokens={config.max_tokens}"
        )

    def _extract_text_from_response(self, response) -> str:
        """
        Robustly extract generated text from Gemini response.
        
        Handles multiple SDK response shapes across versions.
        
        Args:
            response: Gemini API response object
            
        Returns:
            Extracted text content
            
        Raises:
            ValueError: If unable to extract text from response
        """
        # 1) response.text (simple)
        if hasattr(response, "text"):
            text = response.text
            if isinstance(text, str) and text.strip():
                return text.strip()

        # 2) response.candidates -> candidate.output or candidate.text
        # Check if candidates exist and are not empty
        if hasattr(response, "candidates") and response.candidates:
            try:
                cand = response.candidates[0]
                # Some SDKs have .output or .text
                if hasattr(cand, "output"):
                    output = cand.output
                    if isinstance(output, str) and output.strip():
                        return output.strip()
                if hasattr(cand, "text"):
                    text = cand.text
                    if isinstance(text, str) and text.strip():
                        return text.strip()
                # Some SDKs return nested dict
                if isinstance(cand, dict):
                    for key in ("output", "text", "content"):
                        if key in cand and isinstance(cand[key], str) and cand[key].strip():
                            return cand[key].strip()
            except Exception:
                pass

        # 3) response.output_text or response.output
        for attr in ("output_text", "output", "content"):
            if hasattr(response, attr):
                val = getattr(response, attr)
                if isinstance(val, str):
                    val = val.strip()
                    if val:
                        return val

        raise ValueError("Unable to extract text from Gemini response object")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRIABLE_ERRORS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def _make_api_call(self, messages: list[dict[str, str]]) -> str:
        """
        Make API call to Gemini with retry logic.
        
        Args:
            messages: List of message dicts with role and content
            
        Returns:
            Raw response text from Gemini
            
        Raises:
            Exception: On API errors after retries exhausted
        """
        try:
            # Convert messages to Gemini format
            # Gemini uses a simpler format: just concatenate with role labels
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                if role == "system":
                    prompt_parts.append(f"SYSTEM INSTRUCTIONS:\n{content}\n")
                elif role == "user":
                    prompt_parts.append(f"USER:\n{content}\n")
                elif role == "assistant":
                    prompt_parts.append(f"ASSISTANT:\n{content}\n")

            full_prompt = "\n".join(prompt_parts)

            # Make API call with timeout
            start_time = time.time()
            response = self.model.generate_content(
                full_prompt,
                request_options={"timeout": self.config.timeout_seconds}
            )
            elapsed = time.time() - start_time

            # Log success
            logger.info(
                f"Gemini API call successful: "
                f"latency={elapsed:.2f}s, "
                f"model={self.config.model_name}"
            )

            # Extract text from response (handles multiple SDK shapes)
            try:
                text = self._extract_text_from_response(response)
            except Exception as e:
                logger.error("Failed to extract text from Gemini response: %s", type(e).__name__)
                raise

            if not text:
                raise ValueError("Gemini returned empty response text")

            return text

        except Exception as e:
            logger.error(
                "Gemini API call failed: %s (no user content logged)", type(e).__name__
            )
            raise

    def _strip_code_fences(self, text: str) -> str:
        """
        Strip markdown code fences from response.
        
        Gemini sometimes wraps JSON in ```json ... ``` despite
        response_mime_type="application/json" setting.
        
        Args:
            text: Raw response text
            
        Returns:
            Cleaned text without code fences
        """
        text = text.strip()

        # Remove ```json ... ```
        if text.startswith("```json"):
            text = text[7:]  # Remove ```json
            if text.endswith("```"):
                text = text[:-3]  # Remove ```
            text = text.strip()

        # Remove ``` ... ```
        elif text.startswith("```"):
            text = text[3:]  # Remove ```
            if text.endswith("```"):
                text = text[:-3]  # Remove ```
            text = text.strip()

        return text

    def _validate_json_structure(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate response against Pydantic schema.
        
        Args:
            data: Parsed JSON dict
            
        Returns:
            Validated dict matching AnalyzeResponse schema
            
        Raises:
            ValueError: If validation fails
        """
        try:
            # Validate using Pydantic model
            response = AnalyzeResponse(**data)

            # Convert back to dict (ensures all transformations applied)
            validated_dict = response.model_dump()

            logger.info("Response validation successful")
            return validated_dict

        except Exception as e:
            logger.error(f"Response validation failed: {str(e)}")
            raise ValueError(f"Invalid response structure: {str(e)}") from e

    def _attempt_json_repair(self, text: str) -> dict[str, Any] | None:
        """
        Attempt to repair malformed JSON safely.
        
        Common issues:
        - Code fences (```json)
        - Trailing commas
        - Truncated responses (missing closing braces)
        
        Uses regex to avoid corrupting quoted strings.
        
        Args:
            text: Potentially malformed JSON string
            
        Returns:
            Parsed dict if repair successful, None otherwise
        """
        # Remove surrounding code fences first
        t = text.strip()
        t = re.sub(r'^```(?:json)?\s*', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\s*```$', '', t)

        # Extract the first {...} block if there is one
        start = t.find('{')
        end = t.rfind('}')
        if start == -1 or end == -1 or end < start:
            logger.warning("No valid JSON object structure found")
            return None
        body = t[start:end+1]

        # Remove trailing commas just before } or ] (safer regex)
        # Matches comma followed by whitespace and closing bracket
        body = re.sub(r',\s*(?=[}\]])', '', body)

        # Try incremental repairs: try parse; if fails, attempt small fixes
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            # Last ditch: try to balance braces (only if clearly truncated)
            open_count = body.count('{')
            close_count = body.count('}')
            if open_count > close_count and (open_count - close_count) <= 2:
                body += '}' * (open_count - close_count)
                try:
                    parsed = json.loads(body)
                    logger.info("JSON repair successful (added closing braces)")
                    return parsed
                except json.JSONDecodeError:
                    pass

        logger.warning("All JSON repair attempts failed")
        return None

    def analyze(
        self,
        messages: list[dict[str, str]],
        *,
        fallback_on_error: bool = True
    ) -> dict[str, Any]:
        """
        Analyze message using Gemini API.
        
        Args:
            messages: Prompt messages in OpenAI format (role, content)
            fallback_on_error: If True, return safe fallback on API errors
            
        Returns:
            Validated dict matching AnalyzeResponse schema
            
        Raises:
            ValueError: If response invalid and fallback disabled
            RuntimeError: If API call fails and fallback disabled
        """
        start_time = time.time()
        error_type = None

        try:
            # Make API call with retries
            raw_response = self._make_api_call(messages)

            # Strip code fences if present
            cleaned_response = self._strip_code_fences(raw_response)

            # Parse JSON
            try:
                parsed_data = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                logger.warning("JSON parse failed, attempting repair (no content logged)")
                error_type = "json_parse_error"

                # Attempt repair
                parsed_data = self._attempt_json_repair(cleaned_response)

                if parsed_data is None:
                    if fallback_on_error:
                        logger.error("JSON repair failed, using fallback")
                        return self._generate_fallback_response(error_type=error_type)
                    else:
                        raise ValueError(f"Invalid JSON response: {type(e).__name__}") from e

            # Validate against schema
            validated_data = self._validate_json_structure(parsed_data)

            # Add debug metadata (safe: no user content)
            elapsed_ms = (time.time() - start_time) * 1000
            # Ensure model_debug exists and is a dict
            if "model_debug" not in validated_data or validated_data["model_debug"] is None:
                validated_data["model_debug"] = {}
            validated_data["model_debug"].update({
                "model": self.config.model_name,
                "latency_ms": round(elapsed_ms, 2),
                "fallback_used": False
            })

            return validated_data

        except Exception as e:
            error_type = type(e).__name__
            logger.warning("LLM call failed: %s (use fallback=%s)", error_type, fallback_on_error)

            if fallback_on_error:
                logger.info("Using fallback response due to error")
                return self._generate_fallback_response(error_type=error_type)
            else:
                raise RuntimeError(f"LLM analysis failed: {error_type}") from e

    def _generate_fallback_response(self, error_type: str | None = None) -> dict[str, Any]:
        """
        Generate safe fallback response when LLM fails.
        
        Returns deterministic neutral response that passes validation.
        
        Args:
            error_type: Type of error that triggered fallback (for debugging)
        
        Returns:
            Dict matching AnalyzeResponse schema
        """
        fallback = {
            "sentiment": "neutral",
            "emotion": "neutral",
            "stress_score": 5,
            "category": "general",
            "key_phrases": [],
            "suggested_reply": "Thank you for your message. Let me review this and get back to you.",
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
                "error_type": error_type
            }
        }

        logger.info("Generated fallback response (error_type=%s)", error_type)
        return fallback


def create_gemini_client(
    api_key: str | None = None,
    model_name: str | None = None,
    **kwargs
) -> GeminiClient:
    """
    Factory function to create configured Gemini client.
    
    Args:
        api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
        model_name: Model to use (defaults to gemini-2.0-flash-exp)
        **kwargs: Additional LLMConfig parameters
        
    Returns:
        Configured GeminiClient instance
        
    Raises:
        ValueError: If API key not provided and not in environment
    """
    # Get API key from env if not provided
    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found in environment. "
                "Set it or pass api_key parameter."
            )

    # Use default model if not specified
    if model_name is None:
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

    # Create config
    config = LLMConfig(
        api_key=api_key,
        model_name=model_name,
        **kwargs
    )

    return GeminiClient(config)
