"""
main.py
Entry point for Music Tagger.
"""

import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.styles import TAN_STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(TAN_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
