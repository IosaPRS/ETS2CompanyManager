"""Переводы интерфейса. Ключ - исходная русская фраза, перевод лежит в locales/<код>.json.

Новый язык: положите рядом файл locales/<код>.json (см. locales/README.md), он появится в меню «Настройки → Язык».
Нет перевода фразы - показывается русский текст.
tr("Номер: {plate}", plate="AB 123") подставляет значения через str.format (только когда переданы параметры).
"""
import json

from requirements.paths import data_path

LOCALES_DIR = data_path("locales")
_lang = "ru"
_table = {}


def available_langs():
    """{код: название}: русский всегда, остальные из locales/*.json (поле "_name")."""
    langs = {"ru": "Русский"}
    for p in sorted(LOCALES_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        langs[p.stem] = str(data.get("_name", p.stem)) if isinstance(data, dict) else p.stem
    return langs


def set_lang(code):
    global _lang, _table
    _lang, _table = "ru", {}
    if code and code != "ru" and (LOCALES_DIR / f"{code}.json").exists():
        try:
            data = json.loads((LOCALES_DIR / f"{code}.json").read_text(encoding="utf-8"))
            _table = {k: v for k, v in data.items() if isinstance(v, str) and v and not k.startswith("_")}
            _lang = code
        except (OSError, ValueError):
            pass  # битый файл перевода: остаёмся на русском


def get_lang():
    return _lang


def tr(text, **kw):
    text = _table.get(text, text)
    if not kw:
        return text
    try:
        return text.format(**kw)
    except (KeyError, IndexError, ValueError):
        return text
