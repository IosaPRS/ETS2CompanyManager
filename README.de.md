# ETS2 Company Manager

[English](README.md) · [Русский](README.ru.md) · **Deutsch**

Ein Desktop-Programm, mit dem du deine Firma in Euro Truck Simulator 2 im Blick behältst. Es liest den
Spielstand und zeigt Fahrer, Zugmaschinen, Anhänger, Garagen und Aufträge an einer Stelle. Im Spielstand kann es
sicher reparieren, betanken, Kennzeichen ändern, Garagen erweitern und Fahrerfähigkeiten verbessern.
- **Hinweiszeile** über den Tabs: Fahrer mit Problem, verschlissene Lkw, Fahrer ohne Lkw, Lkw ohne Fahrer, freie Garagenplätze. Ein Klick zeigt nur diese Zeilen.

## Funktionen

- **Fahrer**: Stadt, Heimatgarage, XP, Fähigkeiten, Zugmaschine, Anhänger, Status, aktuelle Route, Gewinn und €/Tag.
  Die Status nutzen die Farben des Spiels: im Auftrag, Leerfahrt, geparkt, untätig, defekt, ohne Zugmaschine.
- **Zugmaschinen und Anhänger**: Kilometerstand, Kraftstoff, Verschleiß je Bauteil, dauerhafter Verschleiß, Status.
- **Garagen**: Typ, Plätze, Fahrer, Anhänger, Einkommen pro Tag und Produktivität.
- **Aufträge**: wer was wohin fährt, Entfernung, Fahrtzeit, Fährkosten.
- **Reiter „Fähigkeiten“**: Für jeden Fahrer wählst du wie im Spiel, was verbessert wird (Ferntransport, wertvolle
  und zerbrechliche Fracht, Just-in-time, ökologisches Fahren und die sechs ADR-Klassen).
- **Spielstand ändern**: Reparieren (alle oder Auswahl), Betanken, Kennzeichen ändern, kleine Garage auf groß erweitern, Fähigkeiten erhöhen,
  Firmenkontostand und Spielerstufe ändern (Schraubenschlüssel oder Doppelklick auf die Kacheln *Geld* und *Stufe*).
- **Profile**: beliebiges Profil und beliebigen Spielstand-Slot wählen (*Datei → Profil und Spielstand wählen*), auch Steam-Cloud-Profile.
- Update-Prüfung beim Start (in *Einstellungen* abschaltbar), Oberflächenskalierung, das Fenster öffnet sich dort, wo du es geschlossen hast.
- Dunkles und helles Design, Oberfläche auf Englisch, Russisch, Deutsch und Französisch, Sortieren und Filtern in jeder Tabelle.
- Beobachtet den Spielstand: Schreibt das Spiel einen neuen Autosave, aktualisieren sich die Tabellen von selbst.

## Installation

**Windows-.exe**: `ETS2CompanyManager.exe` herunterladen und starten. Sie findet den neuesten Spielstand unter
`Documents\Euro Truck Simulator 2\profiles\...\save\`; sonst *Datei → Spielstand öffnen* wählen und `game.sii` angeben.

**Aus dem Quellcode** (Python 3.10+):

```
pip install PySide6 cryptography 
python ets2_gui.py
```

`cryptography` wird für verschlüsselte Spielstände gebraucht.
Eine Konsolenübersicht gibt es auch: `python ets2_manager.py "<Pfad zu game.sii>"`.

## Spielstand sicher ändern

- Schließe zuerst das Spiel: Solange es läuft, überschreibt es die Änderungen, und das Programm verweigert das Schreiben.
- Vor jeder Änderung landet eine Kopie im Ordner `ets2cm_backups` neben `game.sii`.
  *Datei → Letzte Änderung rückgängig* (Strg+Z) oder *Datei → Spielstand aus Sicherung wiederherstellen* spielt sie zurück. Die letzten 20 Kopien bleiben erhalten.
- Geld und EP werden auch in `info.sii` aktualisiert, damit die Spielstandliste des Spiels die neuen Werte zeigt.
- Das Programm ändert nur die nötigen Felder, vergleicht das Ergebnis mit dem Original und schreibt nichts,
  wenn sich noch etwas anderes unterscheidet.
- Probiere es zuerst an einer Kopie des Spielstand-Slots aus.

## Sprachen und Designs

*Sprache / Language* und *Design* findest du in der Menüleiste. Die Übersetzungen sind einfache JSON-Dateien in `locales/`.
Für eine neue Sprache `en.json` kopieren, die Werte übersetzen, `"_name"` setzen und die Datei in den Ordner legen; sie erscheint im Menü.
Details in `locales/README.md`.

## Bekannte Grenzen

- Stufen werden aus der Erfahrung nach der Tabelle des Spiels berechnet (Stufen 0–50, danach +6.800 XP pro Stufe); angestellte Fahrer brauchen pro Stufe doppelt so viel Erfahrung wie der Spieler. An einem Spielstand mit dem Spiel abgeglichen (Spieler 368.497 XP = Stufe 69; bei zwei Fahrern stimmte auch der Erfahrungsbalken). Das Fähigkeitslimit im Reiter „Fähigkeiten“ folgt der Stufe des Fahrers (maximal 36) und lässt sich von Hand ändern.
- ADR-Klassen sind den Bits aufsteigend zugeordnet (1, 2, 3, 4, 6, 8); prüfe eine Änderung im Spiel, bevor du dich darauf verlässt.
- „Leerfahrt“ wird aus einem Auftrag mit null Frachteinheiten geschätzt.
- Die Garagenproduktivität wird aus dem Gewinn der letzten 7 Tage und dem Garagenpreis berechnet
  (150.000 € klein, 300.000 € groß); sie stimmte mit den Werten im Spiel überein.
- Die Erweiterungskosten gibst du selbst ein: den Preis, den das Spiel anzeigt.
- Spielstände von American Truck Simulator lassen sich ebenfalls öffnen, aber Lkw-Namen, Logos und Fahrernamen sind für ETS2 gemacht.
- Fahrernamen stammen aus der Tabelle `requirements/driver_names.json` (der Spielstand enthält keine); jeden Fahrer kannst du umbenennen.

## Hinweise

Siehe `NOTICE.md`. Nicht mit SCS Software verbunden.
