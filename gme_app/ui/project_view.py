"""Project details view with video playback, timeline and members management."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QRect, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gme_app.models import AudioProvider, ProcessingRun, Project, ProjectMember, UserProfile, format_datetime
from gme_app.ui.widgets import project_status_label, run_status_label

EMOTION_COLORS: dict[str, QColor] = {
    "happy": QColor("#f59e0b"),
    "sad": QColor("#3b82f6"),
    "angry": QColor("#ef4444"),
    "fear": QColor("#8b5cf6"),
    "surprise": QColor("#10b981"),
    "neutral": QColor("#64748b"),
    "disgust": QColor("#22c55e"),
}

EMOTION_LABELS_RU: dict[str, str] = {
    "happy": "Радость",
    "sad": "Грусть",
    "angry": "Злость",
    "fear": "Страх",
    "surprise": "Удивление",
    "neutral": "Нейтрально",
    "disgust": "Отвращение",
    "contempt": "Презрение",
    "risk": "Риск лжи",
    "deception": "Риск лжи",
    "deception_score": "Риск лжи",
    "lie": "Ложь",
    "truth": "Правда",
    "unknown": "Неизвестно",
}

FEATURE_LABELS_RU: dict[str, str] = {
    "deception_score": "Индекс лжи",
    "risk": "Риск лжи",
    "lie_probability": "Вероятность лжи",
    "speech_rate": "Темп речи",
    "speaking_rate_proxy": "Прокси темпа речи",
    "speaking_rate_proxy_std": "Вариативность темпа речи",
    "pause_ratio": "Доля пауз",
    "pause_duration": "Длительность пауз",
    "pause_count": "Количество пауз",
    "avg_pause_duration": "Средняя длительность пауз",
    "speech_burst_count": "Количество речевых фрагментов",
    "energy": "Энергия сигнала",
    "energy_rms": "Энергия (RMS)",
    "energy_std": "Разброс энергии",
    "intensity": "Интенсивность",
    "intensity_mean": "Средняя интенсивность",
    "intensity_std": "Разброс интенсивности",
    "pitch": "Высота тона",
    "pitch_mean": "Средняя высота тона",
    "pitch_std": "Разброс высоты тона",
    "pitch_variance": "Дисперсия высоты тона",
    "pitch_cv": "Коэффициент вариативности высоты тона",
    "pitch_min": "Минимальная высота тона",
    "pitch_max": "Максимальная высота тона",
    "pitch_range": "Диапазон высоты тона",
    "pitch_contour_slope": "Наклон огибающей тона",
    "pitch_contour_roughness": "Неровность огибающей тона",
    "jitter": "Джиттер",
    "shimmer": "Шиммер",
    "zcr": "Частота нулевых пересечений",
    "hnr": "Отношение гармоник к шуму",
    "spectral_flux": "Спектральный поток",
    "spectral_centroid_mean": "Средний спектральный центроид",
    "spectral_centroid_std": "Разброс спектрального центроида",
    "f1_mean": "Первая форманта (F1)",
    "f2_mean": "Вторая форманта (F2)",
    "f3_mean": "Третья форманта (F3)",
    "voice_instability_index": "Индекс голосовой нестабильности",
    "hesitation_index": "Индекс нерешительности",
}

FEATURE_TOKEN_LABELS_RU: dict[str, str] = {
    "deception": "ложь",
    "risk": "риск",
    "score": "оценка",
    "probability": "вероятность",
    "confidence": "уверенность",
    "audio": "аудио",
    "video": "видео",
    "speech": "речь",
    "rate": "темп",
    "pause": "пауза",
    "duration": "длительность",
    "ratio": "доля",
    "energy": "энергия",
    "intensity": "интенсивность",
    "pitch": "тон",
    "mean": "среднее",
    "std": "стд",
    "variance": "дисперсия",
    "jitter": "джиттер",
    "shimmer": "шиммер",
    "formant": "форманта",
    "voice": "голос",
    "instability": "нестабильность",
    "hesitation": "нерешительность",
    "count": "количество",
    "avg": "средняя",
    "burst": "фрагмент",
    "spectral": "спектральный",
    "centroid": "центроид",
    "contour": "огибающая",
    "slope": "наклон",
    "roughness": "неровность",
    "mfcc": "MFCC",
    "zcr": "ZCR",
    "hnr": "HNR",
}

LIE_RISK_KEYS: tuple[str, ...] = (
    "risk",
    "deception_score",
    "deception",
    "lie_probability",
    "lie_score",
    "lie",
)

LIE_RISK_THRESHOLD = 0.65


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp_unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def format_seconds(seconds: float) -> str:
    seconds_int = max(0, int(round(seconds)))
    minutes = seconds_int // 60
    secs = seconds_int % 60
    return f"{minutes:02d}:{secs:02d}"


def emotion_label_ru(name: str) -> str:
    key = str(name).strip().lower()
    if not key:
        return EMOTION_LABELS_RU["unknown"]
    return EMOTION_LABELS_RU.get(key, key.replace("_", " ").capitalize())


def feature_label_ru(name: str) -> str:
    key = str(name).strip().lower()
    if not key:
        return "Признак"
    if key in FEATURE_LABELS_RU:
        return FEATURE_LABELS_RU[key]

    parts: list[str] = []
    for token in key.replace("-", "_").split("_"):
        clean = token.strip()
        if not clean:
            continue
        parts.append(FEATURE_TOKEN_LABELS_RU.get(clean, clean.upper() if len(clean) <= 4 else clean))

    if not parts:
        return key.capitalize()
    label = " ".join(parts)
    return label[:1].upper() + label[1:]


class EmotionTimelineWidget(QWidget):
    """Painted timeline with click-to-seek support for emotion probabilities."""

    time_clicked = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(320)
        self._points: list[dict[str, Any]] = []
        self._emotions: list[str] = []
        self._max_time = 1.0
        self._selected_time: float | None = None
        self._plot_rect = QRect()

    def set_points(self, points: list[dict[str, Any]]) -> None:
        normalized: list[dict[str, Any]] = []
        emotion_scores: defaultdict[str, list[float]] = defaultdict(list)

        for item in points:
            if not isinstance(item, dict):
                continue
            current_time = max(0.0, safe_float(item.get("time"), 0.0))
            probs_payload = item.get("probabilities")
            if not isinstance(probs_payload, dict):
                continue

            probs: dict[str, float] = {}
            for emotion, value in probs_payload.items():
                name = str(emotion).strip().lower()
                if not name:
                    continue
                probability = min(1.0, max(0.0, safe_float(value, 0.0)))
                probs[name] = probability
                emotion_scores[name].append(probability)

            if not probs:
                continue

            normalized.append({"time": current_time, "probabilities": probs})

        normalized.sort(key=lambda item: safe_float(item.get("time"), 0.0))
        self._points = normalized

        if emotion_scores:
            ordered = sorted(
                emotion_scores.items(),
                key=lambda item: sum(item[1]) / max(1, len(item[1])),
                reverse=True,
            )
            self._emotions = [name for name, _ in ordered[:6]]
        else:
            self._emotions = ["unknown"]

        self._max_time = max(1.0, max((safe_float(item.get("time"), 0.0) for item in normalized), default=1.0))
        self._selected_time = None
        self.update()

    def render_to_pixmap(self) -> QPixmap:
        pixmap = QPixmap(self.size())
        pixmap.fill(QColor("#ffffff"))
        painter = QPainter(pixmap)
        self.render(painter)
        painter.end()
        return pixmap

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#f8faff"))

        left = 58
        right = 20
        top = 20
        bottom = 42
        self._plot_rect = self.rect().adjusted(left, top, -right, -bottom)

        painter.setPen(QPen(QColor("#cfd8f4"), 1))
        painter.drawRect(self._plot_rect)

        if not self._points:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет данных для графика")
            return

        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)

        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        for step in range(0, 5):
            y_ratio = step / 4
            y = int(self._plot_rect.top() + self._plot_rect.height() * y_ratio)
            painter.drawLine(self._plot_rect.left(), y, self._plot_rect.right(), y)

            painter.setPen(QColor("#334155"))
            confidence_value = 1.0 - y_ratio
            painter.drawText(8, y + 4, f"{confidence_value:.2f}")
            painter.setPen(QPen(QColor("#e2e8f0"), 1))

        for step in range(0, 6):
            ratio = step / 5
            x = int(self._plot_rect.left() + self._plot_rect.width() * ratio)
            painter.setPen(QPen(QColor("#e2e8f0"), 1))
            painter.drawLine(x, self._plot_rect.top(), x, self._plot_rect.bottom())
            painter.setPen(QColor("#334155"))
            value = self._max_time * ratio
            painter.drawText(x - 14, self._plot_rect.bottom() + 18, format_seconds(value))

        for emotion in self._emotions:
            color = EMOTION_COLORS.get(emotion, QColor("#0ea5e9"))
            line_points: list[tuple[int, int]] = []

            for item in self._points:
                time_sec = min(self._max_time, max(0.0, safe_float(item.get("time"), 0.0)))
                probs = item.get("probabilities")
                if not isinstance(probs, dict):
                    continue
                probability = min(1.0, max(0.0, safe_float(probs.get(emotion), 0.0)))

                x_ratio = time_sec / self._max_time if self._max_time > 0 else 0.0
                x = int(self._plot_rect.left() + self._plot_rect.width() * x_ratio)
                y = int(self._plot_rect.bottom() - self._plot_rect.height() * probability)
                line_points.append((x, y))

            if len(line_points) == 1:
                painter.setPen(QPen(color, 3))
                painter.drawPoint(line_points[0][0], line_points[0][1])
                continue

            if len(line_points) > 1:
                painter.setPen(QPen(color, 2))
                for idx in range(len(line_points) - 1):
                    painter.drawLine(
                        line_points[idx][0],
                        line_points[idx][1],
                        line_points[idx + 1][0],
                        line_points[idx + 1][1],
                    )

        if self._selected_time is not None:
            selected_ratio = self._selected_time / self._max_time if self._max_time > 0 else 0.0
            selected_x = int(self._plot_rect.left() + self._plot_rect.width() * selected_ratio)
            painter.setPen(QPen(QColor("#ef4444"), 2))
            painter.drawLine(selected_x, self._plot_rect.top(), selected_x, self._plot_rect.bottom())

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if not self._points or not self._plot_rect.contains(event.pos()):
            return

        ratio = (event.position().x() - self._plot_rect.left()) / max(1, self._plot_rect.width())
        ratio = max(0.0, min(1.0, ratio))
        second = ratio * self._max_time
        self._selected_time = second
        self.time_clicked.emit(second)
        self.update()


class MetricTimelineWidget(QWidget):
    """Simple timeline widget for a single numeric metric."""

    time_clicked = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self._points: list[tuple[float, float]] = []
        self._max_time = 1.0
        self._min_value = 0.0
        self._max_value = 1.0
        self._selected_time: float | None = None
        self._plot_rect = QRect()

    def set_points(self, points: list[dict[str, Any]]) -> None:
        normalized: list[tuple[float, float]] = []
        for item in points:
            if not isinstance(item, dict):
                continue
            t = max(0.0, safe_float(item.get("time"), 0.0))
            v = safe_float(item.get("value"), 0.0)
            if v != v:
                continue
            normalized.append((t, v))

        normalized.sort(key=lambda item: item[0])
        self._points = normalized
        self._max_time = max(1.0, max((item[0] for item in normalized), default=1.0))

        if normalized:
            values = [item[1] for item in normalized]
            self._min_value = min(values)
            self._max_value = max(values)
            if abs(self._max_value - self._min_value) < 1e-9:
                padding = max(0.1, abs(self._max_value) * 0.1)
                self._min_value -= padding
                self._max_value += padding
        else:
            self._min_value = 0.0
            self._max_value = 1.0

        self._selected_time = None
        self.update()

    def render_to_pixmap(self) -> QPixmap:
        pixmap = QPixmap(self.size())
        pixmap.fill(QColor("#ffffff"))
        painter = QPainter(pixmap)
        self.render(painter)
        painter.end()
        return pixmap

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#f8faff"))

        left = 64
        right = 18
        top = 14
        bottom = 36
        self._plot_rect = self.rect().adjusted(left, top, -right, -bottom)

        painter.setPen(QPen(QColor("#cfd8f4"), 1))
        painter.drawRect(self._plot_rect)

        if not self._points:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет данных для графика")
            return

        painter.setFont(QFont("", 8))
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        for step in range(0, 5):
            ratio = step / 4
            y = int(self._plot_rect.top() + self._plot_rect.height() * ratio)
            painter.drawLine(self._plot_rect.left(), y, self._plot_rect.right(), y)
            value = self._max_value - ratio * (self._max_value - self._min_value)
            painter.setPen(QColor("#334155"))
            painter.drawText(6, y + 4, f"{value:.2f}")
            painter.setPen(QPen(QColor("#e2e8f0"), 1))

        for step in range(0, 6):
            ratio = step / 5
            x = int(self._plot_rect.left() + self._plot_rect.width() * ratio)
            painter.drawLine(x, self._plot_rect.top(), x, self._plot_rect.bottom())
            painter.setPen(QColor("#334155"))
            painter.drawText(x - 14, self._plot_rect.bottom() + 16, format_seconds(self._max_time * ratio))
            painter.setPen(QPen(QColor("#e2e8f0"), 1))

        chart_points: list[tuple[int, int]] = []
        value_span = self._max_value - self._min_value
        for t, v in self._points:
            x_ratio = t / self._max_time if self._max_time > 0 else 0.0
            y_ratio = (v - self._min_value) / value_span if value_span > 0 else 0.5
            x = int(self._plot_rect.left() + self._plot_rect.width() * x_ratio)
            y = int(self._plot_rect.bottom() - self._plot_rect.height() * y_ratio)
            chart_points.append((x, y))

        painter.setPen(QPen(QColor("#2563eb"), 2))
        if len(chart_points) == 1:
            painter.drawPoint(chart_points[0][0], chart_points[0][1])
        else:
            for idx in range(len(chart_points) - 1):
                painter.drawLine(
                    chart_points[idx][0],
                    chart_points[idx][1],
                    chart_points[idx + 1][0],
                    chart_points[idx + 1][1],
                )

        if self._selected_time is not None:
            selected_ratio = self._selected_time / self._max_time if self._max_time > 0 else 0.0
            selected_x = int(self._plot_rect.left() + self._plot_rect.width() * selected_ratio)
            painter.setPen(QPen(QColor("#ef4444"), 2))
            painter.drawLine(selected_x, self._plot_rect.top(), selected_x, self._plot_rect.bottom())

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if not self._points or not self._plot_rect.contains(event.pos()):
            return
        ratio = (event.position().x() - self._plot_rect.left()) / max(1, self._plot_rect.width())
        ratio = max(0.0, min(1.0, ratio))
        second = ratio * self._max_time
        self._selected_time = second
        self.time_clicked.emit(second)
        self.update()


class CombinedLieTimelineWidget(QWidget):
    """Combined lie-risk timeline with highlighted suspicious intervals."""

    time_clicked = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(240)
        self._points: list[tuple[float, float, float | None, float | None]] = []
        self._max_time = 1.0
        self._selected_time: float | None = None
        self._plot_rect = QRect()
        self._threshold = LIE_RISK_THRESHOLD
        self._highlight_intervals: list[tuple[float, float]] = []
        self._has_audio = False
        self._has_video = False
        self._show_combined = True
        self._show_audio = True
        self._show_video = True

    def set_points(self, points: list[dict[str, Any]], threshold: float = LIE_RISK_THRESHOLD) -> None:
        normalized: list[tuple[float, float, float | None, float | None]] = []
        has_audio = False
        has_video = False

        for item in points:
            if not isinstance(item, dict):
                continue

            t = max(0.0, safe_float(item.get("time"), 0.0))
            combined_raw = item.get("value")
            if combined_raw is None:
                combined_raw = item.get("combined")
            combined = clamp_unit(safe_float(combined_raw, 0.0))

            audio_raw = item.get("audio")
            video_raw = item.get("video")
            audio_value = None if audio_raw is None else clamp_unit(safe_float(audio_raw, 0.0))
            video_value = None if video_raw is None else clamp_unit(safe_float(video_raw, 0.0))

            if audio_value is not None:
                has_audio = True
            if video_value is not None:
                has_video = True

            normalized.append((t, combined, audio_value, video_value))

        normalized.sort(key=lambda item: item[0])
        self._points = normalized
        self._max_time = max(1.0, max((item[0] for item in normalized), default=1.0))
        self._threshold = clamp_unit(threshold)
        self._has_audio = has_audio
        self._has_video = has_video
        self._selected_time = None
        self._highlight_intervals = self._build_highlight_intervals()
        self.update()

    def _build_highlight_intervals(self) -> list[tuple[float, float]]:
        if not self._points:
            return []

        intervals: list[tuple[float, float]] = []
        start_time: float | None = None

        for idx, (t, combined, _, _) in enumerate(self._points):
            if combined >= self._threshold and start_time is None:
                start_time = t
            if combined < self._threshold and start_time is not None:
                intervals.append((start_time, t))
                start_time = None
            if idx == len(self._points) - 1 and start_time is not None:
                intervals.append((start_time, t))
                start_time = None

        return intervals

    def render_to_pixmap(self) -> QPixmap:
        pixmap = QPixmap(self.size())
        pixmap.fill(QColor("#ffffff"))
        painter = QPainter(pixmap)
        self.render(painter)
        painter.end()
        return pixmap

    def set_series_visibility(
        self,
        *,
        show_combined: bool | None = None,
        show_audio: bool | None = None,
        show_video: bool | None = None,
    ) -> None:
        if show_combined is not None:
            self._show_combined = bool(show_combined)
        if show_audio is not None:
            self._show_audio = bool(show_audio)
        if show_video is not None:
            self._show_video = bool(show_video)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#f8faff"))

        left = 64
        right = 20
        top = 16
        bottom = 40
        self._plot_rect = self.rect().adjusted(left, top, -right, -bottom)

        painter.setPen(QPen(QColor("#cfd8f4"), 1))
        painter.drawRect(self._plot_rect)

        if not self._points:
            painter.setPen(QColor("#64748b"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Недостаточно данных для объединенного графика вероятности лжи",
            )
            return

        for start_t, end_t in self._highlight_intervals:
            start_ratio = start_t / self._max_time if self._max_time > 0 else 0.0
            end_ratio = end_t / self._max_time if self._max_time > 0 else 0.0
            x1 = int(self._plot_rect.left() + self._plot_rect.width() * start_ratio)
            x2 = int(self._plot_rect.left() + self._plot_rect.width() * end_ratio)
            width = max(2, x2 - x1)
            painter.fillRect(x1, self._plot_rect.top(), width, self._plot_rect.height(), QColor(239, 68, 68, 44))

        painter.setFont(QFont("", 8))
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        for step in range(0, 5):
            ratio = step / 4
            y = int(self._plot_rect.top() + self._plot_rect.height() * ratio)
            painter.drawLine(self._plot_rect.left(), y, self._plot_rect.right(), y)
            value = 1.0 - ratio
            painter.setPen(QColor("#334155"))
            painter.drawText(8, y + 4, f"{value:.2f}")
            painter.setPen(QPen(QColor("#e2e8f0"), 1))

        for step in range(0, 6):
            ratio = step / 5
            x = int(self._plot_rect.left() + self._plot_rect.width() * ratio)
            painter.drawLine(x, self._plot_rect.top(), x, self._plot_rect.bottom())
            painter.setPen(QColor("#334155"))
            painter.drawText(x - 14, self._plot_rect.bottom() + 16, format_seconds(self._max_time * ratio))
            painter.setPen(QPen(QColor("#e2e8f0"), 1))

        threshold_y = int(self._plot_rect.bottom() - self._plot_rect.height() * self._threshold)
        painter.setPen(QPen(QColor("#ef4444"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(self._plot_rect.left(), threshold_y, self._plot_rect.right(), threshold_y)
        painter.setPen(QColor("#991b1b"))
        painter.drawText(self._plot_rect.left() + 8, max(self._plot_rect.top() + 12, threshold_y - 4), f"Порог {self._threshold:.2f}")

        def _draw_line(
            value_getter,
            color: QColor,
            width: int = 2,
            pen_style: Qt.PenStyle = Qt.PenStyle.SolidLine,
        ) -> None:
            line_points: list[tuple[int, int]] = []
            for t, combined, audio_value, video_value in self._points:
                value = value_getter(combined, audio_value, video_value)
                if value is None:
                    continue
                x_ratio = t / self._max_time if self._max_time > 0 else 0.0
                x = int(self._plot_rect.left() + self._plot_rect.width() * x_ratio)
                y = int(self._plot_rect.bottom() - self._plot_rect.height() * clamp_unit(value))
                line_points.append((x, y))

            if len(line_points) == 1:
                painter.setPen(QPen(color, width, pen_style))
                painter.drawPoint(line_points[0][0], line_points[0][1])
                return
            if len(line_points) < 2:
                return
            painter.setPen(QPen(color, width, pen_style))
            for idx in range(len(line_points) - 1):
                painter.drawLine(
                    line_points[idx][0],
                    line_points[idx][1],
                    line_points[idx + 1][0],
                    line_points[idx + 1][1],
                )

        if self._has_audio and self._show_audio:
            _draw_line(lambda _, audio_value, __: audio_value, QColor("#0ea5e9"), width=1, pen_style=Qt.PenStyle.DashLine)
        if self._has_video and self._show_video:
            _draw_line(lambda _, __, video_value: video_value, QColor("#16a34a"), width=1, pen_style=Qt.PenStyle.DashLine)
        if self._show_combined:
            _draw_line(lambda combined, _audio_value, _video_value: combined, QColor("#dc2626"), width=2)

        if self._selected_time is not None:
            selected_ratio = self._selected_time / self._max_time if self._max_time > 0 else 0.0
            selected_x = int(self._plot_rect.left() + self._plot_rect.width() * selected_ratio)
            painter.setPen(QPen(QColor("#ef4444"), 2))
            painter.drawLine(selected_x, self._plot_rect.top(), selected_x, self._plot_rect.bottom())

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if not self._points or not self._plot_rect.contains(event.pos()):
            return
        ratio = (event.position().x() - self._plot_rect.left()) / max(1, self._plot_rect.width())
        ratio = max(0.0, min(1.0, ratio))
        second = ratio * self._max_time
        self._selected_time = second
        self.time_clicked.emit(second)
        self.update()


class ProjectView(QWidget):
    back_requested = pyqtSignal()
    refresh_requested = pyqtSignal(str, str)
    run_selected = pyqtSignal(str, str)
    start_processing_requested = pyqtSignal(str, str, str, str, str)
    cancel_processing_requested = pyqtSignal(str, str)
    delete_project_requested = pyqtSignal(str)
    add_member_requested = pyqtSignal(str, str, str)
    change_member_role_requested = pyqtSignal(str, str, str)
    remove_member_requested = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.current_user: UserProfile | None = None
        self.current_project: Project | None = None
        self.current_members: list[ProjectMember] = []
        self.current_runs: list[ProcessingRun] = []
        self.current_timeline: list[dict[str, Any]] = []
        self.current_video_timeline: list[dict[str, Any]] = []
        self.current_audio_timeline: list[dict[str, Any]] = []
        self.current_combined_lie_timeline: list[dict[str, float | None]] = []
        self.current_audio_feature_series: dict[str, list[dict[str, float]]] = {}
        self.current_original_video_path: str | None = None
        self.current_overlay_video_path: str | None = None
        self.current_selected_run_id: str | None = None

        self._models: list[str] = []
        self._detectors: list[str] = []
        self._audio_providers: list[AudioProvider] = []
        self._can_edit_project = False
        self._can_manage_members = False
        self._video_enabled_series: set[str] = set()
        self._audio_enabled_series: set[str] = set()
        self._show_combined_risk = True
        self._show_combined_audio = True
        self._show_combined_video = True

        self._current_media_path: str | None = None
        self._pending_seek_ms: int | None = None
        self._resume_after_switch = False

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)

        self._build_ui()
        self._wire_player()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        header = QFrame()
        header.setObjectName("HeaderBar")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.back_button = QPushButton("Назад")
        self.back_button.setObjectName("SecondaryButton")
        self.back_button.clicked.connect(self.back_requested.emit)

        self.breadcrumb_label = QLabel("Dashboard / Проекты")
        self.breadcrumb_label.setObjectName("SectionHint")

        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("SecondaryButton")
        self.refresh_button.clicked.connect(self._emit_refresh)

        top_row.addWidget(self.back_button)
        top_row.addWidget(self.breadcrumb_label, 1)
        top_row.addWidget(self.refresh_button)

        self.project_title_label = QLabel("Проект")
        self.project_title_label.setObjectName("SectionTitle")

        header_layout.addLayout(top_row)
        header_layout.addWidget(self.project_title_label)
        root.addWidget(header)

        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionHint")
        self.status_label.hide()
        root.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        self.video_frame = QFrame()
        self.video_frame.setObjectName("DetailCard")
        video_layout = QVBoxLayout(self.video_frame)
        video_layout.setContentsMargins(12, 12, 12, 12)
        video_layout.setSpacing(10)

        video_header = QHBoxLayout()
        video_header.addWidget(QLabel("Видео анализа"), 1)

        self.overlay_checkbox = QCheckBox("Показывать оверлей модели")
        self.overlay_checkbox.setChecked(True)
        self.overlay_checkbox.toggled.connect(self._sync_video_source)
        video_header.addWidget(self.overlay_checkbox)

        video_layout.addLayout(video_header)

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumHeight(340)
        self.media_player.setVideoOutput(self.video_widget)
        video_layout.addWidget(self.video_widget)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.play_button = QPushButton("▶")
        self.play_button.setObjectName("SecondaryButton")
        self.play_button.setFixedWidth(46)
        self.play_button.clicked.connect(self._toggle_playback)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.media_player.setPosition)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("SectionHint")

        controls_row.addWidget(self.play_button)
        controls_row.addWidget(self.position_slider, 1)
        controls_row.addWidget(self.time_label)

        video_layout.addLayout(controls_row)
        left_col.addWidget(self.video_frame)

        chart_frame = QFrame()
        chart_frame.setObjectName("DetailCard")
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(12, 12, 12, 12)
        chart_layout.setSpacing(8)

        chart_title = QLabel("Видео: вероятности эмоций")
        chart_title.setObjectName("ProjectTitle")
        chart_layout.addWidget(chart_title)

        self.timeline_widget = EmotionTimelineWidget()
        self.timeline_widget.time_clicked.connect(self._seek_video_to_time)
        chart_layout.addWidget(self.timeline_widget, 1)
        self.video_series_controls_layout = QHBoxLayout()
        self.video_series_controls_layout.setSpacing(10)
        chart_layout.addLayout(self.video_series_controls_layout)

        left_col.addWidget(chart_frame)

        combined_lie_frame = QFrame()
        combined_lie_frame.setObjectName("DetailCard")
        combined_lie_layout = QVBoxLayout(combined_lie_frame)
        combined_lie_layout.setContentsMargins(12, 12, 12, 12)
        combined_lie_layout.setSpacing(8)

        combined_lie_title = QLabel("Ложь: объединенный график вероятности")
        combined_lie_title.setObjectName("ProjectTitle")
        combined_lie_layout.addWidget(combined_lie_title)

        self.combined_lie_widget = CombinedLieTimelineWidget()
        self.combined_lie_widget.time_clicked.connect(self._seek_video_to_time)
        combined_lie_layout.addWidget(self.combined_lie_widget, 1)
        self.combined_series_controls_layout = QHBoxLayout()
        self.combined_series_controls_layout.setSpacing(10)
        combined_lie_layout.addLayout(self.combined_series_controls_layout)

        left_col.addWidget(combined_lie_frame)

        audio_risk_frame = QFrame()
        audio_risk_frame.setObjectName("DetailCard")
        audio_risk_layout = QVBoxLayout(audio_risk_frame)
        audio_risk_layout.setContentsMargins(12, 12, 12, 12)
        audio_risk_layout.setSpacing(8)

        audio_risk_title = QLabel("Аудио: риск лжи")
        audio_risk_title.setObjectName("ProjectTitle")
        audio_risk_layout.addWidget(audio_risk_title)

        self.audio_timeline_widget = EmotionTimelineWidget()
        self.audio_timeline_widget.time_clicked.connect(self._seek_video_to_time)
        audio_risk_layout.addWidget(self.audio_timeline_widget, 1)
        self.audio_series_controls_layout = QHBoxLayout()
        self.audio_series_controls_layout.setSpacing(10)
        audio_risk_layout.addLayout(self.audio_series_controls_layout)

        left_col.addWidget(audio_risk_frame)

        audio_features_frame = QFrame()
        audio_features_frame.setObjectName("DetailCard")
        audio_features_layout = QVBoxLayout(audio_features_frame)
        audio_features_layout.setContentsMargins(12, 12, 12, 12)
        audio_features_layout.setSpacing(8)

        audio_features_title = QLabel("Аудио: графики признаков")
        audio_features_title.setObjectName("ProjectTitle")
        audio_features_layout.addWidget(audio_features_title)

        self.audio_features_charts_layout = QVBoxLayout()
        self.audio_features_charts_layout.setSpacing(8)
        audio_features_layout.addLayout(self.audio_features_charts_layout)

        left_col.addWidget(audio_features_frame)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        self.meta_frame = QFrame()
        self.meta_frame.setObjectName("DetailCard")
        meta_layout = QVBoxLayout(self.meta_frame)
        meta_layout.setContentsMargins(12, 12, 12, 12)
        meta_layout.setSpacing(8)

        self.project_status_label = QLabel("-")
        self.project_status_label.setObjectName("ProjectMeta")

        self.project_description_label = QLabel("Описание проекта")
        self.project_description_label.setObjectName("ProjectMeta")
        self.project_description_label.setWordWrap(True)

        self.project_updated_label = QLabel("Обновлен: -")
        self.project_updated_label.setObjectName("ProjectMeta")

        meta_layout.addWidget(self.project_status_label)
        meta_layout.addWidget(self.project_description_label)
        meta_layout.addWidget(self.project_updated_label)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(140)
        self.detector_combo = QComboBox()
        self.detector_combo.setMinimumWidth(150)
        self.processing_mode_combo = QComboBox()
        self.processing_mode_combo.setMinimumWidth(150)
        self.processing_mode_combo.addItem("Только видео", "video_only")
        self.processing_mode_combo.addItem("Только аудио", "audio_only")
        self.processing_mode_combo.addItem("Видео + аудио", "audio_and_video")
        self.processing_mode_combo.currentIndexChanged.connect(self._on_processing_mode_changed)
        self.audio_provider_combo = QComboBox()
        self.audio_provider_combo.setMinimumWidth(150)
        self.audio_provider_combo.addItem("Нет подходящих провайдеров", "__none__")

        self.start_processing_button = QPushButton("Запустить обработку")
        self.start_processing_button.setObjectName("PrimaryButton")
        self.start_processing_button.clicked.connect(self._emit_start_processing)
        self.cancel_processing_button = QPushButton("Остановить запуск")
        self.cancel_processing_button.setObjectName("SecondaryButton")
        self.cancel_processing_button.clicked.connect(self._emit_cancel_processing)

        self.export_button = QPushButton("Экспорт отчета")
        self.export_button.setObjectName("SecondaryButton")
        self.export_button.clicked.connect(self.export_report_pdf)
        self.delete_project_button = QPushButton("Удалить проект")
        self.delete_project_button.setObjectName("SecondaryButton")
        self.delete_project_button.clicked.connect(self._emit_delete_project)

        controls.addWidget(self.model_combo, 1)
        controls.addWidget(self.detector_combo, 1)
        controls.addWidget(self.processing_mode_combo, 1)
        controls.addWidget(self.audio_provider_combo, 1)
        controls.addWidget(self.start_processing_button)
        controls.addWidget(self.cancel_processing_button)
        controls.addWidget(self.export_button)
        controls.addWidget(self.delete_project_button)

        meta_layout.addLayout(controls)
        right_col.addWidget(self.meta_frame)

        runs_frame = QFrame()
        runs_frame.setObjectName("DetailCard")
        runs_layout = QVBoxLayout(runs_frame)
        runs_layout.setContentsMargins(12, 12, 12, 12)
        runs_layout.setSpacing(8)

        runs_title = QLabel("Запуски")
        runs_title.setObjectName("ProjectTitle")
        runs_layout.addWidget(runs_title)

        runs_nav_row = QHBoxLayout()
        runs_nav_row.setSpacing(6)

        self.prev_run_button = QPushButton("←")
        self.prev_run_button.setObjectName("SecondaryButton")
        self.prev_run_button.setFixedWidth(38)
        self.prev_run_button.clicked.connect(self._select_previous_run)

        self.runs_combo = QComboBox()
        self.runs_combo.currentIndexChanged.connect(self._on_run_combo_changed)
        self.next_run_button = QPushButton("→")
        self.next_run_button.setObjectName("SecondaryButton")
        self.next_run_button.setFixedWidth(38)
        self.next_run_button.clicked.connect(self._select_next_run)

        runs_nav_row.addWidget(self.prev_run_button)
        runs_nav_row.addWidget(self.runs_combo, 1)
        runs_nav_row.addWidget(self.next_run_button)
        runs_layout.addLayout(runs_nav_row)

        self.run_status_label = QLabel("Статус: -")
        self.run_status_label.setObjectName("ProjectMeta")
        self.run_model_hint_label = QLabel("-")
        self.run_model_hint_label.setObjectName("ProjectMeta")
        self.run_error_label = QLabel("")
        self.run_error_label.setObjectName("ErrorLabel")
        self.run_error_label.hide()

        runs_layout.addWidget(self.run_status_label)
        runs_layout.addWidget(self.run_model_hint_label)
        runs_layout.addWidget(self.run_error_label)
        right_col.addWidget(runs_frame)

        members_frame = QFrame()
        members_frame.setObjectName("DetailCard")
        members_layout = QVBoxLayout(members_frame)
        members_layout.setContentsMargins(12, 12, 12, 12)
        members_layout.setSpacing(8)

        members_title = QLabel("Участники")
        members_title.setObjectName("ProjectTitle")
        members_layout.addWidget(members_title)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)

        self.member_login_input = QLineEdit()
        self.member_login_input.setPlaceholderText("Логин пользователя")

        self.member_role_combo = QComboBox()
        self.member_role_combo.addItem("Редактор", "editor")
        self.member_role_combo.addItem("Наблюдатель", "viewer")

        self.add_member_button = QPushButton("Добавить")
        self.add_member_button.setObjectName("SecondaryButton")
        self.add_member_button.clicked.connect(self._emit_add_member)

        add_row.addWidget(self.member_login_input, 1)
        add_row.addWidget(self.member_role_combo)
        add_row.addWidget(self.add_member_button)
        members_layout.addLayout(add_row)

        self.members_table = QTableWidget(0, 4)
        self.members_table.setObjectName("RunsTable")
        self.members_table.setHorizontalHeaderLabels(["Пользователь", "Роль", "Сист. роль", "Действия"])
        self.members_table.verticalHeader().setVisible(False)
        self.members_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.members_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.members_table.setMinimumHeight(220)
        header_view = self.members_table.horizontalHeader()
        header_view.setStretchLastSection(True)
        self.members_table.setColumnWidth(0, 170)
        self.members_table.setColumnWidth(1, 145)
        self.members_table.setColumnWidth(2, 95)

        members_layout.addWidget(self.members_table)
        right_col.addWidget(members_frame, 1)

        content_layout.addLayout(left_col, 2)
        content_layout.addLayout(right_col, 1)

        self.scroll.setWidget(content)
        root.addWidget(self.scroll, 1)

    def _wire_player(self) -> None:
        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.durationChanged.connect(self._on_player_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_player_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_player_media_status_changed)
        self.media_player.errorOccurred.connect(self._on_player_error)

    def set_user(self, user: UserProfile) -> None:
        self.current_user = user

    def set_models(self, models: list[str]) -> None:
        self._models = [item.strip() for item in models if item.strip()]
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(self._models)
        self.model_combo.blockSignals(False)
        self._update_permissions_state()

    def set_detectors(self, detectors: list[str]) -> None:
        self._detectors = [item.strip() for item in detectors if item.strip()]
        self.detector_combo.blockSignals(True)
        self.detector_combo.clear()
        for detector in self._detectors:
            self.detector_combo.addItem(detector, detector)
        self.detector_combo.blockSignals(False)
        self._update_permissions_state()

    def set_audio_providers(self, providers: list[AudioProvider]) -> None:
        self._audio_providers = [item for item in providers if item.code]
        self._refresh_audio_providers_for_mode(
            str(self.processing_mode_combo.currentData() or "video_only").strip().lower()
        )
        self._on_processing_mode_changed()
        self._update_permissions_state()

    def set_loading(self, loading: bool, message: str | None = None) -> None:
        self.back_button.setDisabled(loading)
        self.refresh_button.setDisabled(loading)
        self.start_processing_button.setDisabled(loading or not self._can_edit_project)
        self.cancel_processing_button.setDisabled(loading or not self._can_edit_project)
        self.model_combo.setDisabled(loading or not self._can_edit_project)
        self.detector_combo.setDisabled(loading or not self._can_edit_project)
        self.processing_mode_combo.setDisabled(loading or not self._can_edit_project)
        self.audio_provider_combo.setDisabled(loading or not self._can_edit_project)
        self.delete_project_button.setDisabled(loading or not self._can_edit_project)
        self.export_button.setDisabled(loading)
        self.add_member_button.setDisabled(loading or not self._can_manage_members)
        self.member_login_input.setDisabled(loading or not self._can_manage_members)
        self.member_role_combo.setDisabled(loading or not self._can_manage_members)
        if loading and message:
            self.set_status_message(message, is_error=False)

    def set_status_message(self, message: str, *, is_error: bool) -> None:
        if not message:
            self.status_label.hide()
            self.status_label.clear()
            return
        self.status_label.setStyleSheet("color: #c63f57;" if is_error else "color: #4d5a86;")
        self.status_label.setText(message)
        self.status_label.show()

    def set_project_data(
        self,
        *,
        project: Project,
        members: list[ProjectMember],
        runs: list[ProcessingRun],
        selected_run_id: str | None,
        video_timeline_points: list[dict[str, Any]],
        audio_timeline_points: list[dict[str, Any]],
        audio_feature_series: dict[str, list[dict[str, float]]],
        original_video_path: str | None,
        overlay_video_path: str | None,
    ) -> None:
        self.current_project = project
        self.current_members = list(members)
        self.current_runs = list(runs)
        self.current_selected_run_id = selected_run_id
        self.current_video_timeline = list(video_timeline_points)
        self.current_audio_timeline = list(audio_timeline_points)
        self.current_audio_feature_series = {
            str(name): list(points)
            for name, points in audio_feature_series.items()
        }
        self.current_combined_lie_timeline = self._build_combined_lie_timeline(
            self.current_video_timeline,
            self.current_audio_timeline,
        )
        self.current_timeline = (
            list(self.current_video_timeline)
            if self.current_video_timeline
            else list(self.current_audio_timeline)
        )
        self.current_original_video_path = original_video_path
        self.current_overlay_video_path = overlay_video_path

        self.project_title_label.setText(project.title)
        self.breadcrumb_label.setText(f"Dashboard / Проекты / {project.title}")
        self.project_status_label.setText(f"Статус проекта: {project_status_label(project.status)}")
        self.project_description_label.setText(project.description or "Описание не задано")
        self.project_updated_label.setText(f"Обновлен: {format_datetime(project.updated_at)}")

        self._refresh_video_timeline_view()
        self.combined_lie_widget.set_points(self.current_combined_lie_timeline)
        self._refresh_combined_timeline_view()
        self._refresh_audio_timeline_view()
        self._render_audio_feature_widgets()
        self._populate_runs_combo()
        self._render_members_table()
        self._update_permissions_state()
        self._sync_video_source()

    def _render_audio_feature_widgets(self) -> None:
        self._clear_layout(self.audio_features_charts_layout)
        if not self.current_audio_feature_series:
            empty_label = QLabel("Аудио-признаки не обнаружены")
            empty_label.setObjectName("SectionHint")
            self.audio_features_charts_layout.addWidget(empty_label)
            return

        for feature_name, points in self.current_audio_feature_series.items():
            feature_frame = QFrame()
            feature_frame.setObjectName("DetailCard")
            feature_layout = QVBoxLayout(feature_frame)
            feature_layout.setContentsMargins(8, 8, 8, 8)
            feature_layout.setSpacing(6)

            title = QLabel(feature_label_ru(feature_name))
            title.setObjectName("SectionHint")
            feature_layout.addWidget(title)

            chart = MetricTimelineWidget()
            chart.set_points(points)
            chart.time_clicked.connect(self._seek_video_to_time)
            feature_layout.addWidget(chart, 1)

            self.audio_features_charts_layout.addWidget(feature_frame)

    def _clear_layout(self, layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                while child_layout.count():
                    child_item = child_layout.takeAt(0)
                    child_widget = child_item.widget()
                    if child_widget is not None:
                        child_widget.deleteLater()

    @staticmethod
    def _collect_series_names(timeline_points: list[dict[str, Any]]) -> list[str]:
        names: set[str] = set()
        for item in timeline_points:
            if not isinstance(item, dict):
                continue
            probs = item.get("probabilities")
            if not isinstance(probs, dict):
                continue
            for key in probs.keys():
                clean_key = str(key).strip().lower()
                if clean_key:
                    names.add(clean_key)
        return sorted(names)

    @staticmethod
    def _filter_timeline_series(
        timeline_points: list[dict[str, Any]],
        enabled_series: set[str],
    ) -> list[dict[str, Any]]:
        if not enabled_series:
            return []
        filtered: list[dict[str, Any]] = []
        for item in timeline_points:
            if not isinstance(item, dict):
                continue
            probs = item.get("probabilities")
            if not isinstance(probs, dict):
                continue
            sub_probs = {
                str(name): value
                for name, value in probs.items()
                if str(name).strip().lower() in enabled_series
            }
            if not sub_probs:
                continue
            filtered.append(
                {
                    "time": safe_float(item.get("time"), 0.0),
                    "probabilities": sub_probs,
                }
            )
        return filtered

    def _refresh_video_timeline_view(self) -> None:
        series_names = self._collect_series_names(self.current_video_timeline)
        if not self._video_enabled_series:
            self._video_enabled_series = set(series_names)
        else:
            self._video_enabled_series = {
                name for name in self._video_enabled_series if name in series_names
            } or set(series_names)
        self._render_series_toggles(
            layout=self.video_series_controls_layout,
            series_names=series_names,
            enabled_series=self._video_enabled_series,
            source="video",
        )
        self.timeline_widget.set_points(
            self._filter_timeline_series(self.current_video_timeline, self._video_enabled_series)
        )

    def _refresh_audio_timeline_view(self) -> None:
        series_names = self._collect_series_names(self.current_audio_timeline)
        if not self._audio_enabled_series:
            self._audio_enabled_series = set(series_names)
        else:
            self._audio_enabled_series = {
                name for name in self._audio_enabled_series if name in series_names
            } or set(series_names)
        self._render_series_toggles(
            layout=self.audio_series_controls_layout,
            series_names=series_names,
            enabled_series=self._audio_enabled_series,
            source="audio",
        )
        self.audio_timeline_widget.set_points(
            self._filter_timeline_series(self.current_audio_timeline, self._audio_enabled_series)
        )

    def _refresh_combined_timeline_view(self) -> None:
        self.combined_lie_widget.set_series_visibility(
            show_combined=self._show_combined_risk,
            show_audio=self._show_combined_audio,
            show_video=self._show_combined_video,
        )
        self._render_combined_series_toggles()

    def _render_series_toggles(
        self,
        *,
        layout: QLayout,
        series_names: list[str],
        enabled_series: set[str],
        source: str,
    ) -> None:
        self._clear_layout(layout)
        if not series_names:
            hint = QLabel("Нет параметров для отображения")
            hint.setObjectName("SectionHint")
            layout.addWidget(hint)
            return

        caption = QLabel("Параметры:")
        caption.setObjectName("SectionHint")
        layout.addWidget(caption)

        for name in series_names:
            checkbox = QCheckBox(emotion_label_ru(name))
            checkbox.setChecked(name in enabled_series)
            checkbox.toggled.connect(
                lambda checked, metric=name, chart=source: self._on_series_toggle(chart, metric, checked)
            )
            layout.addWidget(checkbox)

        if isinstance(layout, QHBoxLayout):
            layout.addStretch(1)

    def _on_series_toggle(self, source: str, series_name: str, enabled: bool) -> None:
        name = str(series_name).strip().lower()
        if not name:
            return

        if source == "video":
            if enabled:
                self._video_enabled_series.add(name)
            else:
                self._video_enabled_series.discard(name)
            self.timeline_widget.set_points(
                self._filter_timeline_series(self.current_video_timeline, self._video_enabled_series)
            )
            return

        if enabled:
            self._audio_enabled_series.add(name)
        else:
            self._audio_enabled_series.discard(name)
        self.audio_timeline_widget.set_points(
            self._filter_timeline_series(self.current_audio_timeline, self._audio_enabled_series)
        )

    def _render_combined_series_toggles(self) -> None:
        self._clear_layout(self.combined_series_controls_layout)

        caption = QLabel("Параметры:")
        caption.setObjectName("SectionHint")
        self.combined_series_controls_layout.addWidget(caption)

        combined_cb = QCheckBox("Объединенный риск")
        combined_cb.setChecked(self._show_combined_risk)
        combined_cb.toggled.connect(lambda checked: self._on_combined_series_toggle("combined", checked))
        self.combined_series_controls_layout.addWidget(combined_cb)

        if any(item.get("audio") is not None for item in self.current_combined_lie_timeline):
            audio_cb = QCheckBox("Аудио-риск")
            audio_cb.setChecked(self._show_combined_audio)
            audio_cb.toggled.connect(lambda checked: self._on_combined_series_toggle("audio", checked))
            self.combined_series_controls_layout.addWidget(audio_cb)

        if any(item.get("video") is not None for item in self.current_combined_lie_timeline):
            video_cb = QCheckBox("Видео-риск")
            video_cb.setChecked(self._show_combined_video)
            video_cb.toggled.connect(lambda checked: self._on_combined_series_toggle("video", checked))
            self.combined_series_controls_layout.addWidget(video_cb)

        self.combined_series_controls_layout.addStretch(1)

    def _on_combined_series_toggle(self, series_name: str, enabled: bool) -> None:
        if series_name == "combined":
            self._show_combined_risk = enabled
        elif series_name == "audio":
            self._show_combined_audio = enabled
        elif series_name == "video":
            self._show_combined_video = enabled
        else:
            return

        self.combined_lie_widget.set_series_visibility(
            show_combined=self._show_combined_risk,
            show_audio=self._show_combined_audio,
            show_video=self._show_combined_video,
        )

    def _build_combined_lie_timeline(
        self,
        video_timeline: list[dict[str, Any]],
        audio_timeline: list[dict[str, Any]],
    ) -> list[dict[str, float | None]]:
        audio_series = self._extract_risk_series(audio_timeline, source="audio")
        video_series = self._extract_risk_series(video_timeline, source="video")
        if not audio_series and not video_series:
            return []

        timestamps = sorted({time_value for time_value, _ in audio_series} | {time_value for time_value, _ in video_series})
        if not timestamps:
            return []

        result: list[dict[str, float | None]] = []
        audio_idx = 0
        video_idx = 0

        for time_value in timestamps:
            audio_value: float | None = None
            video_value: float | None = None

            if audio_series:
                while audio_idx + 1 < len(audio_series) and audio_series[audio_idx + 1][0] <= time_value:
                    audio_idx += 1
                audio_value = audio_series[audio_idx][1]

            if video_series:
                while video_idx + 1 < len(video_series) and video_series[video_idx + 1][0] <= time_value:
                    video_idx += 1
                video_value = video_series[video_idx][1]

            if audio_value is not None and video_value is not None:
                combined = clamp_unit(audio_value * 0.6 + video_value * 0.4)
            elif audio_value is not None:
                combined = clamp_unit(audio_value)
            elif video_value is not None:
                combined = clamp_unit(video_value)
            else:
                combined = 0.0

            result.append(
                {
                    "time": round(time_value, 3),
                    "value": combined,
                    "audio": audio_value,
                    "video": video_value,
                }
            )

        return result

    def _extract_risk_series(
        self,
        timeline: list[dict[str, Any]],
        *,
        source: str,
    ) -> list[tuple[float, float]]:
        series: list[tuple[float, float]] = []

        for item in timeline:
            if not isinstance(item, dict):
                continue

            probs_raw = item.get("probabilities")
            if not isinstance(probs_raw, dict):
                continue

            current_time = max(0.0, safe_float(item.get("time"), 0.0))
            risk_value = self._risk_from_probabilities(probs_raw, source=source)
            if risk_value is None:
                continue
            series.append((current_time, clamp_unit(risk_value)))

        series.sort(key=lambda payload: payload[0])
        deduplicated: list[tuple[float, float]] = []
        for t, value in series:
            if deduplicated and abs(deduplicated[-1][0] - t) < 1e-9:
                deduplicated[-1] = (t, value)
            else:
                deduplicated.append((t, value))
        return deduplicated

    def _risk_from_probabilities(self, probs_raw: dict[str, Any], *, source: str) -> float | None:
        normalized: dict[str, float] = {}
        for key, value in probs_raw.items():
            clean_key = str(key).strip().lower()
            if not clean_key:
                continue
            normalized[clean_key] = clamp_unit(safe_float(value, 0.0))

        if not normalized:
            return None

        for risk_key in LIE_RISK_KEYS:
            if risk_key in normalized:
                return normalized[risk_key]

        if "truth" in normalized:
            return clamp_unit(1.0 - normalized["truth"])

        if source == "audio":
            return max(normalized.values(), default=0.0)

        fear = normalized.get("fear", 0.0)
        angry = normalized.get("angry", 0.0)
        surprise = normalized.get("surprise", 0.0)
        disgust = normalized.get("disgust", 0.0)
        sad = normalized.get("sad", 0.0)
        neutral = normalized.get("neutral", 0.0)
        happy = normalized.get("happy", 0.0)

        heuristic_score = (
            fear * 0.32
            + angry * 0.26
            + surprise * 0.18
            + disgust * 0.12
            + sad * 0.08
            + (1.0 - neutral) * 0.10
            - happy * 0.06
        )
        return clamp_unit(heuristic_score)

    def _extract_lie_intervals_from_points(
        self,
        points: list[dict[str, float | None]],
        *,
        threshold: float = LIE_RISK_THRESHOLD,
    ) -> list[tuple[float, float]]:
        if not points:
            return []

        intervals: list[tuple[float, float]] = []
        current_start: float | None = None
        threshold_value = clamp_unit(threshold)

        for idx, item in enumerate(points):
            t = max(0.0, safe_float(item.get("time"), 0.0))
            score = clamp_unit(safe_float(item.get("value"), 0.0))

            if score >= threshold_value and current_start is None:
                current_start = t

            if score < threshold_value and current_start is not None:
                intervals.append((current_start, t))
                current_start = None

            if idx == len(points) - 1 and current_start is not None:
                intervals.append((current_start, t))
                current_start = None

        return intervals

    def _emit_refresh(self) -> None:
        if self.current_project is None:
            return
        run_id = self.current_selected_run_id or ""
        self.refresh_requested.emit(str(self.current_project.id), run_id)

    def _emit_start_processing(self) -> None:
        if self.current_project is None:
            return
        model_name = self.model_combo.currentText().strip()
        detector_name = str(self.detector_combo.currentData() or "").strip().lower()
        processing_mode = str(self.processing_mode_combo.currentData() or "video_only").strip().lower()
        audio_provider_raw = str(self.audio_provider_combo.currentData() or "").strip().lower()
        audio_provider = "" if audio_provider_raw in {"", "__none__"} else audio_provider_raw
        if processing_mode in {"video_only", "audio_and_video"} and not model_name:
            self.set_status_message("Выберите модель для запуска обработки.", is_error=True)
            return
        if processing_mode in {"video_only", "audio_and_video"} and not detector_name:
            self.set_status_message("Выберите детектор лица для запуска обработки.", is_error=True)
            return
        if processing_mode in {"audio_only", "audio_and_video"} and audio_provider_raw in {"", "__none__"}:
            self.set_status_message("Для выбранного режима нет подходящего аудио-провайдера.", is_error=True)
            return
        self.start_processing_requested.emit(
            str(self.current_project.id),
            model_name,
            detector_name,
            processing_mode,
            audio_provider,
        )

    def _on_processing_mode_changed(self) -> None:
        mode = str(self.processing_mode_combo.currentData() or "video_only").strip().lower()
        video_enabled = mode in {"video_only", "audio_and_video"}
        audio_enabled = mode in {"audio_only", "audio_and_video"}
        self._refresh_audio_providers_for_mode(mode)
        self.model_combo.setEnabled(self._can_edit_project and video_enabled)
        self.detector_combo.setEnabled(self._can_edit_project and video_enabled)
        has_compatible_audio_provider = str(self.audio_provider_combo.currentData() or "") != "__none__"
        self.audio_provider_combo.setEnabled(self._can_edit_project and audio_enabled and has_compatible_audio_provider)

    def _refresh_audio_providers_for_mode(self, mode: str) -> None:
        selected_code = str(self.audio_provider_combo.currentData() or "").strip().lower()
        self.audio_provider_combo.blockSignals(True)
        self.audio_provider_combo.clear()

        if mode == "audio_and_video":
            video_providers = [item for item in self._audio_providers if item.is_video_provider]
            if video_providers:
                providers = video_providers
            else:
                providers = [item for item in self._audio_providers if item.supports_video]
        elif mode == "audio_only":
            providers = [item for item in self._audio_providers if item.supports_audio]
        else:
            providers = [item for item in self._audio_providers if item.supports_audio or item.supports_video]

        for provider in providers:
            self.audio_provider_combo.addItem(provider.title, provider.code)

        if self.audio_provider_combo.count() == 0:
            self.audio_provider_combo.addItem("Нет подходящих провайдеров", "__none__")

        if selected_code:
            selected_index = self.audio_provider_combo.findData(selected_code)
            if selected_index >= 0:
                self.audio_provider_combo.setCurrentIndex(selected_index)

        self.audio_provider_combo.blockSignals(False)

    def _emit_cancel_processing(self) -> None:
        if self.current_project is None:
            return
        run_id = self.current_selected_run_id or ""
        if not run_id:
            self.set_status_message("Выберите запуск для остановки.", is_error=True)
            return
        self.cancel_processing_requested.emit(str(self.current_project.id), run_id)

    def _emit_delete_project(self) -> None:
        if self.current_project is None:
            return

        reply = QMessageBox.question(
            self,
            "Удаление проекта",
            "Удалить проект? Это действие нельзя отменить.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.delete_project_requested.emit(str(self.current_project.id))

    def _populate_runs_combo(self) -> None:
        self.runs_combo.blockSignals(True)
        self.runs_combo.clear()

        if not self.current_runs:
            self.runs_combo.addItem("Запусков пока нет", "")
            self.run_status_label.setText("Статус запуска: -")
            self.run_model_hint_label.setText("-")
            self.run_error_label.hide()
            self.runs_combo.blockSignals(False)
            return

        for run in self.current_runs:
            label = f"{format_datetime(run.created_at)} · {run_status_label(run.status)}"
            self.runs_combo.addItem(label, str(run.id))

        target_index = 0
        if self.current_selected_run_id:
            for idx in range(self.runs_combo.count()):
                if str(self.runs_combo.itemData(idx)) == self.current_selected_run_id:
                    target_index = idx
                    break
        self.runs_combo.setCurrentIndex(target_index)
        self._sync_runs_nav_buttons()

        self.runs_combo.blockSignals(False)
        self._update_current_run_meta()

    def _on_run_combo_changed(self, _: int) -> None:
        if self.current_project is None:
            return

        run_id = str(self.runs_combo.currentData() or "")
        self.current_selected_run_id = run_id or None
        self._sync_runs_nav_buttons()
        self._update_current_run_meta()
        self.run_selected.emit(str(self.current_project.id), run_id)

    def _select_previous_run(self) -> None:
        index = self.runs_combo.currentIndex()
        if index <= 0:
            return
        self.runs_combo.setCurrentIndex(index - 1)

    def _select_next_run(self) -> None:
        index = self.runs_combo.currentIndex()
        if index < 0 or index >= self.runs_combo.count() - 1:
            return
        self.runs_combo.setCurrentIndex(index + 1)

    def _sync_runs_nav_buttons(self) -> None:
        count = self.runs_combo.count()
        index = self.runs_combo.currentIndex()
        has_runs = count > 1
        self.prev_run_button.setEnabled(has_runs and index > 0)
        self.next_run_button.setEnabled(has_runs and index >= 0 and index < count - 1)

    def _update_current_run_meta(self) -> None:
        run_id = self.current_selected_run_id
        run: ProcessingRun | None = None
        if run_id:
            run = next((item for item in self.current_runs if str(item.id) == run_id), None)

        if run is None:
            self.run_status_label.setText("Статус запуска: -")
            self.run_model_hint_label.setText("-")
            self.run_error_label.hide()
            self.cancel_processing_button.setEnabled(False)
            return

        status_text = run_status_label(run.status)
        self.run_status_label.setText(
            f"Статус запуска: {status_text} · task={run.video_task_id[:10]} · режим={run.launch_mode}"
        )

        if run.completed_at:
            self.run_model_hint_label.setText(f"Завершен: {format_datetime(run.completed_at)}")
        else:
            self.run_model_hint_label.setText(f"Обновлен: {format_datetime(run.updated_at)}")

        if run.error:
            self.run_error_label.setText(run.error)
            self.run_error_label.show()
        else:
            self.run_error_label.hide()
        self.cancel_processing_button.setEnabled(
            self._can_edit_project and run.status in {"scheduled", "pending", "running"}
        )

    def _render_members_table(self) -> None:
        project = self.current_project
        members = self.current_members

        self.members_table.setRowCount(len(members))

        for row, member in enumerate(members):
            user_text = member.ui_name
            if project is not None and member.user_id == project.creator_id:
                user_text = f"{user_text} (создатель)"

            self.members_table.setItem(row, 0, QTableWidgetItem(user_text))
            self.members_table.setItem(row, 2, QTableWidgetItem(member.user_role or "-"))

            role_cell = QWidget()
            role_layout = QHBoxLayout(role_cell)
            role_layout.setContentsMargins(0, 0, 0, 0)
            role_layout.setSpacing(4)

            role_combo = QComboBox()
            role_combo.addItem("Редактор", "editor")
            role_combo.addItem("Наблюдатель", "viewer")
            role_combo.setCurrentIndex(0 if member.member_role == "editor" else 1)

            apply_button = QPushButton("OK")
            apply_button.setObjectName("SecondaryButton")
            apply_button.setFixedWidth(46)

            role_layout.addWidget(role_combo, 1)
            role_layout.addWidget(apply_button, 0)

            can_modify_role = self._can_manage_members and project is not None and member.user_id != project.creator_id
            role_combo.setEnabled(can_modify_role)
            apply_button.setEnabled(can_modify_role)
            apply_button.clicked.connect(
                lambda _checked=False, uid=str(member.user_id), combo=role_combo: self._emit_change_member_role(uid, combo)
            )

            self.members_table.setCellWidget(row, 1, role_cell)

            remove_button = QPushButton("Удалить")
            remove_button.setObjectName("SecondaryButton")
            can_remove = self._can_manage_members and project is not None and member.user_id != project.creator_id
            remove_button.setEnabled(can_remove)
            remove_button.clicked.connect(
                lambda _checked=False, uid=str(member.user_id): self._emit_remove_member(uid)
            )
            self.members_table.setCellWidget(row, 3, remove_button)

    def _emit_add_member(self) -> None:
        if self.current_project is None:
            return

        login = self.member_login_input.text().strip()
        role = str(self.member_role_combo.currentData() or "")

        if len(login) < 3:
            self.set_status_message("Укажите логин пользователя (минимум 3 символа).", is_error=True)
            return
        if role not in {"viewer", "editor"}:
            self.set_status_message("Выберите роль участника.", is_error=True)
            return

        self.add_member_requested.emit(str(self.current_project.id), login, role)

    def _emit_change_member_role(self, user_id: str, combo: QComboBox) -> None:
        if self.current_project is None:
            return
        role = str(combo.currentData() or "")
        if role not in {"viewer", "editor"}:
            self.set_status_message("Некорректная роль участника.", is_error=True)
            return
        self.change_member_role_requested.emit(str(self.current_project.id), user_id, role)

    def _emit_remove_member(self, user_id: str) -> None:
        if self.current_project is None:
            return

        reply = QMessageBox.question(
            self,
            "Удаление участника",
            "Удалить пользователя из проекта?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.remove_member_requested.emit(str(self.current_project.id), user_id)

    def _update_permissions_state(self) -> None:
        project = self.current_project
        user = self.current_user

        self._can_edit_project = False
        self._can_manage_members = False

        if project is not None and user is not None:
            if user.role == "admin" or user.id == project.creator_id:
                self._can_edit_project = True
                self._can_manage_members = True
            else:
                membership = next((item for item in self.current_members if item.user_id == user.id), None)
                if membership is not None and membership.member_role == "editor":
                    self._can_edit_project = True
                    self._can_manage_members = True

        self.start_processing_button.setEnabled(self._can_edit_project and bool(self._models))
        self.processing_mode_combo.setEnabled(self._can_edit_project)
        self._on_processing_mode_changed()
        self.delete_project_button.setEnabled(self._can_edit_project)
        self.add_member_button.setEnabled(self._can_manage_members)
        self.member_login_input.setEnabled(self._can_manage_members)
        self.member_role_combo.setEnabled(self._can_manage_members)

    def _toggle_playback(self) -> None:
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def _on_player_position_changed(self, position_ms: int) -> None:
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(position_ms)
        self.position_slider.blockSignals(False)

        duration_sec = self.media_player.duration() / 1000 if self.media_player.duration() > 0 else 0
        current_sec = position_ms / 1000 if position_ms > 0 else 0
        self.time_label.setText(f"{format_seconds(current_sec)} / {format_seconds(duration_sec)}")

    def _on_player_duration_changed(self, duration_ms: int) -> None:
        self.position_slider.setRange(0, max(0, duration_ms))

    def _on_player_state_changed(self, state) -> None:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setText("⏸")
        else:
            self.play_button.setText("▶")

    def _on_player_media_status_changed(self, status) -> None:
        if status in {
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        }:
            if self._pending_seek_ms is not None:
                self.media_player.setPosition(self._pending_seek_ms)
                self._pending_seek_ms = None
            if self._resume_after_switch:
                self.media_player.play()
                self._resume_after_switch = False

    def _on_player_error(self, *_: object) -> None:
        if self.media_player.error() == QMediaPlayer.Error.NoError:
            return
        error_text = self.media_player.errorString().strip() or "Не удалось открыть видео"
        self.set_status_message(error_text, is_error=True)

    def _sync_video_source(self) -> None:
        preferred_path = self.current_original_video_path
        if self.overlay_checkbox.isChecked() and self.current_overlay_video_path:
            preferred_path = self.current_overlay_video_path

        if not preferred_path:
            self.media_player.stop()
            self._current_media_path = None
            self.time_label.setText("00:00 / 00:00")
            return

        if not Path(preferred_path).exists():
            self._current_media_path = None
            self.set_status_message("Видеофайл недоступен локально.", is_error=True)
            return

        if self._current_media_path == preferred_path:
            return

        current_position = self.media_player.position()
        self._pending_seek_ms = max(0, current_position)
        self._resume_after_switch = self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

        self.media_player.stop()
        self.media_player.setSource(QUrl.fromLocalFile(str(Path(preferred_path).resolve())))
        self._current_media_path = preferred_path

    def _seek_video_to_time(self, second: float) -> None:
        duration_sec = self.media_player.duration() / 1000 if self.media_player.duration() > 0 else 0
        if duration_sec <= 0:
            return

        clamped = max(0.0, min(duration_sec, second))
        self.media_player.setPosition(int(clamped * 1000))

    def export_report_pdf(self) -> None:
        project = self.current_project
        if project is None:
            QMessageBox.warning(self, "Отчет", "Откройте проект перед экспортом отчета")
            return

        if not self.current_timeline and not self.current_combined_lie_timeline:
            QMessageBox.warning(self, "Отчет", "Нет данных графиков для экспорта")
            return

        run_id = self.current_selected_run_id or "no-run"
        default_name = f"{project.title}_{run_id}.pdf".replace(" ", "_")
        filename, _ = QFileDialog.getSaveFileName(self, "Сохранить отчет", default_name, "PDF Files (*.pdf)")
        if not filename:
            return

        output_path = filename if filename.lower().endswith(".pdf") else f"{filename}.pdf"

        try:
            writer = QPdfWriter(output_path)
            writer.setResolution(150)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageOrientation(QPageLayout.Orientation.Portrait)

            painter = QPainter(writer)
            if not painter.isActive():
                raise RuntimeError("Не удалось открыть PDF writer")

            page_rect = writer.pageLayout().paintRectPixels(writer.resolution())
            margin = 48
            y = margin

            title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
            section_font = QFont("Segoe UI", 11, QFont.Weight.Bold)
            text_font = QFont("Segoe UI", 10)
            line_height = 22

            painter.setFont(title_font)
            painter.setPen(QColor("#1f2746"))
            painter.drawText(margin, y + 24, "Отчет проекта EmotionVision")
            y += 46

            painter.setFont(text_font)
            painter.setPen(QColor("#1f2746"))
            metadata_lines = [
                f"Проект: {project.title}",
                f"Статус: {project_status_label(project.status)}",
                f"Обновлен: {format_datetime(project.updated_at)}",
                f"Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                f"Выбранный запуск: {self.current_selected_run_id or '-'}",
            ]
            for line in metadata_lines:
                painter.drawText(margin, y, line)
                y += line_height

            y += 6
            painter.setFont(section_font)
            painter.drawText(margin, y, "Сводка эмоций и риска лжи")
            y += 20

            painter.setFont(text_font)
            summary_lines = self._build_timeline_summary_lines()
            for line in summary_lines:
                if y > page_rect.height() - margin:
                    writer.newPage()
                    page_rect = writer.pageLayout().paintRectPixels(writer.resolution())
                    y = margin
                    painter.setFont(text_font)
                painter.drawText(margin, y, line)
                y += line_height

            if self.current_combined_lie_timeline:
                chart_widget = self.combined_lie_widget
                chart_title = "Объединенный график вероятности лжи"
            elif self.current_video_timeline:
                chart_widget = self.timeline_widget
                chart_title = "Видео: график вероятностей эмоций"
            else:
                chart_widget = self.audio_timeline_widget
                chart_title = "Аудио: график риска лжи"

            chart_pixmap = chart_widget.render_to_pixmap()
            if not chart_pixmap.isNull():
                writer.setPageOrientation(QPageLayout.Orientation.Landscape)
                writer.newPage()
                page_rect = writer.pageLayout().paintRectPixels(writer.resolution())
                y = margin

                painter.setFont(section_font)
                painter.setPen(QColor("#1f2746"))
                painter.drawText(margin, y + 20, chart_title)
                y += 34

                max_width = page_rect.width() - margin * 2
                max_height = page_rect.height() - y - margin
                if max_width > 10 and max_height > 10:
                    scaled = chart_pixmap.scaled(
                        max_width,
                        max_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    x = (page_rect.width() - scaled.width()) // 2
                    painter.drawPixmap(x, y, scaled)

            painter.end()
            self.set_status_message(f"Отчет сохранен: {output_path}", is_error=False)
        except Exception as exc:
            QMessageBox.critical(self, "Отчет", f"Ошибка генерации отчета: {exc}")

    def _build_timeline_summary_lines(self) -> list[str]:
        if not self.current_timeline and not self.current_combined_lie_timeline:
            return ["Нет данных по эмоциям и риску лжи."]

        dominant_counter: Counter[str] = Counter()
        average_scores: defaultdict[str, list[float]] = defaultdict(list)

        for item in self.current_timeline:
            probs = item.get("probabilities")
            if not isinstance(probs, dict):
                continue

            best_emotion = None
            best_value = -1.0
            for emotion, value in probs.items():
                probability = clamp_unit(safe_float(value, 0.0))
                average_scores[str(emotion)].append(probability)
                if probability > best_value:
                    best_value = probability
                    best_emotion = str(emotion)

            if best_emotion:
                dominant_counter[best_emotion] += 1

        lines: list[str] = []
        if self.current_timeline:
            lines.append(f"Всего точек таймлайна эмоций: {len(self.current_timeline)}")

        if dominant_counter:
            dominant_emotion, dominant_count = dominant_counter.most_common(1)[0]
            lines.append(f"Доминирующая эмоция: {emotion_label_ru(dominant_emotion)} ({dominant_count} точек)")

        for emotion, values in sorted(
            average_scores.items(),
            key=lambda item: (sum(item[1]) / max(1, len(item[1]))),
            reverse=True,
        ):
            avg_prob = sum(values) / max(1, len(values))
            lines.append(f"{emotion_label_ru(emotion)}: средняя вероятность {avg_prob:.2f}")

        if self.current_combined_lie_timeline:
            combined_values = [
                clamp_unit(safe_float(item.get("value"), 0.0))
                for item in self.current_combined_lie_timeline
            ]
            if combined_values:
                avg_combined = sum(combined_values) / len(combined_values)
                max_combined = max(combined_values)
                lines.append(f"Средний объединенный риск лжи: {avg_combined:.2f}")
                lines.append(f"Максимальный объединенный риск лжи: {max_combined:.2f}")

            intervals = self._extract_lie_intervals_from_points(
                self.current_combined_lie_timeline,
                threshold=LIE_RISK_THRESHOLD,
            )
            if intervals:
                lines.append(f"Интервалы вероятной лжи (порог {LIE_RISK_THRESHOLD:.2f}):")
                for start_time, end_time in intervals[:6]:
                    lines.append(f"- {format_seconds(start_time)} - {format_seconds(end_time)}")
                if len(intervals) > 6:
                    lines.append(f"- ... и еще {len(intervals) - 6} интервал(ов)")
            else:
                lines.append(f"Выраженных интервалов лжи (порог {LIE_RISK_THRESHOLD:.2f}) не найдено")

        return lines





