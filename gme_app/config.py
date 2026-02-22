"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import QStandardPaths

DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1"


@dataclass(slots=True, frozen=True)
class AppConfig:
    api_base_url: str
    timeout_seconds: float
    session_cookie_name: str
    app_data_dir: Path


def _normalize_api_base_url(raw: str) -> str:
    value = (raw or "").strip().rstrip("/")
    if not value:
        return DEFAULT_API_BASE_URL

    parsed = urlparse(value)
    if not parsed.scheme:
        value = f"http://{value}"
        parsed = urlparse(value)

    if parsed.path in ("", "/"):
        return f"{value.rstrip('/')}/api/v1"
    if parsed.path.rstrip("/") == "/api/v1":
        return value.rstrip("/")
    return value.rstrip("/")


def _resolve_app_data_dir() -> Path:
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    if location:
        path = Path(location)
    else:
        path = Path.cwd() / ".gme-app-data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_config() -> AppConfig:
    api_base_url = _normalize_api_base_url(os.getenv("GME_MANAGEMENT_URL", DEFAULT_API_BASE_URL))
    timeout_seconds = float(os.getenv("GME_REQUEST_TIMEOUT", "15"))
    session_cookie_name = os.getenv("GME_SESSION_COOKIE_NAME", "session_token")
    app_data_dir = _resolve_app_data_dir()
    return AppConfig(
        api_base_url=api_base_url,
        timeout_seconds=timeout_seconds,
        session_cookie_name=session_cookie_name,
        app_data_dir=app_data_dir,
    )
