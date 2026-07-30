from __future__ import annotations

from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.news_event import EventFact, EventType


class EventTypeCompatibilityEntry(BaseModel):
    """One event-category compatibility row for concrete event facts."""

    model_config = ConfigDict(frozen=True)

    event_type: EventType
    event_facts: Tuple[EventFact, ...] = Field(min_length=1)


class EventTypeCompatibility(BaseModel):
    """Immutable policy table relating event categories to supported facts."""

    model_config = ConfigDict(frozen=True)

    entries: Tuple[EventTypeCompatibilityEntry, ...]

    @model_validator(mode="after")
    def validate_unique_entries(self) -> "EventTypeCompatibility":
        event_types: Tuple[EventType, ...] = tuple(
            entry.event_type for entry in self.entries
        )
        if len(set(event_types)) != len(event_types):
            raise ValueError("Compatibility entries must have unique event types.")
        event_facts: Tuple[EventFact, ...] = tuple(
            event_fact
            for entry in self.entries
            for event_fact in entry.event_facts
        )
        if len(set(event_facts)) != len(event_facts):
            raise ValueError(
                "Compatibility entries must assign each event fact only once."
            )
        return self

    def is_compatible(self, event_type: EventType, event_fact: EventFact) -> bool:
        """Return whether the supplied fact is allowed for the event category."""
        return any(
            entry.event_type is event_type and event_fact in entry.event_facts
            for entry in self.entries
        )


DEFAULT_EVENT_TYPE_COMPATIBILITY = EventTypeCompatibility(
    entries=(
        EventTypeCompatibilityEntry(
            event_type=EventType.CORPORATE_EVENT,
            event_facts=(
                EventFact.FACTORY_EXPANSION,
                EventFact.MASS_LAYOFF,
                EventFact.CEO_INTERVIEW,
            ),
        ),
        EventTypeCompatibilityEntry(
            event_type=EventType.FINANCIAL_EVENT,
            event_facts=(EventFact.BANKRUPTCY,),
        ),
        EventTypeCompatibilityEntry(
            event_type=EventType.PRODUCT_EVENT,
            event_facts=(EventFact.PRODUCT_RELEASE,),
        ),
    )
)
