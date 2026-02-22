"""Persistent session storage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PersistedSession:
    api_base_url: str
    session_token: str
    user_login: str


class SessionStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> PersistedSession | None:
        if not self.file_path.exists():
            return None
        try:
            payload = json.loads(self.file_path.read_text(encoding="utf-8"))
            return PersistedSession(
                api_base_url=str(payload["api_base_url"]),
                session_token=str(payload["session_token"]),
                user_login=str(payload.get("user_login", "")),
            )
        except (json.JSONDecodeError, KeyError, OSError, TypeError):
            self.clear()
            return None

    def save(self, *, api_base_url: str, session_token: str, user_login: str) -> None:
        payload = {
            "api_base_url": api_base_url,
            "session_token": session_token,
            "user_login": user_login,
        }
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> None:
        if self.file_path.exists():
            self.file_path.unlink(missing_ok=True)
