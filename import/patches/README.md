# Game patch inputs

`import/cd-runtime-base.json` contains checked byte edits that reproduce the confirmed initial localization hooks from `export/DUNE2.EXE`. It records the original EXE hash, resident and overlay edits, and the code adjustments applied after assembling `import/asm/font/dalmoori-base.asm`. Original and resulting bytes and section hashes are verified by `tools/cd_source.py`.

Normal builds do not read a previous game build or verified archive. Font bitmaps come from the current HEX input, and cheat modules are assembled from the current ASM source.

`dune2eng1.07fix/V107UPG/HITSQUAD/` holds the separate HitSquad 1.07 Fix input. The final build applies its supported fixes after rebuilding the Korean assets.

The complete `import/patches/` contents are versioned build inputs, including patch EXEs and PAKs. The original CD image and extracted original game files remain outside the committed inputs. The Fix package's notices are preserved in its text files.
