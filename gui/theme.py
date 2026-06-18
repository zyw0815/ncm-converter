# gui/theme.py
# 两套主题：浅色（明亮干净）与深色（柔和护眼），统一蓝色强调色，对比度都做足。

ACCENT = "#3b82f6"

LIGHT_QSS = """
* { font-size: 13px; }
QMainWindow, QWidget { background: #f4f6fb; color: #1f2430; }

QLabel { color: #1f2430; background: transparent; }
QLabel#Title { font-size: 16px; font-weight: 700; color: #1f2430; }
QLabel#FieldLabel { color: #5b6472; font-weight: 600; }

QFrame#DropArea {
    border: 2px dashed #b9c2d6; border-radius: 14px;
    background: #ffffff; color: #8a93a6; font-size: 14px;
}
QFrame#DropArea[hover="true"] { border-color: #3b82f6; background: #eef4ff; color: #3b82f6; }

QPushButton {
    padding: 7px 16px; border-radius: 9px; border: 1px solid #d3d9e6;
    background: #ffffff; color: #2a3140;
}
QPushButton:hover { background: #eef2fb; border-color: #b9c2d6; }
QPushButton:pressed { background: #e2e8f6; }
QPushButton:disabled { color: #b3b9c4; background: #f0f1f4; border-color: #e4e6eb; }

QPushButton#Primary {
    background: #3b82f6; color: #ffffff; border: none; font-weight: 700;
}
QPushButton#Primary:hover { background: #2f74e6; }
QPushButton#Primary:pressed { background: #2867d4; }
QPushButton#Primary:disabled { background: #b9ccf3; color: #eef2fb; }

QPushButton#Theme { padding: 6px 14px; border-radius: 16px; background: #ffffff; }

QToolButton#Help {
    min-width: 16px; max-width: 16px; min-height: 16px; max-height: 16px;
    border: 1px solid #c8cfdd; border-radius: 9px; background: #ffffff;
    color: #5b6472; font-weight: 700;
}
QToolButton#Help:hover { background: #eef2fb; border-color: #b9c2d6; color: #3b82f6; }

QLineEdit, QComboBox {
    background: #ffffff; color: #1f2430; border: 1px solid #d3d9e6;
    border-radius: 8px; padding: 6px 10px; min-height: 18px;
}
QLineEdit:focus, QComboBox:focus { border-color: #3b82f6; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #ffffff; color: #1f2430; selection-background-color: #3b82f6;
    selection-color: #ffffff; border: 1px solid #d3d9e6; outline: none;
}
QCheckBox { color: #2a3140; spacing: 6px; }

QTableView {
    background: #ffffff; alternate-background-color: #f7f9fd; color: #1f2430;
    gridline-color: #eef0f5; border: 1px solid #e3e7f0; border-radius: 10px;
    selection-background-color: #e8f0ff; selection-color: #1f2430;
}
QTableView::item { padding: 6px 8px; }
QHeaderView::section {
    background: #eef2fb; color: #5b6472; padding: 8px; border: none;
    border-right: 1px solid #e3e7f0; font-weight: 600;
}

QProgressBar {
    border: none; border-radius: 9px; background: #e6eaf2; text-align: center;
    height: 18px; color: #2a3140; font-weight: 600;
}
QProgressBar::chunk { background: #3b82f6; border-radius: 9px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #c7cedd; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #aeb7cb; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""

DARK_QSS = """
* { font-size: 13px; }
QMainWindow, QWidget { background: #1b1e27; color: #e7eaf0; }

QLabel { color: #e7eaf0; background: transparent; }
QLabel#Title { font-size: 16px; font-weight: 700; color: #f2f4f8; }
QLabel#FieldLabel { color: #99a1b3; font-weight: 600; }

QFrame#DropArea {
    border: 2px dashed #3a4153; border-radius: 14px;
    background: #232734; color: #8b93a7; font-size: 14px;
}
QFrame#DropArea[hover="true"] { border-color: #5b8def; background: #28304a; color: #9cc0ff; }

QPushButton {
    padding: 7px 16px; border-radius: 9px; border: 1px solid #3a4153;
    background: #2a2f3d; color: #e2e6ef;
}
QPushButton:hover { background: #333a4b; border-color: #4a5269; }
QPushButton:pressed { background: #3f4658; }
QPushButton:disabled { color: #5b6377; background: #23262f; border-color: #2e323d; }

QPushButton#Primary {
    background: #4a86f0; color: #ffffff; border: none; font-weight: 700;
}
QPushButton#Primary:hover { background: #5b93f5; }
QPushButton#Primary:pressed { background: #3f78db; }
QPushButton#Primary:disabled { background: #36486e; color: #9fb2d6; }

QPushButton#Theme { padding: 6px 14px; border-radius: 16px; background: #2a2f3d; }

QToolButton#Help {
    min-width: 16px; max-width: 16px; min-height: 16px; max-height: 16px;
    border: 1px solid #4a5269; border-radius: 9px; background: #2a2f3d;
    color: #99a1b3; font-weight: 700;
}
QToolButton#Help:hover { background: #333a4b; border-color: #5b8def; color: #9cc0ff; }

QLineEdit, QComboBox {
    background: #232734; color: #e7eaf0; border: 1px solid #3a4153;
    border-radius: 8px; padding: 6px 10px; min-height: 18px;
}
QLineEdit:focus, QComboBox:focus { border-color: #5b8def; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #232734; color: #e7eaf0; selection-background-color: #4a86f0;
    selection-color: #ffffff; border: 1px solid #3a4153; outline: none;
}
QCheckBox { color: #d4d9e3; spacing: 6px; }

QTableView {
    background: #20242f; alternate-background-color: #242936; color: #e7eaf0;
    gridline-color: #2e323d; border: 1px solid #2e323d; border-radius: 10px;
    selection-background-color: #2f3a55; selection-color: #ffffff;
}
QTableView::item { padding: 6px 8px; }
QHeaderView::section {
    background: #272c3a; color: #99a1b3; padding: 8px; border: none;
    border-right: 1px solid #2e323d; font-weight: 600;
}

QProgressBar {
    border: none; border-radius: 9px; background: #2a2f3d; text-align: center;
    height: 18px; color: #e7eaf0; font-weight: 600;
}
QProgressBar::chunk { background: #4a86f0; border-radius: 9px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #3a4153; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4a5269; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""
