"""
main_window.py
Top-level window: a tab for the scan/tag workflow, a tab for browsing the
SQLite-backed library, and a tab for duplicate detection. Tools menu has
Settings and History/Undo.
"""

from PySide6.QtWidgets import QMainWindow, QTabWidget
from PySide6.QtGui import QAction

from ui.tagging_tab import TaggingTab
from ui.library_tab import LibraryTab
from ui.duplicates_tab import DuplicatesTab
from ui.settings_dialog import SettingsDialog
from ui.history_dialog import HistoryDialog
import config as app_config


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Music Tagger")
        self.resize(1100, 700)

        self.tagging_tab = TaggingTab()
        self.library_tab = LibraryTab()
        self.duplicates_tab = DuplicatesTab()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.tagging_tab, "Tag Files")
        self.tabs.addTab(self.library_tab, "Library")
        self.tabs.addTab(self.duplicates_tab, "Duplicates")
        self.setCentralWidget(self.tabs)

        # Refresh the library view whenever a tagging run finishes
        self.tagging_tab.library_changed.connect(self.library_tab.refresh)
        # Also refresh library view whenever the user switches to that tab
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._build_menu()

    def _on_tab_changed(self, index):
        if self.tabs.widget(index) is self.library_tab:
            self.library_tab.refresh()

    def _build_menu(self):
        menubar = self.menuBar()

        tools_menu = menubar.addMenu("&Tools")

        settings_action = QAction("Settings…", self)
        settings_action.triggered.connect(self.open_settings)
        tools_menu.addAction(settings_action)

        history_action = QAction("History / Undo…", self)
        history_action.triggered.connect(self.open_history)
        tools_menu.addAction(history_action)

    def open_settings(self):
        cfg = app_config.load_config()
        dialog = SettingsDialog(cfg, self)
        if dialog.exec():
            new_cfg = dialog.result_config()
            app_config.save_config(new_cfg)
            self.tagging_tab.cfg = new_cfg

    def open_history(self):
        dialog = HistoryDialog(self)
        dialog.exec()
        self.library_tab.refresh()
