"""Tests for LLM provider abstraction."""
from app.agent.provider import (
    AnthropicProvider,
    ContentBlock,
    LLMProvider,
    ModelResponse,
    ProviderError,
)


def test_content_block_text() -> None:
    block = ContentBlock(type="text", text="Hello world")
    assert block.type == "text"
    assert block.text == "Hello world"


def test_content_block_tool_use() -> None:
    block = ContentBlock(
        type="tool_use",
        id="tool_123",
        name="lookup_duty_cycle",
        input={"process": "mig", "voltage": "240v"},
    )
    assert block.type == "tool_use"
    assert block.name == "lookup_duty_cycle"
    assert block.input["process"] == "mig"


def test_model_response_structure() -> None:
    response = ModelResponse(
        content=[ContentBlock(type="text", text="The duty cycle is 25%")],
        stop_reason="end_turn",
        input_tokens=100,
        output_tokens=50,
    )
    assert response.stop_reason == "end_turn"
    assert len(response.content) == 1
    assert response.input_tokens == 100


def test_provider_error_is_exception() -> None:
    err = ProviderError("API rate limit exceeded")
    assert isinstance(err, Exception)
    assert "rate limit" in str(err)


def test_anthropic_provider_is_llm_provider() -> None:
    """AnthropicProvider must satisfy the LLMProvider interface."""
    assert issubclass(AnthropicProvider, LLMProvider)
