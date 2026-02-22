"""Reusable UI widgets."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gme_app.models import Project, format_datetime

PROJECT_STATUS_LABELS: dict[str, str] = {
    "draft": "Черновик",
    "in_progress": "В работе",
    "done": "Готов",
    "archived": "Архив",
}

RUN_STATUS_LABELS: dict[str, str] = {
    "scheduled": "Запланирован",
    "pending": "В очереди",
    "running": "Выполняется",
    "completed": "Завершен",
    "failed": "Ошибка",
    "cancelled": "Отменен",
}


def project_status_label(status: str) -> str:
    return PROJECT_STATUS_LABELS.get(status, status)


def run_status_label(status: str) -> str:
    return RUN_STATUS_LABELS.get(status, status)


class StatusBadge(QLabel):
    def __init__(self, text: str, status: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("StatusBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(status, text)

    def set_status(self, status: str, text: str | None = None) -> None:
        self.setProperty("status", status)
        if text is not None:
            self.setText(text)
        self.style().unpolish(self)
        self.style().polish(self)


class MetricCard(QFrame):
    def __init__(self, title: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(96)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch(1)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class ProjectCard(QFrame):
    start_processing_requested = pyqtSignal(str)

    def __init__(self, project: Project, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.setObjectName("ProjectCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(190)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        title = QLabel(project.title)
        title.setObjectName("ProjectTitle")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        badge = StatusBadge(project_status_label(project.status), project.status)
        top_row.addWidget(title, 1)
        top_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        description = QLabel(project.description or "Описание не задано")
        description.setWordWrap(True)
        description.setObjectName("ProjectMeta")
        description.setMaximumHeight(54)

        meta = QLabel(f"Обновлен: {format_datetime(project.updated_at)}")
        meta.setObjectName("ProjectMeta")

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addWidget(meta, 1)

        run_button = QPushButton("Запустить обработку")
        run_button.setObjectName("SecondaryButton")
        run_button.clicked.connect(self._emit_start_processing)
        footer.addWidget(run_button, 0)

        layout.addLayout(top_row)
        layout.addWidget(description)
        layout.addStretch(1)
        layout.addLayout(footer)

    def _emit_start_processing(self) -> None:
        self.start_processing_requested.emit(str(self.project.id))


class ResponsiveGrid(QWidget):
    def __init__(
        self,
        *,
        min_column_width: int = 320,
        spacing: int = 16,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._min_column_width = min_column_width
        self._items: list[QWidget] = []
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(spacing)
        self._grid.setVerticalSpacing(spacing)

    def set_min_column_width(self, value: int) -> None:
        self._min_column_width = max(220, value)
        self._reflow()

    def set_items(self, widgets: list[QWidget]) -> None:
        self._items = widgets
        self._reflow()

    def _clear_layout(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self)

    def _reflow(self) -> None:
        self._clear_layout()
        if not self._items:
            return

        available_width = max(self.width(), self.minimumWidth())
        columns = max(1, available_width // self._min_column_width)

        for index, widget in enumerate(self._items):
            row = index // columns
            column = index % columns
            self._grid.addWidget(widget, row, column)

        for column in range(columns):
            self._grid.setColumnStretch(column, 1)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._reflow()
