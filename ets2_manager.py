#!/usr/bin/env python3
"""ETS2 Company Manager: сводка по компании игрока из game.sii.

Запуск:
    python ets2_manager.py "<путь к game.sii>"                  # сводка
    python ets2_manager.py "<путь к game.sii>" driver driver.58  # карточка водителя
    python ets2_manager.py "<путь к game.sii>" dump TYPE [TYPE]  # сырые юниты -> dump2.txt
    (TYPE.поле, например driver_ai.driver_job, покажет юниты, на которые ссылается поле)

Зашифрованные (ScsC) и бинарные (BSII) сейвы читаются сами через sii_decode.py;
для ScsC нужна библиотека:  pip install cryptography
Имён водителей в сейве нет: игра выводит их из номера driver.N. Таблица имён лежит в
requirements/driver_names.json; свои правки хранятся в %APPDATA%\\ETS2CompanyManager\\driver_names.json
(формат {"driver.58": "Иван"}). Имя игрока берётся из названия папки профиля (она записана в hex).
"""
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from requirements.ets2_i18n import tr
from requirements.paths import data_path
from requirements import ets2_names, levels, sii_decode

DECRYPTOR = None  # например r"C:\Tools\SII_Decrypt.exe"

UNIT_START = re.compile(r'^\s*([a-z_0-9]+)\s*:\s*([^\s{]+)\s*\{\s*$')
KV = re.compile(r'^\s*([A-Za-z_0-9]+)(\[\d*\])?\s*:\s*(.*?)\s*$')
TAG = re.compile(r'<[^>]*>')
TRUCK_PATH = re.compile(r'/def/vehicle/truck/([\w.\-]+)/')
TRAILER_PATH = re.compile(r'/def/vehicle/trailer_owned/([\w.\-]+)/')
SKILLS = ("adr", "long_dist", "heavy", "fragile", "urgent", "mechanical")


# ---------- чтение файла ----------

def is_text_sii(path: Path) -> bool:
    with open(path, "rb") as f:
        return b"SiiNunit" in f.read(16)


def external_decrypt(path: Path) -> Path:
    """Запасной путь: расшифровывает копию файла внешней утилитой DECRYPTOR."""
    tmp = Path(tempfile.mkdtemp()) / "game.sii"
    shutil.copy(path, tmp)
    subprocess.run([DECRYPTOR, str(tmp)], check=True)
    if not is_text_sii(tmp):
        raise SystemExit(tr("Внешний декриптор отработал, но файл всё ещё не текстовый."))
    return tmp


def profile_name_from_path(path: Path):
    """.../profiles/58616E646F7273/save/autosave/game.sii -> 'Xandors' (имя профиля в hex)."""
    for part in path.parts:
        if len(part) >= 2 and len(part) % 2 == 0 and re.fullmatch(r"[0-9A-Fa-f]+", part):
            try:
                name = bytes.fromhex(part).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                continue
            if name.isprintable() and name.strip():
                return name
    return None


class Save:
    def __init__(self, path: Path):
        self.units: dict[str, dict] = {}
        self.by_type: dict[str, list] = defaultdict(list)
        path = Path(path)
        self.profile_name = profile_name_from_path(path)
        raw = path.read_bytes()
        kind = sii_decode.detect_file_type(raw)
        if kind is None:
            raise SystemExit(tr("Не похоже на файл сохранения SCS: неизвестный заголовок."))
        if kind == "siin":  # обычный текст читаем построчно прямо с диска
            del raw
            with open(path, encoding="utf-8-sig", errors="replace") as f:
                self._load_lines(f)
            return
        try:
            inner = sii_decode.unwrap(raw)
            del raw
            if sii_decode.detect_file_type(inner) == "bsii":
                self._add_units(sii_decode.bsii_to_units(sii_decode.parse_bsii(inner)))
            else:
                self._load_lines(inner.decode("utf-8-sig", errors="replace").splitlines())
        except sii_decode.SiiError as exc:
            if not DECRYPTOR:
                raise SystemExit(tr("Не удалось расшифровать сейв: {exc}", exc=exc)) from None
            try:
                with open(external_decrypt(path), encoding="utf-8-sig", errors="replace") as f:
                    self.units.clear()
                    self.by_type.clear()
                    self._load_lines(f)
            except (OSError, subprocess.SubprocessError) as ext:
                raise SystemExit(tr("Не удалось расшифровать сейв ни встроенным декодером ({exc}), ни внешним ({ext}).",
                                    exc=exc, ext=ext)) from None

    def _add_units(self, units):
        for u in units:
            self.units[u["_name"]] = u
            self.by_type[u["_type"]].append(u)

    def _load_lines(self, lines):
        cur = None
        for line in lines:
            if cur is None:
                m = UNIT_START.match(line)
                if m:
                    cur = {"_type": m[1], "_name": m[2]}
                continue
            if line.strip() == "}":
                self.units[cur["_name"]] = cur
                self.by_type[cur["_type"]].append(cur)
                cur = None
                continue
            m = KV.match(line)
            if not m:
                continue
            key, arr, val = m.groups()
            val = val.strip('"')
            if arr is not None:
                cur.setdefault(key + "[]", []).append(val)
            else:
                cur[key] = val

    def one(self, unit_type):
        lst = self.by_type.get(unit_type)
        return lst[0] if lst else None

    def ref(self, name):
        if not name or name == "null":
            return None
        return self.units.get(name)


# ---------- значения ----------

def f32(v) -> float:
    """SII хранит дробные числа как &<hex> (биты IEEE754 float32)."""
    if v is None:
        return 0.0
    s = str(v).strip()
    if s.startswith("&") and 1 < len(s) <= 9:
        try:
            return struct.unpack("<f", struct.pack("<I", int(s[1:], 16)))[0]
        except (ValueError, struct.error):
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def to_int(v, default=0) -> int:
    try:
        return int(float(str(v)))
    except (TypeError, ValueError):
        return default


def plate_body(raw) -> str:
    """Редактируемая часть номера: текст после последнего тега до '|' (без региона и герба)."""
    if not raw:
        return ""
    head = raw.split("|")[0]
    return head[head.rfind(">") + 1:].strip()


def clean_plate(raw) -> str:
    if not raw:
        return ""
    text = raw.split("|")[0]
    return re.sub(r"\s+", " ", TAG.sub(" ", text)).strip()


def city(name) -> str:
    return (name or "").replace("garage.", "").capitalize()


# ---------- модели ----------

def accessory_match(sv: Save, unit: dict, pattern):
    """Ищет в аксессуарах юнита строку, подходящую под pattern, и возвращает группу 1."""
    for acc in unit.get("accessories[]", []):
        u = sv.units.get(acc)
        if not u:
            continue
        for v in u.values():
            if isinstance(v, str):
                m = pattern.search(v)
                if m:
                    return m.group(1)
    return None


def truck_model(sv: Save, truck: dict):
    """Марка/модель трака: путь /def/vehicle/truck/<бренд.модель>/ в аксессуарах."""
    return accessory_match(sv, truck, TRUCK_PATH)


def part_wear(unit: dict, key: str) -> float:
    """Износ детали в процентах: ремонтируемая часть + неремонтируемая (_unfixable), как в игре."""
    return min(100.0, (f32(unit.get(key)) + f32(unit.get(key + "_unfixable"))) * 100)


def wheels_wear_pct(unit: dict) -> float:
    w = [f32(x) for x in unit.get("wheels_wear[]", [])]
    u = [f32(x) for x in unit.get("wheels_wear_unfixable[]", [])]
    if not w:
        return 0.0
    u += [0.0] * (len(w) - len(u))
    return min(100.0, sum(a + b for a, b in zip(w, u)) / len(w) * 100)


def wheels_perm_pct(unit: dict) -> float:
    u = [f32(x) for x in unit.get("wheels_wear_unfixable[]", [])]
    return min(100.0, sum(u) / len(u) * 100) if u else 0.0


def perm_info(unit: dict, keys: dict) -> dict:
    """Постоянный (неремонтируемый) износ по деталям, %."""
    out = {name: min(100.0, f32(unit.get(key + "_unfixable")) * 100) for name, key in keys.items()}
    out["wheels"] = wheels_perm_pct(unit)
    return out


TRUCK_PERM_KEYS = {"engine": "engine_wear", "transmission": "transmission_wear", "cabin": "cabin_wear",
                   "chassis": "chassis_wear"}
TRAILER_PERM_KEYS = {"body": "trailer_body_wear", "chassis": "chassis_wear"}


def wear_info(truck: dict) -> dict:
    return {
        "engine": part_wear(truck, "engine_wear"),
        "transmission": part_wear(truck, "transmission_wear"),
        "cabin": part_wear(truck, "cabin_wear"),
        "chassis": part_wear(truck, "chassis_wear"),
        "wheels": wheels_wear_pct(truck),
    }


def build_truck(sv: Save, name):
    t = sv.ref(name)
    if not t:
        return None
    w = wear_info(t)
    code = truck_model(sv, t)
    return {
        "unit": name,
        "code": code or "?",
        "brand": ets2_names.truck_brand(code),
        "model": ets2_names.truck_name(code),
        "plate": clean_plate(t.get("license_plate")),
        "plate_body": plate_body(t.get("license_plate")),
        "odometer": to_int(t.get("odometer")),
        "fuel_pct": round(f32(t.get("fuel_relative")) * 100, 1),
        "wear": w,
        "wear_max": max(w.values()),
        "perm": perm_info(t, TRUCK_PERM_KEYS),
        "perm_max": max(perm_info(t, TRUCK_PERM_KEYS).values()),
    }


def build_trailer(sv: Save, name):
    t = sv.ref(name)
    if not t:
        return None
    d = sv.ref(t.get("trailer_definition")) or {}
    code = accessory_match(sv, t, TRAILER_PATH)
    parts = {
        "body": part_wear(t, "trailer_body_wear"),
        "chassis": part_wear(t, "chassis_wear"),
        "wheels": wheels_wear_pct(t),
    }
    return {
        "unit": name,
        "kind": ets2_names.trailer_name(code, d.get("body_type")),
        "plate": clean_plate(t.get("license_plate")),
        "plate_body": plate_body(t.get("license_plate")),
        "odometer": to_int(t.get("odometer")),
        "wear": max(parts.values()),
        "wear_parts": parts,
        "perm_max": max(perm_info(t, TRAILER_PERM_KEYS).values()),
        "private": str(t.get("is_private")).lower() == "true",
    }


def user_dir() -> Path:
    """Папка настроек пользователя (свои имена водителей и т.п.), не рядом со скриптом."""
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    d = Path(base) / "ETS2CompanyManager"
    d.mkdir(parents=True, exist_ok=True)
    return d


def custom_names_path() -> Path:
    return user_dir() / "driver_names.json"


def _norm_key(k: str) -> str:
    m = re.fullmatch(r"driver\.0*(\d+)", str(k).strip())
    return f"driver.{int(m.group(1))}" if m else str(k)


def _read_names(p: Path) -> dict:
    try:
        return {_norm_key(k): v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if v}
    except (OSError, ValueError):
        return {}


def load_nicknames() -> dict:
    """Имена водителей. В самом сейве имён нет (у driver_ai нет поля имени; игра выводит имя из номера),"""
    names = _read_names(data_path("requirements", "driver_names.json"))
    names.update(_read_names(custom_names_path()))
    return names


def company_city(ref):
    """'company.volatile.posped.birmingham' -> ('posped', 'birmingham')"""
    parts = (ref or "").split(".")
    return (parts[-2], parts[-1]) if len(parts) >= 2 else (ref or "?", "")


def fmt_duration(minutes: int) -> str:
    return tr("{d} д {h} ч", d=minutes // 1440, h=minutes % 1440 // 60)


def parse_job(sv: Save, ref, now: int):
    """Текущий заказ водителя (юнит job_info). Время в сейве считается в игровых минутах."""
    j = sv.ref(ref)
    if not j:
        return None
    empty = (None, "", "null")
    if j.get("cargo") in empty and j.get("source_company") in empty and j.get("target_company") in empty:
        return None  # пустой job_info: у водителя нет заказа (так у только что нанятых и у ждущих в гараже)
    src_co, src_city = company_city(j.get("source_company"))
    dst_co, dst_city = company_city(j.get("target_company"))
    start = to_int(j.get("start_time"))
    return {
        "cargo": (j.get("cargo") or "?").replace("cargo.", ""),
        "source": f"{src_city.capitalize()} ({src_co})",
        "target": f"{dst_city.capitalize()} ({dst_co})",
        "km": to_int(j.get("planned_distance_km")),
        "units": to_int(j.get("units_count")),
        "ferry_price": to_int(j.get("ferry_price")),
        "elapsed_min": max(0, now - start) if start else 0,
        "urgent": to_int(j.get("urgency")) > 0,
        "market": j.get("is_cargo_market_job") == "true",
    }


def profit_stats(sv: Save, ref, now_day: int = 0) -> dict:
    """Статистика водителя по его profit_log."""
    log = sv.ref(ref) or {}
    entries = [sv.units[n] for n in log.get("stats_data[]", []) if n in sv.units]
    rev = sum(to_int(e.get("revenue")) for e in entries)
    wage = sum(to_int(e.get("wage")) for e in entries)
    maint = sum(to_int(e.get("maintenance")) for e in entries)
    fuel = sum(to_int(e.get("fuel")) for e in entries)
    jobs = sorted(
        (e for e in entries if e.get("distance_on_job") == "true"),
        key=lambda e: -to_int(e.get("timestamp_day")),
    )
    km_job = to_int(log.get("acc_distance_on_job"))
    km_free = to_int(log.get("acc_distance_free"))
    net = rev - wage - maint - fuel
    week = [e for e in entries if to_int(e.get("timestamp_day")) >= now_day - 7]
    net7 = sum(to_int(e.get("revenue")) - to_int(e.get("wage")) - to_int(e.get("maintenance"))
               - to_int(e.get("fuel")) for e in week)
    km_all = km_job + km_free
    return {
        "net_day": net7 / 7, "net_km": net / km_all if km_all else 0.0,
        "jobs": len(jobs), "revenue": rev, "wage": wage, "maintenance": maint, "fuel": fuel,
        "net": net, "km_hist": sum(to_int(e.get("distance")) for e in entries if e.get("distance_on_job") == "true"),
        "km_job": km_job, "km_free": km_free,
        "net_per_km": net / km_job if km_job else 0.0,
        "history": [{
            "day": to_int(e.get("timestamp_day")),
            "cargo": e.get("cargo", "?"),
            "route": f"{e.get('source_city', '?')} -> {e.get('destination_city', '?')}",
            "km": to_int(e.get("distance")),
            "revenue": to_int(e.get("revenue")),
        } for e in jobs],
    }


def build_company(sv: Save) -> dict:
    eco, pl = sv.one("economy") or {}, sv.one("player") or {}
    bank = sv.ref(eco.get("bank")) or {}
    nick = load_nicknames()
    now = to_int(eco.get("game_time"))

    # водитель -> домашний гараж
    home = {}
    for g in sv.by_type["garage"]:
        for d in g.get("drivers[]", []):
            home[d] = city(g["_name"])

    # прицеп -> водитель
    trailer_owner = {}
    for did in pl.get("drivers[]", []):
        d = sv.units.get(did, {})
        if d.get("assigned_trailer") not in (None, "null"):
            trailer_owner[d["assigned_trailer"]] = did

    player_trailer = pl.get("assigned_trailer")
    if player_trailer in (None, "", "null"):
        player_trailer = next((n for n in pl.get("trailers[]", [])
                               if str(sv.units.get(n, {}).get("is_private")).lower() == "true"), None)

    slot_truck = {}
    for g in sv.by_type.get("garage", []):
        for dr, vh in zip(g.get("drivers[]", []), g.get("vehicles[]", [])):
            slot_truck[dr] = vh
    drivers = []
    trucks = pl.get("trucks[]", [])
    for i, did in enumerate(pl.get("drivers[]", [])):
        d = sv.units.get(did)
        is_player = d is None or d.get("_type") != "driver_ai"
        src = eco if is_player else d
        d = d or {}
        skills = {k: to_int(src.get(k)) for k in SKILLS}
        adr_classes = bin(skills["adr"]).count("1")
        truck_ref = slot_truck.get(did) or (trucks[i] if i < len(trucks) else None)
        truck = build_truck(sv, truck_ref) if truck_ref else None
        job = parse_job(sv, d.get("driver_job"), now)
        trailer_ref = player_trailer if is_player else d.get("assigned_trailer")
        drivers.append({
            "id": did,
            "name": nick.get(did) or ((sv.profile_name or tr("Я (игрок)")) if is_player else tr("Водитель №{n}", n=did.rpartition('.')[2])),
            "is_player": is_player,
            "hometown": ((pl.get("hq_city") if is_player else d.get("hometown")) or "").capitalize(),
            "city": (d.get("current_city") or (pl.get("hq_city") if is_player else "") or "").capitalize(),
            "garage": home.get(did, ""),
            "state": d.get("state"),
            "status": "в рейсе" if job else ("без трака" if truck is None else "свободен"),
            "xp": to_int(src.get("experience_points")),
            "level": levels.driver_level(to_int(src.get("experience_points")), is_player),
            "skills": skills,
            "skill_unit": eco.get("_name") if is_player else did,  # юнит, где лежат навыки (игрок: economy)
            "adr_classes": adr_classes,
            "skill_sum": adr_classes + sum(v for k, v in skills.items() if k != "adr"),
            "truck": truck,
            "trailer": build_trailer(sv, trailer_ref),
            "stats": profit_stats(sv, d.get("profit_log"), now // 1440),
            "job": job,
        })

    garages = []
    for g in sv.by_type["garage"]:
        if to_int(g.get("status")) > 0:
            garages.append({
                "id": g["_name"],
                "driver_ids": [x for x in g.get("drivers[]", []) if x not in (None, "", "null")],
                "city": city(g["_name"]),
                "status": to_int(g.get("status")),
                "vehicles": sum(1 for x in g.get("vehicles[]", []) if x not in (None, "", "null")),
                "drivers": sum(1 for x in g.get("drivers[]", []) if x not in (None, "", "null")),
                "trailers": sum(1 for x in g.get("trailers[]", []) if x not in (None, "", "null")),
                "productivity": round(f32(g.get("productivity")) * 100, 1),
                "net_day": profit_stats(sv, g.get("profit_log"), now // 1440)["net_day"],
            })

    owned_trailers = [t for t in (build_trailer(sv, n) for n in pl.get("trailers[]", [])) if t]

    return {
        "hq": (pl.get("hq_city") or "").capitalize(),
        "money": bank.get("money_account"),
        "economy_unit": eco.get("_name"),
        "bank_unit": eco.get("bank"),
        "game_days": to_int(eco.get("game_time")) / 1440,
        "xp": to_int(eco.get("experience_points")),
        "skills": {k: to_int(eco.get(k)) for k in SKILLS},
        "distance_km": to_int((eco.get("total_distances_by_mode[]") or [0])[0]),
        "fuel_l": to_int(eco.get("total_fuel_litres")),
        "fines_red_light": to_int(eco.get("red_light_fine_count")),
        "ai_crashes": to_int(eco.get("ai_crash_count")),
        "cancelled_jobs": to_int(eco.get("cancelled_job_count")),
        "cities": len(eco.get("visited_cities[]", [])),
        "drivers": drivers,
        "garages": garages,
        "trailers": owned_trailers,
    }


# ---------- вывод ----------

def table(headers, rows):
    cols = list(zip(headers, *rows)) if rows else [(h,) for h in headers]
    widths = [max(len(str(x)) for x in col) for col in cols]
    fmt = " | ".join("{:<%d}" % w for w in widths)
    print(fmt.format(*headers))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt.format(*[str(x) for x in r]))
    print()


def money(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def show_driver(c: dict, key: str):
    d = next((x for x in c["drivers"] if key in (x["id"], x["name"])), None)
    if not d:
        raise SystemExit(f"Водитель {key} не найден среди твоих.")
    s, st = d["skills"], d["stats"]
    print(f"=== {d['name']} ({d['id']}) ===")
    print(f"Родина: {d['hometown']} | сейчас: {d['city']} | гараж: {d['garage'] or '-'} | XP: {d['xp']}")
    print(f"ADR {d['adr_classes']}/6 | дальние {s['long_dist']} | тяжёлые {s['heavy']} | хрупкие {s['fragile']} "
          f"| срочные {s['urgent']} | эко {s['mechanical']}")
    t = d["truck"]
    if t:
        print(f"Трак: {t['model']} {t['plate']} | пробег {t['odometer']} км | макс. износ {t['wear_max']:.1f}%")
    if d["trailer"]:
        tr = d["trailer"]
        print(f"Прицеп: {tr['kind']} {tr['plate']} | пробег {tr['odometer']} км | износ {tr['wear']:.1f}%")
    j = d["job"]
    if j:
        print(f"Сейчас в рейсе: {j['cargo']} ({j['units']} ед.), {j['source']} -> {j['target']}, "
              f"{j['km']} км, в пути {fmt_duration(j['elapsed_min'])}"
              + (", срочный" if j["urgent"] else ""))
    else:
        print("Сейчас без заказа")
    print(f"Заказов: {st['jobs']} | км по заказам: {st['km_job']} | порожняком: {st['km_free']}")
    print(f"Выручка {money(st['revenue'])} | зарплата {money(st['wage'])} | топливо {money(st['fuel'])} "
          f"| обслуживание {money(st['maintenance'])} | прибыль {money(st['net'])}\n")
    print("Последние заказы:")
    table(["День", "Груз", "Маршрут", "Км", "Выручка"],
          [[h["day"], h["cargo"], h["route"], h["km"], money(h["revenue"])] for h in st["history"][:10]])


def show_summary(c: dict):
    print("=== КОМПАНИЯ ===")
    print(f"Штаб-квартира: {c['hq']} | игровых дней: {c['game_days']:.1f} | городов посещено: {c['cities']}")
    if c["money"] is not None:
        print(f"Деньги: {c['money']}")
    print(f"Пробег: {c['distance_km']} км | топливо: {c['fuel_l']} л | "
          f"штрафы за красный: {c['fines_red_light']} | ДТП с ИИ: {c['ai_crashes']} | "
          f"отменено заказов: {c['cancelled_jobs']}")
    s = c["skills"]
    print(f"Твои навыки: ADR {bin(s['adr']).count('1')}/6 | дальние {s['long_dist']} | "
          f"тяжёлые {s['heavy']} | хрупкие {s['fragile']} | срочные {s['urgent']} | эко {s['mechanical']} | XP {c['xp']}\n")

    print(f"=== ВОДИТЕЛИ ({len(c['drivers'])}) ===")
    rows = []
    for d in sorted(c["drivers"], key=lambda x: -x["xp"]):
        s, t = d["skills"], d["truck"]
        rows.append([
            d["name"], d["hometown"], d["city"], d["garage"], d["xp"],
            f"{d['adr_classes']}/6", s["long_dist"], s["heavy"], s["fragile"], s["urgent"], s["mechanical"],
            f"{t['model']} {t['plate']}" if t else "-",
            f"{d['trailer']['plate']}" if d["trailer"] else "-",
        ])
    table(["Водитель", "Родина", "Сейчас", "Гараж", "XP", "ADR", "Дальн", "Тяж", "Хруп", "Срочн", "Эко", "Трак", "Прицеп"], rows)

    print("=== СТАТИСТИКА ВОДИТЕЛЕЙ (доходы по сохранённой истории) ===")
    rows = []
    for d in sorted(c["drivers"], key=lambda x: -x["stats"]["net"]):
        st = d["stats"]
        rows.append([d["name"], st["jobs"], st["km_job"], st["km_free"], money(st["revenue"]),
                     money(st["wage"]), money(st["fuel"]), money(st["maintenance"]),
                     money(st["net"]), f"{st['net_per_km']:.1f}"])
    table(["Водитель", "Заказов", "Км (заказы)", "Км (порожняк)", "Выручка", "Зарплата",
           "Топливо", "Обслуж.", "Прибыль", "Приб./км"], rows)

    active = [d for d in c["drivers"] if d["job"]]
    print(f"=== ТЕКУЩИЕ РЕЙСЫ ({len(active)} из {len(c['drivers'])} водителей) ===")
    table(["Водитель", "Груз", "Откуда", "Куда", "Км", "В пути", "Паром"],
          [[d["name"], d["job"]["cargo"], d["job"]["source"], d["job"]["target"], d["job"]["km"],
            fmt_duration(d["job"]["elapsed_min"]), money(d["job"]["ferry_price"]) if d["job"]["ferry_price"] else "-"]
           for d in active])

    print(f"=== ТРАКИ ({sum(1 for d in c['drivers'] if d['truck'])}) ===")
    rows = []
    for d in c["drivers"]:
        t = d["truck"]
        if t:
            rows.append([t["plate"], t["model"], d["name"], t["odometer"], t["fuel_pct"],
                         f"{t['wear_max']:.1f}%", f"{t['wear']['engine']:.1f}%", f"{t['wear']['wheels']:.1f}%"])
    table(["Номер", "Модель", "Водитель", "Пробег км", "Топливо %", "Макс.износ", "Двигатель", "Колёса"], rows)

    print(f"=== ПРИЦЕПЫ ({len(c['trailers'])}) ===")
    table(["Номер", "Тип", "Пробег км", "Износ"],
          [[t["plate"], t["kind"], t["odometer"], f"{t['wear']:.1f}%"] for t in c["trailers"]])

    print(f"=== ГАРАЖИ ({len(c['garages'])}) ===")
    table(["Город", "Статус", "Траки", "Водители", "Прицепы", "Продуктивность"],
          [[g["city"], g["status"], g["vehicles"], g["drivers"], g["trailers"], f'{g["productivity"]}%'] for g in c["garages"]])


def write_unit(out, u, max_items=30):
    out.write(f"--- {u['_type']} : {u['_name']}\n")
    for k, v in u.items():
        if k.startswith("_"):
            continue
        if isinstance(v, list):
            out.write(f"  {k} ({len(v)}): {v[:max_items]}\n")
        else:
            out.write(f"  {k}: {v}\n")
    out.write("\n")


def dump(sv: Save, targets, limit=2):
    """TYPE — первые юниты типа; TYPE.поле — юниты, на которые ссылается поле."""
    with open("dump2.txt", "w", encoding="utf-8") as out:
        for t in targets:
            if t in sv.units:  # точный id юнита, например garage.madrid
                out.write(f"=== {t}\n")
                write_unit(out, sv.units[t])
                continue
            if t == "links":
                pl = sv.one("player")
                ptr = pl.get("trucks[]", [])
                out.write("=== links: водитель | idx | трак по player[] | трак по слоту гаража | совпало\n")
                slot = {}
                for g in sv.by_type.get("garage", []):
                    for dr, vh in zip(g.get("drivers[]", []), g.get("vehicles[]", [])):
                        slot[dr] = (g["_name"], vh)
                def desc(ref):
                    tr = build_truck(sv, ref) if ref else None
                    return f"{tr['model']} {tr['plate']} {tr['odometer']}км" if tr else "-"
                for i, did in enumerate(pl.get("drivers[]", [])):
                    a = ptr[i] if i < len(ptr) else None
                    g, b = slot.get(did, ("", None))
                    out.write(f"{did} | {i} | {desc(a)} | {desc(b)} [{g}] | {'да' if a == b else 'НЕТ'}\n")
                continue
            if t == "states":
                out.write("=== states: водитель | state | on_duty_timer | заказ (груз, ед., откуда->куда) | "
                          "текущий город | гараж | прицеп | износ трака\n")
                nk = load_nicknames()
                c = build_company(sv)
                by_id = {d["id"]: d for d in c["drivers"]}
                for u in sv.by_type.get("driver_ai", []):
                    d = by_id.get(u["_name"])
                    if d is None:
                        continue
                    j = d["job"]
                    jt = f"{j['cargo']}, ед.={j['units']}, {j['source']}->{j['target']}, в пути {j['elapsed_min']} мин" if j else "нет"
                    tr = d["trailer"]
                    out.write(f"{d['name']} ({u['_name']}) | state={u.get('state')} | timer={u.get('on_duty_timer')} | "
                              f"{jt} | {u.get('current_city')} | {d['garage']} | "
                              f"{tr['plate'] + (' ЛИЧНЫЙ' if tr['private'] else '') if tr else '-'} | "
                              f"{d['truck']['wear_max'] if d['truck'] else '-'}\n")
                out.write("\n=== сырые юниты водителей (без больших массивов)\n")
                for u in sv.by_type.get("driver_ai", []):
                    if u["_name"] in by_id:
                        write_unit(out, u)
                        jr = sv.ref(u.get("driver_job"))
                        if jr:
                            write_unit(out, jr)
                out.write("\n=== личный прицеп и игрок\n")
                pl = sv.one("player")
                out.write(f"player.assigned_trailer = {pl.get('assigned_trailer')}\n")
                for n in pl.get("trailers[]", []):
                    tu = sv.units.get(n, {})
                    out.write(f"{n}: is_private={tu.get('is_private')} plate={tu.get('license_plate')} "
                              f"odometer={tu.get('odometer')}\n")
                continue
            if t == "prod":
                out.write("=== prod: гараж | тип | слотов | водителей | сырое productivity | по водителям: имя(state,€/день,€/км,выручка 7д)\n")
                c = build_company(sv)
                by_id = {d["id"]: d for d in c["drivers"]}
                for g in sv.by_type.get("garage", []):
                    if to_int(g.get("status")) <= 0:
                        continue
                    ds = [by_id[x] for x in g.get("drivers[]", []) if x in by_id]
                    parts = "; ".join(f"{d['name']}({d.get('state')},{round(d['stats']['net_day'])},"
                                      f"{d['stats']['net_km']:.2f})" for d in ds)
                    out.write(f"{g['_name']} | {g.get('status')} | {len(g.get('vehicles[]', []))} | {len(ds)} | "
                              f"{g.get('productivity')} (={round(f32(g.get('productivity'))*100,2)}%) | {parts}\n")
                out.write("\n=== агрегаты по profit_log гаража: гараж | €/день(7д) | чистая 14д | выручка 14д | рейсов | порожних | км рейсов | км порожняком | топливо порожняком\n")
                now_day = to_int((sv.one("economy") or {}).get("game_time")) // 1440
                for g in sv.by_type.get("garage", []):
                    pr = sv.ref(g.get("profit_log"))
                    if to_int(g.get("status")) <= 0 or not pr:
                        continue
                    es = [sv.units[n] for n in pr.get("stats_data[]", []) if n in sv.units]
                    job = [e for e in es if e.get("distance_on_job") == "true"]
                    emp = [e for e in es if e.get("distance_on_job") != "true"]
                    net = lambda L: sum(to_int(e.get("revenue")) - to_int(e.get("wage")) - to_int(e.get("maintenance")) - to_int(e.get("fuel")) for e in L)
                    wk = [e for e in es if to_int(e.get("timestamp_day")) >= now_day - 7]
                    out.write(f"{g['_name']} | {round(net(wk)/7)} | {net(es)} | {sum(to_int(e.get('revenue')) for e in es)} | "
                              f"{len(job)} | {len(emp)} | {sum(to_int(e.get('distance')) for e in job)} | "
                              f"{sum(to_int(e.get('distance')) for e in emp)} | {sum(to_int(e.get('fuel')) for e in emp)}\n")
                out.write("\n=== profit_log самих гаражей (возможный источник продуктивности)\n")
                for g in sv.by_type.get("garage", []):
                    pr = sv.ref(g.get("profit_log"))
                    if to_int(g.get("status")) > 0 and pr:
                        out.write(f"# {g['_name']}\n")
                        write_unit(out, pr)
                        for n in pr.get("stats_data[]", []):
                            if n in sv.units:
                                write_unit(out, sv.units[n])
                continue
            if t == "garages":  # сводка по всем гаражам с продуктивностью
                out.write("=== garages: id | status | траки | водит. | прицепы | productivity (сырое)\n")
                for u in sv.by_type.get("garage", []):
                    if to_int(u.get("vehicles")) or to_int(u.get("status")):
                        out.write(f"{u['_name']} | {u.get('status')} | {u.get('vehicles')} | "
                                  f"{u.get('drivers')} | {u.get('trailers')} | {u.get('productivity')}\n")
                continue
            if "." in t:
                typ, field = t.split(".", 1)
                out.write(f"=== {t}\n")
                for u in sv.by_type.get(typ, [])[:limit]:
                    out.write(f"{u['_name']}.{field} -> {u.get(field)}\n")
                    r = sv.ref(u.get(field))
                    if r:
                        write_unit(out, r)
                continue
            lst = sv.by_type.get(t, [])
            out.write(f"=== {t}: всего {len(lst)}\n")
            for u in lst[:limit]:
                write_unit(out, u)
    print("Готово: dump2.txt")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    save = Save(Path(sys.argv[1]))
    if len(sys.argv) > 2 and sys.argv[2] == "dump":
        dump(save, sys.argv[3:])
    elif len(sys.argv) > 3 and sys.argv[2] == "driver":
        show_driver(build_company(save), sys.argv[3])
    else:
        show_summary(build_company(save))
