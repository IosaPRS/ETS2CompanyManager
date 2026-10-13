"""Проверка обновлений: последний релиз на GitHub против VERSION. Без Qt, сеть только по запросу."""
import json
import re
import urllib.error
import urllib.request

from requirements.app_info import REPO, VERSION

API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"


class UpdateError(Exception):
    """Не удалось узнать последнюю версию (нет сети, лимит GitHub и т.п.)."""


def parse_version(text):
    """'v1.2.0' -> (1, 2, 0); мусор вокруг цифр игнорируется."""
    nums = re.findall(r"\d+", str(text or ""))[:3]
    return tuple(int(n) for n in nums) + (0,) * (3 - len(nums)) if nums else (0, 0, 0)


def is_newer(remote, local=VERSION):
    return parse_version(remote) > parse_version(local)


def latest_release(timeout=8):
    """{'version': '1.2.0', 'url': ..., 'name': ...} последнего релиза."""
    req = urllib.request.Request(API_URL, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": f"ETS2CompanyManager/{VERSION}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise UpdateError(str(exc)) from None
    tag = data.get("tag_name") or ""
    if not tag:
        raise UpdateError("no tag_name")
    return {"version": tag.lstrip("vV"), "url": data.get("html_url") or RELEASES_URL, "name": data.get("name") or tag}


def check(timeout=8):
    """(есть_новее, данные_релиза)."""
    rel = latest_release(timeout)
    return is_newer(rel["version"]), rel
