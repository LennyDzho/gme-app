"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import QStandardPaths

DEFAULT_API_BASE_URL = "http://localhost:8001/api/v1"
DEFAULT_VIDEO_SERVICE_BASE_URL = "http://localhost:8000"
DEFAULT_AUDIO_SERVICE_BASE_URL = "http://localhost:8002"


@dataclass(slots=True, frozen=True)
class AppConfig:
    api_base_url: str
    video_service_base_url: str
    audio_service_base_url: str
    audio_service_api_key: str | None
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


def _normalize_service_base_url(raw: str, *, default: str) -> str:
    value = (raw or "").strip().rstrip("/")
    if not value:
        value = default.rstrip("/")

    if not urlparse(value).scheme:
        value = f"http://{value}"
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
    video_service_base_url = _normalize_service_base_url(
        os.getenv("GME_VIDEO_SERVICE_URL", DEFAULT_VIDEO_SERVICE_BASE_URL),
        default=DEFAULT_VIDEO_SERVICE_BASE_URL,
    )
    audio_service_base_url = _normalize_service_base_url(
        os.getenv("GME_AUDIO_SERVICE_URL", DEFAULT_AUDIO_SERVICE_BASE_URL),
        default=DEFAULT_AUDIO_SERVICE_BASE_URL,
    )
    audio_service_api_key = (
        (os.getenv("GME_AUDIO_SERVICE_API_KEY", "") or "").strip()
        or (os.getenv("AUDIO_SERVICE_API_KEY", "") or "").strip()
        or (os.getenv("API_KEY", "") or "").strip()
        or None
    )
    timeout_seconds = float(os.getenv("GME_REQUEST_TIMEOUT", "15"))
    session_cookie_name = os.getenv("GME_SESSION_COOKIE_NAME", "session_token")
    app_data_dir = _resolve_app_data_dir()
    return AppConfig(
        api_base_url=api_base_url,
        video_service_base_url=video_service_base_url,
        audio_service_base_url=audio_service_base_url,
        audio_service_api_key=audio_service_api_key,
        timeout_seconds=timeout_seconds,
        session_cookie_name=session_cookie_name,
        app_data_dir=app_data_dir,
    )
