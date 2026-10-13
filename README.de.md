# ETS2 Company Manager

[English](README.md) · [Русский](README.ru.md) · **Deutsch**

Ein Desktop-Programm, mit dem du deine Firma in Euro Truck Simulator 2 im Blick behältst. Es liest den
Spielstand und zeigt Fahrer, Zugmaschinen, Anhänger, Garagen und Aufträge an einer Stelle. Im Spielstand kann es
sicher reparieren, betanken, Kennzeichen ändern, Garagen erweitern, Fahrer verbessern und leere Garagen mit neuen Fahrern, Zugmaschinen und Anhängern auffüllen.

## Funktionen

- **Fahrer**: Stadt, Heimatgarage, XP, Fähigkeiten, Zugmaschine, Anhänger, Status, aktuelle Route, Gewinn und €/Tag.
  Die Status nutzen die Farben des Spiels: im Auftrag, Leerfahrt, geparkt, untätig, defekt, ohne Zugmaschine.
- **Zugmaschinen und Anhänger**: Kilometerstand, Kraftstoff, Verschleiß, Status.
- **Garagen**: Typ, Plätze, Fahrer, Anhänger, Einkommen pro Tag und Produktivität.
- **Aufträge**: wer was wohin fährt, Entfernung, Fahrtzeit, Fährkosten.
- **Reiter „Fähigkeiten“**: Für jeden Fahrer wählst du wie im Spiel, was verbessert wird (Ferntransport, wertvolle
  und zerbrechliche Fracht, Just-in-time, ökologisches Fahren und die sechs ADR-Klassen).
- **Spielstand ändern**: Reparieren (alle oder Auswahl), Betanken, Kennzeichen ändern, kleine Garage auf groß erweitern, Fähigkeiten erhöhen,
  Firmenkontostand und Spielerstufe ändern (Schraubenschlüssel oder Doppelklick auf die Kacheln *Geld* und *Stufe*).
- **Garagen auffüllen** (Reiter *Garagen*): Fahrer aus der Bewerberliste des Spiels auf freie Plätze einstellen
  (beste, zufällige oder günstigste), ihnen freie eigene Zugmaschinen oder Kopien deiner Zugmaschinen geben und Anhänger hinzufügen. Einstellen ohne Zugmaschine geht auch.
- **Hinweiszeile** über den Tabs: Fahrer mit Problem, verschlissene Zugmaschinen, Fahrer ohne Zugmaschine, Zugmaschinen ohne Fahrer, freie Garagenplätze.
  Ein Klick zeigt nur diese Zeilen.
- Beobachtet den Spielstand: Schreibt das Spiel einen neuen Autosave, aktualisieren sich die Tabellen von selbst.

## Installation

**Windows-.exe**: `ETS2CompanyManager.exe` herunterladen und starten. Sie findet den neuesten Spielstand unter
`Documents\Euro Truck Simulator 2\profiles\...\save\`; sonst *Datei → Spielstand öffnen* wählen und `game.sii` angeben.

Spielstände von American Truck Simulator lassen sich ebenfalls öffnen, aber Lkw-Namen, Logos und Fahrernamen sind vorerst für ETS2 gemacht. Unterstützung für ATS-Lkw und -Fahrer kommt bald.

**Aus dem Quellcode** (Python 3.10+):

```
pip install PySide6 cryptography 
python ets2_gui.py
```

`cryptography` wird für verschlüsselte Spielstände gebraucht.
Eine Konsolenübersicht gibt es auch: `python ets2_manager.py "<Pfad zu game.sii>"`.

## Spielstand sicher ändern

- Standardmäßig landet eine Änderung in einem neuen Spielstand-Slot *<Name> Edited*: Der ursprüngliche Spielstand bleibt
  unverändert, und das Spiel darf offen bleiben, lade einfach den neuen Slot. Weitere Änderungen an diesem Slot erfolgen direkt darin.
  Um den gewählten Spielstand selbst zu ändern, schalte *Einstellungen → Änderungen in Kopie des Spielstands speichern* aus; dann muss das Spiel geschlossen sein.
- Vor jeder Änderung landet eine Kopie im Ordner `ets2cm_backups` neben `game.sii`.
  *Datei → Letzte Änderung rückgängig* (Strg+Z) oder *Datei → Spielstand aus Sicherung wiederherstellen* spielt sie zurück. Die letzten 20 Kopien bleiben erhalten.

## Sprachen und Designs

Die Sprache findest du unter *Einstellungen → Sprache* (beim ersten Start die Systemsprache, sonst Englisch), *Design* in der Menüleiste. Die Übersetzungen sind einfache JSON-Dateien in `locales/`.
Für eine neue Sprache `en.json` kopieren, die Werte übersetzen, `"_name"` setzen und die Datei in den Ordner legen; sie erscheint im Menü.
Details in `locales/README.md`.

## Hinweise

Siehe `NOTICE.md`. Nicht mit SCS Software verbunden.
