"""Merge the HitSquad v1.07 fix into the final Korean game build.

The input build is copied. Its translated assets and security-question skip stay
intact; original English resources are never copied over translated ones.
"""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import re
import shutil
import struct
import sys
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from resources import (  # noqa: E402
    expand_compressed,
    expand_pairs,
    iff_chunks,
    pack_pak,
    stored,
    unpack_pak,
)
from translation_data import encode_text, load_latin_records

FIX_SOURCE = ROOT / "import/patches/dune2eng1.07fix/V107UPG/HITSQUAD"
FIX_INPUT_FILES = (
    "DUNE2.EXE", "ENGLISH.PAK", "SCENARIO.PAK", "SETSOUND.TXT",
    "SETUP.EXE", "SETUPENG.DIP", "VOC.PAK", "WAVESET.BAT", "WAVESET.DAT",
)
ORIGINAL_EXE = ROOT / "export/DUNE2.EXE"
GAME = Path("source/VIRGIN/DUNE2")
RESIDENT_PATCH_OFFSETS = (0x26251, *range(0x3DC8B, 0x3DC90), *range(0x3DED8, 0x3DEDD))
SECURITY_PATCH_OFFSETS = (*range(0x47D33, 0x47D39), 0x4ED31)
REGION_RE = re.compile(rb"^([ \t]*ENGTXT\d+[ \t]*=[ \t]*)([^\r\n]*)(\r\n|\r|\n)?$")
REGION_CORRECTIONS = {
    ("REGIONA.INI", "group6:line95"): "아트레이데스는 하코넨을 더 뒤로 밀어냈다.",
    ("REGIONH.INI", "group3:line55"): "오르도스에겐 승산이 전혀 없었다.",
}
# Apply these two established corrections only while their translation rows still
# contain the old draft text. A user's later CSV edit takes precedence.
LEGACY_REGION_TEXT_SHA256 = {
    ("REGIONA.INI", "group6:line95"): "fd931924e8ebb0a6fe2e74b0dd3cdf89b7fe1e6322ad753d3d450245f47d28e7",
    ("REGIONH.INI", "group3:line55"): "d880e080b0053716c155c280bd9cc893838272cefc220333649a6d828930b679",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def member(path: str) -> bytes:
    if path not in FIX_INPUT_FILES:
        raise ValueError(f"Unexpected HitSquad patch input: {path}")
    source = FIX_SOURCE / path
    if not source.is_file():
        raise FileNotFoundError(f"HitSquad 1.07 Fix input is missing: {source}")
    return source.read_bytes()


def font_codes(source: Path) -> dict[str, bytes]:
    with (source / "DUNEHAN.TBL.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["character"]: bytes.fromhex(row["token_hex"]) for row in rows}


def encoder_for_build(source: Path):
    codes = font_codes(source)
    symbols = sorted(cp for cp in load_latin_records(ROOT) if cp > 127)
    return partial(encode_text, codes=codes, latin_symbols=symbols)


def fix_executable(raw: bytes) -> tuple[bytes, dict]:
    original = ORIGINAL_EXE.read_bytes()
    fixed = member("DUNE2.EXE")
    assert len(original) == len(fixed) == 371474
    differences = {i for i, (before, after) in enumerate(zip(original, fixed)) if before != after}
    assert differences == set(RESIDENT_PATCH_OFFSETS) | set(SECURITY_PATCH_OFFSETS), differences
    out = bytearray(raw)
    for offset in RESIDENT_PATCH_OFFSETS:
        assert out[offset] == original[offset], (hex(offset), out[offset], original[offset])
        out[offset] = fixed[offset]
    # The current Korean build deliberately bypasses the security-question
    # scene. Its two overlay edits are therefore not merged back in.
    return bytes(out), {
        "applied_exe_offsets": [hex(i) for i in RESIDENT_PATCH_OFFSETS],
        "security_scene_offsets_not_applied": [hex(i) for i in SECURITY_PATCH_OFFSETS],
        "reason": "existing security-question skip and fade transition are preserved",
    }


def fix_mentat(raw: bytes, name: str, encode) -> tuple[bytes, dict]:
    chunks = iff_chunks(raw)
    payload = {kind: data for kind, _, data in chunks}
    desc_start = next(offset for kind, offset, _ in chunks if kind == b"DESC")
    names, descriptions = payload[b"NAME"], payload[b"DESC"]
    records = []
    at = 0
    while at < len(names):
        size = struct.unpack_from("<H", names, at)[0]
        record = names[at:at + size]
        assert len(record) == size and size >= 9
        records.append((record, int.from_bytes(record[2:5], "big") - desc_start))
        at += size
    assert at == len(names)
    assert len(records) == (49 if name == "MENTATH.ENG" else 47)
    offsets = []
    at = 0
    while at < len(descriptions):
        offsets.append(at)
        at = descriptions.index(0, at) + 1
    assert {offset for _, offset in records} == set(offsets)
    assert len(records) == len(offsets)

    removed = {37, 44} if name == "MENTATH.ENG" else set()
    changed = {}
    corrected_captions = []
    power_labels = {b'powerneeds', encode('전력'), encode('전력소비'), encode('소비전력')}
    for index, old, new in ((8, b"20", b"10"), (21, b"80", b"50")):
        offset = records[index][1]
        end = descriptions.index(0, offset)
        value = descriptions[offset:end]
        caption, marker, body = expand_compressed(value).partition(b"\x0c")
        lines = caption.splitlines(keepends=True)
        for line_index, line in enumerate(lines):
            label, colon, field = line.partition(b':')
            visible_label = re.sub(rb'^[A-Za-z0-9_.-]+\.wsa[*?]', b'', label, flags=re.I)
            field_label = re.sub(rb'[ \t]+', b'', visible_label).lower()
            if not colon or field_label not in power_labels:
                continue
            # Only the value immediately after the power label is eligible.
            # Costs, titles, body text and already-corrected values stay intact.
            match = re.match(rb'([ \t]*)'+old+rb'(?![0-9.])', field)
            if match:
                lines[line_index] = label+colon+match[1]+new+field[match.end():]
        corrected = b''.join(lines)
        if marker and corrected != caption:
            changed[offset] = stored(corrected+marker+body)
            corrected_captions.append(index)

    removed_offsets = {records[index][1] for index in removed}
    new_desc = bytearray()
    relocated = {}
    max_stored = max_expanded = 0
    for offset in offsets:
        if offset in removed_offsets:
            continue
        end = descriptions.index(0, offset)
        value = changed.get(offset, descriptions[offset:end])
        relocated[offset] = len(new_desc)
        new_desc += value + b"\0"
        max_stored = max(max_stored, len(value) + 1)
        max_expanded = max(max_expanded, len(expand_pairs(value)) + 1,
                           len(expand_compressed(value)) + 1)
    kept = [(record, offset) for index, (record, offset) in enumerate(records) if index not in removed]
    new_name_size = sum(len(record) for record, _ in kept)
    sizes = {b"NAME": new_name_size, b"DESC": len(new_desc), b"INFO": 12}
    position = 12
    new_desc_start = None
    for kind, _, _ in chunks:
        if kind == b"DESC":
            new_desc_start = position + 8
        position += 8 + sizes[kind] + (sizes[kind] & 1)
    assert new_desc_start is not None
    new_names = bytearray()
    for record, offset in kept:
        absolute = new_desc_start + relocated[offset]
        assert absolute < (1 << 24)
        new_names += record[:2] + absolute.to_bytes(3, "big") + record[5:]
    assert len(new_names) == new_name_size
    updated = {
        b"NAME": bytes(new_names),
        b"DESC": bytes(new_desc),
        b"INFO": struct.pack(">3I", len(kept), max_expanded, max_stored),
    }
    body = bytearray(b"MENT")
    for kind, _, _ in chunks:
        value = updated[kind]
        body += kind + len(value).to_bytes(4, "big") + value + bytes(len(value) & 1)
    output = b"FORM" + len(body).to_bytes(4, "big") + body
    assert len(iff_chunks(output)) == len(chunks)
    return output, {"records_before": len(records), "records_after": len(kept),
                    "power_watts": {"barracks": 10, "starport": 50},
                    "removed_hit_squad_only_entries": sorted(removed),
                    "corrected_caption_records": corrected_captions}


def region_rows(source: Path, source_rows: list[dict] | None = None) -> dict[str, list[dict]]:
    if source_rows is None:
        # Compatibility for archived standalone inputs. The normal final
        # builder passes the already loaded rows and creates no CSV snapshot.
        path = source / "translation-snapshot/source_strings_complete_ko_draft.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            source_rows = list(csv.DictReader(handle))
    return {name: [row for row in source_rows if row["file"] == name]
            for name in ("REGIONA.INI", "REGIONH.INI", "REGIONO.INI")}


def fix_region(current: bytes, fixed: bytes, name: str, rows: list[dict],
               encode) -> tuple[bytes, dict]:
    current_lines = current.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)
    old = [REGION_RE.match(line) for line in current_lines]
    old = [match for match in old if match]
    assert len(old) == len(rows)
    patched = []
    corrected_lines = []
    for line in fixed_lines:
        match = REGION_RE.match(line)
        if not match:
            patched.append(line)
            continue
        index = len([part for part in patched if REGION_RE.match(part)])
        row = rows[index]
        original_translation = encode(row["translation_ko"] or row["source_en"])
        assert old[index][2].strip() == original_translation.strip(), (name, row["index"])
        key = (name, row["index"])
        old_hash = LEGACY_REGION_TEXT_SHA256.get(key)
        correction = (REGION_CORRECTIONS.get(key) if old_hash and
                      sha(row["translation_ko"].encode("utf-8")) == old_hash else None)
        value = encode(correction) if correction else original_translation
        if correction:
            corrected_lines.append(row["index"])
        patched.append(match[1] + value + (match[3] or b""))
    result = b"".join(patched)
    assert len([1 for line in result.splitlines() if REGION_RE.match(line)]) == len(rows)
    return result, {"translated_lines": len(rows), "corrected_lines": corrected_lines}


def apply_build(source: Path, output: Path,
                translation_rows: list[dict] | None = None) -> dict:
    if output.exists():
        raise FileExistsError("Output already exists: " + str(output))
    assert source.is_dir() and FIX_SOURCE.is_dir()
    missing = [name for name in FIX_INPUT_FILES if not (FIX_SOURCE / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing HitSquad 1.07 Fix files: " + ", ".join(missing))
    source_game = source / GAME
    source_sha = sha((source_game / "DUNE2.EXE").read_bytes())
    encode = encoder_for_build(source)
    region = region_rows(source, translation_rows)
    _, translated_english = unpack_pak((source_game / "ENGLISH.PAK").read_bytes())
    english_names, english = unpack_pak((source_game / "ENGLISH.PAK").read_bytes())
    scenario_names, scenario = unpack_pak((source_game / "SCENARIO.PAK").read_bytes())
    fixed_scenario_names, fixed_scenario = unpack_pak(member("SCENARIO.PAK"))
    assert scenario_names == fixed_scenario_names
    fixed_english_names, _ = unpack_pak(member("ENGLISH.PAK"))
    assert set(english_names) == set(fixed_english_names)
    report = {"source_build": str(source.relative_to(ROOT)),
              "source_exe_sha256": source_sha,
              "fix_source_dir": str(FIX_SOURCE.relative_to(ROOT)).replace("\\", "/"),
              "fix_input_sha256": {name: sha(member(name)) for name in FIX_INPUT_FILES},
              "mentat": {}, "region": {}}
    exe, report["exe"] = fix_executable((source_game / "DUNE2.EXE").read_bytes())
    for name in ("MENTATA.ENG", "MENTATH.ENG", "MENTATO.ENG"):
        english[name], report["mentat"][name] = fix_mentat(english[name], name, encode)
    for name in scenario_names:
        if name.startswith("REGION"):
            scenario[name], report["region"][name] = fix_region(
                scenario[name], fixed_scenario[name], name, region[name], encode)
        else:
            scenario[name] = fixed_scenario[name]
    # Other patched English strings are spelling fixes already superseded by
    # the current Korean translations; preserve every translated text member.
    unchanged_english = [name for name in english_names if name not in report["mentat"]]
    assert all(english[name] == translated_english[name] for name in unchanged_english)

    # These are build-time intermediates, not runtime assets. Keep them in the
    # staging tree for assembly and the HitSquad text corrections, but do not
    # copy them into the runnable final build. Game PAKs already contain CG.
    shutil.copytree(source, output, ignore=shutil.ignore_patterns(
        "cg-assets", "assembly", "translation-snapshot"))
    game = output / GAME
    (game / "DUNE2.EXE").write_bytes(exe)
    (game / "ENGLISH.PAK").write_bytes(pack_pak(english_names, english))
    (game / "SCENARIO.PAK").write_bytes(pack_pak(scenario_names, scenario))
    for name in ("VOC.PAK", "SETUP.EXE", "SETUPENG.DIP", "WAVESET.BAT",
                 "WAVESET.DAT", "SETSOUND.TXT"):
        (game / name).write_bytes(member(name))
    _, voc = unpack_pak((game / "VOC.PAK").read_bytes())
    for folder, files in (("ENGLISH.files", english), ("SCENARIO.files", scenario),
                          ("VOC.files", voc)):
        directory = game / folder
        if directory.is_dir():
            for name, data in files.items():
                path = directory / name
                if path.is_file() and path.read_bytes() != data:
                    path.write_bytes(data)
    report["output_build"] = str(output.relative_to(ROOT))
    report["files"] = {name: {"sha256": sha((game / name).read_bytes()),
                              "size": (game / name).stat().st_size}
                       for name in ("DUNE2.EXE", "ENGLISH.PAK", "SCENARIO.PAK",
                                    "VOC.PAK", "SETUP.EXE", "SETUPENG.DIP")}
    report["not_applied"] = ["SFX-FIX: Windows direct-run speech-lag files",
                             "GUS-FIX: Gravis Ultrasound configuration"]
    report["game_execution"] = "not run; static validation only"
    report["build_integration"] = "original-CD final game build used for BIN/CUE and Xdelta output"
    (output / "hitsquad107-fix-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = apply_build(args.source, args.output)
    print(json.dumps({"output": str(args.output), "exe_sha256": report["files"]["DUNE2.EXE"]["sha256"],
                      "mentat": report["mentat"], "region": report["region"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
