"""Темы оформления: тёмная (графит и оранжевый, как интерфейс ETS2) и светлая."""
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

PALETTES = {
    "dark": {"bg": "#17191d", "panel": "#1f2227", "raised": "#2a2e35", "border": "#363b43", "alt": "#24282e",
             "text": "#e8eaed", "muted": "#8d95a0", "disabled": "#5b626c", "accent": "#ff9f1a",
             "accent_hover": "#ffb54d", "on_accent": "#141414", "good": "#4cc36a", "sel": "rgba(255,159,26,70)"},
    "light": {"bg": "#f1f2f5", "panel": "#ffffff", "raised": "#e6e8ed", "border": "#cfd3da", "alt": "#f6f7f9",
              "text": "#1d2127", "muted": "#667080", "disabled": "#a3aab5", "accent": "#e08600",
              "accent_hover": "#f29a1f", "on_accent": "#ffffff", "good": "#2e9e4f", "sel": "rgba(224,134,0,60)"},
}
_current = dict(PALETTES["dark"])
_mode = "dark"


def c(name):
    """Цвет текущей темы по имени (bg, panel, accent, muted, good...)."""
    return _current[name]


def mode():
    return _mode


def qss(p):
    return f"""
* {{ font-family: "Segoe UI", "Inter", sans-serif; font-size: 10pt; }}
QMainWindow, QDialog, QMessageBox {{ background: {p['bg']}; }}
QWidget {{ color: {p['text']}; }}
QLabel {{ background: transparent; }}
QToolTip {{ background: {p['raised']}; color: {p['text']}; border: 1px solid {p['border']}; padding: 4px; }}

QMenuBar {{ background: {p['bg']}; padding: 2px 6px; }}
QMenuBar::item {{ background: transparent; padding: 5px 10px; border-radius: 4px; }}
QMenuBar::item:selected {{ background: {p['raised']}; }}
QMenu {{ background: {p['panel']}; border: 1px solid {p['border']}; padding: 4px; }}
QMenu::item {{ padding: 6px 24px 6px 14px; border-radius: 4px; }}
QMenu::item:selected {{ background: {p['accent']}; color: {p['on_accent']}; }}
QMenu::separator {{ height: 1px; background: {p['border']}; margin: 4px 8px; }}
QStatusBar {{ background: {p['bg']}; color: {p['muted']}; }}

QTabWidget::pane {{ border: 1px solid {p['border']}; border-radius: 8px; background: {p['panel']}; top: -1px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; color: {p['muted']}; padding: 9px 18px; margin-right: 2px;
               border-bottom: 3px solid transparent; }}
QTabBar::tab:hover {{ color: {p['text']}; }}
QTabBar::tab:selected {{ color: {p['accent']}; border-bottom: 3px solid {p['accent']}; font-weight: 600; }}

QTableView {{ background: {p['panel']}; alternate-background-color: {p['alt']}; border: none; gridline-color: transparent;
             selection-background-color: {p['sel']}; selection-color: {p['text']}; outline: 0; }}
QTableView::item {{ padding: 0 8px; border: none; }}
QHeaderView {{ background: {p['panel']}; }}
QHeaderView::section {{ background: {p['raised']}; color: {p['muted']}; padding: 8px 10px; border: none;
                       border-right: 1px solid {p['bg']}; font-weight: 600; }}
QHeaderView::section:hover {{ color: {p['text']}; }}
QHeaderView::up-arrow {{ image: url(@UI@/arrow_up.png); width: 9px; height: 11px; }}
QHeaderView::down-arrow {{ image: url(@UI@/arrow_down.png); width: 9px; height: 11px; }}
QTableCornerButton::section {{ background: {p['raised']}; border: none; }}

QLineEdit, QSpinBox, QComboBox {{ background: {p['bg']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 6px 10px;
                                  selection-background-color: {p['accent']}; selection-color: {p['on_accent']}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {p['accent']}; }}

QPushButton {{ background: {p['raised']}; border: 1px solid {p['border']}; border-radius: 6px; padding: 7px 16px; }}
QPushButton:hover {{ border-color: {p['accent']}; }}
QPushButton:pressed {{ background: {p['border']}; }}
QPushButton:disabled {{ color: {p['disabled']}; border-color: {p['border']}; }}
QPushButton#primary {{ background: {p['accent']}; color: {p['on_accent']}; border: none; font-weight: 700; }}
QPushButton#primary:hover {{ background: {p['accent_hover']}; }}
QPushButton#primary:disabled {{ background: {p['raised']}; color: {p['disabled']}; }}

QListWidget {{ background: {p['bg']}; border: 1px solid {p['border']}; border-radius: 8px; padding: 4px; outline: 0; }}
QListWidget::item {{ padding: 6px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {p['raised']}; }}
QListWidget::item:selected {{ background: {p['sel']}; border-left: 3px solid {p['accent']}; color: {p['text']}; }}

QFrame#tile {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 8px; }}
QLabel#tileLabel {{ color: {p['muted']}; font-size: 8pt; }}
QLabel#tileValue {{ color: {p['text']}; font-size: 14pt; font-weight: 700; }}
QLabel#tileValue[accent="true"] {{ color: {p['accent']}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p['muted']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['border']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {p['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""

def apply(app: QApplication, ui_dir=None, mode_name="dark"):
    global _current, _mode
    _mode = mode_name if mode_name in PALETTES else "dark"
    _current = dict(PALETTES[_mode])
    p = _current
    app.setStyle("Fusion")
    pal = QPalette()
    for role, key in (
        (QPalette.ColorRole.Window, "bg"), (QPalette.ColorRole.WindowText, "text"), (QPalette.ColorRole.Base, "panel"),
        (QPalette.ColorRole.AlternateBase, "alt"), (QPalette.ColorRole.Text, "text"),
        (QPalette.ColorRole.Button, "raised"), (QPalette.ColorRole.ButtonText, "text"),
        (QPalette.ColorRole.ToolTipBase, "raised"), (QPalette.ColorRole.ToolTipText, "text"),
        (QPalette.ColorRole.Highlight, "accent"), (QPalette.ColorRole.HighlightedText, "on_accent"),
        (QPalette.ColorRole.PlaceholderText, "muted"),
    ):
        pal.setColor(role, QColor(p[key]))
    app.setPalette(pal)
    style = qss(p)
    if ui_dir:
        style = style.replace("@UI@", str(ui_dir).replace("\\", "/"))
    else:
        style = style.replace("image: url(@UI@/arrow_up.png);", "").replace("image: url(@UI@/arrow_down.png);", "")
    app.setStyleSheet(style)
