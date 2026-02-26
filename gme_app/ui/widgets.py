"""Reusable UI widgets."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
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
    open_project_requested = pyqtSignal(str)

    def __init__(self, project: Project, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.setObjectName("ProjectCard")
        # Let cards shrink with available width; otherwise their minimum size can lock content width.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setMinimumHeight(190)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        title = QLabel(project.title)
        title.setObjectName("ProjectTitle")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        badge = StatusBadge(project_status_label(project.status), project.status)
        top_row.addWidget(title, 1)
        top_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        description = QLabel(project.description or "Описание не задано")
        description.setWordWrap(True)
        description.setObjectName("ProjectMeta")
        description.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        description.setMaximumHeight(54)

        meta = QLabel(f"Обновлен: {format_datetime(project.updated_at)}")
        meta.setObjectName("ProjectMeta")
        meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addWidget(meta, 1)

        open_button = QPushButton("Открыть проект")
        open_button.setObjectName("PrimaryButton")
        open_button.clicked.connect(self._emit_open_project)
        footer.addWidget(open_button, 0)

        layout.addLayout(top_row)
        layout.addWidget(description)
        layout.addStretch(1)
        layout.addLayout(footer)

    def _emit_open_project(self) -> None:
        self.open_project_requested.emit(str(self.project.id))


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
        self._last_columns = 0
        self._is_reflowing = False
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(spacing)
        self._grid.setVerticalSpacing(spacing)

    def set_min_column_width(self, value: int) -> None:
        self._min_column_width = max(220, value)
        self._reflow()

    def set_items(self, widgets: list[QWidget]) -> None:
        active_widget_ids = {id(widget) for widget in widgets}
        for widget in self._items:
            if id(widget) in active_widget_ids:
                continue
            self._grid.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._items = widgets
        self._reflow()

    def _clear_layout(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._grid.removeWidget(widget)

    def _reflow(self) -> None:
        if self._is_reflowing:
            return
        self._is_reflowing = True
        try:
            self._clear_layout()
            for column in range(self._last_columns):
                self._grid.setColumnStretch(column, 0)

            if not self._items:
                self._last_columns = 0
                return

            # Derive width from scroll viewport when available, otherwise use local widget width.
            # This prevents stale content width from forcing a single long row after window resize.
            available_width = max(self._available_width(), 1)
            columns = max(1, available_width // self._min_column_width)

            for index, widget in enumerate(self._items):
                row = index // columns
                column = index % columns
                self._grid.addWidget(widget, row, column)

            for column in range(columns):
                self._grid.setColumnStretch(column, 1)
            self._last_columns = columns
        finally:
            self._is_reflowing = False

    def _available_width(self) -> int:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                return parent.viewport().width()
            parent = parent.parentWidget()
        return self.contentsRect().width()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._reflow()
