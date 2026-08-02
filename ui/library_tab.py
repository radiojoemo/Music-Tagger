"""
library_tab.py
Browses everything stored in the local SQLite library: search, view all
tag fields, remove entries from the library (does not delete the file),
and jump to a file's containing folder.
"""

import os
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView,
)

from core import database

COLUMNS = [
    ("artist", "Artist"), ("title", "Title"), ("album", "Album"),
    ("date", "Date"), ("genre", "Genre"), ("label", "Label"),
    ("isrc", "ISRC"),
    ("match_source", "Source"), ("confidence", "Confidence"), ("filepath", "File"),
]

# Fields eligible for the "clear this junk value" cleanup tool below —
# these are the ones prone to junk from scene-release/download-site tools.
CLEANABLE_FIELDS = ["label", "catalognumber", "genre", "isrc"]


class LibraryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search artist, title, album, or file path…")
        self.search_edit.returnPressed.connect(self.refresh)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.refresh)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.search_edit, stretch=1)
        top_row.addWidget(search_btn)
        top_row.addWidget(refresh_btn)
        layout.addLayout(top_row)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #9a9ca6;")
        layout.addWidget(self.stats_label)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _, label in COLUMNS])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table, stretch=1)

        bottom_row = QHBoxLayout()
        open_folder_btn = QPushButton("Open Containing Folder")
        open_folder_btn.clicked.connect(self.open_containing_folder)
        remove_btn = QPushButton("Remove Selected from Library")
        remove_btn.clicked.connect(self.remove_selected)
        bottom_row.addWidget(open_folder_btn)
        bottom_row.addWidget(remove_btn)
        bottom_row.addStretch()
        layout.addLayout(bottom_row)

        cleanup_row = QHBoxLayout()
        cleanup_label = QLabel("Clear junk value across library:")
        cleanup_label.setStyleSheet("color: #b9a789;")
        self.cleanup_edit = QLineEdit()
        self.cleanup_edit.setPlaceholderText("e.g. PMEDIA")
        self.cleanup_edit.setMaximumWidth(220)
        cleanup_btn = QPushButton("Clear from Label / Catalog# / Genre / ISRC")
        cleanup_btn.clicked.connect(self.clear_junk_value)
        cleanup_row.addWidget(cleanup_label)
        cleanup_row.addWidget(self.cleanup_edit)
        cleanup_row.addWidget(cleanup_btn)
        cleanup_row.addStretch()
        layout.addLayout(cleanup_row)

        sanitize_row = QHBoxLayout()
        sanitize_label = QLabel(
            "Or: wipe label/catalog#/genre/ISRC/MusicBrainz-IDs on every track "
            "that's never actually been matched (recommended) —"
        )
        sanitize_label.setStyleSheet("color: #b9a789;")
        sanitize_label.setWordWrap(True)
        sanitize_btn = QPushButton("Sanitize All Unmatched Tracks")
        sanitize_btn.setObjectName("primaryButton")
        sanitize_btn.clicked.connect(self.sanitize_unmatched)
        sanitize_row.addWidget(sanitize_label, stretch=1)
        sanitize_row.addWidget(sanitize_btn)
        layout.addLayout(sanitize_row)

    def refresh(self):
        query = self.search_edit.text().strip()
        tracks = database.get_all_tracks(query)
        self.table.setRowCount(len(tracks))
        for row, track in enumerate(tracks):
            for col, (key, _label) in enumerate(COLUMNS):
                value = track.get(key, "")
                if key == "confidence" and value:
                    value = f"{value}%"
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setData(Qt.UserRole, track["filepath"])
                self.table.setItem(row, col, item)

        stats = database.get_library_stats()
        self.stats_label.setText(
            f"{stats['tracks']} tracks • {stats['artists']} artists • {stats['albums']} albums"
        )

    def _selected_filepaths(self) -> list:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        paths = []
        for row in rows:
            item = self.table.item(row, 0)
            if item:
                paths.append(item.data(Qt.UserRole))
        return paths

    def open_containing_folder(self):
        paths = self._selected_filepaths()
        if not paths:
            QMessageBox.information(self, "No selection", "Select a track first.")
            return
        folder = os.path.dirname(paths[0])
        if os.path.isdir(folder):
            try:
                os.startfile(folder)  # Windows
            except AttributeError:
                subprocess.Popen(["xdg-open", folder])
        else:
            QMessageBox.warning(self, "Not found", f"Folder no longer exists:\n{folder}")

    def remove_selected(self):
        paths = self._selected_filepaths()
        if not paths:
            QMessageBox.information(self, "No selection", "Select one or more tracks first.")
            return
        reply = QMessageBox.question(
            self, "Remove from library",
            f"Remove {len(paths)} track(s) from the library index?\n\n"
            "This only removes the database entry — it does not delete the "
            "actual audio file.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            for path in paths:
                database.remove_track(path)
            self.refresh()

    def clear_junk_value(self):
        value = self.cleanup_edit.text().strip()
        if not value:
            QMessageBox.information(self, "Nothing entered", "Type a value to clear first, e.g. PMEDIA.")
            return

        reply = QMessageBox.question(
            self, "Clear value from library?",
            f'Clear "{value}" from Label, Catalog #, and Genre wherever it appears '
            "in the library (case-insensitive match)?\n\n"
            "This only updates the library index — it does not modify the "
            "actual audio files. Re-scanning a file will refresh it from "
            "MusicBrainz/Discogs as usual.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        count = database.clear_matching_field_value(CLEANABLE_FIELDS, value)
        QMessageBox.information(self, "Done", f'Cleared "{value}" from {count} track(s).')
        self.cleanup_edit.clear()
        self.refresh()

    def sanitize_unmatched(self):
        reply = QMessageBox.question(
            self, "Sanitize unmatched tracks?",
            "This blanks Label, Catalog #, Genre, ISRC, and MusicBrainz IDs "
            "on every track in the library that has never actually been "
            "matched against MusicBrainz or Discogs — regardless of what "
            "value is currently sitting in those fields.\n\n"
            "Use this if you're not sure exactly what junk values might be "
            "in your library, rather than clearing one specific value at a "
            "time. This only updates the library index, not the actual "
            "files.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        count = database.sanitize_unmatched_library()
        QMessageBox.information(self, "Done", f"Sanitized {count} unmatched track(s).")
        self.refresh()
