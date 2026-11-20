"""
graph/state.py — shared state that every node reads from and writes to.

TripState is a TypedDict so LangGraph can pass it between nodes as a plain
dict while still giving us type-checker support.
"""
from typing import TypedDict


class TripState(TypedDict):
    """Shared state threaded through every graph node."""

    # Raw form data submitted by the user (arbitrary key/value pairs).
    user_input: dict

    # Validated and structured trip request; None until the intake node succeeds.
    request: dict | None

    # Passages retrieved from the vector store (populated by the retrieve node).
    passages: list

    # Live weather and distance data (populated by the fetch node).
    live_data: dict

    # Draft itinerary produced by the draft node; None until first draft.
    draft: dict | None

    # Reasons why the current draft failed checks; cleared on each revision.
    feedback: list[str]

    # Number of revision cycles completed (capped at 3 by the graph).
    revisions: int

    # Results from budget, logistics, and source checks for the current draft.
    checks: list[dict]

    # Problems that remain after the revision limit is reached.
    unresolved: list[str]
