"""Camera recording dialog used in project creation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices, QMediaFormat, QMediaRecorder
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CameraRecordDialog(QDialog):
    def __init__(self, *, output_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Запись видео с камеры")
        self.setModal(True)
        self.resize(840, 560)

        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.capture_session = QMediaCaptureSession()
        self.camera: QCamera | None = None
        self.recorder = QMediaRecorder()
        self.recorder.errorOccurred.connect(self._on_recorder_error)
        self.recorder.recorderStateChanged.connect(self._on_recorder_state_changed)

        self._record_target_path: Path | None = None
        self.recorded_path: Path | None = None
        self._started_at_ms: int = 0

        self.timer = QTimer(self)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self._update_duration)

        self._build_ui()
        self._wire_capture()
        self._reload_cameras()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        controls = QFrame()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        controls_layout.addWidget(QLabel("Камера:"))
        self.camera_combo = QComboBox()
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        controls_layout.addWidget(self.camera_combo, 1)

        self.refresh_devices_button = QPushButton("Обновить")
        self.refresh_devices_button.setObjectName("SecondaryButton")
        self.refresh_devices_button.clicked.connect(self._reload_cameras)
        controls_layout.addWidget(self.refresh_devices_button)

        root.addWidget(controls)

        self.preview = QVideoWidget()
        self.preview.setMinimumHeight(360)
        root.addWidget(self.preview, 1)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.status_label = QLabel("Готово к записи")
        self.status_label.setObjectName("SectionHint")
        self.duration_label = QLabel("00:00")
        self.duration_label.setObjectName("SectionHint")
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.duration_label, 0)
        root.addLayout(status_row)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.start_button = QPushButton("Начать запись")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self._start_recording)

        self.stop_button = QPushButton("Остановить")
        self.stop_button.setObjectName("SecondaryButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_recording)

        self.use_button = QPushButton("Использовать видео")
        self.use_button.setObjectName("SecondaryButton")
        self.use_button.setEnabled(False)
        self.use_button.clicked.connect(self._use_recording)

        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addStretch(1)
        actions.addWidget(self.use_button)

        root.addLayout(actions)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setText("Отмена")
            cancel_button.setObjectName("SecondaryButton")
        button_box.rejected.connect(self.reject)
        root.addWidget(button_box)

    def _wire_capture(self) -> None:
        self.capture_session.setRecorder(self.recorder)
        self.capture_session.setVideoOutput(self.preview)

    def _reload_cameras(self) -> None:
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        cameras = list(QMediaDevices.videoInputs())

        for device in cameras:
            self.camera_combo.addItem(device.description(), device)

        self.camera_combo.blockSignals(False)

        if cameras:
            self.camera_combo.setCurrentIndex(0)
            self._activate_camera(cameras[0])
            self.status_label.setText("Камера подключена")
            self.start_button.setEnabled(True)
        else:
            self._release_camera()
            self.status_label.setText("Камеры не найдены")
            self.start_button.setEnabled(False)

    def _on_camera_changed(self, index: int) -> None:
        device = self.camera_combo.itemData(index)
        if device is None:
            return
        self._activate_camera(device)

    def _activate_camera(self, device) -> None:
        self._release_camera()
        self.camera = QCamera(device)
        self.capture_session.setCamera(self.camera)

        media_format = QMediaFormat()
        media_format.setFileFormat(QMediaFormat.FileFormat.MPEG4)
        media_format.setVideoCodec(QMediaFormat.VideoCodec.H264)
        media_format.setAudioCodec(QMediaFormat.AudioCodec.AAC)
        self.recorder.setMediaFormat(media_format)
        self.camera.start()

    def _release_camera(self) -> None:
        if self.camera is not None:
            self.camera.stop()
            self.camera.deleteLater()
            self.camera = None

    def _on_recorder_error(self, *_: object) -> None:
        error_text = self.recorder.errorString().strip() or "Не удалось выполнить запись"
        self.status_label.setText(error_text)

    def _on_recorder_state_changed(self, state) -> None:
        if state == QMediaRecorder.RecorderState.RecordingState:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.use_button.setEnabled(False)
            self.status_label.setText("Идет запись...")
            self._started_at_ms = int(datetime.now().timestamp() * 1000)
            self.timer.start()
            return

        if state == QMediaRecorder.RecorderState.StoppedState:
            self.timer.stop()
            self.stop_button.setEnabled(False)
            self.start_button.setEnabled(self.camera is not None)

            if self._record_target_path and self._record_target_path.exists() and self._record_target_path.stat().st_size > 0:
                self.recorded_path = self._record_target_path
                self.use_button.setEnabled(True)
                self.status_label.setText(f"Запись сохранена: {self.recorded_path.name}")
            else:
                self.use_button.setEnabled(False)
                if self.status_label.text().startswith("Идет запись"):
                    self.status_label.setText("Запись остановлена")

    def _start_recording(self) -> None:
        if self.camera is None:
            QMessageBox.warning(self, "Камера", "Камера недоступна")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._record_target_path = self.output_dir / f"camera_capture_{timestamp}.mp4"
        self.recorded_path = None
        self.recorder.setOutputLocation(QUrl.fromLocalFile(str(self._record_target_path)))
        self.recorder.record()

    def _stop_recording(self) -> None:
        if self.recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            self.recorder.stop()

    def _update_duration(self) -> None:
        if self._started_at_ms <= 0:
            self.duration_label.setText("00:00")
            return

        elapsed_sec = max(0, (int(datetime.now().timestamp() * 1000) - self._started_at_ms) // 1000)
        minutes = elapsed_sec // 60
        seconds = elapsed_sec % 60
        self.duration_label.setText(f"{minutes:02d}:{seconds:02d}")

    def _use_recording(self) -> None:
        if self.recorded_path is None or not self.recorded_path.exists():
            QMessageBox.warning(self, "Запись", "Файл записи не найден")
            return
        self.accept()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.timer.stop()
        if self.recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            self.recorder.stop()
        self._release_camera()
        super().closeEvent(event)
