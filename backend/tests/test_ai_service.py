from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from app.services.ai_service import (
    AIRefusalError,
    AIService,
    AIStructuredOutputError,
    AIUsage,
    compute_cost,
)


class Answer(BaseModel):
    label: str
    confidence: int


def _response(blocks, stop_reason="tool_use", usage=None):
    return SimpleNamespace(
        content=blocks,
        stop_reason=stop_reason,
        stop_details=None,
        usage=usage
        or SimpleNamespace(
            input_tokens=1000,
            output_tokens=500,
            cache_read_input_tokens=2000,
            cache_creation_input_tokens=0,
        ),
    )


def _tool_block(name="record_answer", payload=None):
    return SimpleNamespace(
        type="tool_use", name=name, input=payload or {"label": "ok", "confidence": 90}
    )


def _service(response):
    client = MagicMock()
    client.messages.create.return_value = response
    return AIService(client=client), client


TOOL_SCHEMA = {"name": "record_answer", "input_schema": {"type": "object"}}


def _call(service, **overrides):
    kwargs = dict(
        model="claude-fable-5",
        system="You are a classifier.",
        user_message="Classify this.",
        tool_schema=TOOL_SCHEMA,
        tool_name="record_answer",
        output_model=Answer,
    )
    kwargs.update(overrides)
    return service.call_with_structured_output(**kwargs)


def test_returns_validated_model_and_usage():
    service, _ = _service(_response([_tool_block()]))

    result, usage = _call(service)

    assert isinstance(result, Answer)
    assert result.label == "ok"
    # (1000*10 + 2000*10*0.1 + 500*50) / 1M
    assert usage.cost_usd == Decimal("0.037000")
    assert usage.cache_read_tokens == 2000


def test_thinking_uses_auto_tool_choice_and_caches_system():
    # Forcing a specific tool is rejected while thinking is on, so the thinking
    # path must use tool_choice "auto".
    service, client = _service(_response([_tool_block()]))

    _call(service, thinking=True)

    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "auto"}
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kwargs["thinking"] == {"type": "adaptive"}


def test_omits_thinking_param_and_forces_tool_by_default():
    service, client = _service(_response([_tool_block()]))

    _call(service)

    kwargs = client.messages.create.call_args.kwargs
    assert "thinking" not in kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "record_answer"}


def test_raises_on_refusal():
    service, _ = _service(_response([], stop_reason="refusal"))

    with pytest.raises(AIRefusalError):
        _call(service)


def test_raises_when_truncated_by_max_tokens():
    # A complete-looking tool block but stop_reason=max_tokens means the SDK
    # may have salvaged a partial input — surface truncation, not validation.
    service, _ = _service(_response([_tool_block()], stop_reason="max_tokens"))

    with pytest.raises(AIStructuredOutputError, match="truncated"):
        _call(service)


def test_raises_when_tool_not_called():
    text_block = SimpleNamespace(type="text", text="I cannot use tools.")
    service, _ = _service(_response([text_block], stop_reason="end_turn"))

    with pytest.raises(AIStructuredOutputError, match="did not call"):
        _call(service)


def test_thinking_falls_back_to_forced_tool():
    # With thinking on the model may answer in prose without calling the tool.
    # The gateway retries once with the tool forced (thinking off) and combines
    # the usage of both billed calls.
    no_tool = _response(
        [SimpleNamespace(type="text", text="here is my analysis")],
        stop_reason="end_turn",
    )
    forced = _response([_tool_block()])
    client = MagicMock()
    client.messages.create.side_effect = [no_tool, forced]
    service = AIService(client=client)

    result, usage = _call(service, thinking=True)

    assert isinstance(result, Answer)
    assert client.messages.create.call_count == 2
    retry_kwargs = client.messages.create.call_args_list[1].kwargs
    assert retry_kwargs["tool_choice"] == {"type": "tool", "name": "record_answer"}
    assert "thinking" not in retry_kwargs
    # Usage is the sum of both calls (each billed input=1000, output=500).
    assert usage.input_tokens == 2000
    assert usage.output_tokens == 1000


def test_thinking_fallback_still_raises_if_tool_never_called():
    text = SimpleNamespace(type="text", text="prose")
    no_tool = _response([text], stop_reason="end_turn")
    client = MagicMock()
    client.messages.create.side_effect = [no_tool, no_tool]
    service = AIService(client=client)

    with pytest.raises(AIStructuredOutputError, match="did not call"):
        _call(service, thinking=True)
    assert client.messages.create.call_count == 2


def test_raises_on_invalid_tool_payload():
    bad = _tool_block(payload={"label": "ok", "confidence": "not-a-number-at-all"})
    service, _ = _service(_response([bad]))

    with pytest.raises(AIStructuredOutputError, match="failed validation"):
        _call(service)


def test_compute_cost_unknown_model_falls_back_to_primary_pricing():
    usage = AIUsage(
        model="claude-unknown",
        input_tokens=1_000_000,
        output_tokens=0,
        cache_read_tokens=0,
        cache_write_tokens=0,
        cost_usd=Decimal(0),
    )
    assert compute_cost(usage) == Decimal("5.000000")
