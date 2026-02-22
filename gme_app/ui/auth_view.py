"""Authentication screen."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class AuthView(QWidget):
    login_submitted = pyqtSignal(str, str, bool)
    register_submitted = pyqtSignal(str, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(26, 24, 26, 24)
        self.root_layout.setSpacing(0)
        self.root_layout.addStretch(1)

        self.card = QFrame()
        self.card.setObjectName("AuthCard")
        self.card.setMaximumWidth(920)
        self.card.setMinimumWidth(680)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("AuthHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 14)
        header_layout.setSpacing(4)

        logo = QLabel("EmotionVision")
        logo.setObjectName("AuthLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(logo)

        subtitle = QLabel("Вход в аккаунт и регистрация нового пользователя")
        subtitle.setObjectName("AuthSubhead")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle)

        card_layout.addWidget(header)

        self.info_label = QLabel("")
        self.info_label.setObjectName("InfoLabel")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.hide()
        card_layout.addWidget(self.info_label)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("AuthTabs")
        self.tabs.setMinimumHeight(560)
        self.tabs.addTab(self._build_login_tab(), "Вход")
        self.tabs.addTab(self._build_register_tab(), "Регистрация")
        self.tabs.tabBar().setExpanding(True)
        self.tabs.tabBar().setUsesScrollButtons(False)
        card_layout.addWidget(self.tabs, 1)

        self.info_panel = QFrame()
        self.info_panel.setObjectName("AuthInfoPanel")
        info_layout = QVBoxLayout(self.info_panel)
        info_layout.setContentsMargins(22, 18, 22, 18)
        info_layout.setSpacing(8)

        info_title = QLabel("Что доступно после входа")
        info_title.setObjectName("AuthInfoTitle")
        info_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        info_text = QLabel(
            "Создание и управление проектами, запуск обработки видео, "
            "просмотр последних запусков и быстрый доступ к статусам в одном интерфейсе."
        )
        info_text.setObjectName("AuthInfoText")
        info_text.setWordWrap(True)
        info_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        info_layout.addWidget(info_title)
        info_layout.addWidget(info_text)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        self.content_layout.addWidget(self.card, 0, Qt.AlignmentFlag.AlignHCenter)
        self.content_layout.addWidget(self.info_panel)

        self.root_layout.addWidget(self.content, 0, Qt.AlignmentFlag.AlignHCenter)
        self.root_layout.addStretch(1)

    def _build_login_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        login_label = QLabel("Логин")
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("ivan")

        password_label = QLabel("Пароль")
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Введите пароль")
        self.login_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.remember_checkbox = QCheckBox("Запомнить меня")

        self.login_error_label = QLabel("")
        self.login_error_label.setObjectName("ErrorLabel")
        self.login_error_label.hide()

        self.login_button = QPushButton("Войти")
        self.login_button.setObjectName("PrimaryButton")
        self.login_button.clicked.connect(self._submit_login)
        self.login_password.returnPressed.connect(self._submit_login)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(self.login_button)

        layout.addWidget(login_label)
        layout.addWidget(self.login_input)
        layout.addWidget(password_label)
        layout.addWidget(self.login_password)
        layout.addWidget(self.remember_checkbox)
        layout.addWidget(self.login_error_label)
        layout.addLayout(button_row)
        layout.addStretch(1)
        return page

    def _build_register_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        login_label = QLabel("Логин")
        self.register_login_input = QLineEdit()
        self.register_login_input.setPlaceholderText("ivan")

        email_label = QLabel("Email (необязательно)")
        self.register_email_input = QLineEdit()
        self.register_email_input.setPlaceholderText("your@email.com")

        password_label = QLabel("Пароль")
        self.register_password_input = QLineEdit()
        self.register_password_input.setPlaceholderText("Не менее 8 символов")
        self.register_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        confirm_label = QLabel("Подтвердите пароль")
        self.register_confirm_input = QLineEdit()
        self.register_confirm_input.setPlaceholderText("Повторите пароль")
        self.register_confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.register_confirm_input.returnPressed.connect(self._submit_register)

        self.register_error_label = QLabel("")
        self.register_error_label.setObjectName("ErrorLabel")
        self.register_error_label.hide()

        self.register_button = QPushButton("Создать аккаунт")
        self.register_button.setObjectName("PrimaryButton")
        self.register_button.clicked.connect(self._submit_register)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(self.register_button)

        layout.addWidget(login_label)
        layout.addWidget(self.register_login_input)
        layout.addWidget(email_label)
        layout.addWidget(self.register_email_input)
        layout.addWidget(password_label)
        layout.addWidget(self.register_password_input)
        layout.addWidget(confirm_label)
        layout.addWidget(self.register_confirm_input)
        layout.addWidget(self.register_error_label)
        layout.addLayout(button_row)
        layout.addStretch(1)
        return page

    def _submit_login(self) -> None:
        self.login_error_label.hide()
        login = self.login_input.text().strip()
        password = self.login_password.text()
        remember = self.remember_checkbox.isChecked()

        if not login or not password:
            self.show_login_error("Введите логин и пароль.")
            return
        self.login_submitted.emit(login, password, remember)

    def _submit_register(self) -> None:
        self.register_error_label.hide()
        login = self.register_login_input.text().strip()
        email = self.register_email_input.text().strip()
        password = self.register_password_input.text()
        confirm = self.register_confirm_input.text()

        if len(login) < 3:
            self.show_register_error("Логин должен быть не короче 3 символов.")
            return
        if len(password) < 8:
            self.show_register_error("Пароль должен быть не короче 8 символов.")
            return
        if password != confirm:
            self.show_register_error("Пароли не совпадают.")
            return
        self.register_submitted.emit(login, email, password)

    def show_login_error(self, message: str) -> None:
        self.login_error_label.setText(message)
        self.login_error_label.show()

    def show_register_error(self, message: str) -> None:
        self.register_error_label.setText(message)
        self.register_error_label.show()

    def show_info(self, message: str) -> None:
        self.info_label.setText(message)
        self.info_label.show()

    def clear_info(self) -> None:
        self.info_label.hide()
        self.info_label.clear()

    def set_busy(self, busy: bool, message: str | None = None) -> None:
        self.login_button.setDisabled(busy)
        self.register_button.setDisabled(busy)
        self.tabs.setDisabled(busy)
        if message:
            self.show_info(message)
        elif not busy:
            self.clear_info()

    def prefill_login(self, login: str) -> None:
        if login:
            self.login_input.setText(login)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        width = self.width()
        if width < 760:
            self.root_layout.setContentsMargins(10, 10, 10, 10)
        else:
            self.root_layout.setContentsMargins(26, 24, 26, 24)

        max_width = max(360, min(920, width - 40))
        self.card.setMaximumWidth(max_width)
        if width < 840:
            self.card.setMinimumWidth(0)
            self.tabs.setMinimumHeight(500)
        else:
            self.card.setMinimumWidth(680)
            self.tabs.setMinimumHeight(560)
