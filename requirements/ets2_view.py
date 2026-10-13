"""Данные для окна без Qt: строки таблиц, текст карточки водителя, поиск сейва, имена."""
import html
import json
from pathlib import Path

import ets2_manager as core
from requirements.ets2_i18n import tr

GREEN, RED, AMBER = (76, 175, 80), (229, 57, 53), (255, 179, 0)

DRIVER_HEADERS = ["Водитель", "Город", "Гараж", "XP", "ADR", "Дальн.", "Тяжёл.", "Хрупк.", "Срочн.",
                  "Эко", "Σ навыков", "Трак", "Прицеп", "Статус", "Маршрут", "Прибыль", "€/день"]
TRUCK_HEADERS = ["Модель", "Номер", "Водитель", "Пробег км", "Топливо %", "Двигатель",
                 "Трансм.", "Кабина", "Шасси", "Колёса", "Макс.", "Постоянный", "Статус"]
TRAILER_HEADERS = ["Тип", "Номер", "Водитель", "Пробег км", "Км по рейсам", "Износ", "Статус"]
GARAGE_HEADERS = ["Город", "Тип", "Траки", "Водители", "Прицепы", "€/день", "Продуктивн."]
JOB_HEADERS = ["Водитель", "Груз", "Откуда", "Куда", "Км", "В пути", "Паром", "Срочн."]

PERMANENT_WEAR_LIMIT = 30.0
STATE_NO_TRUCK, STATE_IDLE, STATE_JOB, STATE_PROBLEM, STATE_PARKED = "0", "1", "2", "3", "4"
REST_STATES = {STATE_PARKED}


def job_phase(d):
    """Фаза рейса: 'cargo' (с грузом), 'empty' (порожняком), 'parked' (стоянка/отдых) или None (нет рейса)."""
    if str(d.get("state")) in REST_STATES:
        return "parked"
    if not d["job"]:
        return None
    return "cargo" if d["job"]["units"] > 0 else "empty"


def status_spec(glyph, bg):
    return f"{glyph}@{bg}"


def has_problem(d):
    return str(d.get("state")) == STATE_PROBLEM or bool(d["truck"] and d["truck"]["perm_max"] >= PERMANENT_WEAR_LIMIT)


def driver_status(d):
    """(текст, значок@фон) для водителя."""
    if not d["truck"] or str(d.get("state")) == STATE_NO_TRUCK:
        return tr("без трака"), status_spec("no_vehicle", "red")
    if has_problem(d):
        return tr("требует ремонта"), status_spec("driver_status_truck_undrivable", "red")
    ph = job_phase(d)
    if ph == "parked":
        return tr("на стоянке"), status_spec("driver_status_sleeping", "blue")
    if ph == "empty":
        return tr("порожняком"), status_spec("driver_status_driving", "turquoise")
    if ph == "cargo":
        return tr("в рейсе"), status_spec("driver_status_driving", "green")
    return tr("простаивает"), status_spec("driver_status_idle", "gray")


def truck_status(d):
    t = d["truck"]
    if has_problem(d):
        return tr("требует ремонта"), status_spec("truck_status_undrivable", "red")
    ph = job_phase(d)
    if ph == "parked":
        return tr("на стоянке"), status_spec("truck_status_parked_on_job", "blue")
    if ph == "empty":
        return tr("порожняком"), status_spec("trailer_status_on_job", "turquoise")
    if ph == "cargo":
        return tr("в рейсе"), status_spec("trailer_status_on_job", "green")
    return tr("простаивает"), status_spec("truck_status_idle", "gray")


def trailer_status(t, owner):
    if t.get("private"):
        return tr("личный"), status_spec("trailer_status_private", "blue")
    if t["perm_max"] >= PERMANENT_WEAR_LIMIT or (owner and str(owner.get("state")) == STATE_PROBLEM):
        return tr("требует ремонта"), status_spec("trailer_status_undrivable", "red")
    ph = job_phase(owner) if owner else None
    if ph == "parked":
        return tr("на стоянке"), status_spec("trailer_status_on_job", "blue")
    if ph == "empty":
        return tr("порожняком"), status_spec("trailer_status_on_job", "turquoise")
    if ph == "cargo":
        return tr("в рейсе"), status_spec("trailer_status_on_job", "green")
    return tr("простаивает"), status_spec("trailer_status_idle", "gray")


def avatar_spec(driver_id):
    """'driver.167' -> 'avatar:167' (портрет assets/avatars/167.jpg)."""
    n = str(driver_id).rpartition(".")[2]
    return f"avatar:{n}" if n.isdigit() else None


STATUS_TINT = {"в рейсе": GREEN + (90,), "порожняком": (0, 188, 188, 90), "на стоянке": (66, 133, 244, 90),
               "личный": (66, 133, 244, 90), "простаивает": (158, 158, 158, 90),
               "без трака": RED + (90,), "требует ремонта": RED + (110,)}


def status_tint(text):
    """Цвет фона по (переведённому) тексту статуса."""
    return next((v for k, v in STATUS_TINT.items() if tr(k) == text), None)


def cell(text, sort=None, right=False, tint=None, center=False, icon=None, tip=None):
    """Ячейка таблицы: текст, ключ сортировки, выравнивание, цвет фона (r, g, b, a),"""
    text = str(text)
    return {"text": text, "sort": text.lower() if sort is None else sort, "right": right,
            "center": center, "tint": tint, "icon": icon, "tip": tip}


def skill_tint(v, top=6):
    return GREEN + (int(30 + 120 * v / top),) if v > 0 else None


def wear_tint(pct):
    if pct >= 50:
        return RED + (110,)
    if pct >= 25:
        return AMBER + (110,)
    return None


def wear_cell(x):
    return cell(f"{x:.1f}%", x, tint=wear_tint(x), center=True)


def prod_tint(p):
    if p >= 90:
        return GREEN + (90,)
    return AMBER + (110,) if p >= 50 else RED + (110,)


def num_cell(n):
    return cell(core.money(n), n, True)


def c_num(n, tint=None):
    """Небольшое число по центру колонки."""
    return cell(n, n, tint=tint, center=True)



def route_text(d):
    """Строка маршрута: откуда -> куда, груз, длина. Без заказа - прочерк."""
    j = d["job"]
    if not j:
        return "-"
    return tr("{src} → {dst} · {cargo} · {km} км", src=j["source"], dst=j["target"], cargo=j["cargo"], km=j["km"])


def driver_rows(c):
    rows = []
    for d in c["drivers"]:
        s, st, t, trl = d["skills"], d["stats"], d["truck"], d["trailer"]
        name = cell(("★ " if d["is_player"] else "") + d["name"], icon=avatar_spec(d["id"]))
        st_text, st_icon = driver_status(d)
        cells = [
            name, cell(d["city"]), cell(d["garage"] or "-"),
            num_cell(d["xp"]),
            c_num(d["adr_classes"], skill_tint(d["adr_classes"])),
        ]
        cells += [c_num(s[k], skill_tint(s[k])) for k in ("long_dist", "heavy", "fragile", "urgent", "mechanical")]
        cells += [
            c_num(d["skill_sum"]),
            cell(t["model"], icon=t["brand"], tip=tr("Номер: {plate}", plate=t['plate'])) if t else cell("-"),
            cell(trl["kind"], tip=tr("Номер: {plate}", plate=trl['plate'])) if trl else cell("-"),
            cell(st_text, tint=status_tint(st_text), icon="status:" + st_icon, center=True),
            cell(route_text(d), tip=(tr("В пути {t}", t=core.fmt_duration(d["job"]["elapsed_min"])) if d["job"] else None)),
            num_cell(st["net"]),
            num_cell(round(st["net_day"])),
        ]
        rows.append((d["id"], cells))
    return rows


def truck_rows(c):
    rows = []
    for d in c["drivers"]:
        t = d["truck"]
        if not t:
            continue
        w = t["wear"]
        cells = [cell(t["model"], icon=t["brand"], tip=tr("Номер: {plate}", plate=t['plate'])), cell(t["plate"]),
                 cell(d["name"]), num_cell(t["odometer"]), cell(f'{t["fuel_pct"]:.0f}%', t["fuel_pct"], center=True)]
        cells += [wear_cell(w[k]) for k in ("engine", "transmission", "cabin", "chassis", "wheels")]
        cells.append(wear_cell(t["wear_max"]))
        pm = t["perm_max"]
        cells.append(cell(f"{pm:.1f}%", pm, tint=RED + (110,) if pm >= PERMANENT_WEAR_LIMIT else (AMBER + (110,) if pm >= 20 else None),
                          center=True, tip=tr("Постоянный (неремонтируемый) износ: с 30% водитель отказывается ехать")))
        tx, ti = truck_status(d)
        cells.append(cell(tx, tint=status_tint(tx), icon="status:" + ti, center=True))
        rows.append((d["id"], cells))
    return rows


def trailer_rows(c):
    owner = {d["trailer"]["unit"]: d["name"] for d in c["drivers"] if d["trailer"]}
    by_unit = {d["trailer"]["unit"]: d for d in c["drivers"] if d["trailer"]}
    rows = []
    for t in c["trailers"]:
        own = by_unit.get(t["unit"])
        tx, ti = trailer_status(t, own)
        trip_km = own["stats"]["km_hist"] if own else 0
        rows.append((t["unit"], [cell(t["kind"], tip=tr("Номер: {plate}", plate=t['plate'])), cell(t["plate"]),
                                 cell(owner.get(t["unit"], "-")),
                                 num_cell(t["odometer"]),
                                 cell(f"{trip_km:,}".replace(",", " ") if trip_km else "-", trip_km, True,
                                      tip=tr("Км рейсов водителя за сохранённую историю (до 14 дней), не весь пробег")),
                                 wear_cell(t["wear"]),
                                 cell(tx, tint=status_tint(tx), icon="status:" + ti, center=True)]))
    return rows


GARAGE_TYPES = {0: ("Не куплен", 0), 1: ("Стартовый", 1), 2: ("Малый", 3), 3: ("Большой", 5)}


# Для стартового гаража стоимость неизвестна.
GARAGE_PRICE = {2: 150000, 3: 300000}


def prod_value(g):
    """Продуктивность гаража в процентах или None, если стоимость гаража неизвестна."""
    price = GARAGE_PRICE.get(g["status"])
    if not price:
        return None
    return min(100, round(g["net_day"] * 7 / price * 100))


def prod_cell(g):
    p = prod_value(g)
    if p is None:
        return cell("?", -1, center=True, tip=tr("Для этого типа гаража формула неизвестна: смотрите в игре."))
    return cell(f"{p}%", p, tint=prod_tint(p), center=True,
                tip=tr("Прибыль гаража за 7 дней / стоимость гаража (150 000 € малый, 300 000 € большой)"))


def garage_rows(c):
    rows = []
    for g in c["garages"]:
        name, cap = GARAGE_TYPES.get(g["status"], (tr("Тип {n}", n=g['status']), g["vehicles"]))
        rows.append((g["id"], [
            cell(g["city"]), cell(tr(name), g["status"], center=True, tip=tr("Мест: {n}", n=cap)),
            cell(f'{g["vehicles"]}/{cap}', g["vehicles"], center=True),
            cell(f'{g["drivers"]}/{cap}', g["drivers"], center=True),
            c_num(g["trailers"]),
            num_cell(round(g["net_day"])),
            prod_cell(g),
        ]))
    return rows


def job_rows(c):
    rows = []
    for d in c["drivers"]:
        j = d["job"]
        if not j:
            continue
        rows.append((d["id"], [
            cell(d["name"]), cell(j["cargo"]), cell(j["source"]), cell(j["target"]),
            num_cell(j["km"]),
            cell(core.fmt_duration(j["elapsed_min"]), j["elapsed_min"], True),
            num_cell(j["ferry_price"]) if j["ferry_price"] else cell("-", 0, True),
            cell(tr("да") if j["urgent"] else tr("нет"), center=True),
        ]))
    return rows


# ---------- тексты ----------

def safe_money(v):
    try:
        return core.money(v)
    except (TypeError, ValueError):
        return str(v)


def driver_card_html(d):
    e = html.escape
    s, st, t, trl, j = d["skills"], d["stats"], d["truck"], d["trailer"], d["job"]
    lines = [
        f"<h3>{e(d['name'])} <small>({e(d['id'])})</small></h3>",
        tr("<b>Родина:</b> {home} &nbsp; <b>Сейчас:</b> {city} &nbsp; <b>Гараж:</b> {garage} &nbsp; <b>XP:</b> {xp}",
           home=e(d['hometown']), city=e(d['city']), garage=e(d['garage'] or '-'), xp=core.money(d['xp'])),
        tr("<b>Навыки:</b> ADR {adr}/6, дальние {ld}, тяжёлые {hv}, хрупкие {fr}, срочные {ur}, эко {me}",
           adr=d['adr_classes'], ld=s['long_dist'], hv=s['heavy'], fr=s['fragile'], ur=s['urgent'], me=s['mechanical']),
    ]
    if t:
        lines.append(tr("<b>Трак:</b> {model} {plate}, пробег {odo} км, макс. износ {wear:.1f}%",
                        model=e(t['model']), plate=e(t['plate']), odo=core.money(t['odometer']), wear=t['wear_max']))
    if trl:
        lines.append(tr("<b>Прицеп:</b> {kind} {plate}, пробег {odo} км, износ {wear:.1f}%",
                        kind=e(trl['kind']), plate=e(trl['plate']), odo=core.money(trl['odometer']), wear=trl['wear']))
    if j:
        lines.append(tr("<b>Сейчас в рейсе:</b> {cargo}, {src} → {dst}, {km} км, в пути {t}",
                        cargo=e(j['cargo']), src=e(j['source']), dst=e(j['target']), km=j['km'],
                        t=core.fmt_duration(j['elapsed_min'])) + (tr(", срочный") if j["urgent"] else ""))
    else:
        lines.append(tr("<b>Сейчас без заказа</b>"))
    lines.append(tr("<b>Заказов в истории:</b> {n}, км по заказам {kj}, порожняком {kf}",
                    n=st['jobs'], kj=core.money(st['km_job']), kf=core.money(st['km_free'])))
    lines.append(tr("<b>Выручка</b> {rev}, зарплата {wage}, топливо {fuel}, обслуживание {maint}, <b>прибыль {net}</b>",
                    rev=core.money(st['revenue']), wage=core.money(st['wage']), fuel=core.money(st['fuel']),
                    maint=core.money(st['maintenance']), net=core.money(st['net'])))
    return "<br>".join(lines)


# ---------- сейвы и имена ----------

GAMES = (("ets2", "Euro Truck Simulator 2"), ("ats", "American Truck Simulator"))
PROFILE_DIRS = ("profiles", "steam_profiles")


def documents_dirs():
    """Возможные папки «Документы»: обычная, в OneDrive и из USERPROFILE (без повторов)."""
    import os
    home = Path.home()
    cands = [home / "Documents", home / "OneDrive" / "Documents", home / "OneDrive" / "Документы"]
    if os.environ.get("USERPROFILE"):
        cands.append(Path(os.environ["USERPROFILE"]) / "Documents")
    out, seen = [], set()
    for p in cands:
        key = str(p).lower()
        if key not in seen and p.is_dir():
            seen.add(key)
            out.append(p)
    return out


def _mtime(p):
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def slot_title(slot_dir: Path) -> str:
    """Название слота: поле name из info.sii; если его нет, по имени папки (autosave, quicksave, 1...)."""
    info = slot_dir / "info.sii"
    name = ""
    if info.exists():
        try:
            sv = core.Save(info)
            unit = sv.one("save_container") or next(iter(sv.units.values()), {})
            name = str(unit.get("name") or "").strip()
        except (SystemExit, Exception):  # битый или нечитаемый info.sii не мешает выбору
            name = ""
    if name and not name.startswith("@@"):
        return name
    folder = slot_dir.name
    if folder == "autosave" or folder.startswith("autosave"):
        return tr("Автосохранение")
    if folder == "quicksave":
        return tr("Быстрое сохранение")
    if folder.isdigit():
        return tr("Слот {n}", n=folder)
    return folder


def find_profiles(read_titles=True):
    """Все профили ETS2 и ATS: [{'game', 'game_name', 'name', 'dir', 'saves': [{'title', 'slot', 'path', 'mtime'}], 'mtime'}].

    Сортировка: сначала профили со свежими сейвами. read_titles=False не читает info.sii (быстрее).
    """
    profiles = []
    for docs in documents_dirs():
        for code, game in GAMES:
            for sub in PROFILE_DIRS:
                root = docs / game / sub
                if not root.is_dir():
                    continue
                for pdir in sorted(x for x in root.iterdir() if x.is_dir()):
                    saves = []
                    for gp in (pdir / "save").glob("*/game.sii"):
                        saves.append({"slot": gp.parent.name, "path": gp, "mtime": _mtime(gp),
                                      "title": slot_title(gp.parent) if read_titles else gp.parent.name})
                    if not saves:
                        continue
                    saves.sort(key=lambda x: -x["mtime"])
                    profiles.append({"game": code, "game_name": game, "dir": pdir, "saves": saves,
                                     "name": core.profile_name_from_path(pdir) or pdir.name,
                                     "steam": sub == "steam_profiles", "mtime": saves[0]["mtime"]})
    profiles.sort(key=lambda x: -x["mtime"])
    return profiles


def profile_dir_of(save_path):
    """.../profiles/<hex>/save/<слот>/game.sii -> папка профиля или None."""
    p = Path(save_path)
    if p.parent.parent.name == "save":
        return p.parent.parent.parent
    return None


def find_latest_save(profile_dir=None):
    """Самый свежий game.sii: в указанном профиле или среди всех профилей ETS2 и ATS."""
    if profile_dir:
        found = list(Path(profile_dir).glob("save/*/game.sii"))
        if found:
            return max(found, key=_mtime)
    profiles = find_profiles(read_titles=False)
    return profiles[0]["saves"][0]["path"] if profiles else None


def save_nickname(driver_id, name):
    """Сохраняет своё имя водителя в папку настроек пользователя (пустое имя возвращает имя по умолчанию)."""
    p = core.custom_names_path()
    data = core._read_names(p)
    if name:
        data[driver_id] = name
    else:
        data.pop(driver_id, None)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
