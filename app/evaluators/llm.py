from __future__ import annotations

from typing import List, Sequence

from app.evaluators.requester import PostEvaluationRequester
from app.llms.base import LLMClient
from app.llms.models import ChatMessage, ChatResponse
from app.models.post import Post
from app.prompts.base import PromptBuilder
from app.prompts.evaluator import EvaluatorPromptInput


class LLMPostEvaluationRequester(PostEvaluationRequester):
    """Orchestrates a post evaluation request through prompt and LLM contracts."""

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_builder: PromptBuilder[EvaluatorPromptInput],
    ) -> None:
        self._llm_client: LLMClient = llm_client
        self._prompt_builder: PromptBuilder[EvaluatorPromptInput] = prompt_builder

    async def request(self, posts: Sequence[Post]) -> ChatResponse:
        prompt_input: EvaluatorPromptInput = EvaluatorPromptInput(posts=posts)
        messages: List[ChatMessage] = self._prompt_builder.build(prompt_input)
        return await self._llm_client.chat(messages=messages, config=None)
