"""
settings_dialog.py
Dialog for configuring AcoustID key, Discogs token, fpcalc path, and the
auto-write confidence threshold.
"""

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QSpinBox, QPushButton, QHBoxLayout,
    QVBoxLayout, QLabel, QFileDialog, QCheckBox,
)


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self.config = dict(config)

        layout = QVBoxLayout(self)

        info = QLabel(
            "AcoustID key: get a free key at acoustid.org/api-key (log in, then "
            "'Request an API key' — choose 'application').\n"
            "Discogs token: developers.discogs.com -> your account settings -> "
            "'Generate new token' under Developer."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #9a9ca6;")
        layout.addWidget(info)

        form = QFormLayout()

        self.acoustid_edit = QLineEdit(self.config.get("acoustid_api_key", ""))
        form.addRow("AcoustID API key:", self.acoustid_edit)

        self.discogs_edit = QLineEdit(self.config.get("discogs_token", ""))
        form.addRow("Discogs token:", self.discogs_edit)

        fpcalc_row = QHBoxLayout()
        self.fpcalc_edit = QLineEdit(self.config.get("fpcalc_path", ""))
        fpcalc_browse = QPushButton("Browse…")
        fpcalc_browse.clicked.connect(self._browse_fpcalc)
        fpcalc_row.addWidget(self.fpcalc_edit)
        fpcalc_row.addWidget(fpcalc_browse)
        form.addRow("fpcalc.exe path (optional if on PATH):", fpcalc_row)

        self.email_edit = QLineEdit(self.config.get("musicbrainz_contact_email", ""))
        form.addRow("MusicBrainz contact email:", self.email_edit)

        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 100)
        self.threshold_spin.setValue(int(self.config.get("auto_write_threshold", 85)))
        form.addRow("Auto-write confidence threshold (%):", self.threshold_spin)

        self.cover_art_check = QCheckBox("Download and embed cover art when a match is found")
        self.cover_art_check.setChecked(bool(self.config.get("download_cover_art", True)))
        form.addRow("", self.cover_art_check)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

    def _browse_fpcalc(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select fpcalc.exe", "", "Executable (*.exe)")
        if path:
            self.fpcalc_edit.setText(path)

    def result_config(self) -> dict:
        cfg = dict(self.config)
        cfg["acoustid_api_key"] = self.acoustid_edit.text().strip()
        cfg["discogs_token"] = self.discogs_edit.text().strip()
        cfg["fpcalc_path"] = self.fpcalc_edit.text().strip()
        cfg["musicbrainz_contact_email"] = self.email_edit.text().strip()
        cfg["auto_write_threshold"] = self.threshold_spin.value()
        cfg["download_cover_art"] = self.cover_art_check.isChecked()
        return cfg
