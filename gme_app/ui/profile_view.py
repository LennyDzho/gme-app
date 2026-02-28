"""User profile screen."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gme_app.models import UserProfile, format_datetime


class ProfileView(QWidget):
    back_to_projects_requested = pyqtSignal()
    open_admin_requested = pyqtSignal()
    save_profile_requested = pyqtSignal(object, object)
    change_password_requested = pyqtSignal(str, str, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user: UserProfile | None = None
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

        title = QLabel("Профиль")
        title.setObjectName("SectionTitle")
        header_layout.addWidget(title, 1)

        self.open_projects_button = QPushButton("Проекты")
        self.open_projects_button.setObjectName("SecondaryButton")
        self.open_projects_button.clicked.connect(self.back_to_projects_requested.emit)
        header_layout.addWidget(self.open_projects_button, 0)

        self.open_admin_button = QPushButton("Админ-панель")
        self.open_admin_button.setObjectName("SecondaryButton")
        self.open_admin_button.clicked.connect(self.open_admin_requested.emit)
        self.open_admin_button.hide()
        header_layout.addWidget(self.open_admin_button, 0)

        root.addWidget(header, 0)

        self.status_message = QLabel("")
        self.status_message.setObjectName("SectionHint")
        self.status_message.hide()
        root.addWidget(self.status_message, 0)

        self.user_summary = QLabel("-")
        self.user_summary.setObjectName("SectionHint")
        self.user_summary.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        root.addWidget(self.user_summary, 0)

        profile_card = QFrame()
        profile_card.setObjectName("DetailCard")
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(14, 14, 14, 14)
        profile_layout.setSpacing(8)

        profile_title = QLabel("Данные пользователя")
        profile_title.setObjectName("ProjectTitle")
        profile_layout.addWidget(profile_title)

        profile_layout.addWidget(QLabel("Отображаемое имя"))
        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Как отображать ваше имя")
        profile_layout.addWidget(self.display_name_input)

        profile_layout.addWidget(QLabel("Эл. почта"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("name@example.com")
        profile_layout.addWidget(self.email_input)

        self.save_profile_button = QPushButton("Сохранить профиль")
        self.save_profile_button.setObjectName("PrimaryButton")
        self.save_profile_button.clicked.connect(self._emit_save_profile)
        profile_layout.addWidget(self.save_profile_button, 0, Qt.AlignmentFlag.AlignRight)

        root.addWidget(profile_card, 0)

        password_card = QFrame()
        password_card.setObjectName("DetailCard")
        password_layout = QVBoxLayout(password_card)
        password_layout.setContentsMargins(14, 14, 14, 14)
        password_layout.setSpacing(8)

        password_title = QLabel("Смена пароля")
        password_title.setObjectName("ProjectTitle")
        password_layout.addWidget(password_title)

        password_layout.addWidget(QLabel("Старый пароль"))
        self.old_password_input = QLineEdit()
        self.old_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(self.old_password_input)

        password_layout.addWidget(QLabel("Новый пароль"))
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(self.new_password_input)

        self.revoke_sessions_checkbox = QCheckBox("Завершить остальные сессии")
        self.revoke_sessions_checkbox.setChecked(True)
        password_layout.addWidget(self.revoke_sessions_checkbox)

        self.change_password_button = QPushButton("Обновить пароль")
        self.change_password_button.setObjectName("PrimaryButton")
        self.change_password_button.clicked.connect(self._emit_change_password)
        password_layout.addWidget(self.change_password_button, 0, Qt.AlignmentFlag.AlignRight)

        root.addWidget(password_card, 0)
        root.addStretch(1)

    def set_user(self, user: UserProfile) -> None:
        self._user = user
        self.display_name_input.setText((user.display_name or "").strip())
        self.email_input.setText((user.email or "").strip())
        created_text = format_datetime(user.created_at)
        self.user_summary.setText(
            f"Логин: {user.login}   |   Роль: {user.role}   |   Аккаунт создан: {created_text}"
        )

    def set_admin_mode(self, is_admin: bool) -> None:
        self.open_admin_button.setVisible(is_admin)

    def set_loading(self, loading: bool, message: str | None = None) -> None:
        self.open_projects_button.setDisabled(loading)
        self.open_admin_button.setDisabled(loading)
        self.save_profile_button.setDisabled(loading)
        self.change_password_button.setDisabled(loading)
        self.display_name_input.setDisabled(loading)
        self.email_input.setDisabled(loading)
        self.old_password_input.setDisabled(loading)
        self.new_password_input.setDisabled(loading)
        self.revoke_sessions_checkbox.setDisabled(loading)
        if loading and message:
            self.set_status_message(message, is_error=False)

    def clear_password_inputs(self) -> None:
        self.old_password_input.clear()
        self.new_password_input.clear()

    def set_status_message(self, message: str, *, is_error: bool) -> None:
        if not message:
            self.status_message.hide()
            self.status_message.clear()
            return
        self.status_message.setStyleSheet("color: #c63f57;" if is_error else "color: #4d5a86;")
        self.status_message.setText(message)
        self.status_message.show()

    def _emit_save_profile(self) -> None:
        email_raw = self.email_input.text().strip()
        display_name_raw = self.display_name_input.text().strip()
        email_value = email_raw or None
        display_name_value = display_name_raw or None
        self.save_profile_requested.emit(email_value, display_name_value)

    def _emit_change_password(self) -> None:
        old_password = self.old_password_input.text()
        new_password = self.new_password_input.text()
        revoke = self.revoke_sessions_checkbox.isChecked()
        if not old_password or not new_password:
            self.set_status_message("Заполните старый и новый пароль.", is_error=True)
            return
        self.change_password_requested.emit(old_password, new_password, revoke)
