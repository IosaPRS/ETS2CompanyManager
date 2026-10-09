# Translations / Переводы / Übersetzungen / Traductions

Each file `<code>.json` is one language (`en.json`, `de.json`, `fr.json`, ...). It appears in the menu **Язык / Language** by itself.

Format: a flat JSON object, `"Russian source phrase": "translation"`.
The special key `"_name"` is the language name shown in the menu.

```json
{
 "_name": "Español",
 "Водители": "Conductores",
 "Починить все": "Reparar todo"
}
```

Rules:
- Keep placeholders such as `{n}`, `{plate}`, `{wear:.1f}` exactly as in the key (same names, you may move them around).
- Keep HTML tags such as `<b>…</b>` and `&nbsp;` and line breaks `\n`.
- A missing or empty entry falls back to the Russian text; a broken placeholder shows the phrase without substitution.
- Short table headers (`Дальн.`, `Тяжёл.`, `Трансм.`) should stay short, columns are narrow.

Tip for AI-assisted translation: give the model `en.json` and ask it to translate the **keys** into the new language,
preserving placeholders and tags, and return a JSON object with the same keys.
