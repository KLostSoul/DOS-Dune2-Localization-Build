# Font data and licenses

This folder contains two upstream font sources and glyph data derived from them. The license files beside this notice are the upstream texts.

| Project data | Upstream source | License |
|---|---|---|
| `composed-hangul.hex` — Dalmoori 8×8 Hangul plus Latin, digits, and symbols | [RanolP/dalmoori-font](https://github.com/RanolP/dalmoori-font) | Apache License 2.0; see [`LICENSE-Dalmoori-Apache-2.0.txt`](LICENSE-Dalmoori-Apache-2.0.txt) |
| `unifont-16.0.04.hex` — GNU Unifont glyph source | [GNU Unifont](https://unifoundry.com/unifont/index.html) | SIL Open Font License 1.1 or GPL 2-or-later with the GNU Font Embedding Exception; see [`OFL-1.1.txt`](OFL-1.1.txt) and [`LICENSE-Unifont.txt`](LICENSE-Unifont.txt) |

`composed-hangul.hex` is the project's converted 8×8 glyph table based on Dalmoori. Builds generate `DUNEHAN.FNT` from its used Hangul and non-Hangul glyphs. `DUNEUNI.FNT` and its map are generated from the used glyphs in `unifont-16.0.04.hex`.

Dalmoori's upstream license notice identifies Copyright 2020 RanolP and contributors. The Unifont license file includes the upstream font license statement and GNU Font Embedding Exception. These notices cover the corresponding font data and derived glyphs, not the project's code or other game assets.
