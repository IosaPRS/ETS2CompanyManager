# ETS2 Company Manager

**English** · [Русский](README.ru.md) · [Deutsch](README.de.md)

A desktop tool for managing your in-game company in Euro Truck Simulator 2. It reads your save file and shows
every driver, truck, trailer, garage and job in one place, and can safely repair, refuel, rename plates,
upgrade garages, level up drivers and fill empty garages with new drivers, trucks and trailers.

## Features

- **Drivers**: city, home garage, XP, skills, truck, trailer, status, current route, profit and €/day.
  Statuses use the in-game colours: on a job, empty run, parked, idle, broken, no truck.
- **Trucks and trailers**: odometer, fuel, wear, status.
- **Garages**: type, slots, drivers, trailers, income per day and productivity.
- **Jobs**: who is hauling what, from where to where, distance, time on the road, ferry cost.
- **Skills tab**: pick what to level up for every driver, like in the game (long distance, high value cargo,
  fragile cargo, just-in-time, ecodriving and the six ADR classes).
- **Save editing**: repair (all or selected), refuel, change plates, upgrade a small garage to a large one, raise skills,
  change the company balance and player level.
- **Fill garages** (*Garages* tab): hire drivers into empty garage slots from the game's own pool of applicants
  (best, random or cheapest), give them your spare trucks or copies of your trucks, and add trailers. Drivers can also be hired without trucks.
- **Warnings line** above the tabs: drivers with a problem, worn trucks, drivers without a truck, trucks without a driver, empty garage slots.
  Click an item to see just those rows.
- Follows the save: when the game writes a new autosave the tables refresh by themselves.

## Install

**Windows .exe**: download `ETS2CompanyManager.exe` and run it. It finds your latest save in
`Documents\Euro Truck Simulator 2\profiles\...\save\`; otherwise use *File → Open save* and pick `game.sii`.

American Truck Simulator saves open too, but truck names, logos and driver names are made for ETS2 for now. Support for ATS trucks and drivers is coming soon.

**From source** (Python 3.10+):

```
pip install PySide6 cryptography
python ets2_gui.py
```

`cryptography` is needed to read encrypted saves.
A command-line summary is also available: `python ets2_manager.py "<path to game.sii>"`.

## Editing the save safely

- By default a change goes into a new save slot named *<save name> Edited*; the original save stays as it was, and the game
  can stay open: just load the new slot. Further changes to that slot are made in place.
  To edit the chosen save itself, turn off *Settings → Save edits to a copy of the save*; then the game must be closed.
- Before every change a copy of the save goes to the `ets2cm_backups` folder next to `game.sii`.
  *File → Undo last edit* (Ctrl+Z) or *File → Restore save from backup* puts it back. The last 20 copies are kept.

## Languages and themes

The language is under *Settings → Language* (on first start the system language is used, otherwise English); *Theme* is in the menu bar. Translations are plain JSON files in `locales/`.
To add a language, copy `en.json`, translate the values, set `"_name"` and drop it in the folder; it shows up in the menu.
See `locales/README.md`.

## Credits

See `NOTICE.md`. Not affiliated with SCS Software.
