from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

from app.models.post import Post

_SYSTEM_PROMPT: str = """You are a content evaluator.
Evaluate every input post and return only valid JSON matching this schema:
{"posts":[{"post_id":"input post id","score":0,"is_candidate":false,"reasons":["reason"]}]}
Return exactly one item for every input post in the same order.
Use each input post id unchanged as post_id.
Return only the fields in the schema. Do not add properties, markdown fences, or explanatory text.
"""
_USER_PROMPT: str = "Evaluate the following posts:\n{posts_json}"


def build_evaluator_system_prompt() -> str:
    """Return the evaluator system prompt."""
    return _SYSTEM_PROMPT


def build_evaluator_user_prompt(posts: Sequence[Post]) -> str:
    """Render posts as the evaluator user prompt."""
    posts_json: str = _serialize_posts_for_prompt(posts)
    return _USER_PROMPT.format(posts_json=posts_json)


def _serialize_posts_for_prompt(posts: Sequence[Post]) -> str:
    """Serialize posts for the evaluator prompt representation."""
    post_data: List[Dict[str, Any]] = [post.model_dump(mode="json") for post in posts]
    return json.dumps(post_data, ensure_ascii=False)
