from __future__ import annotations

import json
from typing import Any, Dict, List

from app.models.post import Post

EVALUATOR_SYSTEM_PROMPT: str = "You are a content evaluator."
EVALUATOR_USER_PROMPT: str = "Evaluate the following posts:\n{posts_json}"


def build_evaluator_system_prompt() -> str:
    """Return the evaluator system prompt."""
    return EVALUATOR_SYSTEM_PROMPT


def build_evaluator_user_prompt(posts: List[Post]) -> str:
    """Render posts as the evaluator user prompt."""
    post_data: List[Dict[str, Any]] = [post.model_dump(mode="json") for post in posts]
    posts_json: str = json.dumps(post_data, ensure_ascii=False)
    return EVALUATOR_USER_PROMPT.format(posts_json=posts_json)
