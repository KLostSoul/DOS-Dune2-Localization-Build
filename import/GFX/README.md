# GFX input images

Edit the PNGs in `images/` to change the game's CG artwork. Keep each image's dimensions, frame number, palette indices, and transparency.

Run from the project root:

```powershell
python tools/build_game.py
```

The build extracts original resources and reference PNGs to `export/GFX/`, encodes the PNGs from `import/GFX/images/`, and merges the edited resources into the game PAKs.

Resource selection and encoding options are documented in [GRAPHICS.md](../../doc/GRAPHICS.md).
