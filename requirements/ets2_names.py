"""Красивые названия траков и прицепов (по файлу локализации игры) и привязка к логотипам.

Названия взяты из locale/common.sui игры (ключи truck_browser_brand_*, brand_*, series_*).
"""
import re

# код модели из сейва -> ключ в списке названий
_ALIASES = {
    "daf.xf": "daf",
    "iveco.stralis": "iveco",
    "iveco.hiway": "iveco_h",
    "man.tgx": "man",
    "mercedes.actros": "mercedes",
    "renault.premium": "renault_p",
    "renault.magnum": "renault_m",
}

# truck_browser_brand_<ключ> из common.sui
TRUCK_NAMES = {
    "daf": "DAF XF105", "daf_2021": "DAF NGD", "daf_xd": "DAF XD", "daf_xf_euro6": "DAF XF",
    "daf_xf_electric": "DAF XF Electric",
    "iveco": "Iveco Stralis", "iveco_h": "Iveco Stralis Hi-Way", "iveco_sway": "Iveco S-Way",
    "man": "MAN TGX Euro 5", "man_tgx_euro6": "MAN TGX Euro 6", "man_tgx_2020": "MAN TGX",
    "mercedes": "Mercedes-Benz Actros", "mercedes_actros_2014": "Mercedes-Benz New Actros",
    "renault_etech_t": "Renault E-Tech T", "renault_m": "Renault Magnum", "renault_p": "Renault Premium",
    "renault_t": "Renault T",
    "scania_r": "Scania R 2009", "scania_r_2016": "Scania R", "scania_s_2016": "Scania S",
    "scania_s_2024e": "Scania S BEV", "scania_streamline": "Scania Streamline",
    "volvo_fh16": "Volvo FH3", "volvo_fh16_2012": "Volvo FH4", "volvo_fh_2021": "Volvo FH5",
    "volvo_fh_2024": "Volvo FH6",
}

BRANDS = {"volvo": "Volvo", "mercedes": "Mercedes-Benz", "renault": "Renault", "scania": "Scania",
          "man": "MAN", "iveco": "Iveco", "daf": "DAF"}

# бренды прицепов (brand_* / series_* из common.sui)
TRAILER_BRANDS = {
    "scs": "SCS", "feldbinder": "Feldbinder", "kassbohrer": "Kässbohrer", "kogel": "Kögel", "krone": "Krone",
    "schmitz": "Schmitz Cargobull", "schwmuller": "Schwarzmüller", "tirsan": "Tırsan", "wielton": "Wielton",
}
TRAILER_SERIES = {
    "scs.box": "STD", "scs.chemtank": "CHT", "scs.container": "CNT", "scs.dumper": "DMP",
    "scs.foodtank": "FDT", "scs.fueltank": "FLT", "scs.flatbed": "FLB", "scs.gastank": "GST",
    "scs.livestock": "LST", "scs.log": "LOG", "scs.lowbed": "LWB", "scs.lowloader": "LLD", "scs.silo": "SLO",
}

BODY_TYPES = {
    "dryvan": "Тентованный/фургон", "curtainside": "Штора", "refrigerated": "Рефрижератор",
    "flatbed": "Бортовой", "container": "Контейнеровоз", "tank": "Цистерна", "foodtank": "Пищевая цистерна",
    "chemtank": "Химическая цистерна", "fueltank": "Топливная цистерна", "gastank": "Газовая цистерна",
    "dumper": "Самосвал", "silo": "Силос", "livestock": "Скотовоз", "log": "Лесовоз",
    "lowbed": "Низкорамный", "lowloader": "Низкорамный", "bulk": "Сыпучие", "car_transporter": "Автовоз",
}


def _norm_model(model: str) -> str:
    """'actros2014' -> 'actros_2014' (в игре годы пишутся через подчёркивание)."""
    return re.sub(r"(?<=[a-z])(?=\d{4}$)", "_", model)


def truck_brand(code):
    """'scania.s_2016' -> 'scania' (имя файла логотипа)."""
    if not code or code == "?":
        return None
    return code.split(".", 1)[0].lower()


def truck_name(code) -> str:
    """'scania.s_2016' -> 'Scania S'; неизвестное показываем как есть, но читаемо."""
    if not code or code == "?":
        return "?"
    code = code.lower()
    if code in _ALIASES:
        key = _ALIASES[code]
    else:
        brand, _, model = code.partition(".")
        key = f"{brand}_{_norm_model(model)}"
    if key in TRUCK_NAMES:
        return TRUCK_NAMES[key]
    brand, _, model = code.partition(".")
    return f"{BRANDS.get(brand, brand.capitalize())} {model.replace('_', ' ').upper()}".strip()


def trailer_name(code, body_type=None) -> str:
    """'scs.box' + 'refrigerated' -> 'Рефрижератор · SCS STD'."""
    body = BODY_TYPES.get((body_type or "").lower(), (body_type or "").capitalize())
    if code:
        brand = code.split(".", 1)[0]
        label = f"{TRAILER_BRANDS.get(brand, brand.capitalize())} {TRAILER_SERIES.get(code, code.split('.', 1)[-1].replace('_', ' ').title())}"
    else:
        label = ""
    return " · ".join(x for x in (body, label) if x) or "?"
