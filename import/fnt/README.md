# Game font files

| File | Purpose |
|---|---|
| `glyph_registry.json` | Registered Hangul syllables |
| `DUNEHAN.FNT` | Generated Dalmoori game font |
| `DUNEUNI.FNT` | Generated Unifont cinematic font |
| `DUNEUNI.MAP` | Cinematic glyph lookup table |

Run `python tools/build_game.py` from the project root to generate the font files from the translation CSVs and `font/` HEX sources. New Hangul syllables are registered after a successful build.
