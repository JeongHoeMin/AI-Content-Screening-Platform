from __future__ import annotations

from typing import List

from app.extractors.base import NewsEventExtractor
from app.extractors.parser import NewsEventParser
from app.extractors.requester import NewsEventRequester
from app.llms.models import ChatMessage, ChatResponse
from app.models.article import ArticleEvaluationResult
from app.models.news_event import NewsEvent
from app.prompts.base import PromptBuilder
from app.prompts.news_event import NewsEventPromptInput


class LLMNewsEventExtractor(NewsEventExtractor):
    """Orchestrates prompt building, LLM requesting, and response parsing."""

    def __init__(
        self,
        requester: NewsEventRequester,
        parser: NewsEventParser,
        prompt_builder: PromptBuilder[NewsEventPromptInput],
    ) -> None:
        self._requester: NewsEventRequester = requester
        self._parser: NewsEventParser = parser
        self._prompt_builder: PromptBuilder[NewsEventPromptInput] = prompt_builder

    async def extract(
        self,
        evaluation: ArticleEvaluationResult,
    ) -> List[NewsEvent]:
        prompt_input: NewsEventPromptInput = NewsEventPromptInput(
            evaluation=evaluation
        )
        messages: List[ChatMessage] = self._prompt_builder.build(prompt_input)
        response: ChatResponse = await self._requester.request(messages)
        return self._parser.parse(response, evaluation)
