"""Main application window."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThreadPool
from PyQt6.QtWidgets import QMainWindow, QStackedWidget

from gme_app.api.client import ApiError, GMEManagementClient
from gme_app.config import AppConfig
from gme_app.models import ProcessingRun, Project, UserProfile
from gme_app.services.session_store import PersistedSession, SessionStore
from gme_app.ui.auth_view import AuthView
from gme_app.ui.dashboard_view import DashboardView
from gme_app.workers import Worker


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.client = GMEManagementClient(
            base_url=config.api_base_url,
            timeout_seconds=config.timeout_seconds,
            session_cookie_name=config.session_cookie_name,
        )
        self.session_store = SessionStore(config.app_data_dir / "session.json")
        self.thread_pool = QThreadPool.globalInstance()
        self._active_workers: set[Worker] = set()
        self.current_user: UserProfile | None = None

        self.setWindowTitle("GME App")
        self.setMinimumSize(980, 680)
        self._build_ui()
        self._connect_signals()
        self._restore_session()

    def _build_ui(self) -> None:
        self.stack = QStackedWidget()
        self.auth_view = AuthView()
        self.dashboard_view = DashboardView()
        self.stack.addWidget(self.auth_view)
        self.stack.addWidget(self.dashboard_view)
        self.setCentralWidget(self.stack)
        self.stack.setCurrentWidget(self.auth_view)

    def _connect_signals(self) -> None:
        self.auth_view.login_submitted.connect(self._on_login_submitted)
        self.auth_view.register_submitted.connect(self._on_register_submitted)

        self.dashboard_view.refresh_requested.connect(self.refresh_dashboard)
        self.dashboard_view.create_project_requested.connect(self._on_create_project)
        self.dashboard_view.start_processing_requested.connect(self._on_start_processing)
        self.dashboard_view.logout_requested.connect(self._on_logout)

    def _run_background(
        self,
        fn,
        *,
        on_result=None,
        on_error=None,
        on_finished=None,
    ) -> None:
        worker = Worker(fn)
        self._active_workers.add(worker)
        if on_result is not None:
            worker.signals.result.connect(on_result)
        if on_error is not None:
            worker.signals.error.connect(on_error)

        def _finalize() -> None:
            self._active_workers.discard(worker)
            if on_finished is not None:
                on_finished()

        worker.signals.finished.connect(_finalize)
        self.thread_pool.start(worker)

    def _restore_session(self) -> None:
        persisted = self.session_store.load()
        if not persisted:
            return
        if persisted.api_base_url != self.config.api_base_url:
            self.session_store.clear()
            return

        self.auth_view.prefill_login(persisted.user_login)
        self.auth_view.set_busy(True, "Восстановление сессии...")
        self.client.set_session_token(persisted.session_token)

        def task() -> UserProfile:
            return self.client.get_me()

        def on_success(user: UserProfile) -> None:
            self.auth_view.set_busy(False)
            self._enter_dashboard(user=user, remember=True, login_hint=persisted.user_login)

        def on_error(error: Exception) -> None:
            self.session_store.clear()
            self.client.clear_session_token()
            self.auth_view.set_busy(False)
            self.auth_view.show_info("Сессия истекла. Выполните вход заново.")
            self._show_auth()

        self._run_background(task, on_result=on_success, on_error=on_error)

    def _show_auth(self) -> None:
        self.stack.setCurrentWidget(self.auth_view)

    def _show_dashboard(self) -> None:
        self.stack.setCurrentWidget(self.dashboard_view)

    def _on_login_submitted(self, login: str, password: str, remember: bool) -> None:
        self.auth_view.set_busy(True, "Выполняется вход...")

        def task() -> dict[str, Any]:
            self.client.login(login=login, password=password)
            user = self.client.get_me()
            return {"user": user, "remember": remember, "login": login}

        def on_success(result: dict[str, Any]) -> None:
            self._enter_dashboard(
                user=result["user"],
                remember=bool(result["remember"]),
                login_hint=str(result["login"]),
            )

        def on_error(error: Exception) -> None:
            self.auth_view.show_login_error(self._format_error(error))

        self._run_background(
            task,
            on_result=on_success,
            on_error=on_error,
            on_finished=lambda: self.auth_view.set_busy(False),
        )

    def _on_register_submitted(self, login: str, email: str, password: str) -> None:
        self.auth_view.set_busy(True, "Создание аккаунта...")

        def task() -> dict[str, Any]:
            self.client.register(login=login, password=password, email=email or None)
            self.client.login(login=login, password=password)
            user = self.client.get_me()
            return {"user": user, "login": login}

        def on_success(result: dict[str, Any]) -> None:
            self._enter_dashboard(user=result["user"], remember=True, login_hint=str(result["login"]))

        def on_error(error: Exception) -> None:
            self.auth_view.show_register_error(self._format_error(error))

        self._run_background(
            task,
            on_result=on_success,
            on_error=on_error,
            on_finished=lambda: self.auth_view.set_busy(False),
        )

    def _enter_dashboard(self, *, user: UserProfile, remember: bool, login_hint: str) -> None:
        self.current_user = user
        self.dashboard_view.set_user(user)
        session_token = self.client.get_session_token()
        if remember and session_token:
            self.session_store.save(
                api_base_url=self.config.api_base_url,
                session_token=session_token,
                user_login=login_hint,
            )
        else:
            self.session_store.clear()

        self._show_dashboard()
        self.refresh_dashboard()

    def refresh_dashboard(self) -> None:
        if self.current_user is None:
            return
        self.dashboard_view.set_loading(True, "Загрузка проектов...")

        def task() -> dict[str, Any]:
            projects_page = self.client.list_projects(limit=100, offset=0)
            projects = projects_page.items
            runs: list[tuple[Project, ProcessingRun | None]] = []

            fetch_runs_limit = min(30, len(projects))
            for index, project in enumerate(projects):
                latest_run: ProcessingRun | None = None
                if index < fetch_runs_limit:
                    try:
                        run_page = self.client.list_processing_runs(
                            project_id=str(project.id),
                            limit=1,
                            offset=0,
                        )
                    except ApiError:
                        latest_run = None
                    else:
                        latest_run = run_page.items[0] if run_page.items else None
                runs.append((project, latest_run))

            return {
                "projects": projects,
                "runs": runs,
            }

        def on_success(result: dict[str, Any]) -> None:
            self.dashboard_view.set_dashboard_data(
                projects=list(result["projects"]),
                runs=list(result["runs"]),
            )
            self.dashboard_view.set_status_message(
                f"Данные обновлены: {datetime.now().strftime('%H:%M:%S')}",
                is_error=False,
            )

        def on_error(error: Exception) -> None:
            if isinstance(error, ApiError) and error.status_code == 401:
                self._handle_session_expired()
                return
            self.dashboard_view.set_status_message(self._format_error(error), is_error=True)

        self._run_background(
            task,
            on_result=on_success,
            on_error=on_error,
            on_finished=lambda: self.dashboard_view.set_loading(False),
        )

    def _on_create_project(
        self,
        title: str,
        description: str,
        video_path: str,
        start_processing: bool,
    ) -> None:
        self.dashboard_view.set_loading(True, "Создание проекта...")

        def task() -> dict[str, Any]:
            return self.client.create_project(
                title=title,
                description=description or None,
                video_path=Path(video_path),
                start_processing=start_processing,
            )

        def on_success(_: dict[str, Any]) -> None:
            self.dashboard_view.set_status_message("Проект создан.", is_error=False)
            self.refresh_dashboard()

        def on_error(error: Exception) -> None:
            if isinstance(error, ApiError) and error.status_code == 401:
                self._handle_session_expired()
                return
            self.dashboard_view.set_status_message(self._format_error(error), is_error=True)

        self._run_background(
            task,
            on_result=on_success,
            on_error=on_error,
            on_finished=lambda: self.dashboard_view.set_loading(False),
        )

    def _on_start_processing(self, project_id: str) -> None:
        self.dashboard_view.set_loading(True, "Запуск обработки...")

        def task() -> dict[str, Any]:
            return self.client.start_processing(project_id=project_id)

        def on_success(_: dict[str, Any]) -> None:
            self.dashboard_view.set_status_message("Обработка запущена.", is_error=False)
            self.refresh_dashboard()

        def on_error(error: Exception) -> None:
            if isinstance(error, ApiError) and error.status_code == 401:
                self._handle_session_expired()
                return
            self.dashboard_view.set_status_message(self._format_error(error), is_error=True)

        self._run_background(
            task,
            on_result=on_success,
            on_error=on_error,
            on_finished=lambda: self.dashboard_view.set_loading(False),
        )

    def _on_logout(self) -> None:
        self.dashboard_view.set_loading(True, "Выход из аккаунта...")

        def task() -> None:
            try:
                self.client.logout()
            except ApiError as exc:
                if exc.status_code not in (401, 403):
                    raise

        def on_success(_: Any) -> None:
            self._reset_session()
            self.auth_view.show_info("Вы вышли из аккаунта.")
            self._show_auth()

        def on_error(error: Exception) -> None:
            self.dashboard_view.set_status_message(self._format_error(error), is_error=True)

        self._run_background(
            task,
            on_result=on_success,
            on_error=on_error,
            on_finished=lambda: self.dashboard_view.set_loading(False),
        )

    def _handle_session_expired(self) -> None:
        self._reset_session()
        self.auth_view.show_info("Сессия завершена. Войдите снова.")
        self._show_auth()

    def _reset_session(self) -> None:
        self.current_user = None
        self.client.clear_session_token()
        self.session_store.clear()

    def _format_error(self, error: Exception) -> str:
        if isinstance(error, ApiError):
            return error.message
        return f"Неизвестная ошибка: {error}"
