"""
Input sanitization and prompt-injection detection.

Production-grade multi-layer security with:
- Unicode normalization (NFC)
- Confusable homoglyph detection
- Prompt injection pattern matching
- Code execution prevention
- PII redaction
- DOS protection

Security: All inputs sanitized before LLM processing.
Version: 2.0.0
"""
import re
import html
import logging
import unicodedata
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from itertools import groupby


logger = logging.getLogger(__name__)


# Confusable homoglyph mapping (prevents visual obfuscation attacks)
_CONFUSABLES = {
    '\u043E': 'o',  # Cyrillic small o
    '\u0456': 'i',  # Cyrillic small byelorussian-ukrainian i
    '\u03BF': 'o',  # Greek small omicron
    '\u0131': 'i',  # Latin small dotless i
    '\u0430': 'a',  # Cyrillic small a
    '\u0435': 'e',  # Cyrillic small e
    '\u0441': 'c',  # Cyrillic small es
    '\u0440': 'p',  # Cyrillic small er
    '\u0445': 'x',  # Cyrillic small ha
    '\u0443': 'y',  # Cyrillic small u
    '\u04BB': 'h',  # Cyrillic small shha
    '\u0455': 's',  # Cyrillic small dze
    '\u0458': 'j',  # Cyrillic small je
    '\u03B1': 'a',  # Greek small alpha
    '\u03B5': 'e',  # Greek small epsilon
    '\u03B9': 'i',  # Greek small iota
    '\u03C1': 'p',  # Greek small rho
}


# Threat scoring weights (explainable and tunable)
THREAT_WEIGHTS = {
    "prompt_injection": 50,
    "code_injection": 40,
    "excessive_repetition": 10,
}


class ThreatLevel(str, Enum):
    """Threat severity classification"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SanitizationResult:
    """
    Immutable result of sanitization process.
    
    Attributes:
        sanitized_text: Cleaned and safe text
        is_safe: Whether text passes safety threshold
        threat_level: Assessed threat severity
        detected_threats: List of specific threats found
        modifications_made: List of transformations applied
        original_length: Length of original input (for audit)
    """
    sanitized_text: str
    is_safe: bool
    threat_level: ThreatLevel
    detected_threats: List[str] = field(default_factory=list)
    modifications_made: List[str] = field(default_factory=list)
    original_length: int = 0


class InputSanitizer:
    """
    Production-grade input sanitizer with prompt injection detection.
    
    Security layers:
    1. Unicode normalization (NFC + confusable detection)
    2. Prompt injection pattern detection with whitespace normalization
    3. Code execution pattern detection
    4. PII redaction (email, phone, SSN, credit card)
    5. DOS protection (repetition + length limits)
    6. Control character removal
    7. HTML escaping
    
    Thread-safe, stateless operation.
    """
    
    # Prompt injection patterns (case-insensitive, whitespace-tolerant)
    # These match AFTER canonicalization (punctuation removed, lowercase)
    INJECTION_PATTERNS = [
        r'ignore\s+(?:all\s+)?(?:previous|above|prior|all)\s+(?:instructions?|prompts?|commands?)',
        r'disregard\s+(?:all\s+)?(?:previous|above|prior|all)\s+(?:instructions?|prompts?|commands?)',
        r'forget\s+(?:all\s+)?(?:previous|above|prior|all)\s+(?:instructions?|prompts?|commands?)',
        r'system\s+you\s+are\s+(?:now|a|an|\w+)',  # Canonicalized: no colon
        r'(?:im_start|im_end|system|assistant|user)',  # Canonicalized: no brackets
        r'pretend\s+(?:you\s+are|to\s+be)\s+(?:a|an)',
        r'act\s+as\s+(?:if|though|a|an)',
        r'new\s+(?:instructions?|role|task|prompt)\s+',  # Canonicalized: no colon
        r'override\s+(?:previous|default|system)',
        r'you\s+must\s+(?:now|always|ignore)',
        r'from\s+now\s+on\s+you',
        r'your\s+new\s+(?:role|task|instruction)',
        r'sudo\s+mode',
        r'developer\s+mode',
    ]
    
    # Code execution patterns
    CODE_PATTERNS = [
        r'eval\s*\(',
        r'exec\s*\(',
        r'__import__\s*\(',
        r'os\.system\s*\(',
        r'subprocess\.',
        r'<script[^>]*>',
        r'javascript\s*:',
        r'data\s*:\s*text/html',
        r'onerror\s*=',
        r'onclick\s*=',
    ]
    
    # PII patterns
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE_PATTERN = r'\b(?:\+?1[-.\s]?)?(?:\([0-9]{3}\)|[0-9]{3})[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'
    SSN_PATTERN = r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'
    CREDIT_CARD_PATTERN = r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
    
    # Limits
    MAX_INPUT_LENGTH = 5000
    MAX_LINE_LENGTH = 500
    MAX_CHAR_REPETITION = 50
    MAX_WORD_REPETITION = 10
    
    # Pre-compiled regexes (P1-1 fix: performance optimization)
    _INJECTION_REGEXES = None
    _CODE_REGEXES = None
    _EMAIL_RE = None
    _PHONE_RE = None
    _SSN_RE = None
    _CARD_RE = None
    
    @classmethod
    def _ensure_compiled_regexes(cls) -> None:
        """Lazy compilation of regex patterns."""
        if cls._INJECTION_REGEXES is None:
            cls._INJECTION_REGEXES = [
                re.compile(p, re.IGNORECASE) for p in cls.INJECTION_PATTERNS
            ]
            cls._CODE_REGEXES = [
                re.compile(p, re.IGNORECASE) for p in cls.CODE_PATTERNS
            ]
            cls._EMAIL_RE = re.compile(cls.EMAIL_PATTERN)
            cls._PHONE_RE = re.compile(cls.PHONE_PATTERN)
            cls._SSN_RE = re.compile(cls.SSN_PATTERN)
            cls._CARD_RE = re.compile(cls.CREDIT_CARD_PATTERN)
    
    @classmethod
    def _fold_confusables(cls, text: str) -> str:
        """
        Replace common homoglyphs with ASCII equivalents (P0-1 fix).
        Prevents visual obfuscation attacks using lookalike characters.
        """
        return ''.join(_CONFUSABLES.get(ch, ch) for ch in text)
    
    @classmethod
    def _canonicalize_for_matching(cls, text: str) -> str:
        """
        Produce canonical form for pattern matching (P0-3 fix).
        
        Process:
        1. Unicode normalization (NFC)
        2. Confusable folding
        3. Punctuation removal
        4. Whitespace normalization
        5. Lowercase
        """
        # Normalize Unicode
        txt = unicodedata.normalize('NFC', text)
        
        # Fold confusables
        txt = cls._fold_confusables(txt)
        
        # Remove punctuation except word boundaries
        txt = re.sub(r'[^\w\s]', ' ', txt)
        
        # Collapse whitespace and lowercase
        txt = re.sub(r'\s+', ' ', txt).strip().lower()
        
        return txt
    
    @classmethod
    def sanitize(
        cls,
        text: Optional[str],
        *,
        strict: bool = False,
        preserve_formatting: bool = False,
        redact_pii: bool = True,
        html_escape: bool = True
    ) -> SanitizationResult:
        """
        Sanitize input text through full security pipeline.
        
        Args:
            text: Raw input text (None returns empty result)
            strict: If True, applies aggressive code block removal
            preserve_formatting: If True, preserves indentation/structure
            redact_pii: If True, redacts PII
            html_escape: If True, applies HTML escaping (default True)
            
        Returns:
            SanitizationResult with sanitized text and threat assessment
        """
        cls._ensure_compiled_regexes()
        
        if text is None or not text:
            return SanitizationResult(
                sanitized_text="",
                is_safe=True,
                threat_level=ThreatLevel.NONE,
                original_length=0 if text is None else len(text)
            )
        
        original_length = len(text)
        detected_threats: List[str] = []
        modifications: List[str] = []
        
        # Step 1: Enforce input length limit FIRST (DOS protection)
        if len(text) > cls.MAX_INPUT_LENGTH:
            text = text[:cls.MAX_INPUT_LENGTH]
            modifications.append("Truncated to max length")
        
        # Step 2: Unicode normalization (NFC)
        text, normalized = cls._normalize_unicode(text)
        if normalized:
            modifications.append("Normalized Unicode")
        
        # Step 3: Remove zero-width and bidi characters
        text, removed = cls._remove_invisible_chars(text)
        if removed:
            modifications.append("Removed invisible characters")
        
        # Step 4: Detect prompt injections (with canonicalization)
        had_injection, text = cls._detect_and_remove_injections(text)
        if had_injection:
            detected_threats.append("prompt_injection")
            modifications.append("Removed prompt injection")
        
        # Step 5: Detect code execution attempts
        if strict:
            had_code, text = cls._remove_code_patterns(text)
            if had_code:
                detected_threats.append("code_injection")
                modifications.append("Removed code patterns")
        
        # Step 6: HTML escape (if enabled) - using stdlib
        if html_escape:
            text = html.escape(text, quote=True)
            modifications.append("HTML escaped")
        
        # Step 7: Redact PII if enabled
        if redact_pii:
            text, had_pii = cls._redact_pii(text)
            if had_pii:
                modifications.append("Redacted PII")
        
        # Step 8: Remove control characters
        text = cls._remove_control_chars(text)
        
        # Step 9: Normalize whitespace
        if not preserve_formatting:
            text = cls._normalize_whitespace(text)
            modifications.append("Normalized whitespace")
        
        # Step 10: Remove excessive repetition (with fixed groupby logic)
        had_repetition, text = cls._remove_excessive_repetition(text)
        if had_repetition:
            detected_threats.append("excessive_repetition")
            modifications.append("Removed excessive repetition")
        
        # Step 11: Enforce line length limits
        text = cls._enforce_line_length(text)
        
        # Step 12: Final cleanup
        text = text.strip()
        
        # Threat assessment with weighted scoring (P1-5 fix)
        threat_level = cls._calculate_threat_level(detected_threats)
        is_safe = threat_level in [ThreatLevel.NONE, ThreatLevel.LOW]
        
        # Logging for audit trail (P0-4 fix: no textual content)
        if detected_threats:
            logger.warning(
                "Sanitizer detected threats",
                extra={
                    "threats": detected_threats,
                    "threat_level": threat_level.value,
                    "original_length": original_length,
                    "sanitized_length": len(text),
                    "threat_count": len(detected_threats)
                }
            )
        
        return SanitizationResult(
            sanitized_text=text,
            is_safe=is_safe,
            threat_level=threat_level,
            detected_threats=detected_threats,
            modifications_made=modifications,
            original_length=original_length
        )
    
    @classmethod
    def _normalize_unicode(cls, text: str) -> Tuple[str, bool]:
        """Normalize Unicode to NFC form."""
        original = text
        text = unicodedata.normalize('NFC', text)
        return text, text != original
    
    @classmethod
    def _remove_invisible_chars(cls, text: str) -> Tuple[str, bool]:
        """Remove zero-width characters and bidi overrides."""
        original = text
        
        # Remove zero-width characters
        text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
        
        # Remove bidi override characters
        text = re.sub(r'[\u202A-\u202E]', '', text)
        
        # Remove zero-width joiner/non-joiner abuse
        text = re.sub(r'[\u200C\u200D]{2,}', '', text)
        
        return text, text != original
    
    @classmethod
    def _detect_and_remove_injections(cls, text: str) -> Tuple[bool, str]:
        """
        Detect and remove prompt injection attempts (P0-2, P0-3 fixes).
        Uses canonicalized matching and conservative span replacement.
        """
        found = False
        
        # Canonicalize for matching
        normalized_for_matching = cls._canonicalize_for_matching(text)
        
        # First pass: detect using canonicalized text
        for regex in cls._INJECTION_REGEXES:
            if regex.search(normalized_for_matching):
                found = True
        
        # Second pass: replace on original text if detected
        if found:
            for regex in cls._INJECTION_REGEXES:
                # Try to match and replace on original text
                if regex.search(text):
                    text = regex.sub(
                        "[REMOVED: Potential security violation]",
                        text,
                        count=1
                    )
        
        return found, text
    
    @classmethod
    def _remove_code_patterns(cls, text: str) -> Tuple[bool, str]:
        """Remove code execution patterns in strict mode."""
        found = False
        
        for regex in cls._CODE_REGEXES:
            if regex.search(text):
                found = True
                text = regex.sub("[code removed]", text, count=1)
        
        # Remove code blocks (triple backticks) - careful replacement
        if '```' in text:
            found = True
            text = re.sub(r'```[^`]*```', '[code block removed]', text, flags=re.DOTALL)
            text = text.replace('```', '')
        
        return found, text
    
    @classmethod
    def _redact_pii(cls, text: str) -> Tuple[str, bool]:
        """Redact personally identifiable information."""
        original = text
        
        text = cls._EMAIL_RE.sub('[EMAIL_REDACTED]', text)
        text = cls._PHONE_RE.sub('[PHONE_REDACTED]', text)
        text = cls._SSN_RE.sub('[SSN_REDACTED]', text)
        text = cls._CARD_RE.sub('[CARD_REDACTED]', text)
        
        return text, text != original
    
    @classmethod
    def _remove_control_chars(cls, text: str) -> str:
        """Remove null bytes and control characters."""
        text = text.replace('\x00', '')
        text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        return text
    
    @classmethod
    def _normalize_whitespace(cls, text: str) -> str:
        """
        Normalize whitespace preserving indentation (P0 fix).
        Only collapses excessive spaces within lines and excessive newlines.
        """
        lines = text.split('\n')
        normalized_lines = []
        
        for line in lines:
            stripped = line.lstrip()
            leading_ws = line[:len(line) - len(stripped)]
            # Collapse multiple internal spaces
            stripped = re.sub(r'  +', ' ', stripped)
            normalized_lines.append(leading_ws + stripped.rstrip())
        
        # Join and limit consecutive newlines to 2
        text = '\n'.join(normalized_lines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
    
    @classmethod
    def _remove_excessive_repetition(cls, text: str) -> Tuple[bool, str]:
        """
        Remove excessive character and word repetition (P1-2 fix: groupby).
        Uses deterministic groupby approach for word repetition.
        """
        found = False
        
        # Character repetition
        pattern = r'(.)\1{' + str(cls.MAX_CHAR_REPETITION) + r',}'
        if re.search(pattern, text):
            found = True
            text = re.sub(pattern, r'\1' * cls.MAX_CHAR_REPETITION, text)
        
        # Word repetition - Fixed with groupby
        words = text.split()
        if len(words) > 1:
            clamped = []
            for key, group in groupby(words, key=lambda w: w.lower()):
                g = list(group)
                if len(g) > cls.MAX_WORD_REPETITION:
                    found = True
                clamped.extend(g[:cls.MAX_WORD_REPETITION])
            
            if found:
                text = ' '.join(clamped)
        
        return found, text
    
    @classmethod
    def _enforce_line_length(cls, text: str) -> str:
        """Enforce maximum line length per line."""
        lines = text.split('\n')
        truncated_lines = []
        
        for line in lines:
            if len(line) > cls.MAX_LINE_LENGTH:
                truncated_lines.append(line[:cls.MAX_LINE_LENGTH] + "...")
            else:
                truncated_lines.append(line)
        
        return '\n'.join(truncated_lines)
    
    @classmethod
    def _calculate_threat_level(cls, threats: List[str]) -> ThreatLevel:
        """
        Calculate threat level using weighted scoring (P1-5 fix).
        Explainable and tunable threat assessment.
        """
        if not threats:
            return ThreatLevel.NONE
        
        # Weight-based scoring
        score = 0
        for threat in threats:
            score += THREAT_WEIGHTS.get(threat, 0)
        
        # Threshold-based classification
        if score >= 100:
            return ThreatLevel.CRITICAL
        elif score >= 50:
            return ThreatLevel.HIGH
        elif score >= 20:
            return ThreatLevel.MEDIUM
        else:
            return ThreatLevel.LOW
    
    @classmethod
    def is_safe_for_logging(cls, text: str) -> bool:
        """
        Check if text is safe for logging (no PII).
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains no detected PII
        """
        cls._ensure_compiled_regexes()
        
        if not text:
            return True
        
        if cls._EMAIL_RE.search(text):
            return False
        if cls._PHONE_RE.search(text):
            return False
        if cls._SSN_RE.search(text):
            return False
        if cls._CARD_RE.search(text):
            return False
        
        return True
    
    @classmethod
    def redact_pii(cls, text: Optional[str]) -> Optional[str]:
        """
        Convenience method to redact PII from text.
        
        Args:
            text: Text to redact (can be None)
            
        Returns:
            Text with PII redacted, or None if input was None
        """
        cls._ensure_compiled_regexes()
        
        if text is None:
            return None
        
        redacted, _ = cls._redact_pii(text)
        return redacted
