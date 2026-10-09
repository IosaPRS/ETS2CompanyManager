"""Где лежат данные программы (assets, locales, driver_names.json): из исходников, из .exe PyInstaller или рядом с .exe."""
import sys
from pathlib import Path


def app_dirs():
    """Папки поиска по приоритету: рядом с .exe (можно подменить файлы), внутри сборки, исходники."""
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(Path(sys.executable).resolve().parent)
        if getattr(sys, "_MEIPASS", None):
            dirs.append(Path(sys._MEIPASS))
    dirs.append(Path(__file__).resolve().parent.parent)
    return dirs


def data_path(*parts):
    """Первый существующий путь среди app_dirs(); если нигде нет, путь в папке исходников."""
    for base in app_dirs():
        p = base.joinpath(*parts)
        if p.exists():
            return p
    return app_dirs()[-1].joinpath(*parts)
