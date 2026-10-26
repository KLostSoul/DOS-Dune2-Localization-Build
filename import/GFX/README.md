# GFX import images

`images/` contains the PNG files that the CG encoder reads when building the game. Edit these files to change CG artwork.

The original CD PAK sources (`DUNE.PAK` and `ENGLISH.PAK`) are in `export/PAK/`. Decoded reference PNGs, raw CG resources, and `manifest.json` are kept under `export/GFX/`. The manifest maps each editable frame to its original frame. The build verifies frame count, dimensions, palette indices, transparency, and encoded pixel round trips before merging only changed PAK members.

Use the editor's **최종 빌드 만들기** action to include these images in a translated build. To encode only the edited CG PAKs, run `py -3 tools/edit_cg.py encode` from the project root.
