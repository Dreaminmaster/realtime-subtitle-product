"""Current-session export choices and safe file writers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ui_components import SegmentedControl


DISPLAY_NAMES = {
    "bilingual": "Original + translation",
    "original_only": "Original only",
    "translation_only": "Translation only",
}


@dataclass(frozen=True)
class ExportResult:
    text_path: Path | None = None
    audio_path: Path | None = None


class SessionExportDialog(QDialog):
    """Small explicit choice dialog scoped to the currently selected session."""

    def __init__(self, *, display_mode="bilingual", has_audio=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export selected session")
        self.setModal(True)
        self.setMinimumWidth(460)
        self._choice = "text"

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)
        title = QLabel("Export selected session")
        title.setStyleSheet("font-size: 19px; font-weight: 750;")
        root.addWidget(title)
        copy = QLabel(
            "Choose what to export. Transcript text follows the view currently selected in the session:"
        )
        copy.setWordWrap(True)
        copy.setObjectName("Muted")
        root.addWidget(copy)
        mode = QLabel(DISPLAY_NAMES.get(display_mode, DISPLAY_NAMES["bilingual"]))
        mode.setStyleSheet("font-weight: 700; color: #f5a264;")
        root.addWidget(mode)

        self.selector = SegmentedControl()
        self.selector.addItem("Text", "text")
        self.selector.addItem("Recording", "audio")
        self.selector.addItem("Both", "both")
        self.selector.setItemEnabled("audio", has_audio)
        self.selector.setItemEnabled("both", has_audio)
        self.selector.currentIndexChanged.connect(self._selection_changed)
        root.addWidget(self.selector)

        self.availability = QLabel(
            "Recording is ready to export."
            if has_audio else
            "This session contains subtitles only, so recording export is unavailable."
        )
        self.availability.setObjectName("Muted")
        self.availability.setWordWrap(True)
        root.addWidget(self.availability)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("SecondaryButton")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        confirm = QPushButton("Choose destination")
        confirm.clicked.connect(self.accept)
        actions.addWidget(confirm)
        root.addLayout(actions)

    def _selection_changed(self, *_):
        self._choice = self.selector.currentData() or "text"

    def export_choice(self):
        return self.selector.currentData() or "text"


def write_text_export(path: str | Path, text: str) -> ExportResult:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return ExportResult(text_path=destination)


def copy_audio_export(source: str | Path, destination: str | Path) -> ExportResult:
    source_path = Path(source).expanduser()
    if not source_path.is_file() or source_path.stat().st_size <= 44:
        raise FileNotFoundError("The selected session has no playable recording")
    target = Path(destination).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)
    return ExportResult(audio_path=target)


def write_bundle(directory: str | Path, stem: str, text: str, audio_source: str | Path) -> ExportResult:
    root = Path(directory).expanduser() / stem
    suffix = 2
    while root.exists():
        root = Path(directory).expanduser() / f"{stem} {suffix}"
        suffix += 1
    root.mkdir(parents=True, exist_ok=False)
    text_path = root / "transcript.txt"
    audio_path = root / "recording.wav"
    text_path.write_text(text, encoding="utf-8")
    copy_audio_export(audio_source, audio_path)
    return ExportResult(text_path=text_path, audio_path=audio_path)
