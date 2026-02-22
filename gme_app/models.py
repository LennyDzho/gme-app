"""Typed models for API payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(parsed)
    except ValueError:
        return None


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone().strftime("%d.%m.%Y %H:%M")


@dataclass(slots=True)
class UserSummary:
    id: UUID
    login: str
    role: str
    must_change_password: bool

    @classmethod
    def from_api(cls, payload: dict) -> "UserSummary":
        return cls(
            id=UUID(str(payload["id"])),
            login=str(payload["login"]),
            role=str(payload["role"]),
            must_change_password=bool(payload.get("must_change_password", False)),
        )


@dataclass(slots=True)
class UserProfile:
    id: UUID
    login: str
    email: str | None
    role: str
    is_active: bool
    display_name: str | None
    created_at: datetime | None

    @classmethod
    def from_api(cls, payload: dict) -> "UserProfile":
        return cls(
            id=UUID(str(payload["id"])),
            login=str(payload["login"]),
            email=payload.get("email"),
            role=str(payload["role"]),
            is_active=bool(payload.get("is_active", True)),
            display_name=payload.get("display_name"),
            created_at=parse_datetime(payload.get("created_at")),
        )

    @property
    def ui_name(self) -> str:
        return (self.display_name or self.login or "Пользователь").strip()


@dataclass(slots=True)
class Project:
    id: UUID
    creator_id: UUID
    title: str
    description: str | None
    status: str
    video_path: str
    created_at: datetime | None
    updated_at: datetime | None
    deleted_at: datetime | None

    @classmethod
    def from_api(cls, payload: dict) -> "Project":
        return cls(
            id=UUID(str(payload["id"])),
            creator_id=UUID(str(payload["creator_id"])),
            title=str(payload["title"]),
            description=payload.get("description"),
            status=str(payload["status"]),
            video_path=str(payload["video_path"]),
            created_at=parse_datetime(payload.get("created_at")),
            updated_at=parse_datetime(payload.get("updated_at")),
            deleted_at=parse_datetime(payload.get("deleted_at")),
        )


@dataclass(slots=True)
class ProcessingRun:
    id: UUID
    project_id: UUID
    video_task_id: str
    provider: str
    status: str
    launch_mode: str
    created_at: datetime | None
    updated_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_api(cls, payload: dict) -> "ProcessingRun":
        return cls(
            id=UUID(str(payload["id"])),
            project_id=UUID(str(payload["project_id"])),
            video_task_id=str(payload["video_task_id"]),
            provider=str(payload["provider"]),
            status=str(payload["status"]),
            launch_mode=str(payload["launch_mode"]),
            created_at=parse_datetime(payload.get("created_at")),
            updated_at=parse_datetime(payload.get("updated_at")),
            completed_at=parse_datetime(payload.get("completed_at")),
        )


@dataclass(slots=True)
class ProjectsPage:
    items: list[Project]
    total: int
    limit: int
    offset: int

    @classmethod
    def from_api(cls, payload: dict) -> "ProjectsPage":
        return cls(
            items=[Project.from_api(item) for item in payload.get("items", [])],
            total=int(payload.get("total", 0)),
            limit=int(payload.get("limit", 0)),
            offset=int(payload.get("offset", 0)),
        )


@dataclass(slots=True)
class ProcessingRunsPage:
    items: list[ProcessingRun]
    total: int
    limit: int
    offset: int

    @classmethod
    def from_api(cls, payload: dict) -> "ProcessingRunsPage":
        return cls(
            items=[ProcessingRun.from_api(item) for item in payload.get("items", [])],
            total=int(payload.get("total", 0)),
            limit=int(payload.get("limit", 0)),
            offset=int(payload.get("offset", 0)),
        )
