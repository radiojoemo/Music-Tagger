"""
duplicates_tab.py
Scans the SQLite library for duplicate tracks (fingerprint match, same
MusicBrainz recording, or fuzzy artist/title match) and lets the user
select specific files to delete from disk.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTreeWidget,
    QTreeWidgetItem, QMessageBox, QAbstractItemView,
)

from core import duplicates, database


class DuplicatesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        info = QLabel(
            "Scans your whole library (not just the last folder scanned) for "
            "likely duplicate tracks."
        )
        info.setStyleSheet("color: #9a9ca6;")
        scan_btn = QPushButton("Scan for Duplicates")
        scan_btn.setObjectName("primaryButton")
        scan_btn.clicked.connect(self.run_scan)
        top_row.addWidget(info, stretch=1)
        top_row.addWidget(scan_btn)
        layout.addLayout(top_row)

        self.result_label = QLabel("")
        self.result_label.setStyleSheet("color: #9a9ca6;")
        layout.addWidget(self.result_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Artist / Track", "Album", "Date", "File"])
        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(1, 200)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.tree, stretch=1)

        bottom_row = QHBoxLayout()
        delete_btn = QPushButton("Delete Selected Files…")
        delete_btn.clicked.connect(self.delete_selected)
        bottom_row.addWidget(delete_btn)
        bottom_row.addStretch()
        layout.addLayout(bottom_row)

    def run_scan(self):
        tracks = database.get_all_tracks()
        if len(tracks) > 5000:
            self.result_label.setText(
                "Scanning a large library — the fuzzy artist/title pass may take a "
                "moment…"
            )

        self.groups = duplicates.find_duplicates(tracks)
        self.tree.clear()

        if not self.groups:
            self.result_label.setText("No duplicates found.")
            return

        total_dupes = sum(len(g.tracks) for g in self.groups)
        self.result_label.setText(
            f"Found {len(self.groups)} duplicate group(s), {total_dupes} files involved."
        )

        for group in self.groups:
            group_item = QTreeWidgetItem([f"{group.reason} ({len(group.tracks)} files)"])
            group_item.setFlags(group_item.flags() & ~Qt.ItemIsSelectable)
            font = group_item.font(0)
            font.setBold(True)
            group_item.setFont(0, font)
            self.tree.addTopLevelItem(group_item)

            for track in group.tracks:
                child = QTreeWidgetItem([
                    f"{track.get('artist','')} - {track.get('title','')}",
                    track.get("album", ""),
                    track.get("date", ""),
                    track.get("filepath", ""),
                ])
                child.setData(0, Qt.UserRole, track.get("filepath", ""))
                group_item.addChild(child)

            group_item.setExpanded(True)

    def delete_selected(self):
        selected_paths = []
        for item in self.tree.selectedItems():
            path = item.data(0, Qt.UserRole)
            if path:
                selected_paths.append(path)

        if not selected_paths:
            QMessageBox.information(
                self, "No selection",
                "Select individual duplicate files (not the group header) to delete."
            )
            return

        reply = QMessageBox.warning(
            self, "Delete files permanently?",
            "This will permanently delete " + str(len(selected_paths)) +
            " file(s) from disk and remove them from the library:\n\n" +
            "\n".join(selected_paths[:10]) +
            ("\n…" if len(selected_paths) > 10 else "") +
            "\n\nThis cannot be undone. Continue?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return

        deleted, failed = 0, []
        for path in selected_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
                database.remove_track(path)
                deleted += 1
            except OSError as exc:
                failed.append(f"{path}: {exc}")

        msg = f"Deleted {deleted} file(s)."
        if failed:
            msg += f"\n\n{len(failed)} failed:\n" + "\n".join(failed[:5])
        QMessageBox.information(self, "Done", msg)

        self.run_scan()
