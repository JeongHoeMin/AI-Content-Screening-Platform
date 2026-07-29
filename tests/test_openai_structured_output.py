from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Type

import pytest
from pydantic import BaseModel

from app.llms import (
    OpenAIResponsesStructuredOutputClient,
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
@pytest.mark.parametrize("status", ("failed", "incomplete", "completed"))
async def test_structured_client_rejects_non_parsed_or_incomplete_responses(status: str) -> None:
    responses = FakeResponses(FakeResponse(status=status, output_parsed=None))
    client = OpenAIResponsesStructuredOutputClient(FakeAsyncOpenAI(responses))  # type: ignore[arg-type]

    with pytest.raises(StructuredOutputResponseError):
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
