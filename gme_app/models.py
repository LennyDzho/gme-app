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


def parse_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
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
class UsersPage:
    items: list[UserProfile]
    total: int
    limit: int
    offset: int

    @classmethod
    def from_api(cls, payload: dict) -> "UsersPage":
        return cls(
            items=[UserProfile.from_api(item) for item in payload.get("items", [])],
            total=int(payload.get("total", 0)),
            limit=int(payload.get("limit", 0)),
            offset=int(payload.get("offset", 0)),
        )


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
class ProjectMember:
    project_id: UUID
    user_id: UUID
    member_role: str
    created_at: datetime | None
    created_by: UUID | None
    user_login: str | None
    user_display_name: str | None
    user_role: str | None

    @classmethod
    def from_api(cls, payload: dict) -> "ProjectMember":
        return cls(
            project_id=UUID(str(payload["project_id"])),
            user_id=UUID(str(payload["user_id"])),
            member_role=str(payload["member_role"]),
            created_at=parse_datetime(payload.get("created_at")),
            created_by=parse_uuid(payload.get("created_by")),
            user_login=payload.get("user_login"),
            user_display_name=payload.get("user_display_name"),
            user_role=str(payload["user_role"]) if payload.get("user_role") is not None else None,
        )

    @property
    def ui_name(self) -> str:
        return (self.user_display_name or self.user_login or str(self.user_id)).strip()


@dataclass(slots=True)
class ProcessingRun:
    id: UUID
    project_id: UUID
    video_task_id: str
    provider: str
    status: str
    launch_mode: str
    scheduled_for: datetime | None
    triggered_at: datetime | None
    input_path: str | None
    output_path: str | None
    error: str | None
    started_by: UUID | None
    created_at: datetime | None
    updated_at: datetime | None
    completed_at: datetime | None
    last_sync_at: datetime | None

    @classmethod
    def from_api(cls, payload: dict) -> "ProcessingRun":
        return cls(
            id=UUID(str(payload["id"])),
            project_id=UUID(str(payload["project_id"])),
            video_task_id=str(payload["video_task_id"]),
            provider=str(payload["provider"]),
            status=str(payload["status"]),
            launch_mode=str(payload["launch_mode"]),
            scheduled_for=parse_datetime(payload.get("scheduled_for")),
            triggered_at=parse_datetime(payload.get("triggered_at")),
            input_path=payload.get("input_path"),
            output_path=payload.get("output_path"),
            error=payload.get("error"),
            started_by=parse_uuid(payload.get("started_by")),
            created_at=parse_datetime(payload.get("created_at")),
            updated_at=parse_datetime(payload.get("updated_at")),
            completed_at=parse_datetime(payload.get("completed_at")),
            last_sync_at=parse_datetime(payload.get("last_sync_at")),
        )


@dataclass(slots=True)
class AudioProvider:
    code: str
    title: str
    description: str
    supports_audio: bool
    supports_video: bool
    is_video_provider: bool

    @classmethod
    def from_api(cls, payload: dict) -> "AudioProvider":
        code = str(payload.get("code", "")).strip().lower()
        return cls(
            code=code,
            title=str(payload.get("title") or code),
            description=str(payload.get("description") or ""),
            supports_audio=bool(payload.get("supports_audio", True)),
            supports_video=bool(payload.get("supports_video", True)),
            is_video_provider=bool(payload.get("is_video_provider", False)),
        )


@dataclass(slots=True)
class Artifact:
    artifact_id: str
    task_id: str
    type: str
    path: str
    mime_type: str
    checksum: str | None
    size_bytes: int
    ttl: datetime | None
    created_at: datetime | None

    @classmethod
    def from_api(cls, payload: dict) -> "Artifact":
        return cls(
            artifact_id=str(payload["artifact_id"]),
            task_id=str(payload["task_id"]),
            type=str(payload["type"]),
            path=str(payload["path"]),
            mime_type=str(payload["mime_type"]),
            checksum=str(payload["checksum"]) if payload.get("checksum") is not None else None,
            size_bytes=int(payload.get("size_bytes", 0)),
            ttl=parse_datetime(payload.get("ttl")),
            created_at=parse_datetime(payload.get("created_at")),
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


@dataclass(slots=True)
class ProjectMembersPage:
    items: list[ProjectMember]
    total: int

    @classmethod
    def from_api(cls, payload: dict) -> "ProjectMembersPage":
        return cls(
            items=[ProjectMember.from_api(item) for item in payload.get("items", [])],
            total=int(payload.get("total", 0)),
        )


@dataclass(slots=True)
class ArtifactsList:
    artifacts: list[Artifact]

    @classmethod
    def from_api(cls, payload: dict) -> "ArtifactsList":
        return cls(
            artifacts=[Artifact.from_api(item) for item in payload.get("artifacts", [])],
        )
