# gui/theme.py
LIGHT_QSS = """
QWidget { font-size: 13px; }
QFrame#DropArea { border: 2px dashed #b0b0b0; border-radius: 10px; background: #fafafa; color: #666; }
QPushButton { padding: 6px 12px; border-radius: 6px; border: 1px solid #c8c8c8; background: #ffffff; }
QPushButton:hover { background: #f0f0f0; }
QProgressBar { border: 1px solid #c8c8c8; border-radius: 6px; text-align: center; height: 18px; }
QProgressBar::chunk { background: #4a90d9; border-radius: 5px; }
"""

DARK_QSS = """
QWidget { font-size: 13px; background: #2b2b2b; color: #e0e0e0; }
QFrame#DropArea { border: 2px dashed #555; border-radius: 10px; background: #333; color: #aaa; }
QPushButton { padding: 6px 12px; border-radius: 6px; border: 1px solid #555; background: #3a3a3a; color: #e0e0e0; }
QPushButton:hover { background: #454545; }
QLineEdit, QComboBox { background: #3a3a3a; color: #e0e0e0; border: 1px solid #555; border-radius: 4px; padding: 3px; }
QHeaderView::section { background: #3a3a3a; color: #e0e0e0; }
QTableView { background: #2b2b2b; color: #e0e0e0; gridline-color: #444; }
QProgressBar { border: 1px solid #555; border-radius: 6px; text-align: center; height: 18px; }
QProgressBar::chunk { background: #4a90d9; border-radius: 5px; }
"""
