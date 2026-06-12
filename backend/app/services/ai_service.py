"""Single gateway for all Claude API calls.

Every AI response that feeds downstream code goes through
``AIService.call_with_structured_output`` — a forced tool_use call whose
input is validated into a Pydantic model. Free-form text is never parsed.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.config import settings

T = TypeVar("T", bound=BaseModel)

# USD per million tokens: (input, output). Cache reads bill at 0.1x input,
# cache writes at 1.25x input (5-minute TTL).
MODEL_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    "claude-fable-5": (Decimal("10.00"), Decimal("50.00")),
    "claude-opus-4-8": (Decimal("5.00"), Decimal("25.00")),
    "claude-sonnet-4-6": (Decimal("3.00"), Decimal("15.00")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
}
CACHE_READ_FACTOR = Decimal("0.1")
CACHE_WRITE_FACTOR = Decimal("1.25")
MTOK = Decimal(1_000_000)


class AIError(Exception):
    """Base class for AI service failures."""


class AIRefusalError(AIError):
    """The model declined the request (stop_reason == 'refusal')."""

    def __init__(self, category: str | None = None):
        self.category = category
        super().__init__(f"Model refused the request (category={category})")


class AIStructuredOutputError(AIError):
    """The model's tool input failed schema validation or the tool was not called."""


@dataclass(frozen=True)
class AIUsage:
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: Decimal


def compute_cost(usage: AIUsage) -> Decimal:
    input_price, output_price = MODEL_PRICING.get(
        usage.model, MODEL_PRICING["claude-fable-5"]
    )
    cost = (
        Decimal(usage.input_tokens) * input_price
        + Decimal(usage.cache_read_tokens) * input_price * CACHE_READ_FACTOR
        + Decimal(usage.cache_write_tokens) * input_price * CACHE_WRITE_FACTOR
        + Decimal(usage.output_tokens) * output_price
    ) / MTOK
    return cost.quantize(Decimal("0.000001"))


class AIService:
    def __init__(self, client: anthropic.Anthropic | None = None):
        self._client = client

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    def call_with_structured_output(
        self,
        *,
        model: str,
        system: str,
        user_message: str,
        tool_schema: dict[str, Any],
        tool_name: str,
        output_model: type[T],
        thinking: bool = False,
        max_tokens: int = 8192,
    ) -> tuple[T, AIUsage]:
        """Force a tool call and validate its input into ``output_model``.

        The system prompt gets a cache_control breakpoint — it is static per
        feature, so repeat calls bill cached tokens at ~10% of input price.
        """
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "messages": [{"role": "user", "content": user_message}],
            "tools": [tool_schema],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        # Fable 5: thinking is always on; adaptive is the only accepted value.
        # Haiku/fast models: omit the param entirely.
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}

        response = self.client.messages.create(**kwargs)

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise AIRefusalError(getattr(details, "category", None))

        usage = AIUsage(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(response.usage, "cache_creation_input_tokens", 0)
            or 0,
            cost_usd=Decimal(0),
        )
        usage = AIUsage(**{**usage.__dict__, "cost_usd": compute_cost(usage)})

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                try:
                    return output_model.model_validate(block.input), usage
                except ValidationError as exc:
                    raise AIStructuredOutputError(
                        f"{tool_name} output failed validation: {exc}"
                    ) from exc

        raise AIStructuredOutputError(
            f"Model did not call {tool_name} despite forced tool_choice"
        )
