"""Append-only event log: single writer per session (in-memory default)."""

from typing import Any

from .model import Event


class EventLog:
    """
    Append-only log keyed by ``session_id``.

    Swap for Postgres/SQLite/event store in production; keep the same interface.
    """

    def __init__(self) -> None:
        self._entries: dict[str, list[Event]] = {}

    def append(self, session_id: str, event: Event) -> None:
        if session_id not in self._entries:
            self._entries[session_id] = []
        self._entries[session_id].append(event)

    def read(self, session_id: str) -> list[Event]:
        return list(self._entries.get(session_id, []))

    def read_as_dicts(self, session_id: str) -> list[dict[str, Any]]:
        return [e.to_log_line() for e in self.read(session_id)]
