"""Запись в сейв: ремонт, заправка, номера, апгрейд гаража, навыки, баланс и опыт. Перед записью делается копия в ets2cm_backups."""
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

from requirements import sii_decode

import ets2_manager as core
from requirements.ets2_i18n import tr

WEAR_KEY = re.compile(r"^(?:engine|transmission|cabin|chassis|trailer_body)_wear$|^wheels_wear$")
LINE_KV = re.compile(r"^(\s*)([A-Za-z_0-9]+)(\[(\d+)\])?(\s*:\s*)(.*?)(\s*)$")
PLATE_OK = re.compile(r"^[A-Z0-9][A-Z0-9 \-]{0,11}$")
BACKUP_DIR = "ets2cm_backups"


class EditError(Exception):
    """Понятная пользователю причина, по которой правка не выполнена."""


# ---------- проверки окружения ----------

GAME_EXES = ("eurotrucks2.exe", "amtrucks.exe")  # ETS2 и ATS


def game_running() -> bool:
    """True, если запущена ETS2 или ATS (Windows, по списку процессов). На других системах всегда False."""
    if not sys.platform.startswith("win"):
        return False
    try:
        out = subprocess.run(["tasklist", "/NH", "/FO", "CSV"], capture_output=True,
                             text=True, timeout=10, creationflags=0x08000000).stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False
    return any(f'"{exe}"' in out for exe in GAME_EXES)


# ---------- текст сейва ----------

def read_text(path: Path) -> str:
    try:
        text = sii_decode.decode_to_text(Path(path).read_bytes())
    except sii_decode.SiiError as exc:
        raise EditError(tr("Не удалось прочитать сейв: {exc}", exc=exc)) from None
    return text.replace("\r\n", "\n")


def parse_text(text: str) -> "core.Save":
    sv = object.__new__(core.Save)
    sv.units, sv.by_type, sv.profile_name = {}, defaultdict(list), ""
    sv._load_lines(text.splitlines())
    return sv


def _block_bounds(lines, unit_id):
    start = None
    for i, line in enumerate(lines):
        m = core.UNIT_START.match(line)
        if m and m[2] == unit_id:
            start = i
            break
    if start is None:
        raise EditError(tr("В сейве нет юнита {unit}: файл изменился, обновите данные (F5).", unit=unit_id))
    for j in range(start + 1, len(lines)):
        if lines[j].strip() == "}":
            return start + 1, j
    raise EditError(tr("Не найден конец юнита {unit}.", unit=unit_id))


def _replace_in_unit(lines, unit_id, fn):
    """fn(key, index, value) -> новое значение или None. Возвращает число изменённых строк."""
    a, b = _block_bounds(lines, unit_id)
    changed = 0
    for i in range(a, b):
        m = LINE_KV.match(lines[i])
        if not m:
            continue
        ind, key, _, idx, sep, val, tail = m.groups()
        new = fn(key, None if idx is None else int(idx), val)
        if new is not None and new != val:
            lines[i] = f"{ind}{key}{'' if idx is None else f'[{idx}]'}{sep}{new}{tail}"
            changed += 1
    return changed


# ---------- операции ----------

def repair_unit(lines, unit_id, full=False) -> int:
    """Обнуляет износ. full=False: как ремонт в сервисе, только ремонтируемый износ; full=True: и неремонтируемый."""
    def fn(key, idx, val):
        base = key[:-len("_unfixable")] if key.endswith("_unfixable") else key
        if not WEAR_KEY.match(base):
            return None
        if key.endswith("_unfixable") and not full:
            return None
        if idx is None and key == "wheels_wear":  # это счётчик элементов массива, не износ
            return None
        if idx is None and key == "wheels_wear_unfixable":
            return None
        return "0"
    return _replace_in_unit(lines, unit_id, fn)


def plate_parts(raw: str):
    """'F<..>GG 7378|germany' -> (префикс, номер, хвост). Меняется только видимая часть номера."""
    value = raw[1:-1] if raw.startswith('"') and raw.endswith('"') else raw
    head, sep, country = value.partition("|")
    cut = head.rfind(">") + 1
    return head[:cut], head[cut:], sep + country


def set_plate(lines, unit_id, new_body: str) -> int:
    new_body = new_body.strip().upper()
    if not PLATE_OK.match(new_body):
        raise EditError(tr("Номер: до 12 символов, только латинские буквы, цифры, пробел и дефис."))

    def fn(key, idx, val):
        if key != "license_plate" or idx is not None:
            return None
        quoted = val.startswith('"') and val.endswith('"')
        pre, _, tail = plate_parts(val)
        out = pre + new_body + tail
        return f'"{out}"' if quoted or not re.fullmatch(r"[A-Za-z0-9_]+", out) else out
    return _replace_in_unit(lines, unit_id, fn)


def set_field(lines, unit_id, key, value) -> int:
    """Меняет скалярное поле, если оно есть в юните (новые поля не добавляются)."""
    return _replace_in_unit(lines, unit_id, lambda k, idx, v: value if (k == key and idx is None) else None)


def get_field(lines, unit_id, key):
    a, b = _block_bounds(lines, unit_id)
    for i in range(a, b):
        m = LINE_KV.match(lines[i])
        if m and m[2] == key and m[4] is None:
            return m[6]
    return None


def extend_array(lines, unit_id, key, extra, fill="null"):
    """Добавляет extra пустых элементов в массив key (счётчик key и строки key[i])."""
    a, b = _block_bounds(lines, unit_id)
    count_i, last_i, n = None, None, 0
    for i in range(a, b):
        m = LINE_KV.match(lines[i])
        if not m or m[2] != key:
            continue
        if m[4] is None:
            count_i, n = i, int(m[6])
        else:
            last_i = i
    if count_i is None:
        raise EditError(tr("У гаража нет массива {key}: структура сейва неожиданная, апгрейд отменён.", key=key))
    m = LINE_KV.match(lines[count_i])
    ind = m[1]
    lines[count_i] = f"{ind}{key}{m[5]}{n + extra}"
    at = (last_i if last_i is not None else count_i) + 1
    for k in range(extra):
        lines.insert(at + k, f"{ind}{key}[{n + k}]: {fill}")
    return n


def upgrade_garage(lines, garage_id, bank_id, cost: int):
    """Малый гараж (status 2, 3 места) -> большой (status 3, 5 мест); деньги списываются со счёта компании."""
    if get_field(lines, garage_id, "status") != "2":
        raise EditError(tr("Апгрейд доступен только для малого гаража (3 места)."))
    money = get_field(lines, bank_id, "money_account")
    if money is None or not re.fullmatch(r"-?\d+", money):
        raise EditError(tr("Не нашёл счёт компании в сейве, апгрейд отменён."))
    if cost < 0 or int(money) < cost:
        raise EditError(tr("Не хватает денег: на счёте {have} €, нужно {need} €.", have=f"{int(money):,}".replace(",", " "), need=f"{cost:,}".replace(",", " ")))
    for key in ("vehicles", "drivers"):
        if extend_array(lines, garage_id, key, 2) != 3:
            raise EditError(tr("В гараже {key} не из 3 элементов: структура неожиданная, апгрейд отменён.", key=key))
    set_field(lines, garage_id, "status", "3")
    if cost:
        set_field(lines, bank_id, "money_account", str(int(money) - cost))


SKILL_KEYS = ("long_dist", "heavy", "fragile", "urgent", "mechanical")
ADR_MASK = 0b111111
SKILL_MAX = 6


def raise_skills(lines, unit_id, changes: dict):
    """Повышает навыки (понижать нельзя, как в игре): {'long_dist': 3, ..., 'adr': новая_маска}."""
    for key, new in changes.items():
        cur = get_field(lines, unit_id, key)
        if cur is None or not re.fullmatch(r"\d+", cur):
            raise EditError(tr("У юнита {unit} нет поля {key}: структура сейва неожиданная, правка отменена.", unit=unit_id, key=key))
        cur, new = int(cur), int(new)
        if key == "adr":
            if new & ~ADR_MASK or new & cur != cur:
                raise EditError(tr("ADR: можно только добавлять классы (допустимы 6 классов)."))
        elif key in SKILL_KEYS:
            if not cur <= new <= SKILL_MAX:
                raise EditError(tr("Навык {key}: допустимо от текущего значения {cur} до {max}.", key=key, cur=cur, max=SKILL_MAX))
        else:
            raise EditError(tr("Неизвестный навык {key}.", key=key))
        set_field(lines, unit_id, key, str(new))


MONEY_MIN, MONEY_MAX = -2_147_483_648, 2_147_483_647  # поле в игре 64-битное; берём безопасный 32-битный диапазон
XP_MAX = 4_294_967_295  # предел 32-битного поля без знака; в игре не проверен


def set_int_field(lines, unit_id, key, value: int, lo: int, hi: int, what: str):
    """Меняет целое поле (баланс, опыт). Поле должно уже быть в юните и быть целым числом."""
    cur = get_field(lines, unit_id, key)
    if cur is None or not re.fullmatch(r"-?\d+", cur):
        raise EditError(tr("У юнита {unit} нет поля {key}: структура сейва неожиданная, правка отменена.", unit=unit_id, key=key))
    value = int(value)
    if not lo <= value <= hi:
        raise EditError(tr("{what}: допустимо от {lo} до {hi}.", what=what, lo=f"{lo:,}".replace(",", " "),
                           hi=f"{hi:,}".replace(",", " ")))
    return set_field(lines, unit_id, key, str(value))


# ---------- сверка и запись ----------

def _diff_units(a: "core.Save", b: "core.Save"):
    """Список (unit, field) с отличиями между двумя разобранными сейвами; структурные отличия -> EditError."""
    if set(a.units) != set(b.units):
        raise EditError(tr("Сверка не прошла: набор юнитов в результате отличается от оригинала."))
    diffs = []
    for name, ua in a.units.items():
        ub = b.units[name]
        if ua.keys() != ub.keys():
            raise EditError(tr("Сверка не прошла: у юнита {name} изменился набор полей.", name=name))
        for k, v in ua.items():
            if v != ub[k]:
                diffs.append((name, k))
    return diffs


def backup(path: Path) -> Path:
    folder = Path(path).parent / BACKUP_DIR
    folder.mkdir(exist_ok=True)
    dst = folder / f"{Path(path).stem}_{time.strftime('%Y%m%d_%H%M%S')}{Path(path).suffix}"
    shutil.copy2(path, dst)
    return dst


def list_backups(path: Path):
    folder = Path(path).parent / BACKUP_DIR
    return sorted(folder.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.exists() else []


def restore_backup(path: Path, backup_file: Path):
    if game_running():
        raise EditError(tr("Закройте игру перед восстановлением сейва."))
    shutil.copy2(backup_file, path)


def apply_ops(path, ops, expected_mtime=None):
    """ops: [('repair', unit, full), ('plate', unit, 'ABC 123'), ('skills', unit, {'long_dist': 3}),
    ('money', bank_unit, 100000), ('xp', economy_unit, 50000), ...]. Возвращает отчёт."""
    path = Path(path)
    if game_running():
        raise EditError(tr("Игра запущена. Закройте Euro Truck Simulator 2 (или American Truck Simulator) и повторите: "
                           "пока игра открыта, она перезапишет изменения."))
    if expected_mtime is not None and path.stat().st_mtime != expected_mtime:
        raise EditError(tr("Сейв изменился после загрузки в программу. Обновите данные (F5) и повторите."))

    text = read_text(path)
    original = parse_text(text)
    ref = core.Save(path)
    if _diff_units(ref, original):
        raise EditError(tr("Сверка не прошла: текстовая версия сейва расходится с исходным файлом, запись отменена."))

    lines = text.split("\n")
    touched, expected = 0, set()
    for op in ops:
        if op[0] == "repair":
            n = repair_unit(lines, op[1], full=op[2])
            touched += n
            expected.add(op[1])
        elif op[0] == "plate":
            touched += set_plate(lines, op[1], op[2])
            expected.add(op[1])
        elif op[0] == "refuel":
            touched += set_field(lines, op[1], "fuel_relative", "1")
            expected.add(op[1])
        elif op[0] == "upgrade":  # ('upgrade', garage_unit, bank_unit, cost)
            upgrade_garage(lines, op[1], op[2], op[3])
            touched += 1
            expected.update(op[1:3])
        elif op[0] == "money":  # ('money', bank_unit, новый_баланс)
            touched += set_int_field(lines, op[1], "money_account", op[2], MONEY_MIN, MONEY_MAX, tr("Баланс"))
            expected.add(op[1])
        elif op[0] == "xp":  # ('xp', economy_unit, новый_опыт)
            touched += set_int_field(lines, op[1], "experience_points", op[2], 0, XP_MAX, tr("Опыт"))
            expected.add(op[1])
        elif op[0] == "skills":  # ('skills', unit, {поле: значение})
            raise_skills(lines, op[1], op[2])
            touched += 1
            expected.add(op[1])
        else:
            raise EditError(tr("Неизвестная операция {op}", op=op[0]))
    new_text = "\n".join(lines)
    result = parse_text(new_text)
    diffs = _diff_units(original, result)
    stray = [d for d in diffs if d[0] not in expected]
    if stray:
        raise EditError(tr("Сверка не прошла: изменилось лишнее ({what}), запись отменена.", what=stray[0]))
    if not diffs:
        return {"changed_fields": 0, "units": 0, "backup": None}

    bak = backup(path)
    tmp = path.with_name(path.name + ".ets2cm.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_text)
        os.replace(tmp, path)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise EditError(tr("Не удалось записать файл ({exc}). Возможно, он занят другой программой.", exc=exc)) from None
    return {"changed_fields": len(diffs), "units": len({d[0] for d in diffs}), "backup": bak}
