#!/usr/bin/env python3
"""Декодер сейвов SCS (ETS2/ATS): ScsC (AES-256-CBC + zlib), BSII (бинарный) и SiiN (текст).

Python-порт проекта sii-decode-rs (https://github.com/fangyi-zhou/sii-decode-rs, лицензия MIT),
который сам портирован с SII_Decrypt (František Milt, MPL-2.0) и sii-decryptsharp (Joshua Menzel).
Формат описан в документации SII_Decrypt: "Binary SII - Format.txt" и "Binary SII - Types.txt".

Для расшифровки ScsC нужна библиотека AES:  pip install cryptography   (или pycryptodome)

Командная строка:
    python sii_decode.py game.sii game_text.sii      # превратить любой сейв в текстовый
"""
import math
import struct
import sys
import zlib

SCSC_KEY = bytes.fromhex("2a5fcb1791d22fb60245b3d8369ed0b2c27371563fbf1f3c9edf6b11825a5d0a")
_CHARS = "0123456789abcdefghijklmnopqrstuvwxyz_"
_ALNUM = frozenset(b"0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_BOM = b"\xef\xbb\xbf"


class SiiError(Exception):
    """Файл не удалось расшифровать или разобрать."""


# ---------- тип файла и ScsC ----------

def detect_file_type(data: bytes):
    """'scsc' | 'bsii' | 'siin' | None по первым четырём байтам."""
    head = data[3:7] if data.startswith(_BOM) else data[:4]
    return {b"ScsC": "scsc", b"BSII": "bsii", b"SiiN": "siin"}.get(head)


def _aes_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        Cipher = None
    if Cipher is not None:
        dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return dec.update(data) + dec.finalize()
    try:
        from Crypto.Cipher import AES
    except ImportError:
        raise SiiError("Для расшифровки нужна библиотека AES: pip install cryptography") from None
    return AES.new(key, AES.MODE_CBC, iv).decrypt(data)


def decrypt_scsc(data: bytes) -> bytes:
    """ScsC -> внутренние данные (BSII или SiiN).

    Структура: 'ScsC', HMAC (32 байта), IV (16), размер распакованных данных (u32 LE), данные.
    Данные зашифрованы AES-256-CBC без паддинга и сжаты zlib. HMAC не проверяется.
    """
    if data.startswith(_BOM):
        data = data[3:]
    if data[:4] != b"ScsC" or len(data) < 56:
        raise SiiError("Некорректный заголовок ScsC")
    iv = data[36:52]
    size = struct.unpack_from("<I", data, 52)[0]
    payload = data[56:]
    if len(payload) % 16:
        raise SiiError("Размер зашифрованных данных не кратен 16: файл повреждён или обрезан")
    plain = _aes_cbc_decrypt(SCSC_KEY, iv, payload)
    try:
        out = zlib.decompressobj().decompress(plain)
    except zlib.error as exc:
        raise SiiError(f"Ошибка распаковки: {exc}") from None
    if len(out) < size:
        raise SiiError("После распаковки данных меньше, чем заявлено в заголовке")
    return out[:size]


def unwrap(data: bytes) -> bytes:
    """Снимает слой ScsC, если он есть. Возвращает BSII или SiiN."""
    return decrypt_scsc(data) if detect_file_type(data) == "scsc" else data


# ---------- форматирование значений (как в текстовом .sii) ----------

def _f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _fmt_float(x: float) -> str:
    if math.isfinite(x) and x == math.trunc(x) and abs(x) <= 1e7:
        return "-0" if x == 0 and math.copysign(1.0, x) < 0 else str(int(x))
    return "&%08x" % struct.unpack("<I", struct.pack("<f", x))[0]


def _fmt_string(b: bytes) -> str:
    if not b:
        return '""'
    if all(c in _ALNUM for c in b):
        return b.decode("ascii")
    return '"' + "".join(chr(c) if 32 <= c <= 127 else "\\x%02x" % c for c in b) + '"'


def _fmt_u16(v): return "nil" if v == 0xFFFF else str(v)
def _fmt_u32(v): return "nil" if v == 0xFFFFFFFF else str(v)
def _fmt_u64(v): return "nil" if v == 0xFFFFFFFFFFFFFFFF else str(v)
def _fmt_bool(v): return "true" if v else "false"


def _fmt_vec(values) -> str:
    return "(" + ", ".join(_fmt_float(v) for v in values) + ")"


def _fmt_vec4(v) -> str:
    return "(%s; %s, %s, %s)" % tuple(_fmt_float(x) for x in v)


def _fmt_vec8(v) -> str:
    """Placement: координаты x и z хранятся со сдвигом в четвёртом числе."""
    f1, f2, f3, f4, f5, f6, f7, f8 = v
    coef = int(f4) if math.isfinite(f4) else 0
    coef = max(-(2 ** 31), min(2 ** 31 - 1, coef))
    x = _f32(f1 + (((coef & 0xFFF) - 2048) << 9))
    z = _f32(f3 + ((((coef >> 12) & 0xFFF) - 2048) << 9))
    return "(%s, %s, %s) (%s; %s, %s, %s)" % tuple(_fmt_float(t) for t in (x, f2, z, f5, f6, f7, f8))


def _fmt_nameless(v: int) -> str:
    if v == 0:
        return "_nameless.0"
    parts, started = ["_nameless"], False
    for shift in (48, 32, 16, 0):
        part = (v >> shift) & 0xFFFF
        if not started and part != 0:
            started = True
            parts.append("%x" % part)
        elif started:
            parts.append("%04x" % part)
    return ".".join(parts)


# ---------- бинарный BSII ----------

class _Reader:
    __slots__ = ("d", "p")

    def __init__(self, data: bytes, pos: int = 0):
        self.d, self.p = data, pos

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def u64(self):
        v = struct.unpack_from("<Q", self.d, self.p)[0]
        self.p += 8
        return v

    def take(self, n: int) -> bytes:
        if self.p + n > len(self.d):
            raise SiiError("Файл обрезан")
        b = self.d[self.p:self.p + n]
        self.p += n
        return b

    def raw_str(self) -> bytes:
        return self.take(self.u32())

    def name(self) -> str:
        return self.raw_str().decode("utf-8", errors="replace")

    def floats(self, n: int):
        v = struct.unpack_from("<%df" % n, self.d, self.p)
        self.p += 4 * n
        return v

    def encoded(self) -> str:
        v = self.u64() & 0x7FFFFFFFFFFFFFFF
        out = []
        while v:
            v, last = divmod(v, 38)
            if last == 0:
                raise SiiError("Некорректная закодированная строка")
            out.append(_CHARS[last - 1])
        return "".join(out)

    def id(self) -> str:
        n = self.u8()
        if n == 0xFF:
            return _fmt_nameless(self.u64())
        if n == 0:
            return "null"
        return ".".join(self.encoded() for _ in range(n))


# тип массива -> тип элемента
_ARRAY_ELEM = {0x02: 0x01, 0x04: 0x03, 0x06: 0x05, 0x12: 0x11, 0x18: 0x17, 0x1A: 0x19, 0x26: 0x25,
               0x28: 0x27, 0x2C: 0x2B, 0x32: 0x31, 0x34: 0x33, 0x36: 0x35, 0x3A: 0x39, 0x3C: 0x3B}
# числовые массивы читаются одним вызовом struct: тип -> (код struct, размер, форматтер)
_BULK = {0x06: ("f", 4, _fmt_float), 0x26: ("i", 4, str), 0x28: ("I", 4, _fmt_u32), 0x2C: ("H", 2, _fmt_u16),
         0x32: ("q", 8, str), 0x34: ("Q", 8, _fmt_u64), 0x36: ("B", 1, _fmt_bool)}
_SCALARS = {0x01, 0x03, 0x05, 0x07, 0x09, 0x11, 0x19, 0x25, 0x27, 0x2F, 0x2B, 0x31, 0x33, 0x35, 0x37,
            0x39, 0x3B, 0x3D}


def _read_elem(r: _Reader, t: int, enums) -> str:
    if t == 0x01:
        return _fmt_string(r.raw_str())
    if t == 0x03:
        s = r.encoded()
        return s if s else '""'
    if t == 0x05:
        return _fmt_float(r.floats(1)[0])
    if t == 0x07:
        return _fmt_vec(r.floats(2))
    if t == 0x09:
        return _fmt_vec(r.floats(3))
    if t == 0x11:
        return "(%d, %d, %d)" % struct.unpack_from("<3i", r.d, _advance(r, 12))
    if t == 0x17:
        return _fmt_vec4(r.floats(4))
    if t == 0x19:
        return _fmt_vec8(r.floats(8))
    if t == 0x25:
        return str(struct.unpack_from("<i", r.d, _advance(r, 4))[0])
    if t in (0x27, 0x2F):
        return _fmt_u32(r.u32())
    if t == 0x2B:
        return _fmt_u16(struct.unpack_from("<H", r.d, _advance(r, 2))[0])
    if t == 0x31:
        return str(struct.unpack_from("<q", r.d, _advance(r, 8))[0])
    if t == 0x33:
        return _fmt_u64(r.u64())
    if t == 0x35:
        return _fmt_bool(r.u8())
    if t == 0x37:
        key = r.u32()
        if not enums or key not in enums:
            raise SiiError(f"Неизвестное значение перечисления {key}")
        return _fmt_string(enums[key].encode("utf-8"))
    if t in (0x39, 0x3B, 0x3D):
        return r.id()
    raise SiiError("Неподдерживаемый тип значения 0x%x" % t)


def _advance(r: _Reader, n: int) -> int:
    """Возвращает текущую позицию и сдвигает читатель на n байт."""
    pos = r.p
    r.p += n
    return pos


def _read_value(r: _Reader, t: int, enums):
    """Возвращает (значение, это_массив). Значение — строка или список строк."""
    if t in _BULK:
        code, size, fmt = _BULK[t]
        n = r.u32()
        vals = struct.unpack_from("<%d%s" % (n, code), r.d, r.p)
        r.p += n * size
        return [fmt(v) for v in vals], True
    if t in _ARRAY_ELEM:
        et = _ARRAY_ELEM[t]
        n = r.u32()
        return [_read_elem(r, et, enums) for _ in range(n)], True
    if t in _SCALARS:
        return _read_elem(r, t, enums), False
    raise SiiError("Неподдерживаемый тип значения 0x%x" % t)


def parse_bsii(data: bytes):
    """Разбирает BSII. Возвращает список блоков (тип юнита, id, [(поле, значение, массив?)])."""
    if data.startswith(_BOM):
        data = data[3:]
    if data[:4] != b"BSII":
        raise SiiError("Это не BSII")
    try:
        r = _Reader(data, 4)
        if r.u32() == 1:
            raise SiiError("BSII версии 1 не поддерживается")
        protos, blocks = {}, []
        while True:
            block_id = r.u32()
            if block_id == 0:
                if r.u8() == 0:  # конец файла
                    return blocks
                pid, name, fields = r.u32(), r.name(), []
                while True:
                    t = r.u32()
                    if t == 0:
                        break
                    fname, enums = r.name(), None
                    if t == 0x37:
                        enums = {}
                        for _ in range(r.u32()):
                            key = r.u32()
                            enums[key] = r.name()
                    fields.append((fname, t, enums))
                protos[pid] = (name, fields)
            else:
                name, fields = protos[block_id]
                bid = r.id()
                values = []
                for fname, t, enums in fields:
                    value, is_array = _read_value(r, t, enums)
                    values.append((fname, value, is_array))
                blocks.append((name, bid, values))
    except (struct.error, IndexError, KeyError) as exc:
        raise SiiError(f"Файл повреждён или имеет неизвестную структуру ({type(exc).__name__}: {exc})") from None


def bsii_to_units(blocks):
    """Блоки BSII -> список словарей в том же виде, что даёт разбор текстового .sii."""
    units = []
    for name, bid, values in blocks:
        unit = {"_type": name, "_name": bid}
        for fname, value, is_array in values:
            if is_array:
                unit[fname] = str(len(value))
                if value:
                    unit[fname + "[]"] = [v.strip('"') for v in value]
            else:
                unit[fname] = value.strip('"')
        units.append(unit)
    return units


def bsii_to_text(data: bytes) -> str:
    """BSII -> текстовый SiiNunit."""
    out = ["SiiNunit", "{"]
    for name, bid, values in parse_bsii(data):
        out.append("%s : %s {" % (name, bid))
        for fname, value, is_array in values:
            if is_array:
                out.append("  %s: %d" % (fname, len(value)))
                out.extend("  %s[%d]: %s" % (fname, i, v) for i, v in enumerate(value))
            else:
                out.append("  %s: %s" % (fname, value))
        out.append("}")
    out.append("}")
    return "\n".join(out) + "\n"


def decode_to_text(data: bytes) -> str:
    """Любой поддерживаемый формат -> текст."""
    inner = unwrap(data)
    kind = detect_file_type(inner)
    if kind == "bsii":
        return bsii_to_text(inner)
    if kind == "siin":
        return inner.decode("utf-8-sig", errors="replace")
    raise SiiError("Неизвестный формат файла")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    try:
        with open(sys.argv[1], "rb") as f:
            text = decode_to_text(f.read())
    except SiiError as exc:
        raise SystemExit(f"Ошибка: {exc}")
    with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("Готово:", sys.argv[2])
