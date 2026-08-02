"""
tagging_tab.py
The scan -> match -> tag workflow, as a QWidget tab. Every processed file is
upserted into the SQLite library (core/database.py), and every tag write is
logged under a batch_id so the whole run can be undone later via the
History dialog. A local (API-key-free) Chromaprint fingerprint is computed
per file when fpcalc is available, purely for duplicate detection.
"""

import os

from PySide6.QtCore import QThread, QObject, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QProgressBar, QFileDialog, QTextEdit,
    QMessageBox, QHeaderView,
)

from core import scanner, tagger, matcher, database, fingerprint, coverart
import config as app_config
from ui.settings_dialog import SettingsDialog
from ui.review_dialog import ReviewDialog

COL_FILE, COL_ARTIST, COL_TITLE, COL_STATUS, COL_CONFIDENCE = range(5)


class Worker(QObject):
    file_status = Signal(int, str, str, str)
    needs_review = Signal(int, str, dict, object)
    log = Signal(str)
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, filepaths, cfg, batch_id):
        super().__init__()
        self.filepaths = filepaths
        self.cfg = cfg
        self.batch_id = batch_id
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        total = len(self.filepaths)
        threshold = self.cfg.get("auto_write_threshold", 85)
        fpcalc_path = self.cfg.get("fpcalc_path", "")

        for i, filepath in enumerate(self.filepaths):
            if self._stop:
                break

            self.progress.emit(i + 1, total)
            fname = os.path.basename(filepath)

            try:
                current_tags = tagger.read_tags(filepath)
            except Exception as exc:
                self.log.emit(f"[ERROR] Failed to read tags for {fname}: {exc}")
                self.file_status.emit(i, "Error", fname, "")
                continue

            # Local fingerprint for duplicate detection (no API key needed)
            duration, local_fp = 0.0, ""
            try:
                duration, local_fp = fingerprint.compute_local_fingerprint(filepath, fpcalc_path)
            except fingerprint.FpcalcNotFoundError:
                pass  # fingerprinting just won't be available; not fatal

            self.file_status.emit(i, "Matching…", fname, "")

            try:
                result = matcher.match_file(
                    filepath, current_tags,
                    acoustid_key=self.cfg.get("acoustid_api_key", ""),
                    discogs_token=self.cfg.get("discogs_token", ""),
                    fpcalc_path=fpcalc_path,
                )
            except Exception as exc:
                self.log.emit(f"[ERROR] Matching failed for {fname}: {exc}")
                self.file_status.emit(i, "Error", fname, "")
                continue

            if result is None:
                self.log.emit(f"[NO MATCH] {fname}")
                self.file_status.emit(i, "No match", fname, "")
                safe_tags = matcher.sanitize_unmatched_tags(current_tags)
                database.upsert_track(filepath, safe_tags, fingerprint=local_fp, duration=duration)
                continue

            artist_title = f"{result.tags.get('artist','')} - {result.tags.get('title','')}"

            if result.confidence >= threshold:
                try:
                    cover_bytes, cover_mime = None, None
                    if self.cfg.get("download_cover_art", True):
                        cover_bytes, cover_mime = coverart.fetch_cover_art(
                            mbid=result.tags.get("musicbrainz_albumid", ""),
                            discogs_release_id=result.discogs_release_id,
                            discogs_token=self.cfg.get("discogs_token", ""),
                        )
                    tagger.write_tags(
                        filepath, result.tags,
                        cover_bytes=cover_bytes, cover_mime=cover_mime or "image/jpeg",
                    )
                    database.record_tag_history(self.batch_id, filepath, current_tags, result.tags)
                    database.upsert_track(
                        filepath, result.tags, fingerprint=local_fp, duration=duration,
                        match_source=result.source, confidence=result.confidence,
                    )
                    cover_note = " +cover art" if cover_bytes else ""
                    self.log.emit(
                        f"[OK] {fname} -> {artist_title} ({result.source}, {result.confidence}%){cover_note}"
                    )
                    self.file_status.emit(i, "Tagged", artist_title, f"{result.confidence}%")
                except Exception as exc:
                    self.log.emit(f"[ERROR] Failed to write tags for {fname}: {exc}")
                    self.file_status.emit(i, "Error", fname, "")
            else:
                self.log.emit(
                    f"[REVIEW] {fname} -> {artist_title} "
                    f"({result.source}, {result.confidence}%, below threshold)"
                )
                self.file_status.emit(i, "Needs review", artist_title, f"{result.confidence}%")
                # Show the proposed match (MusicBrainz/Discogs-sourced), not
                # whatever was already sitting in the file's own tags.
                database.upsert_track(
                    filepath, result.tags, fingerprint=local_fp, duration=duration,
                    match_source=f"{result.source} (pending review)", confidence=result.confidence,
                )
                self.needs_review.emit(i, filepath, current_tags, result)

        self.finished.emit()


class TaggingTab(QWidget):
    library_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.cfg = app_config.load_config()
        self.review_queue = {}
        self.filepaths = []
        self.thread = None
        self.worker = None
        self.current_batch_id = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("color: #9a9ca6;")
        select_btn = QPushButton("Select Folder…")
        select_btn.clicked.connect(self.select_folder)
        self.start_btn = QPushButton("Start Scan && Tag")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setEnabled(False)
        self.review_btn = QPushButton("Review Queue (0)")
        self.review_btn.clicked.connect(self.open_review_queue)
        self.review_btn.setEnabled(False)
        settings_btn = QPushButton("Settings…")
        settings_btn.clicked.connect(self.open_settings)

        top_row.addWidget(select_btn)
        top_row.addWidget(self.folder_label, stretch=1)
        top_row.addWidget(self.review_btn)
        top_row.addWidget(self.start_btn)
        top_row.addWidget(settings_btn)
        layout.addLayout(top_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["File", "Artist", "Title", "Status", "Confidence"])
        self.table.horizontalHeader().setSectionResizeMode(COL_FILE, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_ARTIST, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, stretch=3)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(160)
        layout.addWidget(self.log_view, stretch=1)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select music folder", self.cfg.get("last_folder", "")
        )
        if not folder:
            return

        self.cfg["last_folder"] = folder
        app_config.save_config(self.cfg)

        self.filepaths = list(scanner.scan_folder(folder))
        self.folder_label.setText(f"{folder}  ({len(self.filepaths)} audio files found)")
        self._populate_table()
        self.start_btn.setEnabled(len(self.filepaths) > 0)
        self.review_queue.clear()
        self._update_review_button()

    def _populate_table(self):
        self.table.setRowCount(len(self.filepaths))
        for row, path in enumerate(self.filepaths):
            self.table.setItem(row, COL_FILE, QTableWidgetItem(os.path.basename(path)))
            self.table.setItem(row, COL_ARTIST, QTableWidgetItem(""))
            self.table.setItem(row, COL_TITLE, QTableWidgetItem(""))
            self.table.setItem(row, COL_STATUS, QTableWidgetItem("Pending"))
            self.table.setItem(row, COL_CONFIDENCE, QTableWidgetItem(""))

    def open_settings(self):
        dialog = SettingsDialog(self.cfg, self)
        if dialog.exec():
            self.cfg = dialog.result_config()
            app_config.save_config(self.cfg)
            self.log_view.append("Settings saved.")

    def start_processing(self):
        if not self.filepaths:
            return
        if not self.cfg.get("acoustid_api_key") and not self.cfg.get("discogs_token"):
            reply = QMessageBox.question(
                self, "No API keys configured",
                "No AcoustID key or Discogs token is set. Matching will rely on "
                "MusicBrainz text search only. Continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.No:
                self.open_settings()
                return

        self.start_btn.setEnabled(False)
        self.review_queue.clear()
        self._update_review_button()
        self.progress_bar.setValue(0)
        self.log_view.clear()
        self.current_batch_id = database.new_batch_id()

        self.thread = QThread()
        self.worker = Worker(self.filepaths, self.cfg, self.current_batch_id)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.file_status.connect(self._on_file_status)
        self.worker.needs_review.connect(self._on_needs_review)
        self.worker.log.connect(self.log_view.append)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.thread.quit)

        self.thread.start()

    def _on_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_file_status(self, row, status, artist_title, confidence_str):
        self.table.setItem(row, COL_STATUS, QTableWidgetItem(status))
        self.table.setItem(row, COL_CONFIDENCE, QTableWidgetItem(confidence_str))
        if " - " in artist_title:
            artist, title = artist_title.split(" - ", 1)
            self.table.setItem(row, COL_ARTIST, QTableWidgetItem(artist))
            self.table.setItem(row, COL_TITLE, QTableWidgetItem(title))

    def _on_needs_review(self, row, filepath, current_tags, match_result):
        self.review_queue[row] = (filepath, current_tags, match_result)
        self._update_review_button()

    def _update_review_button(self):
        count = len(self.review_queue)
        self.review_btn.setText(f"Review Queue ({count})")
        self.review_btn.setEnabled(count > 0)

    def _on_finished(self):
        self.start_btn.setEnabled(True)
        self.log_view.append("Done. " + (
            f"{len(self.review_queue)} file(s) need review."
            if self.review_queue else "All files processed."
        ))
        self.library_changed.emit()

    def open_review_queue(self):
        rows = list(self.review_queue.keys())
        for row in rows:
            filepath, current_tags, match_result = self.review_queue[row]
            dialog = ReviewDialog(filepath, current_tags, match_result, self)
            if dialog.exec():
                try:
                    cover_bytes, cover_mime = None, None
                    if self.cfg.get("download_cover_art", True):
                        cover_bytes, cover_mime = coverart.fetch_cover_art(
                            mbid=dialog.accepted_tags.get("musicbrainz_albumid", ""),
                            discogs_release_id=match_result.discogs_release_id,
                            discogs_token=self.cfg.get("discogs_token", ""),
                        )
                    tagger.write_tags(
                        filepath, dialog.accepted_tags,
                        cover_bytes=cover_bytes, cover_mime=cover_mime or "image/jpeg",
                    )
                    database.record_tag_history(
                        self.current_batch_id, filepath, current_tags, dialog.accepted_tags
                    )
                    database.upsert_track(
                        filepath, dialog.accepted_tags,
                        match_source=match_result.source + " (reviewed)",
                        confidence=match_result.confidence,
                    )
                    self.log_view.append(f"[OK] Reviewed & tagged: {os.path.basename(filepath)}")
                    self.table.setItem(row, COL_STATUS, QTableWidgetItem("Tagged (reviewed)"))
                except Exception as exc:
                    self.log_view.append(f"[ERROR] Writing reviewed tags failed: {exc}")
            else:
                self.log_view.append(f"[SKIPPED] {os.path.basename(filepath)}")
                self.table.setItem(row, COL_STATUS, QTableWidgetItem("Skipped"))
            del self.review_queue[row]
        self._update_review_button()
        self.library_changed.emit()
