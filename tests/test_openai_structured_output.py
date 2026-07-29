from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Type

import pytest
from openai import APIConnectionError
from pydantic import BaseModel

from app.llms import (
    OpenAIResponsesStructuredOutputClient,
    StructuredOutputCallError,
    StructuredOutputResponseError,
)


class Output(BaseModel):
    value: str


@dataclass
class FakeResponse:
    status: str
    output_parsed: Optional[Output]
    output: tuple[object, ...] = ()


class FakeResponses:
    def __init__(self, response: FakeResponse, error: Optional[Exception] = None) -> None:
        self._response: FakeResponse = response
        self._error: Optional[Exception] = error
        self.request: Optional[dict[str, Any]] = None

    async def parse(self, **kwargs: Any) -> FakeResponse:
        self.request = kwargs
        if self._error is not None:
            raise self._error
        return self._response


class FakeAsyncOpenAI:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses: FakeResponses = responses


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_structured_client_returns_only_completed_parsed_result() -> None:
    responses = FakeResponses(FakeResponse(status="completed", output_parsed=Output(value="ok")))
    client = OpenAIResponsesStructuredOutputClient(FakeAsyncOpenAI(responses))  # type: ignore[arg-type]

    result = await client.parse(
        model="test-model",
        system_prompt="system",
        user_prompt="user",
        response_model=Output,
    )

    assert result == Output(value="ok")
    assert responses.request == {
        "model": "test-model",
        "instructions": "system",
        "input": "user",
        "text_format": Output,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "expected_reason"),
    (
        ("failed", "response_failed"),
        ("incomplete", "response_incomplete"),
        ("unknown", "unknown_response_status:unknown"),
    ),
)
async def test_structured_client_preserves_response_status_reason(
    status: str,
    expected_reason: str,
) -> None:
    responses = FakeResponses(FakeResponse(status=status, output_parsed=None))
    client = OpenAIResponsesStructuredOutputClient(FakeAsyncOpenAI(responses))  # type: ignore[arg-type]

    with pytest.raises(StructuredOutputResponseError, match=expected_reason):
        await client.parse(
            model="test-model",
            system_prompt="system",
            user_prompt="user",
            response_model=Output,
        )


@pytest.mark.anyio
async def test_structured_client_rejects_completed_response_without_parsed_output() -> None:
    responses = FakeResponses(FakeResponse(status="completed", output_parsed=None))
    client = OpenAIResponsesStructuredOutputClient(FakeAsyncOpenAI(responses))  # type: ignore[arg-type]

    with pytest.raises(StructuredOutputResponseError, match="missing_parsed_output"):
        await client.parse(
            model="test-model",
            system_prompt="system",
            user_prompt="user",
            response_model=Output,
        )


@pytest.mark.anyio
async def test_structured_client_converts_sdk_error_to_safe_call_error() -> None:
    responses = FakeResponses(
        FakeResponse(status="completed", output_parsed=Output(value="unused")),
        error=APIConnectionError(request=None),
    )
    client = OpenAIResponsesStructuredOutputClient(FakeAsyncOpenAI(responses))  # type: ignore[arg-type]

    with pytest.raises(StructuredOutputCallError, match="APIConnectionError"):
        await client.parse(
            model="test-model",
            system_prompt="system",
            user_prompt="user",
            response_model=Output,
        )


@pytest.mark.anyio
async def test_structured_client_labels_refusal_separately() -> None:
    refusal_content = type("Refusal", (), {"type": "refusal"})()
    refusal_output = type("OutputItem", (), {"content": (refusal_content,)})()
    responses = FakeResponses(
        FakeResponse(status="completed", output_parsed=None, output=(refusal_output,))
    )
    client = OpenAIResponsesStructuredOutputClient(FakeAsyncOpenAI(responses))  # type: ignore[arg-type]

    with pytest.raises(StructuredOutputResponseError, match="refusal"):
        await client.parse(
            model="test-model",
            system_prompt="system",
            user_prompt="user",
            response_model=Output,
        )
