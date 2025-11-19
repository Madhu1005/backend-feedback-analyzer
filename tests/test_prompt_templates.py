"""
Tests for prompt templates and prompt building functionality.

Covers:
- System prompt structure
- Few-shot examples validity
- Schema injection
- Context building
- Token budget management
- JSON extraction/validation
"""
import json
import pytest
from app.core.prompt_templates import (
    SYSTEM_PROMPT,
    FEW_SHOT_EXAMPLES,
    PROMPT_INJECTION_EXAMPLE,
    PromptContext,
    PromptBuilder,
    build_prompt,
    get_system_prompt,
    get_few_shot_examples,
)
from app.schemas.analysis import (
    AnalyzeResponse,
    SentimentEnum,
    EmotionEnum,
    CategoryEnum,
)


class TestSystemPrompt:
    """Test system prompt structure and requirements."""
    
    def test_system_prompt_not_empty(self):
        """System prompt should contain content"""
        assert SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 100
    
    def test_system_prompt_mentions_json(self):
        """System prompt should emphasize JSON output"""
        assert "JSON" in SYSTEM_PROMPT
        assert "json" in SYSTEM_PROMPT.lower()
    
    def test_system_prompt_mentions_schema(self):
        """System prompt should reference schema requirements"""
        assert "schema" in SYSTEM_PROMPT.lower()
    
    def test_system_prompt_warns_about_formatting(self):
        """System prompt should warn against markdown/code blocks"""
        prompt_lower = SYSTEM_PROMPT.lower()
        assert any(word in prompt_lower for word in ["markdown", "code block", "exact"])
    
    def test_system_prompt_mentions_edge_cases(self):
        """System prompt should mention edge case handling"""
        prompt_lower = SYSTEM_PROMPT.lower()
        assert "sarcasm" in prompt_lower or "edge case" in prompt_lower


class TestFewShotExamples:
    """Test few-shot examples validity and coverage."""
    
    def test_has_multiple_examples(self):
        """Should have at least 5 examples"""
        assert len(FEW_SHOT_EXAMPLES) >= 5
    
    def test_examples_have_required_fields(self):
        """Each example should have user_message and assistant_response"""
        for example in FEW_SHOT_EXAMPLES:
            assert "user_message" in example
            assert "assistant_response" in example
            assert isinstance(example["user_message"], str)
            assert isinstance(example["assistant_response"], dict)
    
    def test_example_responses_are_valid_schema(self):
        """All assistant responses should validate against AnalyzeResponse schema"""
        for i, example in enumerate(FEW_SHOT_EXAMPLES):
            response_dict = example["assistant_response"]
            
            # Should be parseable by Pydantic model
            try:
                AnalyzeResponse(**response_dict)
            except Exception as e:
                pytest.fail(f"Example {i} failed validation: {str(e)}")
    
    def test_examples_cover_different_sentiments(self):
        """Examples should cover positive, negative, and neutral sentiments"""
        sentiments = [ex["assistant_response"]["sentiment"] for ex in FEW_SHOT_EXAMPLES]
        assert "positive" in sentiments
        assert "negative" in sentiments
        assert "neutral" in sentiments
    
    def test_examples_cover_different_emotions(self):
        """Examples should demonstrate variety of emotions"""
        emotions = [ex["assistant_response"]["emotion"] for ex in FEW_SHOT_EXAMPLES]
        assert len(set(emotions)) >= 5  # At least 5 different emotions
    
    def test_examples_cover_different_categories(self):
        """Examples should cover different message categories"""
        categories = [ex["assistant_response"]["category"] for ex in FEW_SHOT_EXAMPLES]
        assert len(set(categories)) >= 3  # At least 3 different categories
    
    def test_examples_include_edge_cases(self):
        """Should include examples for sarcasm, burnout, long messages"""
        messages = [ex["user_message"].lower() for ex in FEW_SHOT_EXAMPLES]
        all_messages = " ".join(messages)
        
        # Check for sarcasm indicators
        has_sarcasm = any("oh great" in msg or "definitely don't" in msg for msg in messages)
        
        # Check for burnout indicators
        has_burnout = any("exhausted" in msg or "12-hour" in msg for msg in messages)
        
        # Check for long messages
        has_long = any(len(msg) > 300 for msg in messages)
        
        assert has_sarcasm or "sarcasm" in all_messages
        assert has_burnout or "burnout" in all_messages
        assert has_long
    
    def test_examples_have_varied_stress_scores(self):
        """Examples should demonstrate range of stress scores"""
        stress_scores = [ex["assistant_response"]["stress_score"] for ex in FEW_SHOT_EXAMPLES]
        assert min(stress_scores) <= 2  # Low stress example
        assert max(stress_scores) >= 7  # High stress example
    
    def test_examples_show_urgency_variation(self):
        """Examples should show both urgent and non-urgent cases"""
        urgent_flags = [ex["assistant_response"]["urgency"] for ex in FEW_SHOT_EXAMPLES]
        assert True in urgent_flags
        assert False in urgent_flags


class TestPromptInjectionExample:
    """Test defensive prompt injection example."""
    
    def test_injection_example_exists(self):
        """Prompt injection example should exist"""
        assert PROMPT_INJECTION_EXAMPLE
        assert "user_message" in PROMPT_INJECTION_EXAMPLE
        assert "assistant_response" in PROMPT_INJECTION_EXAMPLE
    
    def test_injection_example_handles_meta_instructions(self):
        """Example should show how to handle meta-instructions"""
        message = PROMPT_INJECTION_EXAMPLE["user_message"].lower()
        assert "ignore" in message or "system prompt" in message or "previous instructions" in message
    
    def test_injection_response_is_neutral(self):
        """Response to injection attempt should be neutral"""
        response = PROMPT_INJECTION_EXAMPLE["assistant_response"]
        assert response["sentiment"] == "neutral"
        assert response["emotion"] == "neutral"


class TestPromptContext:
    """Test PromptContext dataclass."""
    
    def test_context_with_message_only(self):
        """Should create context with just message"""
        ctx = PromptContext(message="Test message")
        assert ctx.message == "Test message"
        assert ctx.sender_id is None
        assert ctx.conversation_history is None
        assert ctx.metadata is None
    
    def test_context_with_all_fields(self):
        """Should create context with all optional fields"""
        ctx = PromptContext(
            message="Test",
            sender_id="user123",
            conversation_history=[{"sender": "User", "content": "Previous"}],
            metadata={"channel": "general"}
        )
        assert ctx.message == "Test"
        assert ctx.sender_id == "user123"
        assert len(ctx.conversation_history) == 1
        assert ctx.metadata["channel"] == "general"


class TestPromptBuilder:
    """Test PromptBuilder functionality."""
    
    def test_build_basic_prompt(self):
        """Should build basic prompt with message only"""
        ctx = PromptContext(message="I'm feeling stressed about the deadline")
        messages = PromptBuilder.build_analysis_prompt(ctx)
        
        assert isinstance(messages, list)
        assert len(messages) >= 2  # At least system + user
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert "I'm feeling stressed" in messages[-1]["content"]
    
    def test_system_message_includes_schema(self):
        """System message should include schema when requested"""
        ctx = PromptContext(message="Test")
        messages = PromptBuilder.build_analysis_prompt(ctx, include_schema=True)
        
        system_msg = messages[0]["content"]
        assert "JSON SCHEMA" in system_msg or "schema" in system_msg.lower()
        assert "sentiment" in system_msg.lower()
    
    def test_system_message_without_schema(self):
        """Should be able to exclude schema"""
        ctx = PromptContext(message="Test")
        messages = PromptBuilder.build_analysis_prompt(ctx, include_schema=False)
        
        system_msg = messages[0]["content"]
        # Should have system prompt but not schema JSON
        assert len(system_msg) < 2000  # Shorter without schema
    
    def test_includes_few_shot_examples(self):
        """Should include few-shot examples when requested"""
        ctx = PromptContext(message="Test")
        messages = PromptBuilder.build_analysis_prompt(
            ctx,
            include_examples=True,
            max_examples=2
        )
        
        # Should have system + examples (user+assistant pairs) + final user
        assert len(messages) >= 5  # system + 2*(user+assistant) + user
        
        # Check for assistant examples
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) >= 1
    
    def test_excludes_examples_when_disabled(self):
        """Should exclude examples when disabled"""
        ctx = PromptContext(message="Test")
        messages = PromptBuilder.build_analysis_prompt(
            ctx,
            include_examples=False
        )
        
        # Should only have system + user
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
    
    def test_respects_max_examples_limit(self):
        """Should respect max_examples parameter"""
        ctx = PromptContext(message="Test")
        messages = PromptBuilder.build_analysis_prompt(
            ctx,
            include_examples=True,
            max_examples=1
        )
        
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
    
    def test_includes_metadata_context(self):
        """Should include metadata in user message"""
        ctx = PromptContext(
            message="Test",
            metadata={
                "channel": "team-updates",
                "sender_name": "John Doe"
            }
        )
        messages = PromptBuilder.build_analysis_prompt(ctx)
        
        user_msg = messages[-1]["content"]
        assert "team-updates" in user_msg or "Context" in user_msg
    
    def test_includes_conversation_history(self):
        """Should include conversation history"""
        ctx = PromptContext(
            message="What's the status?",
            conversation_history=[
                {"sender": "Alice", "content": "We're working on the feature"},
                {"sender": "Bob", "content": "Almost done"}
            ]
        )
        messages = PromptBuilder.build_analysis_prompt(ctx)
        
        user_msg = messages[-1]["content"]
        assert "conversation" in user_msg.lower() or "Alice" in user_msg


class TestTokenEstimation:
    """Test token estimation and budget management."""
    
    def test_estimate_tokens(self):
        """Should estimate tokens roughly"""
        text = "This is a test message with some content"
        tokens = PromptBuilder.estimate_tokens(text)
        
        assert tokens > 0
        assert tokens < len(text)  # Should be less than character count
    
    def test_token_budget_respected(self):
        """Should not exceed max_context_tokens"""
        ctx = PromptContext(message="Test")
        messages = PromptBuilder.build_analysis_prompt(
            ctx,
            include_schema=True,
            include_examples=True,
            max_examples=10,
            max_context_tokens=2000
        )
        
        # Should have limited examples due to token budget
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) < 10  # Should be limited by token budget


class TestJSONValidation:
    """Test JSON validation and extraction utilities."""
    
    def test_validate_pure_json(self):
        """Should validate pure JSON response"""
        response = '{"sentiment": "positive", "stress_score": 3}'
        is_valid, error = PromptBuilder.validate_response_structure(response)
        assert is_valid
        assert error is None
    
    def test_reject_markdown_wrapped_json(self):
        """Should reject JSON wrapped in markdown"""
        response = '```json\n{"sentiment": "positive"}\n```'
        is_valid, error = PromptBuilder.validate_response_structure(response)
        assert not is_valid
        assert "markdown" in error.lower()
    
    def test_reject_text_before_json(self):
        """Should reject text before JSON"""
        response = 'Here is the analysis: {"sentiment": "positive"}'
        is_valid, error = PromptBuilder.validate_response_structure(response)
        assert not is_valid
    
    def test_reject_text_after_json(self):
        """Should reject text after JSON"""
        response = '{"sentiment": "positive"} - This is the result'
        is_valid, error = PromptBuilder.validate_response_structure(response)
        assert not is_valid
    
    def test_reject_invalid_json(self):
        """Should reject malformed JSON"""
        response = '{"sentiment": "positive"'  # Missing closing brace
        is_valid, error = PromptBuilder.validate_response_structure(response)
        assert not is_valid
        assert "JSON" in error
    
    def test_extract_json_from_pure_response(self):
        """Should extract from pure JSON response"""
        response = '{"sentiment": "positive"}'
        extracted = PromptBuilder.extract_json_from_response(response)
        assert extracted == response
        assert json.loads(extracted)  # Should be valid JSON
    
    def test_extract_json_from_markdown(self):
        """Should extract JSON from markdown code block"""
        response = '```json\n{"sentiment": "positive"}\n```'
        extracted = PromptBuilder.extract_json_from_response(response)
        assert extracted is not None
        assert "```" not in extracted
        assert json.loads(extracted)
    
    def test_extract_json_from_text(self):
        """Should extract JSON from text with surrounding content"""
        response = 'Here is the analysis:\n{"sentiment": "positive"}\nHope this helps!'
        extracted = PromptBuilder.extract_json_from_response(response)
        assert extracted is not None
        assert extracted == '{"sentiment": "positive"}'
    
    def test_extract_returns_none_for_no_json(self):
        """Should return None when no JSON found"""
        response = 'This is just plain text without JSON'
        extracted = PromptBuilder.extract_json_from_response(response)
        assert extracted is None


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_build_prompt_function(self):
        """build_prompt should work as shortcut"""
        messages = build_prompt("Test message")
        assert isinstance(messages, list)
        assert len(messages) >= 2
    
    def test_build_prompt_with_kwargs(self):
        """build_prompt should accept kwargs"""
        messages = build_prompt(
            "Test",
            include_schema=False,
            include_examples=False
        )
        assert len(messages) == 2  # Just system + user
    
    def test_get_system_prompt_with_schema(self):
        """get_system_prompt should include schema when requested"""
        prompt = get_system_prompt(include_schema=True)
        assert "JSON SCHEMA" in prompt or "schema" in prompt.lower()
        assert len(prompt) > len(SYSTEM_PROMPT)
    
    def test_get_system_prompt_without_schema(self):
        """get_system_prompt should exclude schema when requested"""
        prompt = get_system_prompt(include_schema=False)
        assert prompt == SYSTEM_PROMPT
    
    def test_get_few_shot_examples(self):
        """get_few_shot_examples should return examples"""
        examples = get_few_shot_examples(max_count=3)
        assert len(examples) == 3
        assert all("user_message" in ex for ex in examples)
    
    def test_get_few_shot_examples_respects_max(self):
        """get_few_shot_examples should respect max_count"""
        examples = get_few_shot_examples(max_count=100)
        assert len(examples) <= len(FEW_SHOT_EXAMPLES)


class TestSchemaRetrieval:
    """Test schema retrieval functionality."""
    
    def test_get_schema_json(self):
        """Should retrieve clean schema"""
        schema = PromptBuilder.get_schema_json()
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "sentiment" in schema["properties"]
    
    def test_schema_has_required_fields(self):
        """Schema should include all required fields"""
        schema = PromptBuilder.get_schema_json()
        props = schema["properties"]
        
        required_fields = [
            "sentiment",
            "emotion",
            "stress_score",
            "confidence_scores",
            "category"
        ]
        
        for field in required_fields:
            assert field in props
    
    def test_format_json_instruction(self):
        """Should provide JSON formatting instruction"""
        instruction = PromptBuilder.format_json_instruction()
        assert "JSON" in instruction
        assert "markdown" in instruction.lower() or "code block" in instruction.lower()


class TestExampleSelection:
    """Test intelligent example selection."""
    
    def test_select_examples_prioritizes_edge_cases(self):
        """Should prioritize edge cases (sarcasm, burnout)"""
        selected = PromptBuilder._select_examples(max_count=3, token_budget=1000)
        
        # First selected should include edge cases
        messages = [ex["user_message"].lower() for ex in selected]
        all_text = " ".join(messages)
        
        # Should include challenging examples
        has_edge_case = any([
            "oh great" in all_text,
            "exhausted" in all_text,
            "12-hour" in all_text
        ])
        assert has_edge_case
    
    def test_select_examples_respects_token_budget(self):
        """Should respect token budget"""
        # Very small budget should return fewer examples
        selected_small = PromptBuilder._select_examples(max_count=10, token_budget=100)
        assert len(selected_small) < 3
        
        # Larger budget should allow more examples
        selected_large = PromptBuilder._select_examples(max_count=10, token_budget=5000)
        assert len(selected_large) > len(selected_small)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_message(self):
        """Should handle empty message"""
        ctx = PromptContext(message="")
        messages = PromptBuilder.build_analysis_prompt(ctx)
        assert len(messages) >= 2
    
    def test_very_long_message(self):
        """Should handle very long message"""
        long_msg = "Test " * 1000
        ctx = PromptContext(message=long_msg)
        messages = PromptBuilder.build_analysis_prompt(ctx)
        assert messages[-1]["content"]  # Should include message
    
    def test_none_metadata(self):
        """Should handle None metadata gracefully"""
        ctx = PromptContext(message="Test", metadata=None)
        messages = PromptBuilder.build_analysis_prompt(ctx)
        assert len(messages) >= 2
    
    def test_empty_conversation_history(self):
        """Should handle empty history"""
        ctx = PromptContext(message="Test", conversation_history=[])
        messages = PromptBuilder.build_analysis_prompt(ctx)
        assert len(messages) >= 2
