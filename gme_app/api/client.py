"""HTTP client for gme-managment API."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from gme_app.models import ProcessingRunsPage, ProjectsPage, UserProfile, UserSummary


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
        timeout_seconds: float = 15.0,
        session_cookie_name: str = "session_token",
    ) -> None:
        self.base_url = base_url.rstrip("/")
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

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected: tuple[int, ...] = (200,),
        **kwargs: Any,
    ) -> Any:
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

    def list_projects(self, *, q: str | None = None, limit: int = 100, offset: int = 0) -> ProjectsPage:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if q:
            params["q"] = q
        data = self._request("GET", "/projects", params=params, expected=(200,))
        return ProjectsPage.from_api(data)

    def create_project(
        self,
        *,
        title: str,
        description: str | None,
        video_path: Path,
        start_processing: bool = False,
    ) -> dict[str, Any]:
        if not video_path.exists():
            raise ApiError(f"Файл не найден: {video_path}")

        form = {
            "title": title,
            "description": description or "",
            "start_processing": "true" if start_processing else "false",
            "launch_mode": "immediate",
        }
        with video_path.open("rb") as handle:
            files = {"video": (video_path.name, handle, "video/mp4")}
            return self._request(
                "POST",
                "/projects",
                data=form,
                files=files,
                expected=(201,),
            )

    def start_processing(self, *, project_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/projects/{project_id}/processing/start",
            json={"launch_mode": "immediate"},
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
