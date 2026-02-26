"""Admin panel screen."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gme_app.models import Project, UserProfile, format_datetime

ROLE_ITEMS: tuple[tuple[str, str], ...] = (
    ("Администратор", "admin"),
    ("Сотрудник", "worker"),
    ("Новичок", "newcomer"),
)


def role_label(role: str) -> str:
    mapping = {
        "admin": "Администратор",
        "worker": "Сотрудник",
        "newcomer": "Новичок",
    }
    return mapping.get(role, role)


class AdminView(QWidget):
    back_to_projects_requested = pyqtSignal()
    open_profile_requested = pyqtSignal()
    users_filter_requested = pyqtSignal(str, object, object)
    projects_filter_requested = pyqtSignal(str)
    change_user_role_requested = pyqtSignal(str, str)
    change_user_active_requested = pyqtSignal(str, bool)
    open_project_requested = pyqtSignal(str)
    delete_project_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._users: list[UserProfile] = []
        self._projects: list[Project] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        header = QFrame()
        header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(8)

        title = QLabel("Админ-панель")
        title.setObjectName("SectionTitle")
        header_layout.addWidget(title, 1)

        self.open_projects_button = QPushButton("Проекты")
        self.open_projects_button.setObjectName("SecondaryButton")
        self.open_projects_button.clicked.connect(self.back_to_projects_requested.emit)
        header_layout.addWidget(self.open_projects_button, 0)

        self.open_profile_button = QPushButton("Профиль")
        self.open_profile_button.setObjectName("SecondaryButton")
        self.open_profile_button.clicked.connect(self.open_profile_requested.emit)
        header_layout.addWidget(self.open_profile_button, 0)

        root.addWidget(header, 0)

        self.status_message = QLabel("")
        self.status_message.setObjectName("SectionHint")
        self.status_message.hide()
        root.addWidget(self.status_message, 0)

        users_card = QFrame()
        users_card.setObjectName("DetailCard")
        users_layout = QVBoxLayout(users_card)
        users_layout.setContentsMargins(14, 14, 14, 14)
        users_layout.setSpacing(8)

        users_title = QLabel("Пользователи")
        users_title.setObjectName("ProjectTitle")
        users_layout.addWidget(users_title)

        users_filter_row = QHBoxLayout()
        users_filter_row.setSpacing(8)

        self.user_search_input = QLineEdit()
        self.user_search_input.setPlaceholderText("Поиск: логин или email")
        users_filter_row.addWidget(self.user_search_input, 1)

        self.user_role_filter = QComboBox()
        self.user_role_filter.addItem("Все роли", "")
        for title_text, role_code in ROLE_ITEMS:
            self.user_role_filter.addItem(title_text, role_code)
        users_filter_row.addWidget(self.user_role_filter, 0)

        self.user_active_filter = QComboBox()
        self.user_active_filter.addItem("Все", "__all__")
        self.user_active_filter.addItem("Только активные", "true")
        self.user_active_filter.addItem("Только заблокированные", "false")
        users_filter_row.addWidget(self.user_active_filter, 0)

        self.refresh_users_button = QPushButton("Обновить пользователей")
        self.refresh_users_button.setObjectName("SecondaryButton")
        self.refresh_users_button.clicked.connect(self._emit_users_filter_requested)
        users_filter_row.addWidget(self.refresh_users_button, 0)

        users_layout.addLayout(users_filter_row)

        self.users_table = QTableWidget(0, 7)
        self.users_table.setObjectName("RunsTable")
        self.users_table.setHorizontalHeaderLabels(
            ["Логин", "Display", "Email", "Роль", "Статус", "Создан", "Действия"]
        )
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.users_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.users_table.setMinimumHeight(270)
        self.users_table.horizontalHeader().setStretchLastSection(True)
        self.users_table.setColumnWidth(0, 130)
        self.users_table.setColumnWidth(1, 130)
        self.users_table.setColumnWidth(2, 170)
        self.users_table.setColumnWidth(3, 180)
        self.users_table.setColumnWidth(4, 110)
        self.users_table.setColumnWidth(5, 140)
        users_layout.addWidget(self.users_table)

        root.addWidget(users_card, 1)

        projects_card = QFrame()
        projects_card.setObjectName("DetailCard")
        projects_layout = QVBoxLayout(projects_card)
        projects_layout.setContentsMargins(14, 14, 14, 14)
        projects_layout.setSpacing(8)

        projects_title = QLabel("Проекты")
        projects_title.setObjectName("ProjectTitle")
        projects_layout.addWidget(projects_title)

        projects_filter_row = QHBoxLayout()
        projects_filter_row.setSpacing(8)

        self.project_search_input = QLineEdit()
        self.project_search_input.setPlaceholderText("Поиск по проектам")
        projects_filter_row.addWidget(self.project_search_input, 1)

        self.refresh_projects_button = QPushButton("Обновить проекты")
        self.refresh_projects_button.setObjectName("SecondaryButton")
        self.refresh_projects_button.clicked.connect(self._emit_projects_filter_requested)
        projects_filter_row.addWidget(self.refresh_projects_button, 0)
        projects_layout.addLayout(projects_filter_row)

        self.projects_table = QTableWidget(0, 6)
        self.projects_table.setObjectName("RunsTable")
        self.projects_table.setHorizontalHeaderLabels(
            ["Название", "Статус", "Создатель", "Обновлен", "Открыть", "Удалить"]
        )
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.projects_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.projects_table.setMinimumHeight(220)
        self.projects_table.horizontalHeader().setStretchLastSection(True)
        self.projects_table.setColumnWidth(0, 200)
        self.projects_table.setColumnWidth(1, 120)
        self.projects_table.setColumnWidth(2, 170)
        self.projects_table.setColumnWidth(3, 140)
        self.projects_table.setColumnWidth(4, 90)
        self.projects_table.setColumnWidth(5, 90)
        projects_layout.addWidget(self.projects_table)

        root.addWidget(projects_card, 1)

    def set_status_message(self, message: str, *, is_error: bool) -> None:
        if not message:
            self.status_message.hide()
            self.status_message.clear()
            return
        self.status_message.setStyleSheet("color: #c63f57;" if is_error else "color: #4d5a86;")
        self.status_message.setText(message)
        self.status_message.show()

    def set_loading(self, loading: bool, message: str | None = None) -> None:
        self.open_projects_button.setDisabled(loading)
        self.open_profile_button.setDisabled(loading)
        self.user_search_input.setDisabled(loading)
        self.user_role_filter.setDisabled(loading)
        self.user_active_filter.setDisabled(loading)
        self.refresh_users_button.setDisabled(loading)
        self.project_search_input.setDisabled(loading)
        self.refresh_projects_button.setDisabled(loading)
        if loading and message:
            self.set_status_message(message, is_error=False)

    def set_users(self, users: list[UserProfile]) -> None:
        self._users = list(users)
        self._render_users_table()

    def set_projects(self, projects: list[Project]) -> None:
        self._projects = list(projects)
        self._render_projects_table()

    def _emit_users_filter_requested(self) -> None:
        query = self.user_search_input.text().strip()
        role = str(self.user_role_filter.currentData() or "").strip() or None
        active_raw = str(self.user_active_filter.currentData() or "__all__")
        if active_raw == "true":
            active_value: bool | None = True
        elif active_raw == "false":
            active_value = False
        else:
            active_value = None
        self.users_filter_requested.emit(query, role, active_value)

    def _emit_projects_filter_requested(self) -> None:
        self.projects_filter_requested.emit(self.project_search_input.text().strip())

    def _render_users_table(self) -> None:
        self.users_table.setRowCount(len(self._users))
        for row, user in enumerate(self._users):
            self.users_table.setItem(row, 0, QTableWidgetItem(user.login))
            self.users_table.setItem(row, 1, QTableWidgetItem(user.display_name or "-"))
            self.users_table.setItem(row, 2, QTableWidgetItem(user.email or "-"))
            self.users_table.setItem(row, 4, QTableWidgetItem("Активен" if user.is_active else "Заблокирован"))
            self.users_table.setItem(row, 5, QTableWidgetItem(format_datetime(user.created_at)))

            role_cell = QWidget()
            role_layout = QHBoxLayout(role_cell)
            role_layout.setContentsMargins(0, 0, 0, 0)
            role_layout.setSpacing(4)

            role_combo = QComboBox()
            for role_title, role_code in ROLE_ITEMS:
                role_combo.addItem(role_title, role_code)
            selected = role_combo.findData(user.role)
            if selected >= 0:
                role_combo.setCurrentIndex(selected)

            apply_role_button = QPushButton("Сохранить")
            apply_role_button.setObjectName("SecondaryButton")
            apply_role_button.clicked.connect(
                lambda _checked=False, uid=str(user.id), combo=role_combo: self._emit_change_user_role(uid, combo)
            )
            role_layout.addWidget(role_combo, 1)
            role_layout.addWidget(apply_role_button, 0)
            self.users_table.setCellWidget(row, 3, role_cell)

            active_button = QPushButton("Разбан" if not user.is_active else "Бан")
            active_button.setObjectName("SecondaryButton")
            active_button.clicked.connect(
                lambda _checked=False, uid=str(user.id), active=user.is_active: self.change_user_active_requested.emit(
                    uid, not active
                )
            )
            self.users_table.setCellWidget(row, 6, active_button)

    def _render_projects_table(self) -> None:
        self.projects_table.setRowCount(len(self._projects))
        for row, project in enumerate(self._projects):
            self.projects_table.setItem(row, 0, QTableWidgetItem(project.title))
            self.projects_table.setItem(row, 1, QTableWidgetItem(project.status))
            self.projects_table.setItem(row, 2, QTableWidgetItem(str(project.creator_id)))
            self.projects_table.setItem(row, 3, QTableWidgetItem(format_datetime(project.updated_at)))

            open_button = QPushButton("Открыть")
            open_button.setObjectName("SecondaryButton")
            open_button.clicked.connect(
                lambda _checked=False, project_id=str(project.id): self.open_project_requested.emit(project_id)
            )
            self.projects_table.setCellWidget(row, 4, open_button)

            delete_button = QPushButton("Удалить")
            delete_button.setObjectName("SecondaryButton")
            delete_button.clicked.connect(
                lambda _checked=False, project_id=str(project.id): self.delete_project_requested.emit(project_id)
            )
            self.projects_table.setCellWidget(row, 5, delete_button)

    def _emit_change_user_role(self, user_id: str, combo: QComboBox) -> None:
        role = str(combo.currentData() or "").strip()
        if not role:
            self.set_status_message("Выберите роль пользователя.", is_error=True)
            return
        self.change_user_role_requested.emit(user_id, role)
