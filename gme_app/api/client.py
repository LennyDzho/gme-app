"""HTTP client for gme-managment API."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from gme_app.models import (
    AudioProvider,
    ArtifactsList,
    ProcessingRunsPage,
    Project,
    ProjectMember,
    ProjectMembersPage,
    ProjectsPage,
    UserProfile,
    UserSummary,
    UsersPage,
)


class ApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code

    def __str__(self) -> str:
        prefix = f"[{self.status_code}] " if self.status_code else ""
        if self.code:
            return f"{prefix}{self.code}: {self.message}"
        return f"{prefix}{self.message}"


class GMEManagementClient:
    def __init__(
        self,
        *,
        base_url: str,
        video_service_base_url: str | None = None,
        audio_service_base_url: str | None = None,
        audio_service_api_key: str | None = None,
        timeout_seconds: float = 15.0,
        session_cookie_name: str = "session_token",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.video_service_base_url = (video_service_base_url or "").rstrip("/") or None
        self.audio_service_base_url = (audio_service_base_url or "").rstrip("/") or None
        self.audio_service_api_key = (audio_service_api_key or "").strip() or None
        self.timeout_seconds = timeout_seconds
        self.session_cookie_name = session_cookie_name
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "gme-app/0.1.0",
            }
        )

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _video_url(self, path: str) -> str:
        if not self.video_service_base_url:
            raise ApiError("Не задан GME_VIDEO_SERVICE_URL для работы с детекторами лица.")
        return f"{self.video_service_base_url}/{path.lstrip('/')}"

    def _audio_url(self, path: str) -> str:
        if not self.audio_service_base_url:
            raise ApiError("Не задан GME_AUDIO_SERVICE_URL для работы с аудио-провайдерами.")
        return f"{self.audio_service_base_url}/{path.lstrip('/')}"

    def _request_raw(
        self,
        method: str,
        path: str,
        *,
        expected: tuple[int, ...] = (200,),
        **kwargs: Any,
    ) -> requests.Response:
        try:
            response = self.session.request(
                method=method,
                url=self._url(path),
                timeout=self.timeout_seconds,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ApiError(
                "Не удалось подключиться к gme-managment. Проверьте URL и доступность сервиса.",
            ) from exc

        if response.status_code not in expected:
            raise self._build_error(response)
        return response

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected: tuple[int, ...] = (200,),
        **kwargs: Any,
    ) -> Any:
        response = self._request_raw(method, path, expected=expected, **kwargs)

        if response.status_code == 204 or not response.content:
            return None

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()

        try:
            return response.json()
        except ValueError:
            return response.text

    def _build_error(self, response: requests.Response) -> ApiError:
        detail = f"HTTP {response.status_code}"
        code: str | None = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = str(payload.get("detail", detail))
                raw_code = payload.get("code")
                code = str(raw_code) if raw_code is not None else None
        except ValueError:
            if response.text:
                detail = response.text[:400]
        return ApiError(detail, status_code=response.status_code, code=code)

    def _video_request(
        self,
        method: str,
        path: str,
        *,
        expected: tuple[int, ...] = (200,),
        **kwargs: Any,
    ) -> Any:
        url = self._video_url(path)
        try:
            response = requests.request(
                method=method,
                url=url,
                timeout=self.timeout_seconds,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ApiError("Не удалось подключиться к gme-video-service.") from exc

        if response.status_code not in expected:
            detail = f"HTTP {response.status_code}"
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = str(payload.get("detail", detail))
            except ValueError:
                if response.text:
                    detail = response.text[:400]
            raise ApiError(detail, status_code=response.status_code)

        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def _audio_request(
        self,
        method: str,
        path: str,
        *,
        expected: tuple[int, ...] = (200,),
        **kwargs: Any,
    ) -> Any:
        url = self._audio_url(path)
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.audio_service_api_key:
            headers["x-api-key"] = self.audio_service_api_key
        headers.setdefault("Accept", "application/json")
        try:
            response = requests.request(
                method=method,
                url=url,
                timeout=self.timeout_seconds,
                headers=headers,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ApiError("Не удалось подключиться к gme-audio-service.") from exc

        if response.status_code not in expected:
            detail = f"HTTP {response.status_code}"
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = str(payload.get("detail", detail))
            except ValueError:
                if response.text:
                    detail = response.text[:400]
            raise ApiError(detail, status_code=response.status_code)

        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def set_session_token(self, token: str) -> None:
        parsed = urlparse(self.base_url)
        domain = parsed.hostname
        if domain:
            self.session.cookies.set(
                self.session_cookie_name,
                token,
                domain=domain,
                path="/",
            )
            return
        self.session.cookies.set(self.session_cookie_name, token, path="/")

    def get_session_token(self) -> str | None:
        return self.session.cookies.get(self.session_cookie_name)

    def clear_session_token(self) -> None:
        self.session.cookies.clear()

    def register(self, *, login: str, password: str, email: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"login": login, "password": password}
        if email:
            payload["email"] = email
        return self._request("POST", "/auth/register", json=payload, expected=(201,))

    def login(self, *, login: str, password: str) -> UserSummary:
        payload = {"login": login, "password": password}
        data = self._request("POST", "/auth/login", json=payload, expected=(200,))
        return UserSummary.from_api(data["user"])

    def logout(self) -> None:
        self._request("POST", "/auth/logout", expected=(204,))

    def get_me(self) -> UserProfile:
        data = self._request("GET", "/users/me", expected=(200,))
        return UserProfile.from_api(data)

    def update_me(self, *, email: str | None = None, display_name: str | None = None) -> UserProfile:
        payload: dict[str, Any] = {}
        if email is not None:
            payload["email"] = email
        if display_name is not None:
            payload["display_name"] = display_name
        data = self._request("PATCH", "/users/me", json=payload, expected=(200,))
        return UserProfile.from_api(data)

    def change_my_password(
        self,
        *,
        old_password: str,
        new_password: str,
        revoke_other_sessions: bool = True,
    ) -> None:
        payload = {
            "old_password": old_password,
            "new_password": new_password,
            "revoke_other_sessions": revoke_other_sessions,
        }
        self._request("PATCH", "/users/me/password", json=payload, expected=(204,))

    def admin_list_users(
        self,
        *,
        q: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> UsersPage:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if q:
            params["q"] = q
        if role:
            params["role"] = role
        if is_active is not None:
            params["is_active"] = is_active
        data = self._request("GET", "/admin/users", params=params, expected=(200,))
        return UsersPage.from_api(data)

    def admin_patch_user_role(self, *, user_id: str, role: str) -> UserProfile:
        data = self._request(
            "PATCH",
            f"/admin/users/{user_id}/role",
            json={"role": role},
            expected=(200,),
        )
        return UserProfile.from_api(data)

    def admin_patch_user_active(self, *, user_id: str, is_active: bool) -> UserProfile:
        data = self._request(
            "PATCH",
            f"/admin/users/{user_id}/active",
            json={"is_active": is_active},
            expected=(200,),
        )
        return UserProfile.from_api(data)

    def list_projects(self, *, q: str | None = None, limit: int = 100, offset: int = 0) -> ProjectsPage:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if q:
            params["q"] = q
        data = self._request("GET", "/projects", params=params, expected=(200,))
        return ProjectsPage.from_api(data)

    def get_project(self, *, project_id: str) -> Project:
        data = self._request("GET", f"/projects/{project_id}", expected=(200,))
        return Project.from_api(data)

    def get_processing_models(self) -> list[str]:
        data = self._request("GET", "/processing/models", expected=(200,))
        if not isinstance(data, list):
            raise ApiError("Некорректный формат списка моделей")
        return [str(item) for item in data if isinstance(item, str)]

    def get_audio_providers(self) -> list[AudioProvider]:
        last_error: ApiError | None = None

        try:
            data = self._request("GET", "/processing/audio-providers", expected=(200,))
            if isinstance(data, list):
                providers = self._normalize_audio_provider_entries(data)
                if providers:
                    return providers
        except ApiError as exc:
            last_error = exc

        data = self._audio_request("GET", "/api/v1/solutions/providers", expected=(200,))
        if not isinstance(data, dict):
            if last_error is not None:
                raise last_error
            raise ApiError("Некорректный формат списка аудио-провайдеров")
        items = data.get("items", [])
        if not isinstance(items, list):
            return []
        providers = self._normalize_audio_provider_entries(items)
        if providers:
            return providers
        if last_error is not None:
            raise last_error
        return []

    @staticmethod
    def _normalize_audio_provider_entries(items: list[Any]) -> list[AudioProvider]:
        providers: list[AudioProvider] = []
        seen_codes: set[str] = set()
        for item in items:
            if isinstance(item, dict):
                code = str(item.get("code", "")).strip().lower()
                title = str(item.get("title") or code).strip() or code
                description = str(item.get("description") or "").strip()
                supports_audio = bool(item.get("supports_audio", True))
                supports_video = bool(item.get("supports_video", True))
                is_video_provider = bool(item.get("is_video_provider", False))
            elif isinstance(item, str):
                code = item.strip().lower()
                title = code
                description = ""
                supports_audio = True
                supports_video = True
                is_video_provider = False
            else:
                continue
            if code:
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                providers.append(
                    AudioProvider(
                        code=code,
                        title=title,
                        description=description,
                        supports_audio=supports_audio,
                        supports_video=supports_video,
                        is_video_provider=is_video_provider,
                    )
                )
        return providers

    def get_face_detectors(self) -> list[str]:
        data = self._video_request("GET", "/api/v1/face-detectors", expected=(200,))
        if not isinstance(data, list):
            raise ApiError("Некорректный ответ по детекторам лица.")
        detectors: list[str] = []
        for item in data:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip().lower()
                if name:
                    detectors.append(name)
        return detectors

    def select_face_detector(self, detector_name: str) -> str:
        normalized = detector_name.strip().lower()
        if not normalized:
            raise ApiError("Детектор лица не выбран.")
        data = self._video_request(
            "POST",
            "/api/v1/face-detectors/select",
            json={"detector": normalized},
            expected=(200,),
        )
        if isinstance(data, dict):
            selected = str(data.get("detector", normalized)).strip().lower()
            return selected or normalized
        return normalized

    def create_project(
        self,
        *,
        title: str,
        description: str | None,
        video_path: Path,
        start_processing: bool = False,
        model_name: str | None = None,
        detector_name: str | None = None,
        processing_mode: str = "video_only",
        audio_provider: str | None = None,
    ) -> dict[str, Any]:
        if not video_path.exists():
            raise ApiError(f"Файл не найден: {video_path}")

        form = {
            "title": title,
            "description": description or "",
            "start_processing": "true" if start_processing else "false",
            "launch_mode": "immediate",
        }
        normalized_model = (model_name or "").strip()
        if normalized_model:
            form["model_name"] = normalized_model
        normalized_detector = (detector_name or "").strip().lower()
        if normalized_detector:
            form["detector_name"] = normalized_detector
        normalized_mode = (processing_mode or "").strip().lower() or "video_only"
        form["processing_mode"] = normalized_mode
        normalized_audio_provider = (audio_provider or "").strip().lower()
        if normalized_audio_provider:
            form["audio_provider"] = normalized_audio_provider

        content_type, _ = mimetypes.guess_type(video_path.name)
        if not content_type:
            content_type = "application/octet-stream"

        with video_path.open("rb") as handle:
            files = {"video": (video_path.name, handle, content_type)}
            return self._request(
                "POST",
                "/projects",
                data=form,
                files=files,
                expected=(201,),
            )

    def replace_project_video(self, *, project_id: str, video_path: Path) -> Project:
        if not video_path.exists():
            raise ApiError(f"Файл не найден: {video_path}")

        content_type, _ = mimetypes.guess_type(video_path.name)
        if not content_type:
            content_type = "application/octet-stream"

        with video_path.open("rb") as handle:
            files = {"video": (video_path.name, handle, content_type)}
            data = self._request(
                "PUT",
                f"/projects/{project_id}/video",
                files=files,
                expected=(200,),
            )
        return Project.from_api(data)

    def start_processing(
        self,
        *,
        project_id: str,
        model_name: str | None = None,
        detector_name: str | None = None,
        processing_mode: str = "video_only",
        audio_provider: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"launch_mode": "immediate"}
        normalized_model = (model_name or "").strip()
        if normalized_model:
            payload["model_name"] = normalized_model
        normalized_detector = (detector_name or "").strip().lower()
        if normalized_detector:
            payload["detector_name"] = normalized_detector
        normalized_mode = (processing_mode or "").strip().lower() or "video_only"
        payload["processing_mode"] = normalized_mode
        normalized_audio_provider = (audio_provider or "").strip().lower()
        if normalized_audio_provider:
            payload["audio_provider"] = normalized_audio_provider

        return self._request(
            "POST",
            f"/projects/{project_id}/processing/start",
            json=payload,
            expected=(202,),
        )

    def list_processing_runs(
        self,
        *,
        project_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> ProcessingRunsPage:
        data = self._request(
            "GET",
            f"/projects/{project_id}/processing",
            params={"limit": limit, "offset": offset},
            expected=(200,),
        )
        return ProcessingRunsPage.from_api(data)

    def sync_processing_run(self, *, project_id: str, run_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/projects/{project_id}/processing/{run_id}/sync",
            expected=(200,),
        )

    def cancel_processing_run(self, *, project_id: str, run_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/projects/{project_id}/processing/{run_id}/cancel",
            expected=(200,),
        )

    def list_project_members(self, *, project_id: str) -> ProjectMembersPage:
        data = self._request(
            "GET",
            f"/projects/{project_id}/members",
            expected=(200,),
        )
        return ProjectMembersPage.from_api(data)

    def delete_project(self, *, project_id: str) -> None:
        self._request("DELETE", f"/projects/{project_id}", expected=(204,))

    def add_project_member(
        self,
        *,
        project_id: str,
        member_role: str,
        user_login: str | None = None,
        user_id: str | None = None,
    ) -> ProjectMember:
        payload: dict[str, Any] = {"member_role": member_role}
        if user_id:
            payload["user_id"] = user_id
        if user_login:
            payload["user_login"] = user_login

        data = self._request(
            "POST",
            f"/projects/{project_id}/members",
            json=payload,
            expected=(201,),
        )
        return ProjectMember.from_api(data)

    def update_project_member_role(
        self,
        *,
        project_id: str,
        user_id: str,
        member_role: str,
    ) -> ProjectMember:
        data = self._request(
            "PATCH",
            f"/projects/{project_id}/members/{user_id}",
            json={"member_role": member_role},
            expected=(200,),
        )
        return ProjectMember.from_api(data)

    def remove_project_member(self, *, project_id: str, user_id: str) -> None:
        self._request(
            "DELETE",
            f"/projects/{project_id}/members/{user_id}",
            expected=(204,),
        )

    def list_artifacts(self, *, project_id: str, run_id: str | None = None) -> ArtifactsList:
        params: dict[str, Any] = {}
        if run_id:
            params["run_id"] = run_id
        data = self._request(
            "GET",
            f"/projects/{project_id}/artifacts",
            params=params or None,
            expected=(200,),
        )
        return ArtifactsList.from_api(data)

    def download_artifact(
        self,
        *,
        project_id: str,
        artifact_id: str,
        target_path: Path,
        run_id: str | None = None,
    ) -> Path:
        params: dict[str, Any] = {}
        if run_id:
            params["run_id"] = run_id

        response = self._request_raw(
            "GET",
            f"/projects/{project_id}/artifacts/{artifact_id}/download",
            params=params or None,
            expected=(200,),
            stream=True,
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
        return target_path

    def download_project_video(self, *, project_id: str, target_path: Path) -> Path:
        response = self._request_raw(
            "GET",
            f"/projects/{project_id}/video/content",
            expected=(200,),
            stream=True,
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
        return target_path
