"""
styles.py
A warm tan / dark-tan theme via Qt Style Sheets (QSS).
"""

TAN_STYLESHEET = """
QWidget {
    background-color: #3b322b;
    color: #f2e8d5;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #3b322b;
}

QTabWidget::pane {
    border: 1px solid #5c4a3a;
    background-color: #3b322b;
}
QTabBar::tab {
    background-color: #46392f;
    color: #d8c9ac;
    padding: 7px 16px;
    border: 1px solid #5c4a3a;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background-color: #6b563f;
    color: #f2e8d5;
}
QTabBar::tab:hover {
    background-color: #59493a;
}

QPushButton {
    background-color: #6b563f;
    border: 1px solid #7c6449;
    border-radius: 6px;
    padding: 6px 14px;
    color: #f2e8d5;
}
QPushButton:hover {
    background-color: #7c6449;
}
QPushButton:pressed {
    background-color: #5a4632;
}
QPushButton:disabled {
    background-color: #443a30;
    color: #8a7a63;
}

QPushButton#primaryButton {
    background-color: #c9a15a;
    border: none;
    color: #2b2118;
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background-color: #d4ac68;
}
QPushButton#primaryButton:pressed {
    background-color: #b58f4c;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #46392f;
    border: 1px solid #5c4a3a;
    border-radius: 5px;
    padding: 5px 8px;
    color: #f2e8d5;
}

QTableWidget, QTreeWidget {
    background-color: #423527;
    alternate-background-color: #4d4033;
    gridline-color: #5c4a3a;
    border: 1px solid #5c4a3a;
    border-radius: 6px;
    color: #f2e8d5;
}
QHeaderView::section {
    background-color: #46392f;
    color: #e8d9bd;
    padding: 6px;
    border: none;
    border-bottom: 2px solid #5c4a3a;
}
QTreeWidget::item:selected, QTableWidget::item:selected {
    background-color: #7c6449;
}

QProgressBar {
    background-color: #46392f;
    border: 1px solid #5c4a3a;
    border-radius: 5px;
    text-align: center;
    color: #f2e8d5;
}
QProgressBar::chunk {
    background-color: #c9a15a;
    border-radius: 5px;
}

QLabel#statusPending { color: #b9a789; }
QLabel#statusMatched { color: #8fbf7a; }
QLabel#statusReview { color: #d9a441; }
QLabel#statusError { color: #c96a4e; }

QTextEdit {
    background-color: #2c241d;
    border: 1px solid #5c4a3a;
    border-radius: 6px;
    font-family: Consolas, monospace;
    font-size: 12px;
    color: #e8d9bd;
}

QGroupBox {
    border: 1px solid #5c4a3a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    color: #e8d9bd;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QMenuBar {
    background-color: #3b322b;
    color: #f2e8d5;
}
QMenuBar::item:selected {
    background-color: #6b563f;
}
QMenu {
    background-color: #46392f;
    border: 1px solid #5c4a3a;
    color: #f2e8d5;
}
QMenu::item:selected {
    background-color: #6b563f;
}

QScrollBar:vertical {
    background: #3b322b;
    width: 12px;
}
QScrollBar::handle:vertical {
    background: #6b563f;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #7c6449;
}
"""
