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
  change the company balance and player level (the wrench or a double-click on the *Money* and *Level* tiles).
- **Fill garages** (*Garages* tab): hire drivers into empty garage slots from the game's own pool of applicants
  (best, random or cheapest), give them your spare trucks or copies of your trucks, and add trailers. Drivers can also be hired without trucks.
- **Warnings line** above the tabs: drivers with a problem, worn trucks, drivers without a truck, trucks without a driver, empty garage slots.
  Click an item to see just those rows.
- Follows the save: when the game writes a new autosave the tables refresh by themselves.

## Install

**Windows .exe**: download `ETS2CompanyManager.exe` and run it. It finds your latest save in
`Documents\Euro Truck Simulator 2\profiles\...\save\`; otherwise use *File → Open save* and pick `game.sii`.

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
- Money and XP are also updated in `info.sii`, so the game's save list shows the new values.
- The program changes only the fields it needs, then compares the result with the original and writes nothing
  if anything else would differ.

## Languages and themes

The language is under *Settings → Language* (on first start the system language is used, otherwise English); *Theme* is in the menu bar. Translations are plain JSON files in `locales/`.
To add a language, copy `en.json`, translate the values, set `"_name"` and drop it in the folder; it shows up in the menu.
See `locales/README.md`.

## Known limits

- Levels are calculated from XP with the in-game table (levels 0–50, then +6,800 XP per level); hired drivers need twice the player's XP per level. Checked against the game on one save (player 368,497 XP = level 69; two drivers matched including the XP bar). On the Skills tab a driver gets one skill point per level (maximum 36); change the level there to get more points.
- Hired drivers come from the applicants the game already has in the save; new trucks and trailers are copies of ones you own, reset to new. Checked in the game on one save.
- ADR classes are mapped to bits in ascending order (1, 2, 3, 4, 6, 8); check one change in the game before relying on it.
- "Empty run" is guessed from a job with zero cargo units.
- Garage productivity is calculated from the last 7 days of garage profit and the garage price
  (€150,000 small, €300,000 large); it matched the values seen in the game.
- The upgrade cost is entered by hand: type the price the game shows.
- American Truck Simulator saves open too, but truck names, logos and driver names are made for ETS2.
- Driver names come from a table in `requirements/driver_names.json` (the save has none); you can rename any driver.

## Credits

See `NOTICE.md`. Not affiliated with SCS Software.
