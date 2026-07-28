from __future__ import annotations

from typing import Protocol, TypeVar

RequestT = TypeVar("RequestT")
ResultT = TypeVar("ResultT")


class Workflow(Protocol[RequestT, ResultT]):
    """Common interface for workflows."""

    async def run(self, request: RequestT) -> ResultT:
        """Run a workflow."""
