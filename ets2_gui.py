#!/usr/bin/env python3
"""ETS2 Company Manager: окно на PySide6.

Установка:  pip install PySide6
Запуск:     python ets2_gui.py
Рядом с ets2_gui.py должны лежать ets2_manager.py и папки requirements, tools, assets, locales.
"""
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import QObject, QPointF, QRect, QRectF, QSettings, QSize, QSortFilterProxyModel, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QAction, QActionGroup, QBrush, QColor, QDesktopServices, QGuiApplication, QIcon, QPainter,
                           QPalette, QPen, QPixmap, QStandardItem, QStandardItemModel)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QGraphicsOpacityEffect, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QCheckBox, QFrame, QInputDialog, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTableView, QToolButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from tools import ets2_edit as edit
from tools import ets2_fill as fill
from requirements import ets2_theme as theme
from requirements.paths import data_path
from requirements.ets2_i18n import available_langs, get_lang, set_lang, tr
import ets2_manager as core
from requirements import ets2_view as view
from requirements import updates
from requirements.app_info import APP_NAME, VERSION
from requirements import levels
from requirements.levels import SKILL_POINTS_MAX

LEVEL_MAX = 500

ASSETS_ROOT = data_path("assets")
ASSETS = ASSETS_ROOT / "brands"
ICON_H = 22
_icons = {}
SETTINGS_ORG, SETTINGS_APP = "ets2-company-manager", "gui"
UI_SCALES = (100, 110, 125, 150, 175)  # масштаб интерфейса поверх масштаба Windows, %


def app_settings():
    return QSettings(SETTINGS_ORG, SETTINGS_APP)

BG_FILES = {"green": "on_duty", "turquoise": "returning", "blue": "parked", "red": "idle"}
GRAY_BG = (128, 128, 128)


def tinted(pm, color):
    pm = QPixmap(pm)
    painter = QPainter(pm)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pm.rect(), QColor(color))
    painter.end()
    return pm


def avatar_pixmap(n, size=ICON_H + 6):
    path = ASSETS_ROOT / "avatars" / f"{n}.jpg"
    if not path.exists():
        return None
    return QPixmap(str(path)).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)


def _status_icon(spec, key):
    name, _, bg_name = spec.partition("@")
    """Иконка статуса: цветной фон из игры + белый силуэт сверху."""
    if key not in _icons:
        glyph = QPixmap(str(ASSETS_ROOT / "status" / f"{name}.png"))
        bg = QPixmap(str(ASSETS_ROOT / "status" / f"bg_{BG_FILES.get(bg_name, 'idle')}.png"))
        if bg_name == "gray":
            bg = QPixmap(64, 64)
            bg.fill(Qt.GlobalColor.transparent)
            bp = QPainter(bg)
            bp.setRenderHint(QPainter.RenderHint.Antialiasing)
            bp.setBrush(QColor(*GRAY_BG))
            bp.setPen(Qt.PenStyle.NoPen)
            bp.drawRoundedRect(0, 0, 64, 64, 10, 10)
            bp.end()
        if glyph.isNull():
            _icons[key] = None
        else:
            size = 64
            canvas = QPixmap(size, size)
            canvas.fill(Qt.GlobalColor.transparent)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            if not bg.isNull():
                painter.drawPixmap(0, 0, bg.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation))
            g = glyph.scaledToWidth(size - 12, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((size - g.width()) // 2, (size - g.height()) // 2, g)
            painter.end()
            _icons[key] = QIcon(canvas)
    return _icons[key]


def spec_icon(spec):
    """'brand', 'status:<имя>' или 'avatar:<N>' -> QIcon (или None)."""
    if not spec:
        return None
    if spec.startswith("avatar:"):
        pm = avatar_pixmap(spec[7:], 64)
        return QIcon(pm) if pm else None
    if spec.startswith("status:"):
        return _status_icon(spec[7:], spec)
    return brand_icon(spec)


def brand_icon(name):
    """Логотип марки (белый силуэт из assets/brands), перекрашенный под цвет текста темы."""
    key = name if name and (ASSETS / f"{name}.png").exists() else "all"
    if key not in _icons:
        pm = QPixmap(str(ASSETS / f"{key}.png"))
        if pm.isNull():
            _icons[key] = None
        else:
            color = QApplication.palette().color(QPalette.ColorRole.Text)
            pm = pm.scaledToHeight(ICON_H * 2, Qt.TransformationMode.SmoothTransformation)
            painter = QPainter(pm)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pm.rect(), color)
            painter.end()
            _icons[key] = QIcon(pm)
    return _icons[key]


SORT_ROLE = Qt.ItemDataRole.UserRole
KEY_ROLE = Qt.ItemDataRole.UserRole + 1


class TablePage(QWidget):
    """Вкладка: поле фильтра + таблица с сортировкой по клику на заголовок."""

    rowActivated = Signal(str)

    def __init__(self, headers, stretch=False):
        super().__init__()
        self.model = QStandardItemModel(0, len(headers))
        self.model.setHorizontalHeaderLabels([tr(h) for h in headers])

        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)  # искать по всем колонкам

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setIconSize(QSize(ICON_H * 2, ICON_H + 4))
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        if stretch:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header.setMinimumSectionSize(60)
        else:
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.doubleClicked.connect(self._on_double_click)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("Фильтр по любой колонке…"))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self.proxy.setFilterFixedString)
        self.filter.textChanged.connect(lambda _=None: self._update_count())
        self.count = QLabel()

        top = QHBoxLayout()
        top.addWidget(self.filter, 1)
        top.addWidget(self.count)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(self.actions)
        layout.addWidget(self.table)

    def add_action(self, widget):
        """Кнопка или флажок в строке действий над таблицей."""
        if self.actions.count() == 0:
            self.actions.addStretch(1)
        self.actions.insertWidget(self.actions.count() - 1, widget)

    def set_rows(self, rows):
        self.model.removeRows(0, self.model.rowCount())
        for key, cells in rows:
            items = []
            for c in cells:
                it = QStandardItem(c["text"])
                it.setEditable(False)
                it.setData(c["sort"], SORT_ROLE)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # весь текст в таблицах по центру
                if c.get("icon"):
                    icon = spec_icon(c["icon"])
                    if icon:
                        it.setIcon(icon)
                if c.get("tip"):
                    it.setToolTip(c["tip"])
                if c["tint"]:
                    it.setBackground(QBrush(QColor(*c["tint"])))
                items.append(it)
            if items:
                items[0].setData(key, KEY_ROLE)
            self.model.appendRow(items)
        self._update_count()

    def _update_count(self):
        self.count.setText(tr("{a} из {b}", a=self.proxy.rowCount(), b=self.model.rowCount()))

    def selected_keys(self):
        keys = []
        for idx in self.table.selectionModel().selectedRows():
            first = self.model.item(self.proxy.mapToSource(idx).row(), 0)
            key = first.data(KEY_ROLE) if first else None
            if key:
                keys.append(key)
        return keys

    def current_key(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        first = self.model.item(self.proxy.mapToSource(index).row(), 0)
        return first.data(KEY_ROLE) if first else None

    def _on_double_click(self, index):
        src = self.proxy.mapToSource(index)
        first = self.model.item(src.row(), 0)
        key = first.data(KEY_ROLE) if first else None
        if key:
            self.rowActivated.emit(key)


SKILL_ROWS = [
    ("long_dist", "long_distance", "Дальние перевозки", "Рейсы на большие расстояния"),
    ("heavy", "high_value", "Ценные грузы", "Дорогие грузы (high value)"),
    ("fragile", "fragile", "Хрупкие грузы", "Хрупкие грузы"),
    ("urgent", "jit", "Срочная доставка", "Доставка точно в срок (just in time)"),
    ("mechanical", "mechanical", "Экономичное вождение", "Расход топлива (eco driving)"),
]
ADR_CLASSES = (1, 2, 3, 4, 6, 8)  # бит i маски adr = i-й класс по возрастанию
ADR_NAMES = {1: "Взрывчатые", 2: "Газы", 3: "Горючие жидкости", 4: "Горючие твёрдые", 6: "Токсичные", 8: "Едкие"}


def skill_pixmap(name, size, dim=False):
    pm = QPixmap(str(ASSETS_ROOT / "skills" / f"{name}.png"))
    if pm.isNull():
        return pm
    pm = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    if dim:
        out = QPixmap(pm.size())
        out.fill(Qt.GlobalColor.transparent)
        p = QPainter(out)
        p.setOpacity(0.3)
        p.drawPixmap(0, 0, pm)
        p.end()
        return out
    return pm


class SkillsPage(QWidget):
    """Вкладка «Навыки»: прокачка навыков имеющихся водителей, как в игре: выбираешь, что поднять, и применяешь."""
    applyRequested = Signal(str, dict, int)  # id водителя, {навык: новое значение}, новый уровень (-1: без изменений)
    PIP = 30

    def __init__(self, settings):
        super().__init__()
        self.settings, self.company = settings, None
        self.driver, self.pending = None, {}
        self.current_id = None

        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("Поиск водителя…"))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._fill_list)
        self.list = QListWidget()
        self.list.setIconSize(QSize(40, 40))
        self.list.currentItemChanged.connect(self._on_pick)
        left = QVBoxLayout()
        left.addWidget(self.filter)
        left.addWidget(self.list, 1)
        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(280)

        self.avatar = QLabel()
        self.avatar.setFixedSize(96, 96)
        self.title = QLabel()
        self.title.setTextFormat(Qt.TextFormat.RichText)
        self.points = QLabel()
        self.points.setTextFormat(Qt.TextFormat.RichText)
        self.new_level = None  # новый уровень водителя или None
        self.level = QSpinBox()
        self.level.setRange(0, LEVEL_MAX)
        self.level.setToolTip(tr("Уровень водителя. Очков навыков столько же, сколько уровней (максимум 36). "
                                 "Новый уровень записывается в сейв как опыт ровно на начало этого уровня."))
        self.level.valueChanged.connect(self._level_changed)
        head = QHBoxLayout()
        head.addWidget(self.avatar)
        info = QVBoxLayout()
        info.addWidget(self.title)
        info.addWidget(self.points)
        lim_row = QHBoxLayout()
        lim_row.addWidget(QLabel(tr("Уровень:")))
        lim_row.addWidget(self.level)
        lim_row.addStretch(1)
        info.addLayout(lim_row)
        head.addLayout(info, 1)

        self.rows_box = QVBoxLayout()
        self.rows_box.setSpacing(10)
        self.apply_btn = QPushButton(tr("Применить к сейву…"))
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self._apply)
        self.reset_btn = QPushButton(tr("Сбросить выбор"))
        self.reset_btn.clicked.connect(self._reset)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.reset_btn)
        btns.addWidget(self.apply_btn)

        body = QVBoxLayout()
        body.addLayout(head)
        body.addLayout(self.rows_box)
        body.addStretch(1)
        body_w = QWidget()
        body_w.setLayout(body)
        scroll = QScrollArea()  # на небольшом экране или при масштабе 125-150% навыки не обрезаются
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body_w)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll.viewport().setAutoFillBackground(False)
        body_w.setAutoFillBackground(False)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(scroll, 1)
        right.addLayout(btns)
        right_w = QWidget()
        right_w.setLayout(right)

        lay = QHBoxLayout(self)
        lay.addWidget(left_w)
        lay.addWidget(right_w, 1)

    # ----- данные -----

    def set_company(self, company):
        self.company = company
        self._fill_list()

    def _fill_list(self):
        if not self.company:
            return
        q = self.filter.text().strip().lower()
        self.list.blockSignals(True)
        self.list.clear()
        keep = None
        for d in self.company["drivers"]:
            if q and q not in d["name"].lower() and q not in d["id"].lower():
                continue
            item = QListWidgetItem(f"{'★ ' if d['is_player'] else ''}{d['name']}\n" + tr("ур. {n}", n=d["level"]) + "  ·  "
                                   + tr("Σ навыков {n}/36", n=d['skill_sum']))
            item.setData(Qt.ItemDataRole.UserRole, d["id"])
            pm = avatar_pixmap(d["id"].rpartition(".")[2], 40)
            if pm:
                item.setIcon(QIcon(pm))
            self.list.addItem(item)
            if d["id"] == self.current_id:
                keep = item
        self.list.blockSignals(False)
        if keep is None and self.list.count():
            keep = self.list.item(0)
        if keep:
            self.list.setCurrentItem(keep)
            self._select(keep.data(Qt.ItemDataRole.UserRole))
        else:
            self._select(None)

    def _on_pick(self, item, _prev=None):
        self._select(item.data(Qt.ItemDataRole.UserRole) if item else None)

    def _select(self, did):
        self.current_id = did
        self.driver = next((d for d in self.company["drivers"] if d["id"] == did), None) if self.company else None
        self.pending, self.new_level = {}, None
        if self.driver:
            d = self.driver
            self.level.blockSignals(True)
            # ниже уже потраченных очков уровень не опустить: навыки не снимаются
            self.level.setRange(min(d["level"], d["skill_sum"]), max(LEVEL_MAX, d["level"]))
            self.level.setValue(d["level"])
            self.level.blockSignals(False)
        self._render()

    def _level_changed(self, v):
        if not self.driver:
            return
        self.new_level = None if v == self.driver["level"] else v
        if self._sum() > self._limit():  # выбранные навыки больше не помещаются в новый уровень
            self.pending = {}
        self._render()

    def _limit(self):
        return min(SKILL_POINTS_MAX, self.level.value())

    def _reset(self):
        self._select(self.current_id)

    # ----- состояние -----

    def _level(self, key):
        return self.pending.get(key, self.driver["skills"][key])

    def _mask(self):
        return self.pending.get("adr", self.driver["skills"]["adr"])

    def _sum(self):
        return sum(self._level(k) for k, *_ in SKILL_ROWS) + bin(self._mask()).count("1")

    def _free(self):
        return max(0, self._limit() - self._sum())

    def _set_level(self, key, i):
        base, cur = self.driver["skills"][key], self._level(key)
        if i > cur:
            i = min(i, cur + self._free())
        elif i == cur and cur > base:
            i = cur - 1
        i = max(base, i)
        if i == base:
            self.pending.pop(key, None)
        else:
            self.pending[key] = i
        self._render()

    def _toggle_adr(self, bit):
        base, cur = self.driver["skills"]["adr"], self._mask()
        if base >> bit & 1:
            return
        if cur >> bit & 1:
            cur &= ~(1 << bit)
        elif self._free() > 0:
            cur |= 1 << bit
        if cur == base:
            self.pending.pop("adr", None)
        else:
            self.pending["adr"] = cur
        self._render()

    # ----- отрисовка -----

    def _clear_rows(self):
        while self.rows_box.count():
            it = self.rows_box.takeAt(0)
            lay = it.layout()
            if lay is not None:
                while lay.count():
                    sub = lay.takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
            if it.widget():
                it.widget().deleteLater()

    def _render(self):
        self._clear_rows()
        d = self.driver
        changed = bool(d and (self.pending or self.new_level is not None))
        self.apply_btn.setEnabled(changed)
        self.reset_btn.setEnabled(changed)
        if not d:
            self.title.setText(tr("Нет водителей"))
            self.points.clear()
            self.avatar.clear()
            return
        pm = avatar_pixmap(d["id"].rpartition(".")[2], 96)
        if pm:
            self.avatar.setPixmap(pm)
        else:
            self.avatar.clear()
        st_text, _ = view.driver_status(d)
        self.title.setText(f"<span style='font-size:16pt'><b>{('★ ' if d['is_player'] else '') + d['name']}</b></span><br>"
                           f"{d['city'] or '-'} · {st_text}<br>" + view.level_text(d))
        free = self._free()
        self.points.setText(tr("Свободно очков: ") + f"<b style='color:{theme.c('accent') if free else theme.c('muted')}'>{free}</b> "
                            + tr("· Σ {a} из {b}", a=self._sum(), b=self._limit()))

        for key, icon, name, hint in SKILL_ROWS:
            level, base = self._level(key), d["skills"][key]
            row = QHBoxLayout()
            ic = QLabel()
            ic.setPixmap(skill_pixmap(icon if level else icon + "_off", 56))
            ic.setFixedSize(60, 60)
            muted = theme.c("muted")
            txt = QLabel(f"<b>{tr(name)}</b><br><span style='color:{muted}'>{tr(hint)}</span>")
            txt.setTextFormat(Qt.TextFormat.RichText)
            txt.setMinimumWidth(240)
            row.addWidget(ic)
            row.addWidget(txt)
            row.addStretch(1)
            for i in range(1, 7):
                b = QPushButton(str(i))
                b.setFixedSize(self.PIP, self.PIP)
                if i <= base:
                    color, fg = theme.c("accent"), theme.c("on_accent")
                elif i <= level:
                    color, fg = theme.c("good"), theme.c("on_accent")
                else:
                    color, fg = "transparent", theme.c("muted")
                b.setStyleSheet(f"QPushButton {{ background: {color}; color: {fg}; border: 1px solid {theme.c('muted')}; "
                                f"border-radius: 4px; }}")
                b.setEnabled(i > base)
                if i > base and i > level and free == 0:
                    b.setEnabled(False)
                b.clicked.connect(lambda _=False, k=key, n=i: self._set_level(k, n))
                row.addWidget(b)
            row_w = QWidget()
            row_w.setLayout(row)
            self.rows_box.addWidget(row_w)

        # ADR: шесть классов, полученные нельзя убрать
        base_mask, mask = d["skills"]["adr"], self._mask()
        adr_head = QLabel(tr("<b>ADR: опасные грузы</b> · классов {n} из 6", n=bin(mask).count('1')))
        adr_head.setTextFormat(Qt.TextFormat.RichText)
        ic = QLabel()
        ic.setPixmap(skill_pixmap("adr" if mask else "adr_off", 56))
        top = QHBoxLayout()
        top.addWidget(ic)
        top.addWidget(adr_head)
        top.addStretch(1)
        top_w = QWidget()
        top_w.setLayout(top)
        self.rows_box.addWidget(top_w)
        cls = QHBoxLayout()
        for bit, k in enumerate(ADR_CLASSES):
            have, new = bool(base_mask >> bit & 1), bool(mask >> bit & 1) and not (base_mask >> bit & 1)
            on = have or new
            b = QPushButton()
            b.setIcon(QIcon(skill_pixmap(f"adr_{k}", 64, dim=not on)))
            b.setIconSize(QSize(64, 64))
            b.setFixedSize(76, 76)
            border = theme.c("accent") if have else (theme.c("good") if new else theme.c("border"))
            b.setStyleSheet(f"QPushButton {{ border: 2px solid {border}; border-radius: 6px; background: transparent; }}")
            b.setToolTip(tr("Класс {k}: {name}", k=k, name=tr(ADR_NAMES[k])) + (tr(" (уже есть)") if have else ""))
            b.setEnabled(not have and (on or free > 0))
            b.clicked.connect(lambda _=False, bt=bit: self._toggle_adr(bt))
            cls.addWidget(b)
        cls.addStretch(1)
        cls_w = QWidget()
        cls_w.setLayout(cls)
        self.rows_box.addWidget(cls_w)
        for i in range(self.rows_box.count()):  # строки не сжимаются: при нехватке места появляется прокрутка
            w = self.rows_box.itemAt(i).widget()
            if w:
                w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _apply(self):
        if self.driver and (self.pending or self.new_level is not None):
            self.applyRequested.emit(self.driver["id"], dict(self.pending), -1 if self.new_level is None else self.new_level)


def wrench_icon(size=32):
    """Гаечный ключ, нарисованный цветом текста темы (без эмодзи, чтобы везде выглядел одинаково)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24, size / 24)
    color = QColor(theme.c("text"))
    p.setPen(QPen(color, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(5, 19), QPointF(13.2, 10.8))  # рукоять
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(15.5, 8.5), 5.2, 5.2)  # головка
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    p.translate(15.5, 8.5)
    p.rotate(-45)
    p.drawRect(QRectF(-1.7, -7, 3.4, 6.5))  # зев ключа
    p.end()
    return QIcon(pm)


class EditButton(QToolButton):
    """Полупрозрачная кнопка правки в углу плитки; при наведении становится яркой."""

    def __init__(self, parent, tip):
        super().__init__(parent)
        self.setObjectName("tileEdit")
        self.setIcon(wrench_icon())
        self.setIconSize(QSize(14, 14))
        self.setFixedSize(20, 20)
        self.setToolTip(tip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.fx = QGraphicsOpacityEffect(self)
        self.fx.setOpacity(0.35)
        self.setGraphicsEffect(self.fx)

    def enterEvent(self, event):
        self.fx.setOpacity(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.fx.setOpacity(0.35)
        super().leaveEvent(event)


class Tile(QFrame):
    """Плитка сводки. С on_edit: ключ в правом верхнем углу и двойной клик открывают правку."""
    doubleClicked = Signal()

    def __init__(self, tip=None):
        super().__init__()
        self.edit_btn = EditButton(self, tip) if tip else None
        if tip:
            self.setToolTip(tip)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def resizeEvent(self, event):
        if self.edit_btn:
            self.edit_btn.move(self.width() - self.edit_btn.width() - 3, 3)
            self.edit_btn.raise_()
        super().resizeEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)


class StatBar(QWidget):
    """Плитки сводки по компании над вкладками."""
    editMoney = Signal()
    editLevel = Signal()

    def __init__(self):
        super().__init__()
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(10)
        self.hint = QLabel(tr("Открой сейв: Файл → Открыть сейв…"))
        self.hint.setStyleSheet(f"color: {theme.c('muted')}; padding: 10px;")
        self.lay.addWidget(self.hint)

    def _tile(self, label, value, accent=False, on_edit=None, tip=None):
        tile = Tile(tip if on_edit else None)
        tile.setObjectName("tile")
        if on_edit:
            tile.doubleClicked.connect(on_edit)
            tile.edit_btn.clicked.connect(on_edit)
        box = QVBoxLayout(tile)
        box.setContentsMargins(14, 8, 26 if on_edit else 14, 8)  # справа место под ключ
        box.setSpacing(0)
        cap = QLabel(label.upper())
        cap.setObjectName("tileLabel")
        val = QLabel(value)
        val.setObjectName("tileValue")
        val.setProperty("accent", "true" if accent else "false")
        box.addWidget(cap)
        box.addWidget(val)
        return tile

    def set_company(self, c):
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        busy = sum(1 for d in c["drivers"] if d["job"])
        tiles = []
        if c["money"] is not None:
            tiles.append((tr("Деньги"), view.safe_money(c["money"]), True, self.editMoney.emit,
                          tr("Изменить баланс (или двойной клик по плитке)")))
        tiles += [
            (tr("Штаб"), c["hq"] or "-", False),
            (tr("Уровень"), str(levels.level_for_xp(c["xp"])), False, self.editLevel.emit,
             tr("Изменить уровень (или двойной клик по плитке)")),
            (tr("Водители"), f"{len(c['drivers'])}  ·  " + tr("в рейсе {n}", n=busy), False),
            (tr("Траки"), str(sum(1 for d in c["drivers"] if d["truck"])), False),
            (tr("Прицепы"), str(len(c["trailers"])), False),
            (tr("Гаражи"), str(len(c["garages"])), False),
            (tr("Пробег"), f"{core.money(c['distance_km'])} " + tr("км"), False),
            (tr("Игровых дней"), f"{c['game_days']:.1f}", False),
        ]
        for t in tiles:
            self.lay.addWidget(self._tile(*t))
        self.lay.addStretch(1)


class DriverDialog(QDialog):
    """Карточка водителя: сводка, имя и история последних заказов."""

    def __init__(self, driver, parent, on_rename):
        super().__init__(parent)
        self.driver, self.on_rename = driver, on_rename
        self.setWindowTitle(tr("Водитель {name}", name=driver['name']))
        self.resize(760, 600)

        info = QLabel(view.driver_card_html(driver))
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.name_edit = QLineEdit(driver["name"])
        self.name_edit.setPlaceholderText(tr("Своё имя для {id} (пусто = имя по умолчанию)", id=driver['id']))
        save = QPushButton(tr("Сохранить имя"))
        save.clicked.connect(self._rename)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(tr("Имя:")))
        name_row.addWidget(self.name_edit, 1)
        name_row.addWidget(save)

        history = driver["stats"]["history"][:30]
        table = QTableWidget(len(history), 5)
        table.setHorizontalHeaderLabels([tr(x) for x in ("День", "Груз", "Маршрут", "Км", "Выручка")])
        table.verticalHeader().setVisible(False)
        for r, h in enumerate(history):
            values = [h["day"], h["cargo"], h["route"], h["km"], core.money(h["revenue"])]
            for col, val in enumerate(values):
                it = QTableWidgetItem(str(val))
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r, col, it)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)

        head = QHBoxLayout()
        pm = avatar_pixmap(driver["id"].rpartition(".")[2], 160)
        if pm:
            pic = QLabel()
            pic.setPixmap(pm)
            pic.setAlignment(Qt.AlignmentFlag.AlignTop)
            head.addWidget(pic)
        head.addWidget(info, 1)
        st_text, st_icon = view.driver_status(driver)
        info.setText(tr("<b>Статус: {s}</b>", s=st_text) + "<br>" + view.driver_card_html(driver))

        layout = QVBoxLayout(self)
        layout.addLayout(head)
        layout.addLayout(name_row)
        layout.addWidget(QLabel(tr("Последние заказы (по сохранённой истории):")))
        layout.addWidget(table, 1)

    def _rename(self):
        self.on_rename(self.driver["id"], self.name_edit.text().strip())
        self.accept()


class ProfileDialog(QDialog):
    """Выбор профиля (ETS2 и ATS) и слота сохранения."""

    def __init__(self, parent, current=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Выбор профиля и сохранения"))
        self.resize(760, 460)
        self.chosen = None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.profiles = view.find_profiles()
        finally:
            QApplication.restoreOverrideCursor()
        cur_dir = view.profile_dir_of(current) if current else None

        self.plist = QListWidget()
        self.slist = QListWidget()
        self.plist.currentRowChanged.connect(self._fill_slots)
        self.slist.itemDoubleClicked.connect(lambda _it: self._accept())
        keep = 0
        for i, p in enumerate(self.profiles):
            game = "ETS2" if p["game"] == "ets2" else "ATS"
            when = datetime.fromtimestamp(p["mtime"]).strftime("%d.%m.%Y %H:%M")
            it = QListWidgetItem(f"{p['name']}\n{game} · " + tr("сохранений: {n}", n=len(p["saves"])) + f" · {when}")
            it.setToolTip(str(p["dir"]))
            self.plist.addItem(it)
            if cur_dir and Path(p["dir"]) == Path(cur_dir):
                keep = i
        self.current = current

        cols = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        left.addWidget(QLabel(tr("Профиль:")))
        left.addWidget(self.plist, 1)
        right.addWidget(QLabel(tr("Сохранение (сверху самое свежее):")))
        right.addWidget(self.slist, 1)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        self.open_btn = buttons.button(QDialogButtonBox.StandardButton.Open)

        lay = QVBoxLayout(self)
        if not self.profiles:
            lay.addWidget(QLabel(tr("Профили не найдены в папке «Документы». Откройте game.sii вручную: Файл → Открыть сейв…")))
        lay.addLayout(cols, 1)
        lay.addWidget(buttons)
        if self.profiles:
            self.plist.setCurrentRow(keep)
        else:
            self.open_btn.setEnabled(False)

    def _fill_slots(self, row):
        self.slist.clear()
        if row < 0 or row >= len(self.profiles):
            return
        keep = 0
        for i, sv in enumerate(self.profiles[row]["saves"]):
            when = datetime.fromtimestamp(sv["mtime"]).strftime("%d.%m.%Y %H:%M")
            it = QListWidgetItem(f"{sv['title']}  ·  {when}")
            it.setToolTip(str(sv["path"]))
            self.slist.addItem(it)
            if self.current and Path(sv["path"]) == Path(self.current):
                keep = i
        self.slist.setCurrentRow(keep)

    def _accept(self):
        p, s_row = self.plist.currentRow(), self.slist.currentRow()
        if 0 <= p < len(self.profiles) and 0 <= s_row < len(self.profiles[p]["saves"]):
            self.chosen = self.profiles[p]["saves"][s_row]["path"]
            self.accept()


def big_spin(lo, hi, value):
    box = QSpinBox()
    box.setRange(lo, hi)
    box.setGroupSeparatorShown(True)
    box.setSingleStep(1000)
    box.setValue(max(lo, min(hi, value)))
    box.setMinimumWidth(200)
    return box


class ValueDialog(QDialog):
    """Окно правки одного числа (баланс или уровень): поле, пояснение, ОК / Отмена."""

    def __init__(self, parent, title, label, spin, note):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.spin = spin
        self.start = spin.value()  # значение вне диапазона поля уже обрезано: без правки ничего не запишется
        form = QFormLayout()
        form.addRow(label, spin)
        hint = QLabel(note)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {theme.c('muted')};")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addWidget(buttons)
        spin.setFocus()
        spin.selectAll()

    def new_value(self):
        """Новое значение или None, если не меняли."""
        return self.spin.value() if self.spin.value() != self.start else None


class FillDialog(QDialog):
    """Заполнение гаражей: свободные места, водители из агентства и запаса игры (с фото), образцы грузовика и прицепа."""

    SKILL_COLS = (("long_dist", "Дальн."), ("heavy", "Тяжёл."), ("fragile", "Хрупк."), ("urgent", "Срочн."), ("mechanical", "Эко"))

    def __init__(self, parent, sv):
        super().__init__(parent)
        self.setWindowTitle(tr("Заполнить гаражи"))
        self.resize(980, 760)
        self.slots = fill.free_slots(sv)
        self.pool = sorted(fill.pool_drivers(sv), key=lambda d: (-d["xp"], d["name"]))
        self.trucks = fill.truck_templates(sv)
        self.trailers = fill.trailer_templates(sv)
        self.plan = None

        # --- гаражи ---
        by_garage = {}
        for s in self.slots:
            by_garage.setdefault(s["garage"], []).append(s)
        self.garages = list(by_garage.items())
        self.gtable = QTableWidget(len(self.garages), 4)
        self.gtable.setHorizontalHeaderLabels([tr("Гараж"), tr("Свободных мест"), tr("Нужно водителей"), tr("Нужно грузовиков")])
        self.gtable.verticalHeader().setVisible(False)
        self.gtable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, (gid, slots) in enumerate(self.garages):
            it = QTableWidgetItem(slots[0]["city"])
            it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Checked)
            self.gtable.setItem(r, 0, it)
            for c, v in enumerate((len(slots), sum(not s["has_driver"] for s in slots),
                                   sum(not s["has_truck"] for s in slots)), 1):
                cell = QTableWidgetItem(str(v))
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.gtable.setItem(r, c, cell)
        self.gtable.resizeColumnsToContents()
        self.gtable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.gtable.setMaximumHeight(200)
        self.gtable.itemChanged.connect(lambda *_: self._update())

        # --- водители ---
        heads = ["", tr("Имя"), tr("Ур."), "ADR"] + [tr(t) for _, t in self.SKILL_COLS] + [tr("Где")]
        self.dtable = QTableWidget(len(self.pool), len(heads))
        self.dtable.setHorizontalHeaderLabels(heads)
        self.dtable.verticalHeader().setVisible(False)
        self.dtable.verticalHeader().setDefaultSectionSize(44)
        self.dtable.setIconSize(QSize(40, 40))
        self.dtable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dtable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for r, d in enumerate(self.pool):
            pic = QTableWidgetItem()
            pm = avatar_pixmap(d["id"].rpartition(".")[2], 40)
            if pm:
                pic.setIcon(QIcon(pm))
            pic.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            pic.setCheckState(Qt.CheckState.Unchecked)
            self.dtable.setItem(r, 0, pic)
            vals = [d["name"], d["level"], d["adr_classes"]] + [d["skills"][k] for k, _ in self.SKILL_COLS] + \
                   [tr("агентство") if d["offered"] else tr("запас")]
            for c, v in enumerate(vals, 1):
                cell = QTableWidgetItem(str(v))
                if c > 1:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.dtable.setItem(r, c, cell)
        self.dtable.resizeColumnsToContents()
        self.dtable.setColumnWidth(0, 64)
        self.dtable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.dtable.itemChanged.connect(lambda *_: self._update())
        best = QPushButton(tr("Выбрать лучших"))
        best.setToolTip(tr("Отмечает водителей с самым высоким уровнем, сколько нужно для отмеченных гаражей"))
        best.clicked.connect(self._pick_best)
        none = QPushButton(tr("Снять выбор"))
        none.clicked.connect(lambda: self._check_drivers(set()))

        # --- грузовик, прицеп, цены ---
        self.truck_box = QCheckBox(tr("Ставить грузовик в пустые места"))
        self.truck_box.setChecked(bool(self.trucks))
        self.truck_box.setEnabled(bool(self.trucks))
        self.truck_combo = QComboBox()
        for t in self.trucks:
            self.truck_combo.addItem(f"{t['model']} · {t['plate']}", t["unit"])
        self.trailer_combo = QComboBox()
        self.trailer_combo.addItem(tr("Без прицепа"), None)
        for t in self.trailers:
            self.trailer_combo.addItem(f"{t['kind']} · {t['plate']}", t["unit"])
        self.hire_price = big_spin(0, 10_000_000, fill.HIRE_FEE)
        self.truck_price = big_spin(0, 10_000_000, 100_000)
        self.trailer_price = big_spin(0, 10_000_000, 30_000)
        self.truck_box.toggled.connect(lambda *_: self._update())
        for w in (self.truck_combo, self.trailer_combo):
            w.currentIndexChanged.connect(lambda *_: self._update())
        for w in (self.hire_price, self.truck_price, self.trailer_price):
            w.valueChanged.connect(lambda *_: self._update())
        form = QFormLayout()
        form.addRow(tr("Найм одного водителя, €:"), self.hire_price)
        truck_row = QHBoxLayout()
        truck_row.addWidget(self.truck_combo, 1)
        truck_row.addWidget(QLabel(tr("цена, €:")))
        truck_row.addWidget(self.truck_price)
        form.addRow(self.truck_box, truck_row)
        trailer_row = QHBoxLayout()
        trailer_row.addWidget(self.trailer_combo, 1)
        trailer_row.addWidget(QLabel(tr("цена, €:")))
        trailer_row.addWidget(self.trailer_price)
        form.addRow(tr("Прицеп каждому новому водителю:"), trailer_row)
        hint = QLabel(tr("Грузовик и прицеп — копии выбранных ваших, как новые: пробег 0, износ 0, полный бак, свой номер. "
                         "Цены по умолчанию примерные, поставьте цены из игры или 0, чтобы не списывать."))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {theme.c('muted')};")
        self.summary = QLabel()
        self.summary.setWordWrap(True)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Заполнить"))
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)

        pick_row = QHBoxLayout()
        pick_row.addWidget(QLabel(tr("Свободные водители (агентство и запас игры). Отметьте, кого нанять:")), 1)
        pick_row.addWidget(best)
        pick_row.addWidget(none)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("Гаражи со свободными местами:")))
        lay.addWidget(self.gtable)
        lay.addLayout(pick_row)
        lay.addWidget(self.dtable, 1)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addWidget(self.summary)
        lay.addWidget(self.buttons)
        self._pick_best()

    # --- выбор ---
    def _chosen_garages(self):
        return [slots for r, (_, slots) in enumerate(self.garages)
                if self.gtable.item(r, 0).checkState() == Qt.CheckState.Checked]

    def _need_drivers(self):
        return sum(not s["has_driver"] for slots in self._chosen_garages() for s in slots)

    def _chosen_drivers(self):
        return [d["id"] for r, d in enumerate(self.pool)
                if self.dtable.item(r, 0).checkState() == Qt.CheckState.Checked]

    def _check_drivers(self, ids):
        self.dtable.blockSignals(True)
        for r, d in enumerate(self.pool):
            self.dtable.item(r, 0).setCheckState(Qt.CheckState.Checked if d["id"] in ids else Qt.CheckState.Unchecked)
        self.dtable.blockSignals(False)
        self._update()

    def _pick_best(self):
        self._check_drivers({d["id"] for d in self.pool[:self._need_drivers()]})

    def build_plan(self):
        drivers = self._chosen_drivers()
        trucks = self.truck_box.isChecked() and self.truck_combo.currentData() is not None
        trailer = self.trailer_combo.currentData()
        plan_slots = []
        for slots in self._chosen_garages():
            for s in slots:
                new_driver = None
                if not s["has_driver"]:
                    if not drivers:
                        continue
                    new_driver = drivers.pop(0)
                plan_slots.append({"garage": s["garage"], "slot": s["slot"], "driver": new_driver,
                                   "truck": trucks and not s["has_truck"], "trailer": bool(trailer and new_driver)})
        plan_slots = [s for s in plan_slots if s["driver"] or s["truck"]]
        n_drv = sum(1 for s in plan_slots if s["driver"])
        n_trk = sum(1 for s in plan_slots if s["truck"])
        n_trl = sum(1 for s in plan_slots if s["trailer"])
        cost = n_drv * self.hire_price.value() + n_trk * self.truck_price.value() + n_trl * self.trailer_price.value()
        return {"slots": plan_slots, "truck_template": self.truck_combo.currentData() if trucks else None,
                "trailer_template": trailer, "cost": cost}, (n_drv, n_trk, n_trl, len(drivers))

    def _update(self):
        plan, (n_drv, n_trk, n_trl, extra) = self.build_plan()
        text = tr("Будет нанято водителей: {d}, грузовиков: {t}, прицепов: {p}. Всего к списанию: {cost} €.",
                  d=n_drv, t=n_trk, p=n_trl, cost=core.money(plan["cost"]))
        if extra:
            text += " " + tr("Отмечено лишних водителей: {n}, для них нет свободных мест.", n=extra)
        if not self.trucks:
            text += " " + tr("Своих грузовиков нет, копировать нечего: будут только водители.")
        self.summary.setText(text)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(plan["slots"]))

    def _accept(self):
        self.plan, _ = self.build_plan()
        self.accept()

    def counts(self):
        return self.build_plan()[1]


class UpdateChecker(QObject):
    """Проверка обновлений в фоновом потоке (daemon), чтобы окно не подвисало без сети и не ждало её при выходе."""
    done = Signal(bool, dict, str)  # есть новее, данные релиза, ошибка

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            newer, rel = updates.check()
            result = (newer, rel, "")
        except updates.UpdateError as exc:
            result = (False, {}, str(exc) or "?")
        self.running = False
        try:
            self.done.emit(*result)
        except RuntimeError:  # окно уже закрыто
            pass


def fit_to_screens(win, default_size=QSize(1300, 740)):
    """Если окно оказалось за пределами экранов (отключили второй монитор, сменили масштаб), возвращает его на основной."""
    screens = QGuiApplication.screens()
    frame = win.frameGeometry()
    # заголовок окна должен быть виден хотя бы на одном экране, иначе окно не перетащить
    title = QRect(frame.left() + 40, frame.top(), max(1, frame.width() - 80), 30)
    if any(sc.availableGeometry().intersects(title) for sc in screens) and not win.isMaximized():
        avail = (win.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        if win.width() > avail.width() or win.height() > avail.height():
            win.resize(min(win.width(), avail.width()), min(win.height(), avail.height()))
        return
    if win.isMaximized():
        return
    avail = QGuiApplication.primaryScreen().availableGeometry()
    w = min(default_size.width(), int(avail.width() * 0.95))
    h = min(default_size.height(), int(avail.height() * 0.9))
    win.resize(w, h)
    win.move(avail.left() + (avail.width() - w) // 2, avail.top() + (avail.height() - h) // 2)


class MainWindow(QMainWindow):
    TABS = [
        ("drivers", "Водители", view.DRIVER_HEADERS, view.driver_rows),
        ("trucks", "Траки", view.TRUCK_HEADERS, view.truck_rows),
        ("trailers", "Прицепы", view.TRAILER_HEADERS, view.trailer_rows),
        ("garages", "Гаражи", view.GARAGE_HEADERS, view.garage_rows),
        ("jobs", "Рейсы", view.JOB_HEADERS, view.job_rows),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        avail = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(1300, int(avail.width() * 0.95)), min(740, int(avail.height() * 0.9)))
        self.settings = app_settings()
        self.updater = UpdateChecker(self)
        self.updater.running = False
        self.updater.done.connect(self._on_update_result)
        self._manual_update = False
        self._rebuilding = False
        self.company = None
        self.save_path = None
        self.mtime = 0.0

        self.header = StatBar()
        self.header.editMoney.connect(self.edit_money)
        self.header.editLevel.connect(self.edit_level)
        self.tabs = QTabWidget()
        self.pages = {}
        for key, title, headers, _ in self.TABS:
            page = TablePage(headers, stretch=key in ('trucks', 'trailers', 'garages', 'jobs'))
            self.pages[key] = page
            self.tabs.addTab(page, tr(title))
        for key in ("drivers", "trucks", "jobs"):
            self.pages[key].rowActivated.connect(self.open_driver)
        self.skills = SkillsPage(self.settings)
        self.skills.applyRequested.connect(self.apply_skills)
        self.tabs.addTab(self.skills, tr("Навыки"))

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        layout.addWidget(self.header)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        menu = self.menuBar().addMenu(tr("Файл"))
        self._action(menu, tr("Выбрать профиль и сохранение…"), self.choose_profile, "Ctrl+P")
        self._action(menu, tr("Открыть сейв…"), self.open_dialog, "Ctrl+O")
        self._action(menu, tr("Найти последний сейв"), self.open_latest, "Ctrl+L")
        self._action(menu, tr("Обновить"), self.reload, "F5")
        menu.addSeparator()
        self.watch_action = self._action(menu, tr("Следить за изменениями сейва"), lambda: None, checkable=True)
        self.watch_action.setChecked(self.settings.value("watch", True, type=bool))
        self.watch_action.toggled.connect(lambda on: self.settings.setValue("watch", on))
        menu.addSeparator()
        self._action(menu, tr("Восстановить сейв из резервной копии…"), self.restore_dialog)
        menu.addSeparator()
        self._action(menu, tr("Выход"), self.close, "Ctrl+Q")

        lmenu = self.menuBar().addMenu("Язык / Language")
        for code, name in available_langs().items():
            act = self._action(lmenu, name, lambda c=code: self.switch_language(c), checkable=True)
            act.setChecked(code == get_lang())
        tmenu = self.menuBar().addMenu(tr("Тема"))
        self.theme_actions = []
        for mode, label in (("dark", tr("Тёмная")), ("light", tr("Светлая"))):
            act = self._action(tmenu, label, lambda m=mode: self.switch_theme(m), checkable=True)
            act.setData(mode)
            act.setChecked(mode == theme.mode())
            self.theme_actions.append(act)

        smenu = self.menuBar().addMenu(tr("Настройки"))
        self.update_action = self._action(smenu, tr("Проверять обновления при запуске"), lambda: None, checkable=True)
        self.update_action.setChecked(self.settings.value("check_updates", True, type=bool))
        self.update_action.toggled.connect(lambda on: self.settings.setValue("check_updates", on))
        scale_menu = smenu.addMenu(tr("Масштаб интерфейса"))
        group = QActionGroup(self)
        cur_scale = self.settings.value("ui_scale", 100, type=int)
        for pct in UI_SCALES:
            act = self._action(scale_menu, f"{pct}%", lambda p=pct: self.set_ui_scale(p), checkable=True)
            act.setChecked(pct == cur_scale)
            group.addAction(act)
        smenu.addSeparator()
        self._action(smenu, tr("Сбросить положение окна"), self.reset_window)

        hmenu = self.menuBar().addMenu(tr("Справка"))
        self._action(hmenu, tr("Проверить обновления"), lambda: self.check_updates(manual=True))
        self._action(hmenu, tr("Страница проекта на GitHub"),
                     lambda: QDesktopServices.openUrl(QUrl(f"https://github.com/{updates.REPO}")))
        self._action(hmenu, tr("О программе"), self.show_about)
        self._build_action_rows()
        self.pages["drivers"].model.setHeaderData(
            view.DRIVER_HEADERS.index("Σ навыков"), Qt.Orientation.Horizontal,
            tr("Сумма очков навыков водителя (ADR считается по числу классов). Максимум 36: 6 навыков по 6. "
               "Обычно равна уровню: одно очко за уровень."), Qt.ItemDataRole.ToolTipRole)
        self.pages["drivers"].model.setHeaderData(
            view.DRIVER_HEADERS.index("Ур."), Qt.Orientation.Horizontal,
            tr("Уровень по опыту, как в игре. У нанятых водителей порог каждого уровня вдвое выше, чем у игрока."),
            Qt.ItemDataRole.ToolTipRole)

        self.timer = QTimer(self)
        self.timer.setInterval(3000)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    def switch_language(self, code):
        """Сохраняет язык и открывает окно заново уже на нём (сейв подгружается тот же)."""
        if code == get_lang():
            self.menuBar().update()
            for act in self.findChildren(QAction):
                if act.isCheckable() and act.text() in available_langs().values():
                    act.setChecked(act.text() == available_langs()[code])
            return
        self.settings.setValue("lang", code)
        set_lang(code)
        self._rebuild()

    def switch_theme(self, mode):
        if mode == theme.mode():
            for act in self.theme_actions:
                act.setChecked(act.data() == mode)
            return
        self.settings.setValue("theme", mode)
        theme.apply(QApplication.instance(), ASSETS_ROOT / "ui", mode)
        _icons.clear()  # логотипы марок перекрашиваются под цвет текста темы
        self._rebuild()

    def _rebuild(self):
        """Окно создаётся заново (язык и тема применяются целиком), сейв подгружается тот же."""
        global _window
        old = _window
        old._remember_geometry()
        old._rebuilding = True
        _window = MainWindow()
        _window.restoreGeometry(old.saveGeometry())  # то же место, размер и монитор
        _window.show()
        _window.startup()
        old.close()

    # ----- окно: положение, масштаб -----

    def _remember_geometry(self):
        self.settings.setValue("geometry", self.saveGeometry())

    def restore_window(self):
        """Возвращает окно туда, где его закрыли; если того экрана уже нет, ставит на основной."""
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        fit_to_screens(self)

    def closeEvent(self, event):
        if not self._rebuilding:
            self._remember_geometry()
        super().closeEvent(event)

    def reset_window(self):
        self.settings.remove("geometry")
        self.showNormal()
        avail = QGuiApplication.primaryScreen().availableGeometry()
        w, h = min(1300, int(avail.width() * 0.95)), min(740, int(avail.height() * 0.9))
        self.resize(w, h)
        self.move(avail.left() + (avail.width() - w) // 2, avail.top() + (avail.height() - h) // 2)

    def set_ui_scale(self, pct):
        if pct == self.settings.value("ui_scale", 100, type=int):
            return
        self.settings.setValue("ui_scale", pct)
        QMessageBox.information(self, tr("Масштаб интерфейса"),
                                tr("Масштаб {pct}% применится после перезапуска программы.", pct=pct))

    # ----- обновления -----

    def check_updates(self, manual=False):
        self._manual_update = self._manual_update or manual
        if self.updater.running:
            return
        self.updater.start()
        if manual:
            self.statusBar().showMessage(tr("Проверяю обновления…"), 5000)

    def _on_update_result(self, newer, rel, err):
        manual, self._manual_update = self._manual_update, False
        if err:
            if manual:
                QMessageBox.warning(self, tr("Проверка обновлений"),
                                    tr("Не удалось проверить обновления: {err}", err=err))
            return
        if not newer:
            if manual:
                QMessageBox.information(self, tr("Проверка обновлений"),
                                        tr("У вас последняя версия ({v}).", v=VERSION))
            return
        if not manual and self.settings.value("skip_version", "") == rel["version"]:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(tr("Доступно обновление"))
        box.setText(tr("Вышла версия {new} (у вас {cur}). Скачать её можно на странице релиза на GitHub.",
                       new=rel["version"], cur=VERSION))
        open_btn = box.addButton(tr("Открыть страницу релиза"), QMessageBox.ButtonRole.AcceptRole)
        skip_btn = box.addButton(tr("Не напоминать об этой версии"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("Позже"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl(rel["url"]))
        elif box.clickedButton() is skip_btn:
            self.settings.setValue("skip_version", rel["version"])

    def show_about(self):
        QMessageBox.about(self, tr("О программе"),
                          f"<b>{APP_NAME}</b> {VERSION}<br>"
                          + tr("Просмотр и правка компании в сейве Euro Truck Simulator 2.") + "<br>"
                          f"<a href='https://github.com/{updates.REPO}'>github.com/{updates.REPO}</a>")

    def _btn(self, page, text, slot, tip="", primary=False):
        b = QPushButton(text)
        if tip:
            b.setToolTip(tip)
        if primary:
            b.setObjectName("primary")
        b.clicked.connect(lambda checked=False, f=slot: f())
        self.pages[page].add_action(b)
        return b

    def _build_action_rows(self):
        """Кнопки правки сейва прямо на вкладках (раньше были в меню «Правка сейва»)."""
        self.full_repair_boxes = []
        for page in ("trucks", "trailers"):
            box = QCheckBox(tr("Обнулять и неремонтируемый износ"))
            box.setToolTip(tr("Без галочки: как ремонт в сервисе игры (неремонтируемый износ остаётся)"))
            box.toggled.connect(self._sync_full_repair)
            self.full_repair_boxes.append(box)
            self.pages[page].add_action(box)
        self._btn("drivers", tr("Починить трак"), self.repair_selected, tr("Чинит трак выбранного водителя"))
        self._btn("drivers", tr("Заправить трак"), self.refuel_selected, tr("Заправляет трак выбранного водителя"))
        self._btn("trucks", tr("Починить выбранный"), self.repair_selected)
        self._btn("trucks", tr("Починить все"), self.repair_all, tr("Все траки и прицепы компании"))
        self._btn("trucks", tr("Заправить выбранный"), self.refuel_selected)
        self._btn("trucks", tr("Заправить все"), self.refuel_all)
        self._btn("trucks", tr("Сменить номер…"), self.change_plate)
        self._btn("trailers", tr("Починить выбранный"), self.repair_selected)
        self._btn("trailers", tr("Починить все"), self.repair_all, tr("Все траки и прицепы компании"))
        self._btn("trailers", tr("Сменить номер…"), self.change_plate)
        self._btn("garages", tr("Улучшить до большого…"), self.upgrade_selected_garage,
                  tr("Малый гараж (3 места) -> большой (5 мест)"))
        self._btn("garages", tr("Заполнить гаражи…"), self.fill_garages,
                  tr("Нанять водителей в свободные места и поставить им грузовики и прицепы"))

    def _sync_full_repair(self, on):
        for box in self.full_repair_boxes:
            box.blockSignals(True)
            box.setChecked(on)
            box.blockSignals(False)

    def full_repair_checked(self):
        return self.full_repair_boxes[0].isChecked()

    def _action(self, menu, text, slot, shortcut=None, checkable=False):
        act = QAction(text, self)
        act.setCheckable(checkable)
        if shortcut:
            act.setShortcut(shortcut)
        act.triggered.connect(lambda checked=False, f=slot: f())
        menu.addAction(act)
        return act

    # ----- загрузка -----

    def startup(self):
        last = self.settings.value("last_path", "")
        if last and Path(last).exists():
            self.load(last)
        else:
            self.open_latest(silent=True)

    def open_dialog(self):
        last = self.settings.value("last_path", "")
        start = str(Path(last).parent) if last else str(Path.home() / "Documents")
        path, _ = QFileDialog.getOpenFileName(self, tr("Выбери game.sii"), start, tr("ETS2 сейв (game.sii);;Все файлы (*)"))
        if path:
            self.load(path)

    def choose_profile(self):
        dlg = ProfileDialog(self, self.save_path)
        if dlg.exec() and dlg.chosen:
            self.load(dlg.chosen)

    def open_latest(self, silent=False):
        """Самый свежий сейв: в профиле открытого сейва, а если сейв не открыт, среди всех профилей."""
        path = view.find_latest_save(view.profile_dir_of(self.save_path) if self.save_path else None)
        if path:
            self.load(path)
        elif not silent:
            QMessageBox.information(self, tr("Сейвы не найдены"), tr("Не нашёл сейвов в Documents\\Euro Truck Simulator 2. "
                                    "Открой game.sii вручную: Файл → Открыть сейв…"))

    def reload(self):
        if self.save_path:
            self.load(self.save_path)
        else:
            self.open_dialog()

    def load(self, path, quiet=False):
        path = Path(path)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            mtime = path.stat().st_mtime
            company = core.build_company(core.Save(path))
        except (SystemExit, Exception) as exc:  # SystemExit: сообщения парсера о шифровании
            msg = str(exc) or repr(exc)
            if "pip install" in msg:
                msg += tr("\n\nУстанови в консоли и перезапусти программу.")
            if quiet:
                self.statusBar().showMessage(tr("Не удалось обновить: {msg}", msg=msg), 8000)
            else:
                QMessageBox.warning(self, tr("Не удалось прочитать сейв"), msg)
            return False
        finally:
            QApplication.restoreOverrideCursor()

        self.company, self.save_path, self.mtime = company, path, mtime
        self.settings.setValue("last_path", str(path))
        self.refresh_views()
        self.statusBar().showMessage(tr("{path}  ·  загружено в {t}", path=path, t=f"{datetime.now():%H:%M:%S}"))
        return True

    def poll(self):
        if not (self.watch_action.isChecked() and self.save_path):
            return
        try:
            mtime = self.save_path.stat().st_mtime
        except OSError:
            return
        if mtime != self.mtime:
            self.mtime = mtime
            QTimer.singleShot(1500, lambda: self.load(self.save_path, quiet=True))  # даём игре дописать файл

    # ----- отображение -----

    def refresh_views(self):
        c = self.company
        self.header.set_company(c)
        for i, (key, title, _, rows_fn) in enumerate(self.TABS):
            rows = rows_fn(c)
            self.pages[key].set_rows(rows)
            self.tabs.setTabText(i, f"{tr(title)} ({len(rows)})")
        self.skills.set_company(c)

    def open_driver(self, driver_id):
        driver = next((d for d in self.company["drivers"] if d["id"] == driver_id), None)
        if driver:
            DriverDialog(driver, self, self.rename_driver).exec()

    # ----- правка сейва -----

    def _selected_unit(self):
        """(тип, id юнита, обёртка с данными) выбранного трака или прицепа на текущей вкладке."""
        if not self.company:
            return None
        if self.tabs.currentIndex() >= len(self.TABS):
            return None
        tab = self.TABS[self.tabs.currentIndex()][0]
        key = self.pages[tab].current_key()
        if not key:
            return None
        if tab in ("drivers", "trucks"):
            d = next((x for x in self.company["drivers"] if x["id"] == key), None)
            return ("truck", d["truck"]["unit"], d["truck"]) if d and d["truck"] else None
        if tab == "trailers":
            t = next((x for x in self.company["trailers"] if x["unit"] == key), None)
            return ("trailer", t["unit"], t) if t else None
        return None

    def _confirm_write(self, text):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("Изменение сейва"))
        box.setText(text + tr("\n\nИгра должна быть закрыта. Перед записью программа сделает копию сейва в папке "
                              "ets2cm_backups рядом с game.sii. Лучше сначала проверить на копии слота сохранения."))
        box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Ok

    def _run_ops(self, ops, done_text):
        try:
            report = edit.apply_ops(self.save_path, ops, expected_mtime=self.mtime)
        except edit.EditError as exc:
            QMessageBox.warning(self, tr("Сейв не изменён"), str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, tr("Ошибка записи"), f"{type(exc).__name__}: {exc}\n" + tr("Сейв не изменён."))
            return
        self.load(self.save_path)
        if report["backup"]:
            QMessageBox.information(self, tr("Готово"), done_text + "\n" + tr("Изменено полей: {n}.", n=report['changed_fields']) + "\n"
                                    + tr("Копия до правки: {path}", path=report['backup']))
        else:
            QMessageBox.information(self, tr("Без изменений"), tr("Менять было нечего: значения уже такие."))

    def _need_save(self):
        if not self.save_path:
            QMessageBox.information(self, tr("Нет сейва"), tr("Сначала откройте сейв."))
            return False
        return True

    def repair_selected(self):
        if not self._need_save():
            return
        sel = self._selected_unit()
        if not sel:
            QMessageBox.information(self, tr("Не выбрано"), tr("Выберите строку с траком или прицепом "
                                    "(вкладки «Траки», «Прицепы» или «Водители»)."))
            return
        kind, unit, obj = sel
        name = obj["model"] if kind == "truck" else obj["kind"]
        q = tr("Починить трак {name} ({plate})?", name=name, plate=obj['plate']) if kind == "truck" \
            else tr("Починить прицеп {name} ({plate})?", name=name, plate=obj['plate'])
        if self._confirm_write(q):
            self._run_ops([("repair", unit, self.full_repair_checked())], tr("{name} починен.", name=name))

    def repair_all(self):
        if not self._need_save():
            return
        units = [d["truck"]["unit"] for d in self.company["drivers"] if d["truck"]]
        units += [t["unit"] for t in self.company["trailers"]]
        if self._confirm_write(tr("Починить все траки и прицепы компании ({n} шт.)?", n=len(units))):
            full = self.full_repair_checked()
            self._run_ops([("repair", u, full) for u in dict.fromkeys(units)], tr("Весь парк починен."))

    def refuel_selected(self):
        if not self._need_save():
            return
        sel = self._selected_unit()
        if not sel or sel[0] != "truck":
            QMessageBox.information(self, tr("Не выбрано"), tr("Выберите строку с траком (вкладка «Траки» или «Водители»)."))
            return
        _, unit, obj = sel
        if self._confirm_write(tr("Заправить {model} ({plate}) до полного бака?", model=obj['model'], plate=obj['plate'])):
            self._run_ops([("refuel", unit)], tr("Бак заполнен."))

    def refuel_all(self):
        if not self._need_save():
            return
        units = [d["truck"]["unit"] for d in self.company["drivers"] if d["truck"]]
        if self._confirm_write(tr("Заправить все траки компании ({n} шт.) до полного бака?", n=len(units))):
            self._run_ops([("refuel", u) for u in dict.fromkeys(units)], tr("Все баки заполнены."))

    def upgrade_selected_garage(self):
        if not self._need_save():
            return
        if self.tabs.currentIndex() < len(self.TABS) and self.TABS[self.tabs.currentIndex()][0] == "garages":
            gid = self.pages["garages"].current_key()
        else:
            gid = None
        if not gid:
            QMessageBox.information(self, tr("Не выбрано"), tr("Откройте вкладку «Гаражи» и выберите гараж."))
            return
        self.upgrade_garage(gid)

    def upgrade_garage(self, gid):
        if not self._need_save():
            return
        g = next((x for x in self.company["garages"] if x["id"] == gid), None)
        if not g or g["status"] != 2:
            QMessageBox.information(self, tr("Апгрейд недоступен"), tr("Улучшить можно только малый гараж (3 места) до большого (5 мест)."))
            return
        cost, ok = QInputDialog.getInt(
            self, tr("Стоимость апгрейда"), tr("Гараж {city}: малый -> большой.\nСколько списать со счёта? Введите цену, "
            "которую показывает игра (по умолчанию разница цен 150 000 €; 0 — не списывать).", city=g['city']),
            150000, 0, 1000000000, 1000)
        if ok and self._confirm_write(tr("Улучшить гараж {city} до большого за {cost} €?", city=g['city'], cost=f"{cost:,}".replace(",", " "))):
            self._run_ops([("upgrade", gid, self.company["bank_unit"], cost)], tr("Гараж {city} улучшен до большого.", city=g['city']))

    def fill_garages(self):
        if not self._need_save():
            return
        try:
            sv = core.Save(self.save_path)
        except (OSError, SystemExit) as exc:
            QMessageBox.warning(self, tr("Сейв не прочитан"), str(exc))
            return
        if not fill.free_slots(sv):
            QMessageBox.information(self, tr("Свободных мест нет"), tr("Во всех ваших гаражах уже есть водители и грузовики."))
            return
        dlg = FillDialog(self, sv)
        if not dlg.exec() or not dlg.plan:
            return
        n_drv, n_trk, n_trl, _ = dlg.counts()
        if self._confirm_write(tr("Нанять водителей: {d}, поставить грузовиков: {t}, прицепов: {p}. Списать {cost} €?",
                                  d=n_drv, t=n_trk, p=n_trl, cost=core.money(dlg.plan["cost"]))):
            self._run_ops([("fill", dlg.plan)], tr("Гаражи заполнены."))

    def apply_skills(self, did, changes, new_level=-1):
        if not self._need_save():
            return
        d = next((x for x in self.company["drivers"] if x["id"] == did), None)
        if not d:
            return
        names = {k: n for k, _, n, _ in SKILL_ROWS}
        parts, ops = [], []
        if new_level >= 0:
            parts.append(tr("Уровень: {a} -> {b}", a=d["level"], b=new_level))
            ops.append(("xp", d["skill_unit"], levels.xp_for_driver_level(new_level, d["is_player"])))
        for k, v in changes.items():
            if k == "adr":
                parts.append(tr("ADR: классов {a} -> {b}", a=bin(d['skills']['adr']).count('1'), b=bin(v).count('1')))
            else:
                parts.append(f"{tr(names[k])}: {d['skills'][k]} -> {v}")
        if changes:
            ops.append(("skills", d["skill_unit"], changes))
        if self._confirm_write(tr("Изменить водителя: {name}", name=d['name']) + "\n" + "\n".join(parts)):
            self._run_ops(ops, tr("Водитель {name} изменён.", name=d['name']))

    def _economy_ready(self, need):
        if not self._need_save():
            return False
        if not self.company.get(need):
            QMessageBox.information(self, tr("Нет данных"), tr("Не нашёл в сейве счёт компании или опыт игрока."))
            return False
        return True

    def edit_money(self):
        c = self.company
        if not self._economy_ready("bank_unit") or c.get("money") is None:
            return
        money = core.to_int(c["money"])
        dlg = ValueDialog(self, tr("Баланс"), tr("Баланс компании, €:"), big_spin(edit.MONEY_MIN, edit.MONEY_MAX, money),
                          tr("Сейчас: {money} €.", money=core.money(money)))
        new = dlg.new_value() if dlg.exec() else None
        if new is None:
            return
        if self._confirm_write(tr("Баланс: {a} € -> {b} €", a=core.money(money), b=core.money(new))):
            self._run_ops([("money", c["bank_unit"], new)], tr("Баланс изменён."))

    def edit_level(self):
        c = self.company
        if not self._economy_ready("economy_unit"):
            return
        cur = levels.level_for_xp(c["xp"])
        spin = QSpinBox()
        spin.setRange(0, max(LEVEL_MAX, cur))
        spin.setValue(cur)
        dlg = ValueDialog(self, tr("Уровень"), tr("Уровень игрока:"), spin,
                          tr("Сейчас: уровень {lvl}. В сейв записывается опыт ровно на начало выбранного уровня; "
                             "очки навыков программа не начисляет.", lvl=cur))
        new = dlg.new_value() if dlg.exec() else None
        if new is None:
            return
        if self._confirm_write(tr("Уровень: {a} -> {b}", a=cur, b=new)):
            self._run_ops([("xp", c["economy_unit"], levels.xp_for_level(new))], tr("Уровень изменён."))

    def change_plate(self):
        if not self._need_save():
            return
        sel = self._selected_unit()
        if not sel:
            QMessageBox.information(self, tr("Не выбрано"), tr("Выберите строку с траком или прицепом."))
            return
        kind, unit, obj = sel
        new, ok = QInputDialog.getText(
            self, tr("Новый номер"), tr("Номер {plate}. Меняется только сам номер ({body}), регион и "
            "герб остаются. Латиница, цифры, пробел, дефис, до 12 символов:", plate=obj['plate'], body=obj['plate_body']),
            text=obj["plate_body"])
        if not ok or new.strip().upper() == obj["plate_body"].upper():
            return
        if self._confirm_write(tr("Сменить номер {old} на {new}?", old=obj['plate_body'], new=new.strip().upper())):
            self._run_ops([("plate", unit, new)], tr("Номер изменён."))

    def restore_dialog(self):
        if not self._need_save():
            return
        backups = edit.list_backups(self.save_path)
        if not backups:
            QMessageBox.information(self, tr("Нет копий"), tr("Резервных копий этого сейва пока нет."))
            return
        names = [f"{b.name}  ({datetime.fromtimestamp(b.stat().st_mtime):%d.%m %H:%M})" for b in backups]
        choice, ok = QInputDialog.getItem(self, tr("Восстановление"), tr("Копия (сверху самая свежая):"), names, 0, False)
        if not ok:
            return
        if QMessageBox.question(self, tr("Восстановить?"), tr("Текущий game.sii будет заменён выбранной копией.")) \
                != QMessageBox.StandardButton.Yes:
            return
        try:
            edit.restore_backup(self.save_path, backups[names.index(choice)])
        except (edit.EditError, OSError) as exc:
            QMessageBox.warning(self, tr("Не удалось"), str(exc))
            return
        self.load(self.save_path)

    def rename_driver(self, driver_id, name):
        view.save_nickname(driver_id, name)
        for d in self.company["drivers"]:
            if d["id"] == driver_id:
                d["name"] = name or driver_id
        self.refresh_views()


_window = None


def main():
    global _window
    scale = app_settings().value("ui_scale", 100, type=int)
    if scale in UI_SCALES and scale != 100 and "QT_SCALE_FACTOR" not in os.environ:
        os.environ["QT_SCALE_FACTOR"] = str(scale / 100)
    # дробный масштаб Windows (125%, 150%) без округления до целого
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    if sys.platform.startswith("win"):  # иначе на панели задач будет значок Python
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ets2.company.manager")
        except (AttributeError, OSError):
            pass
    app.setWindowIcon(QIcon(str(ASSETS_ROOT / "ui" / "app_icon.png")))
    set_lang(app_settings().value("lang", "ru"))
    theme.apply(app, ASSETS_ROOT / "ui", app_settings().value("theme", "dark"))
    _window = MainWindow()
    _window.restore_window()
    _window.show()
    QTimer.singleShot(0, _window.startup)
    if _window.update_action.isChecked():
        QTimer.singleShot(1500, lambda: _window.check_updates(manual=False))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
