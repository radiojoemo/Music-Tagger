"""
review_dialog.py
Shown for low-confidence matches (or when the user wants to double check).
Displays current tags vs the proposed match side by side, editable, with
Accept / Skip actions.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QLabel,
    QPushButton, QGroupBox,
)

FIELDS = [
    ("artist", "Artist"),
    ("title", "Title"),
    ("album", "Album"),
    ("albumartist", "Album Artist"),
    ("date", "Date"),
    ("tracknumber", "Track #"),
    ("discnumber", "Disc #"),
    ("genre", "Genre"),
    ("label", "Label"),
    ("catalognumber", "Catalog #"),
    ("isrc", "ISRC"),
]


class ReviewDialog(QDialog):
    def __init__(self, filepath: str, current_tags: dict, match_result, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review match")
        self.setMinimumWidth(720)
        self.match_result = match_result
        self.accepted_tags = None

        layout = QVBoxLayout(self)

        header = QLabel(f"<b>{filepath}</b>")
        header.setWordWrap(True)
        layout.addWidget(header)

        confidence_label = QLabel(
            f"Match source: {match_result.source} — confidence: {match_result.confidence}%"
        )
        confidence_label.setStyleSheet("color: #f2c14e;")
        layout.addWidget(confidence_label)

        columns = QHBoxLayout()

        current_box = QGroupBox("Current tags")
        current_form = QFormLayout()
        for key, label in FIELDS:
            current_form.addRow(label + ":", QLabel(current_tags.get(key, "") or "—"))
        current_box.setLayout(current_form)
        columns.addWidget(current_box)

        proposed_box = QGroupBox("Proposed tags (editable)")
        proposed_form = QFormLayout()
        self.edits = {}
        for key, label in FIELDS:
            edit = QLineEdit(match_result.tags.get(key, "") or "")
            self.edits[key] = edit
            proposed_form.addRow(label + ":", edit)
        proposed_box.setLayout(proposed_form)
        columns.addWidget(proposed_box)

        layout.addLayout(columns)

        buttons = QHBoxLayout()
        skip_btn = QPushButton("Skip this file")
        skip_btn.clicked.connect(self.reject)
        accept_btn = QPushButton("Accept & write tags")
        accept_btn.setObjectName("primaryButton")
        accept_btn.clicked.connect(self._accept)
        buttons.addWidget(skip_btn)
        buttons.addStretch()
        buttons.addWidget(accept_btn)
        layout.addLayout(buttons)

    def _accept(self):
        self.accepted_tags = {key: edit.text() for key, edit in self.edits.items()}
        # Preserve MusicBrainz IDs from the original match even though they're not shown/edited
        for id_key in ("musicbrainz_trackid", "musicbrainz_albumid", "musicbrainz_artistid"):
            self.accepted_tags[id_key] = self.match_result.tags.get(id_key, "")
        self.accept()
