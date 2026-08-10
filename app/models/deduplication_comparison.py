from __future__ import annotations

from typing import List, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr

# Bounded Union[Strict*, None] instead of a bare `object`: OpenAI's Structured
# Outputs strict mode rejects untyped schema properties outright (BadRequestError:
# "schema must have a 'type' key"), but every branch here still needs an explicit
# isinstance check in LLMEventComparator._parse, which owns all range/enum/shape
# validity — matching the same pattern already used in app/models/screening.py
# and app/models/cross_validation.py.
IndexValue = Union[StrictInt, StrictStr, StrictBool, None]
RelationValue = Union[StrictStr, StrictInt, StrictBool, None]
ScoreValue = Union[StrictInt, StrictFloat, StrictStr, StrictBool, None]
TextListValue = Union[StrictStr, StrictInt, StrictFloat, StrictBool, None]


class DeduplicationComparisonResponseItem(BaseModel):
    """Untrusted structured LLM observation for one deterministic candidate pair."""

    model_config = ConfigDict(extra="forbid")

    candidate_index: IndexValue = None
    relation: RelationValue = None
    confidence: ScoreValue = None
    reasons: List[TextListValue] = Field(default_factory=list)


class DeduplicationComparisonResponse(BaseModel):
    """Provider-validated envelope parsed again against requested candidates."""

    model_config = ConfigDict(extra="forbid")

    comparisons: List[DeduplicationComparisonResponseItem]
