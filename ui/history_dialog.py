"""
history_dialog.py
Lists every past tagging batch (one per "Start Scan & Tag" run, plus one
covering all reviewed-queue writes) and lets the user undo an entire batch,
restoring each file's previous tags.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QAbstractItemView,
)

from core import database, tagger


class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tagging History / Undo")
        self.setMinimumSize(700, 420)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Each row is one processing run. Undo restores every file in that "
            "run to its previous tags."
        )
        info.setStyleSheet("color: #9a9ca6;")
        layout.addWidget(info)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Started", "Files changed", "Already undone", "Batch ID"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.table, stretch=1)

        buttons = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        undo_btn = QPushButton("Undo Selected Batch")
        undo_btn.setObjectName("primaryButton")
        undo_btn.clicked.connect(self.undo_selected)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(refresh_btn)
        buttons.addStretch()
        buttons.addWidget(undo_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self):
        batches = database.get_batches()
        self.table.setRowCount(len(batches))
        for row, b in enumerate(batches):
            self.table.setItem(row, 0, QTableWidgetItem(b["started"]))
            self.table.setItem(row, 1, QTableWidgetItem(str(b["file_count"])))
            self.table.setItem(row, 2, QTableWidgetItem(str(b["undone_count"])))
            self.table.setItem(row, 3, QTableWidgetItem(b["batch_id"]))

    def undo_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "No selection", "Select a batch to undo.")
            return
        row = rows[0].row()
        batch_id = self.table.item(row, 3).text()
        file_count = self.table.item(row, 1).text()

        reply = QMessageBox.question(
            self, "Undo batch?",
            f"Restore previous tags for {file_count} file(s) from this batch?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        entries = database.get_batch_entries(batch_id)
        restored, failed = 0, []
        for entry in entries:
            if entry.get("undone"):
                continue
            filepath = entry["filepath"]
            old_tags = entry["old_tags"]
            try:
                tagger.write_tags(filepath, old_tags)
                database.upsert_track(filepath, old_tags)
                restored += 1
            except Exception as exc:
                failed.append(f"{filepath}: {exc}")

        database.mark_batch_undone(batch_id)

        msg = f"Restored {restored} file(s)."
        if failed:
            msg += f"\n\n{len(failed)} failed:\n" + "\n".join(failed[:5])
        QMessageBox.information(self, "Undo complete", msg)
        self.refresh()
