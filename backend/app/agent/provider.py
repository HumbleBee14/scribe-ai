"""LLM provider abstraction — clean boundary between agent logic and SDK.

The orchestrator depends on this interface, not on the Anthropic SDK directly.
This enables:
- Test isolation (mock provider returns canned responses)
- Future provider swaps without touching orchestration logic
- Clear SDK boundary as required by the challenge
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContentBlock:
    """A single block in a model response (text or tool_use)."""

    type: str  # "text" or "tool_use"
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    """Normalized response from any LLM provider."""

    content: list[ContentBlock]
    stop_reason: str  # "end_turn", "tool_use", "max_tokens"
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(ABC):
    """Abstract LLM provider interface.

    The orchestrator depends on this, not on any vendor SDK.
    """

    @abstractmethod
    async def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> ModelResponse:
        """Send a message and return the complete response."""
        ...


class AnthropicProvider(LLMProvider):
    """Claude provider using the official Anthropic Python SDK."""

    def __init__(self, api_key: str) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> ModelResponse:
        """Call Claude via the Anthropic SDK and normalize the response."""
        import anthropic

        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=messages,
            )
        except anthropic.APIError as e:
            raise ProviderError(str(e)) from e

        blocks: list[ContentBlock] = []
        for block in response.content:
            if block.type == "text":
                blocks.append(ContentBlock(type="text", text=block.text))
            elif block.type == "tool_use":
                blocks.append(ContentBlock(
                    type="tool_use",
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))

        return ModelResponse(
            content=blocks,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


class ProviderError(Exception):
    """Raised when the LLM provider returns an error."""
