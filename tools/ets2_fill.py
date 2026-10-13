"""Заполнение гаражей: найм водителей из пула игры, копия грузовика и прицепа в свободные места.

Повторяет то, что игра пишет в сейв при найме и покупке (сверено на парах сейвов «до/после», профиль test, 13.10.2026):
- водитель берётся из economy.driver_pool, получает город гаража и место в garage.drivers[i];
- грузовик ставится в garage.vehicles[i] того же места (так игра связывает водителя и грузовик);
- прицеп добавляется в garage.trailers[].
"""
import random
import re

import ets2_manager as core
from requirements.ets2_i18n import tr

from tools.ets2_edit import LINE_KV, EditError, MONEY_MIN, plate_parts

HIRE_FEE = 1500          # плата за найм в игре (видно в сейве: −1 500 €)
HIRE_READY_MIN = 37      # игра ставит событие «водитель готов» через 37 игровых минут после найма
WEAR_RESET = re.compile(r"^(?:engine|transmission|cabin|chassis|trailer_body)_wear(?:_unfixable)?$"
                        r"|^wheels_wear(?:_unfixable)?$")
ZERO_KEYS = {"odometer", "odometer_float_part", "integrity_odometer", "integrity_odometer_float_part",
             "trip_fuel_l", "trip_fuel", "trip_recuperation_kwh", "trip_recuperation", "trip_distance_km",
             "trip_distance", "trip_time_min", "trip_time", "cargo_mass", "cargo_damage"}


def is_empty(v) -> bool:
    return v in (None, "", "null")


# ---------- сейв как набор блоков ----------

class Blocks:
    """Текст сейва, разбитый на юниты: правки внутри одного юнита не требуют прохода по всему файлу."""

    def __init__(self, lines):
        self.segs, self.index, self.extra = [], {}, []
        cur = None
        for line in lines:
            if cur is None:
                m = core.UNIT_START.match(line)
                if m:
                    cur = [line]
                    self.index[m[2]] = cur
                    self.segs.append(cur)
                    continue
                self.segs.append([line])
            else:
                cur.append(line)
                if line.strip() == "}":
                    cur = None
        self.taken = set(self.index)
        self.tail = max(i for i, s in enumerate(self.segs) if s[0].strip() == "}")  # закрывающая скобка SiiNunit

    def lines(self):
        segs = self.segs[:self.tail] + self.extra + self.segs[self.tail:]
        return [line for seg in segs for line in seg]

    def unit(self, name):
        if name not in self.index:
            raise EditError(tr("В сейве нет юнита {unit}: файл изменился, обновите данные (F5).", unit=name))
        return self.index[name]

    def new_id(self):
        while True:
            v = (random.randint(0x1f8, 0xfff) << 32) | random.getrandbits(32)
            name = "_nameless.%x.%04x.%04x" % (v >> 32, (v >> 16) & 0xFFFF, v & 0xFFFF)
            if name not in self.taken:
                self.taken.add(name)
                return name

    def add_unit(self, utype, name, body):
        """Новый юнит перед закрывающей скобкой файла (игра ссылается на юниты по имени, порядок не важен)."""
        seg = [f"{utype} : {name} {{", *body, "}"]
        self.extra += [seg, [""]]
        self.index[name] = seg

    # --- поля ---
    def get(self, name, key):
        for line in self.unit(name)[1:-1]:
            m = LINE_KV.match(line)
            if m and m[2] == key and m[4] is None:
                return m[6]
        return None

    def set(self, name, key, value, idx=None):
        seg = self.unit(name)
        for i, line in enumerate(seg[1:-1], 1):
            m = LINE_KV.match(line)
            if m and m[2] == key and (m[4] is None if idx is None else m[4] == str(idx)):
                seg[i] = f"{m[1]}{key}{'' if idx is None else f'[{idx}]'}{m[5]}{value}{m[7]}"
                return
        raise EditError(tr("У юнита {unit} нет поля {key}: структура сейва неожиданная, правка отменена.",
                           unit=name, key=key if idx is None else f"{key}[{idx}]"))

    def array(self, name, key):
        out = []
        for line in self.unit(name)[1:-1]:
            m = LINE_KV.match(line)
            if m and m[2] == key and m[4] is not None:
                out.append(m[6])
        return out

    def _array_pos(self, seg, key):
        count_i, items = None, []
        for i, line in enumerate(seg[1:-1], 1):
            m = LINE_KV.match(line)
            if m and m[2] == key:
                if m[4] is None:
                    count_i = i
                else:
                    items.append(i)
        return count_i, items

    def append(self, name, key, value):
        seg = self.unit(name)
        count_i, items = self._array_pos(seg, key)
        if count_i is None:
            raise EditError(tr("У юнита {unit} нет поля {key}: структура сейва неожиданная, правка отменена.",
                               unit=name, key=key))
        m = LINE_KV.match(seg[count_i])
        n = len(items)
        seg[count_i] = f"{m[1]}{key}{m[5]}{n + 1}"
        seg.insert((items[-1] if items else count_i) + 1, f"{m[1]}{key}[{n}]: {value}")

    def insert_at(self, name, key, pos, value):
        vals = self.array(name, key)
        vals.insert(pos, value)
        self._rewrite(name, key, vals)

    def remove(self, name, key, value):
        vals = self.array(name, key)
        if value in vals:
            vals.remove(value)
            self._rewrite(name, key, vals)

    def _rewrite(self, name, key, vals):
        seg = self.unit(name)
        count_i, items = self._array_pos(seg, key)
        m = LINE_KV.match(seg[count_i])
        ind = m[1]
        for i in reversed(items):
            del seg[i]
        seg[count_i] = f"{ind}{key}{m[5]}{len(vals)}"
        for k, v in enumerate(vals):
            seg.insert(count_i + 1 + k, f"{ind}{key}[{k}]: {v}")


# ---------- что можно сделать ----------

def pool_drivers(sv):
    """Свободные водители: список агентства (economy.drivers_offer) и запас игры (economy.driver_pool)."""
    eco = sv.one("economy") or {}
    offer = set(eco.get("drivers_offer[]", []))
    names = core.load_nicknames()
    out = []
    for did in eco.get("drivers_offer[]", []) + eco.get("driver_pool[]", []):
        d = sv.units.get(did)
        if not d or d.get("_type") != "driver_ai":
            continue
        skills = {k: core.to_int(d.get(k)) for k in core.SKILLS}
        xp = core.to_int(d.get("experience_points"))
        out.append({
            "id": did,
            "name": names.get(did) or tr("Водитель №{n}", n=did.rpartition(".")[2]),
            "xp": xp,
            "level": core.levels.driver_level(xp, False),
            "skills": skills,
            "adr_classes": bin(skills["adr"]).count("1"),
            "offered": did in offer,
        })
    return out


def free_slots(sv):
    """[{garage, city, slot, has_driver, has_truck}] для мест в своих гаражах, где нет водителя или грузовика."""
    out = []
    for g in sv.by_type.get("garage", []):
        if core.to_int(g.get("status")) <= 0:
            continue
        drivers, vehicles = g.get("drivers[]", []), g.get("vehicles[]", [])
        for i in range(max(len(drivers), len(vehicles))):
            d = drivers[i] if i < len(drivers) else None
            v = vehicles[i] if i < len(vehicles) else None
            if is_empty(d) or is_empty(v):
                out.append({"garage": g["_name"], "city": core.city(g["_name"]), "slot": i,
                            "has_driver": not is_empty(d), "has_truck": not is_empty(v)})
    return out


def truck_templates(sv):
    pl = sv.one("player") or {}
    return [t for t in (core.build_truck(sv, n) for n in pl.get("trucks[]", [])) if t]


def trailer_templates(sv):
    """Свои прицепы, которые можно копировать (одиночные и сцепки)."""
    pl = sv.one("player") or {}
    out = []
    for n in pl.get("trailers[]", []):
        t = core.build_trailer(sv, n)
        if t:
            out.append(t)
    return out


# ---------- запись ----------

def _random_plate_body(body: str) -> str:
    """Тот же вид номера (буквы на месте букв, цифры на месте цифр), другие символы."""
    out = []
    for ch in body:
        if ch.isdigit():
            out.append(random.choice("0123456789"))
        elif ch.isalpha() and ch.isascii():
            out.append(random.choice("ABCDEFGHJKLMNPRSTUVWXYZ"))
        else:
            out.append(ch)
    return "".join(out)


def _new_plate(raw: str) -> str:
    pre, body, tail = plate_parts(raw)
    return '"' + pre + _random_plate_body(body) + tail + '"'


def _reset_vehicle(body, game_time, purchase=True):
    """Состояние нового: износ 0, пробег 0, полный бак, время покупки."""
    out = []
    for line in body:
        m = LINE_KV.match(line)
        if m:
            ind, key, _, idx, sep, val, tail = m.groups()
            rep = None
            if WEAR_RESET.match(key) and not (idx is None and key.startswith("wheels_wear")):
                rep = "0"
            elif key in ZERO_KEYS and idx is None:
                rep = "0"
            elif key == "fuel_relative":
                rep = "1"
            elif key == "purchase_time" and purchase:
                rep = str(game_time)
            elif key == "license_plate" and idx is None:
                rep = _new_plate(val)
            elif key == "is_private":
                rep = "false"
            if rep is not None:
                line = f"{ind}{key}{'' if idx is None else f'[{idx}]'}{sep}{rep}{tail}"
        out.append(line)
    return out


def _clone(b: Blocks, name, game_time, new_units, refs=("accessories",), reset=True):
    """Копия юнита name вместе с его аксессуарами (новые имена). Возвращает имя копии."""
    seg = b.unit(name)
    utype = core.UNIT_START.match(seg[0])[1]
    body = list(seg[1:-1])
    for i, line in enumerate(body):
        m = LINE_KV.match(line)
        if m and m[2] in refs and m[4] is not None and not is_empty(m[6]):
            acc = b.unit(m[6])
            acc_type = core.UNIT_START.match(acc[0])[1]
            nid = b.new_id()
            b.add_unit(acc_type, nid, list(acc[1:-1]))
            new_units.add(nid)
            body[i] = f"{m[1]}{m[2]}[{m[4]}]{m[5]}{nid}{m[7]}"
    if reset:
        body = _reset_vehicle(body, game_time)
    nid = b.new_id()
    b.add_unit(utype, nid, body)
    new_units.add(nid)
    return nid


def _clone_trailer(b: Blocks, name, game_time, new_units, depth=0):
    """Копия прицепа вместе со сцепкой (slave_trailer: второй и третий прицеп у двойных и HCT)."""
    if depth > 4:
        raise EditError(tr("Сцепка прицепов-образца слишком длинная, заполнение отменено."))
    tid = _clone(b, name, game_time, new_units)
    slave = b.get(tid, "slave_trailer")
    if not is_empty(slave):
        b.set(tid, "slave_trailer", _clone_trailer(b, slave, game_time, new_units, depth + 1))
    return tid


def _add_event(b: Blocks, sv, eco, time_, unit_link, param, new_units):
    """Событие в economy_event_queue; очередь отсортирована по времени, вставляем после событий с тем же временем."""
    queue = eco.get("event_queue") or (sv.one("economy_event_queue") or {}).get("_name")
    if not queue:
        raise EditError(tr("Не нашёл очередь событий игры, найм отменён."))
    times = {u["_name"]: core.to_int(u.get("time")) for u in sv.by_type.get("economy_event", [])}
    data = b.array(queue, "data")
    pos = len(data)
    for i, ev in enumerate(data):
        if times.get(ev, 0) > time_:
            pos = i
            break
    nid = b.new_id()
    b.add_unit("economy_event", nid, [f" time: {time_}", f" unit_link: {unit_link}", f" param: {param}"])
    new_units.add(nid)
    b.insert_at(queue, "data", pos, nid)
    return queue


def apply_fill(lines, sv, plan):
    """plan = {"slots": [{"garage", "slot", "driver": id|None, "truck": bool, "trailer": bool}],
    "truck_template": id|None, "trailer_template": id|None, "cost": int}.
    Меняет lines на месте. Возвращает (юниты, которые меняются; новые юниты)."""
    eco, pl = sv.one("economy"), sv.one("player")
    if not eco or not pl:
        raise EditError(tr("В сейве нет данных компании, заполнение отменено."))
    bank = eco.get("bank")
    game_time = core.to_int(eco.get("game_time"))
    b = Blocks(lines)
    touched, new_units = {eco["_name"], pl["_name"]}, set()

    pool = list(eco.get("driver_pool[]", []))
    offers = list(eco.get("drivers_offer[]", []))
    hired = [s["driver"] for s in plan["slots"] if s.get("driver")]
    if len(set(hired)) != len(hired):
        raise EditError(tr("Один водитель выбран дважды."))
    for did in hired:
        if did not in pool and did not in offers:
            raise EditError(tr("Водителя {d} уже нет среди свободных: обновите данные (F5).", d=did))

    cost = int(plan.get("cost") or 0)
    if cost:
        money = b.get(bank, "money_account")
        if money is None or not re.fullmatch(r"-?\d+", money):
            raise EditError(tr("Не нашёл счёт компании в сейве, заполнение отменено."))
        if int(money) - cost < MONEY_MIN or int(money) < cost:
            raise EditError(tr("Не хватает денег: на счёте {have} €, нужно {need} €.",
                               have=f"{int(money):,}".replace(",", " "), need=f"{cost:,}".replace(",", " ")))
        b.set(bank, "money_account", str(int(money) - cost))
        touched.add(bank)

    spare = [d for d in pool if d not in hired]
    for s in plan["slots"]:
        gid, slot = s["garage"], s["slot"]
        touched.add(gid)
        town = gid.partition(".")[2]
        if s.get("driver"):
            did = s["driver"]
            if not is_empty(b.array(gid, "drivers")[slot]):
                raise EditError(tr("Место {n} в гараже {g} уже занято: обновите данные (F5).", n=slot + 1, g=gid))
            b.set(gid, "drivers", did, idx=slot)
            b.set(did, "hometown", town)
            b.set(did, "current_city", town)
            b.set(did, "training_policy", "1")
            touched.add(did)
            for key, val in (("drivers", did), ("driver_flags", "0"), ("driver_readiness_timer", "0"),
                             ("driver_undrivable_truck_timers", "0")):
                b.append(pl["_name"], key, val)
            if did in offers:  # как в игре: на его место в списке агентства встаёт водитель из запаса
                k = offers.index(did)
                repl = spare.pop(random.randrange(len(spare))) if spare else None
                if repl:
                    b.set(eco["_name"], "drivers_offer", repl, idx=k)
                    b.remove(eco["_name"], "driver_pool", repl)
                    offers[k] = repl
                else:
                    b.remove(eco["_name"], "drivers_offer", did)
                    offers.remove(did)
            else:
                b.remove(eco["_name"], "driver_pool", did)
            touched.add(_add_event(b, sv, eco, game_time + HIRE_READY_MIN, did, 3, new_units))
        if s.get("truck"):
            if not plan.get("truck_template"):
                raise EditError(tr("Не выбран грузовик-образец."))
            if not is_empty(b.array(gid, "vehicles")[slot]):
                raise EditError(tr("Место {n} в гараже {g} уже занято: обновите данные (F5).", n=slot + 1, g=gid))
            vid = _clone(b, plan["truck_template"], game_time, new_units)
            log = b.new_id()
            b.add_unit("profit_log", log, [" stats_data: 0", " acc_distance_free: 0", " acc_distance_on_job: 0",
                                           " history_age: nil"])
            new_units.add(log)
            b.set(gid, "vehicles", vid, idx=slot)
            b.append(pl["_name"], "trucks", vid)
            b.append(pl["_name"], "truck_profit_logs", log)
        if s.get("trailer"):
            tpl = plan.get("trailer_template")
            if not tpl:
                raise EditError(tr("Не выбран прицеп-образец."))
            tdef = b.get(tpl, "trailer_definition")
            if is_empty(tdef):
                raise EditError(tr("У прицепа-образца нет описания, заполнение отменено."))
            nd = b.new_id()
            b.add_unit("trailer_def", nd, list(b.unit(tdef)[1:-1]))
            new_units.add(nd)
            tid = _clone_trailer(b, tpl, game_time, new_units)
            b.set(tid, "trailer_definition", nd)
            ulog = b.new_id()
            b.add_unit("trailer_utilization_log", ulog, [" entries: 0", " total_driven_distance_km: 0",
                                                         " total_transported_cargoes: 0",
                                                         " total_transported_weight: 0"])
            new_units.add(ulog)
            b.append(gid, "trailers", tid)
            b.append(pl["_name"], "trailers", tid)
            b.append(pl["_name"], "trailer_utilization_logs", ulog)
            b.append(pl["_name"], "trailer_defs", nd)
    lines[:] = b.lines()
    return touched, new_units
