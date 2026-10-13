"""Уровень по опыту, как в игре.

Игрок: таблица уровней 0..50, дальше +6 800 XP за уровень. Проверено в игре: 368 497 XP = 69 уровень.
Нанятый водитель: те же пороги, умноженные на 2. Проверено в игре на двух водителях
(14 066 XP = 7 уровень, 2 666 / 3 200 XP; 22 415 XP = 10 уровень, 215 / 4 600 XP), а в сейве у 351 из 354 водителей
сумма очков навыков равна этому уровню.
"""

# Опыт для уровней 0..50 (таблица из игры). Проверено на реальном сейве: 368 497 XP = 69 уровень в игре.
LEVEL_XP = (0, 200, 700, 1400, 2300, 3300, 4400, 5700, 7300, 9000,
            11100, 13400, 16000, 18700, 21600, 24600, 27700, 31100, 34800, 38800,
            43100, 47700, 52400, 57300, 62500, 68200, 74100, 80200, 86300, 92900,
            99700, 106500, 113300, 120100, 126900, 133700, 140500, 147300, 154100, 160900,
            167700, 174500, 181300, 188100, 194900, 201700, 208500, 215300, 222100, 228900,
            235700)
LEVEL_STEP = 6800  # после 30-го уровня каждый следующий +6 800 XP; выше 50-го шаг продолжен по той же формуле


def xp_for_level(level: int) -> int:
    """Сколько опыта нужно, чтобы получить уровень level."""
    level = max(0, int(level))
    if level < len(LEVEL_XP):
        return LEVEL_XP[level]
    return LEVEL_XP[-1] + (level - len(LEVEL_XP) + 1) * LEVEL_STEP


def level_for_xp(xp: int) -> int:
    """Уровень игрока по опыту (как в игре)."""
    xp = max(0, int(xp))
    if xp < LEVEL_XP[-1]:
        return max(i for i, need in enumerate(LEVEL_XP) if need <= xp)
    return len(LEVEL_XP) - 1 + (xp - LEVEL_XP[-1]) // LEVEL_STEP


DRIVER_XP_FACTOR = 2
SKILL_POINTS_MAX = 36  # 6 навыков по 6 очков (ADR считается по классам)


def driver_level(xp: int, is_player=False) -> int:
    """Уровень игрока или нанятого водителя по его опыту."""
    return level_for_xp(xp) if is_player else level_for_xp(int(xp) // DRIVER_XP_FACTOR)


def level_progress(xp: int, is_player=False):
    """(уровень, опыт внутри уровня, опыта на весь уровень), как полоска в игре."""
    k = 1 if is_player else DRIVER_XP_FACTOR
    lvl = level_for_xp(int(xp) // k)
    start = xp_for_level(lvl) * k
    return lvl, int(xp) - start, xp_for_level(lvl + 1) * k - start


def xp_for_driver_level(level: int, is_player=False) -> int:
    """Опыт на начало уровня: у игрока по таблице, у нанятого водителя вдвое больше."""
    return xp_for_level(level) * (1 if is_player else DRIVER_XP_FACTOR)
