"""Append-only event log. Single writer per session."""

from typing import Any

from .model import Event


class EventLog:
    """Append-only log keyed by session_id. In-memory for the example."""

    def __init__(self) -> None:
        self._entries: dict[str, list[Event]] = {}

    def append(self, session_id: str, event: Event) -> None:
        if session_id not in self._entries:
            self._entries[session_id] = []
        self._entries[session_id].append(event)

    def read(self, session_id: str) -> list[Event]:
        return self._entries.get(session_id, [])

    def read_as_dicts(self, session_id: str) -> list[dict[str, Any]]:
        return [e.to_log_line() for e in self.read(session_id)]
