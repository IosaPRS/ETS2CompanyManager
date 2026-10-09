# ETS2 Company Manager

**English** · [Русский](README.ru.md) · [Deutsch](README.de.md)

A desktop tool for managing your in-game company in Euro Truck Simulator 2. It reads your save file and shows
every driver, truck, trailer, garage and job in one place, and can safely repair, refuel, rename plates,
upgrade garages and level up driver skills in the save.

## Features

- **Drivers**: city, home garage, XP, skills, truck, trailer, status, current route, profit and €/day.
  Statuses use the in-game colours: on a job, empty run, parked, idle, broken, no truck.
- **Trucks and trailers**: odometer, fuel, wear per part, permanent wear (a driver refuses to drive from 30%), status.
- **Garages**: type, slots, drivers, trailers, income per day and productivity.
- **Jobs**: who is hauling what, from where to where, distance, time on the road, ferry cost.
- **Skills tab**: pick what to level up for every driver, like in the game (long distance, high value cargo,
  fragile cargo, just-in-time, ecodriving and the six ADR classes).
- **Save editing**: repair (all or selected), refuel, change plates, upgrade a small garage to a large one, raise skills.
- Dark and light theme, English / Russian / German / French interface, sorting and filtering in every table.
- Follows the save: when the game writes a new autosave the tables refresh by themselves.

## Install

**Windows .exe**: download `ETS2CompanyManager.exe` and run it. It finds your latest save in
`Documents\Euro Truck Simulator 2\profiles\...\save\`; otherwise use *File → Open save* and pick `game.sii`.

**From source** (Python 3.10+):

```
pip install PySide6 cryptography pillow
python ets2_gui.py
```

`cryptography` is needed to read encrypted saves, `pillow` only for `tools/convert_assets.py`.
A command-line summary is also available: `python ets2_manager.py "<path to game.sii>"`.

## Editing the save safely

- Close the game first. While it is running it would overwrite the changes, and the program refuses to write.
- Before every change a copy of the save goes to the `ets2cm_backups` folder next to `game.sii`.
  *File → Restore save from backup* puts it back.
- The program changes only the fields it needs, then compares the result with the original and writes nothing
  if anything else would differ.
- Try it on a copy of a save slot first.

## Languages and themes

*Language / Language* and *Theme* are in the menu bar. Translations are plain JSON files in `locales/`.
To add a language, copy `en.json`, translate the values, set `"_name"` and drop it in the folder; it shows up in the menu.
See `locales/README.md`.

## Known limits

- The skill limit on the Skills tab is set by hand (maximum 36): the program has no XP-to-level table yet.
- ADR classes are mapped to bits in ascending order (1, 2, 3, 4, 6, 8); check one change in the game before relying on it.
- "Empty run" is guessed from a job with zero cargo units.
- Garage productivity is calculated from the last 7 days of garage profit and the garage price
  (€150,000 small, €300,000 large); it matched the values seen in the game.
- The upgrade cost is entered by hand: type the price the game shows.
- Driver names come from a table in `requirements/driver_names.json` (the save has none); you can rename any driver.

## Credits

See `NOTICE.md`. Not affiliated with SCS Software.
