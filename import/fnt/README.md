# Generated game fonts

The final build generates `DUNEHAN.FNT`, `DUNEUNI.FNT` and `DUNEUNI.MAP` here, then applies those exact bytes to the game directory.

`glyph_registry.json` is the shared registered extra-syllable list. The standalone builder combines it with newly used Hangul from the current CSV, sorts the result, and reassigns two-byte tokens. It does not read an editor session to determine the game glyph set.
