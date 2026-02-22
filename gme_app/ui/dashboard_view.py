"""Projects dashboard screen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gme_app.models import ProcessingRun, Project, UserProfile, format_datetime
from gme_app.ui.widgets import MetricCard, ProjectCard, ResponsiveGrid, run_status_label


@dataclass(slots=True)
class CreateProjectPayload:
    title: str
    description: str
    video_path: str
    start_processing: bool


class CreateProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Создание проекта")
        self.setModal(True)
        self.resize(620, 420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title_label = QLabel("Название проекта")
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Например: Customer research")

        description_label = QLabel("Описание")
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Кратко опишите задачу проекта")
        self.description_input.setFixedHeight(120)

        video_label = QLabel("Видео")
        file_row = QHBoxLayout()
        file_row.setSpacing(8)
        self.video_input = QLineEdit()
        self.video_input.setReadOnly(True)
        self.video_input.setPlaceholderText("Выберите видеофайл")
        browse_button = QPushButton("Выбрать файл")
        browse_button.setObjectName("SecondaryButton")
        browse_button.clicked.connect(self._browse_video)
        file_row.addWidget(self.video_input, 1)
        file_row.addWidget(browse_button)

        self.start_processing_checkbox = QCheckBox("Сразу запустить обработку")

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.hide()

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button:
            ok_button.setText("Создать")
            ok_button.setObjectName("PrimaryButton")
        if cancel_button:
            cancel_button.setText("Отмена")
            cancel_button.setObjectName("SecondaryButton")

        layout.addWidget(title_label)
        layout.addWidget(self.title_input)
        layout.addWidget(description_label)
        layout.addWidget(self.description_input)
        layout.addWidget(video_label)
        layout.addLayout(file_row)
        layout.addWidget(self.start_processing_checkbox)
        layout.addWidget(self.error_label)
        layout.addStretch(1)
        layout.addWidget(self.button_box)

    def _browse_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбор видео",
            "",
            "Видео (*.mp4 *.mov *.avi *.mkv);;Все файлы (*.*)",
        )
        if file_path:
            self.video_input.setText(file_path)

    def _on_accept(self) -> None:
        self.error_label.hide()
        title = self.title_input.text().strip()
        video_path = self.video_input.text().strip()
        if len(title) < 3:
            self._show_error("Название должно быть не короче 3 символов.")
            return
        if not video_path:
            self._show_error("Выберите видеофайл.")
            return
        if not Path(video_path).exists():
            self._show_error("Указанный видеофайл не найден.")
            return
        self.accept()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def payload(self) -> CreateProjectPayload:
        return CreateProjectPayload(
            title=self.title_input.text().strip(),
            description=self.description_input.toPlainText().strip(),
            video_path=self.video_input.text().strip(),
            start_processing=self.start_processing_checkbox.isChecked(),
        )


class DashboardView(QWidget):
    refresh_requested = pyqtSignal()
    logout_requested = pyqtSignal()
    create_project_requested = pyqtSignal(str, str, str, bool)
    start_processing_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all_projects: list[Project] = []
        self._runs_by_project: dict[str, ProcessingRun | None] = {}
        self._build_ui()
        self._apply_responsive_mode()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(14)

        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar, 0)

        self.main_panel = QFrame()
        self.main_panel.setObjectName("MainPanel")
        self.main_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout = QVBoxLayout(self.main_panel)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        header = self._build_header()
        main_layout.addWidget(header, 0)

        self.status_message = QLabel("")
        self.status_message.setObjectName("SectionHint")
        self.status_message.hide()
        main_layout.addWidget(self.status_message)

        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)

        self.metrics_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.metrics_layout.setSpacing(10)
        self.total_metric = MetricCard("Всего проектов", "0")
        self.active_metric = MetricCard("Активные", "0")
        self.done_metric = MetricCard("Завершенные", "0")
        self.runs_metric = MetricCard("С последним запуском", "0")
        self.metrics_layout.addWidget(self.total_metric)
        self.metrics_layout.addWidget(self.active_metric)
        self.metrics_layout.addWidget(self.done_metric)
        self.metrics_layout.addWidget(self.runs_metric)
        content_layout.addLayout(self.metrics_layout)

        projects_header = QHBoxLayout()
        projects_title = QLabel("Проекты")
        projects_title.setObjectName("SectionTitle")
        projects_hint = QLabel("Запуск и мониторинг доступны из карточек")
        projects_hint.setObjectName("SectionHint")
        projects_header.addWidget(projects_title)
        projects_header.addStretch(1)
        projects_header.addWidget(projects_hint)
        content_layout.addLayout(projects_header)

        self.projects_grid = ResponsiveGrid(min_column_width=330, spacing=14)
        content_layout.addWidget(self.projects_grid)

        runs_title = QLabel("Последние запуски")
        runs_title.setObjectName("SectionTitle")
        content_layout.addWidget(runs_title)

        self.runs_table = QTableWidget(0, 5)
        self.runs_table.setObjectName("RunsTable")
        self.runs_table.setHorizontalHeaderLabels(
            ["Проект", "Статус", "Создан", "Обновлен", "Провайдер"]
        )
        self.runs_table.verticalHeader().setVisible(False)
        self.runs_table.setAlternatingRowColors(False)
        self.runs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.runs_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.runs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.runs_table.setMinimumHeight(240)
        header_view = self.runs_table.horizontalHeader()
        header_view.setStretchLastSection(True)
        self.runs_table.setColumnWidth(0, 280)
        self.runs_table.setColumnWidth(1, 160)
        self.runs_table.setColumnWidth(2, 170)
        self.runs_table.setColumnWidth(3, 170)
        content_layout.addWidget(self.runs_table)

        content_layout.addStretch(1)
        self.content_scroll.setWidget(content)
        main_layout.addWidget(self.content_scroll, 1)

        root.addWidget(self.main_panel, 1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(10)

        self.brand_label = QLabel("EmotionVision")
        self.brand_label.setStyleSheet("font-size: 24px; font-weight: 700; color: #2b3f71;")
        layout.addWidget(self.brand_label)

        self.sidebar_buttons: list[QPushButton] = []
        nav_data = [
            ("◈ Обзор", "◈"),
            ("▣ Проекты", "▣"),
            ("⌁ Артефакты", "⌁"),
            ("◎ Профиль", "◎"),
        ]
        for idx, (full_text, compact_text) in enumerate(nav_data):
            button = QPushButton(full_text)
            button.setObjectName("SidebarNavButton")
            if idx == 1:
                button.setProperty("active", "true")
            button.setEnabled(False)
            button.setProperty("fullText", full_text)
            button.setProperty("compactText", compact_text)
            self.sidebar_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)

        self.sidebar_user_label = QLabel("Пользователь")
        self.sidebar_user_label.setStyleSheet("font-weight: 700; color: #243760;")
        self.sidebar_role_label = QLabel("-")
        self.sidebar_role_label.setObjectName("SectionHint")
        self.sidebar_logout_button = QPushButton("Выйти")
        self.sidebar_logout_button.setObjectName("SecondaryButton")
        self.sidebar_logout_button.clicked.connect(self.logout_requested.emit)

        layout.addWidget(self.sidebar_user_label)
        layout.addWidget(self.sidebar_role_label)
        layout.addWidget(self.sidebar_logout_button)
        return sidebar

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("HeaderBar")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.header_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.header_layout.setSpacing(12)

        self.greeting_label = QLabel("Добро пожаловать")
        self.greeting_label.setObjectName("GreetingLabel")
        self.greeting_label.setWordWrap(True)
        self.header_layout.addWidget(self.greeting_label, 1)

        actions = QWidget()
        self.actions_layout = QHBoxLayout(actions)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по названию или описанию")
        self.search_input.textChanged.connect(self._apply_filter)
        self.search_input.setMinimumWidth(250)

        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("SecondaryButton")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

        self.create_button = QPushButton("Создать проект")
        self.create_button.setObjectName("PrimaryButton")
        self.create_button.clicked.connect(self._open_create_dialog)

        self.actions_layout.addWidget(self.search_input)
        self.actions_layout.addWidget(self.refresh_button)
        self.actions_layout.addWidget(self.create_button)

        self.header_layout.addWidget(actions, 0)
        layout.addLayout(self.header_layout)
        return frame

    def _open_create_dialog(self) -> None:
        dialog = CreateProjectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            payload = dialog.payload()
            self.create_project_requested.emit(
                payload.title,
                payload.description,
                payload.video_path,
                payload.start_processing,
            )

    def set_user(self, user: UserProfile) -> None:
        self.greeting_label.setText(f"Добро пожаловать, {user.ui_name}")
        self.sidebar_user_label.setText(user.ui_name)
        self.sidebar_role_label.setText(user.role)

    def set_loading(self, loading: bool, message: str | None = None) -> None:
        self.refresh_button.setDisabled(loading)
        self.create_button.setDisabled(loading)
        self.sidebar_logout_button.setDisabled(loading)
        if loading and message:
            self.set_status_message(message, is_error=False)

    def set_status_message(self, message: str, *, is_error: bool) -> None:
        if not message:
            self.status_message.hide()
            self.status_message.clear()
            return
        self.status_message.setStyleSheet(
            "color: #c63f57;" if is_error else "color: #4d5a86;"
        )
        self.status_message.setText(message)
        self.status_message.show()

    def set_dashboard_data(
        self,
        *,
        projects: list[Project],
        runs: list[tuple[Project, ProcessingRun | None]],
    ) -> None:
        self._all_projects = list(projects)
        self._runs_by_project = {str(project.id): run for project, run in runs}
        self._refresh_metrics()
        self._apply_filter()

    def _refresh_metrics(self) -> None:
        total = len(self._all_projects)
        active = sum(1 for project in self._all_projects if project.status in {"draft", "in_progress"})
        done = sum(1 for project in self._all_projects if project.status == "done")
        with_runs = sum(
            1 for project in self._all_projects if self._runs_by_project.get(str(project.id)) is not None
        )
        self.total_metric.set_value(str(total))
        self.active_metric.set_value(str(active))
        self.done_metric.set_value(str(done))
        self.runs_metric.set_value(str(with_runs))

    def _apply_filter(self, *_: object) -> None:
        query = self.search_input.text().strip().lower()
        if not query:
            projects = list(self._all_projects)
        else:
            projects = [
                project
                for project in self._all_projects
                if query in project.title.lower()
                or query in (project.description or "").lower()
            ]
        self._render_project_cards(projects)
        self._render_runs_table(projects)

    def _render_project_cards(self, projects: list[Project]) -> None:
        items: list[QWidget] = []
        if not projects:
            empty = QFrame()
            empty.setObjectName("EmptyState")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(24, 24, 24, 24)
            empty_layout.setSpacing(6)
            title = QLabel("Проекты не найдены")
            title.setObjectName("ProjectTitle")
            hint = QLabel("Измените фильтр или создайте новый проект.")
            hint.setObjectName("SectionHint")
            empty_layout.addWidget(title)
            empty_layout.addWidget(hint)
            empty_layout.addStretch(1)
            items.append(empty)
        else:
            for project in projects:
                card = ProjectCard(project)
                card.start_processing_requested.connect(self.start_processing_requested.emit)
                items.append(card)

        self.projects_grid.set_items(items)

    def _render_runs_table(self, projects: list[Project]) -> None:
        rows: list[tuple[Project, ProcessingRun | None]] = []
        for project in projects:
            rows.append((project, self._runs_by_project.get(str(project.id))))

        def sort_key(item: tuple[Project, ProcessingRun | None]) -> float:
            run = item[1]
            dt = run.created_at if run else item[0].updated_at
            return dt.timestamp() if dt else 0.0

        rows.sort(key=sort_key, reverse=True)
        rows = rows[:20]

        self.runs_table.setRowCount(len(rows))
        for row_index, (project, run) in enumerate(rows):
            status_value = run.status if run else "-"
            status_text = run_status_label(status_value) if run else "Нет запусков"
            status_item = QTableWidgetItem(status_text)
            if run:
                status_color = self._status_color(run.status)
                status_item.setForeground(QBrush(status_color))

            self.runs_table.setItem(row_index, 0, QTableWidgetItem(project.title))
            self.runs_table.setItem(row_index, 1, status_item)
            self.runs_table.setItem(
                row_index,
                2,
                QTableWidgetItem(format_datetime(run.created_at if run else None)),
            )
            self.runs_table.setItem(
                row_index,
                3,
                QTableWidgetItem(format_datetime(run.updated_at if run else project.updated_at)),
            )
            self.runs_table.setItem(
                row_index,
                4,
                QTableWidgetItem(run.provider if run else "-"),
            )

    def _status_color(self, status: str) -> QColor:
        mapping = {
            "scheduled": QColor("#2f5cb1"),
            "pending": QColor("#6f50b5"),
            "running": QColor("#996f00"),
            "completed": QColor("#1f7c4a"),
            "failed": QColor("#bb334a"),
            "cancelled": QColor("#566084"),
        }
        return mapping.get(status, QColor("#4d5a84"))

    def _apply_responsive_mode(self) -> None:
        width = self.width()
        compact_sidebar = width < 1240
        narrow = width < 980

        if compact_sidebar:
            self.sidebar.setFixedWidth(82)
            self.brand_label.hide()
            self.sidebar_user_label.hide()
            self.sidebar_role_label.hide()
            for button in self.sidebar_buttons:
                button.setText(str(button.property("compactText")))
                button.setToolTip(str(button.property("fullText")))
        else:
            self.sidebar.setFixedWidth(220)
            self.brand_label.show()
            self.sidebar_user_label.show()
            self.sidebar_role_label.show()
            for button in self.sidebar_buttons:
                button.setText(str(button.property("fullText")))
                button.setToolTip("")

        if narrow:
            self.header_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.metrics_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self.projects_grid.set_min_column_width(240)
        else:
            self.header_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self.metrics_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            if width < 1350:
                self.projects_grid.set_min_column_width(290)
            else:
                self.projects_grid.set_min_column_width(330)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_responsive_mode()
