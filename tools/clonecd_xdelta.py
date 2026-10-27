"""Build/apply a CloneCD IMG xdelta without changing the owner's source CD.

The source is the hash-verified original, single-track Mode 1/2352 CD image.
Unmodified sectors stay byte-for-byte intact. Enlarged ISO files are placed after
the original lead-out and their ISO9660 directory records are updated. Every
changed/new raw sector gets a valid Mode 1 EDC and P/Q ECC.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import subprocess
from pathlib import Path
from cd_source import find_image, IMAGE_SHA256 as ORIGINAL_SHA256

SECTOR = 2352
PAYLOAD = 2048
ROOT = Path(__file__).resolve().parent.parent
GAME_SUBDIR = Path("source/VIRGIN/DUNE2")
OUTPUT = ROOT / "output"
PRODUCT = "Dune2-Battle-for-Arrakis-Korean-v1.01"
BIN = OUTPUT / f"{PRODUCT}.bin"
CUE = OUTPUT / f"{PRODUCT}.cue"
PATCH = OUTPUT / f"{PRODUCT}.bin.xdelta"
MANIFEST = OUTPUT / f"{PRODUCT}.json"
NEW_FILES = (
    "DUNEHAN.FNT", "DUNEHAN.TBL", "DUNEUNI.FNT", "DUNEUNI.MAP",
    "SETSOUND.TXT", "WAVESET.BAT", "WAVESET.DAT",
)
SKIP_EXISTING = {"DUNE.CFG"}  # Local sound/setup choices belong to the owner.


def sha256(data: bytes | bytearray | Path) -> str:
    h = hashlib.sha256()
    if isinstance(data, (bytes, bytearray)):
        h.update(data)
    else:
        with data.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
    return h.hexdigest()


def bcd(value: int) -> int:
    assert 0 <= value < 100
    return (value // 10) * 16 + value % 10


def msf(frame: int) -> tuple[int, int, int]:
    return frame // 4500, (frame // 75) % 60, frame % 75


def subq_crc(data: bytes) -> int:
    crc = 0
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xFFFF
    return crc ^ 0xFFFF


def subchannel(sector_number: int) -> bytes:
    rel = bytes(map(bcd, msf(sector_number)))
    absolute = bytes(map(bcd, msf(sector_number + 150)))
    q = bytes((0x41, 0x01, 0x01)) + rel + b"\x00" + absolute
    q += subq_crc(q).to_bytes(2, "big")
    return bytes(12) + q + bytes(72)


ECC_F = [((i << 1) ^ (0x11D if i & 0x80 else 0)) & 0xFF for i in range(256)]
ECC_B = [0] * 256
for _i in range(256):
    ECC_B[ECC_F[_i] ^ _i] = _i

EDC = []
for _i in range(256):
    _value = _i
    for _ in range(8):
        _value = (_value >> 1) ^ (0xD8018001 if _value & 1 else 0)
    EDC.append(_value)


def ecc(source: bytes, major_count: int, minor_count: int,
        major_mult: int, minor_inc: int) -> bytes:
    size = major_count * minor_count
    result = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            value = source[index]
            index = (index + minor_inc) % size
            a ^= value
            b ^= value
            a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        result[major] = a
        result[major + major_count] = a ^ b
    return bytes(result)


def fix_mode1(sector: bytearray) -> None:
    checksum = 0
    for value in sector[:2064]:
        checksum = (checksum >> 8) ^ EDC[(checksum ^ value) & 0xFF]
    sector[2064:2068] = struct.pack("<I", checksum)
    sector[2068:2076] = bytes(8)
    sector[2076:2248] = ecc(sector[12:2076], 86, 24, 2, 86)
    sector[2248:2352] = ecc(sector[12:2248], 52, 43, 86, 88)


def make_sector(number: int, payload: bytes) -> bytes:
    sector = bytearray(SECTOR)
    sector[:12] = b"\x00" + bytes((0xFF,)) * 10 + b"\x00"
    sector[12:15] = bytes(map(bcd, msf(number + 150)))
    sector[15] = 1
    sector[16:16 + len(payload)] = payload
    fix_mode1(sector)
    return bytes(sector)


def get_payload(image: bytearray, number: int) -> bytes:
    offset = number * SECTOR + 16
    return bytes(image[offset:offset + PAYLOAD])


def put_payload(image: bytearray, number: int, payload: bytes) -> None:
    assert len(payload) == PAYLOAD
    offset = number * SECTOR
    sector = bytearray(image[offset:offset + SECTOR])
    sector[16:2064] = payload
    fix_mode1(sector)
    image[offset:offset + SECTOR] = sector


def number_pair(record: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", record, offset, value)
    struct.pack_into(">I", record, offset + 4, value)


def iso_file_records(directory: bytes) -> dict[str, tuple[int, int, int, int]]:
    records = {}
    at = 0
    while at < len(directory) and directory[at]:
        length = directory[at]
        record = directory[at:at + length]
        name = record[33:33 + record[32]].decode("ascii")
        if name not in ("\x00", "\x01"):
            records[name.split(";")[0]] = (
                at, length, struct.unpack_from("<I", record, 2)[0],
                struct.unpack_from("<I", record, 10)[0],
            )
        at += length
    return records


def new_record(name: str, extent: int, size: int, template: bytes) -> bytes:
    identifier = (name + ";1").encode("ascii")
    length = 33 + len(identifier) + (len(identifier) % 2 == 0)
    record = bytearray(length)
    record[:min(33, len(template))] = template[:33]
    record[0] = length
    number_pair(record, 2, extent)
    number_pair(record, 10, size)
    record[25] = 0
    record[32] = len(identifier)
    record[33:33 + len(identifier)] = identifier
    return bytes(record)


def build_image(original: Path, game_dir: Path, output: Path) -> dict:
    assert sha256(original) == ORIGINAL_SHA256, "Unexpected original CD IMG hash"
    image = bytearray(original.read_bytes())
    assert len(image) % SECTOR == 0
    original_sectors = len(image) // SECTOR
    pvd = bytearray(get_payload(image, 16))
    assert pvd[:7] == b"\x01CD001\x01"
    assert struct.unpack_from("<I", pvd, 80)[0] == original_sectors
    directory = bytearray(get_payload(image, 22))
    records = iso_file_records(directory)
    assert len(records) == 26
    cursor = 0
    while directory[cursor]:
        cursor += directory[cursor]
    changed = []
    for name, (position, record_length, extent, old_size) in records.items():
        if name in SKIP_EXISTING:
            continue
        source = game_dir / name
        assert source.is_file(), f"Missing original CD file in build: {source}"
        old_data = b"".join(get_payload(image, n) for n in
                            range(extent, extent + math.ceil(old_size / PAYLOAD)))[:old_size]
        data = source.read_bytes()
        if old_data == data:
            continue
        capacity = math.ceil(old_size / PAYLOAD) * PAYLOAD
        if len(data) > capacity:
            new_extent = len(image) // SECTOR
            for index in range(0, len(data), PAYLOAD):
                image.extend(make_sector(len(image) // SECTOR, data[index:index + PAYLOAD]))
        else:
            new_extent = extent
            for index in range(0, len(data), PAYLOAD):
                old_payload = bytearray(get_payload(image, extent + index // PAYLOAD))
                part = data[index:index + PAYLOAD]
                old_payload[:len(part)] = part
                put_payload(image, extent + index // PAYLOAD, old_payload)
        number_pair(directory, position + 2, new_extent)
        number_pair(directory, position + 10, len(data))
        changed.append({"name": name, "old_size": old_size,
                        "new_size": len(data), "extent": new_extent,
                        "sha256": sha256(data)})

    for name in NEW_FILES:
        assert name not in records
        source = game_dir / name
        assert source.is_file(), f"Missing additional build file: {source}"
        data = source.read_bytes()
        extent = len(image) // SECTOR
        for index in range(0, len(data), PAYLOAD):
            image.extend(make_sector(len(image) // SECTOR, data[index:index + PAYLOAD]))
        record = new_record(name, extent, len(data), directory[68:112])
        assert cursor + len(record) <= PAYLOAD, "ISO directory has insufficient space"
        directory[cursor:cursor + len(record)] = record
        cursor += len(record)
        changed.append({"name": name, "old_size": None,
                        "new_size": len(data), "extent": extent,
                        "sha256": sha256(data)})

    put_payload(image, 22, directory)
    number_pair(pvd, 80, len(image) // SECTOR)
    put_payload(image, 16, pvd)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image)
    return {"source_img_sha256": ORIGINAL_SHA256,
            "target_bin_sha256": sha256(image),
            "source_sectors": original_sectors,
            "target_sectors": len(image) // SECTOR,
            "files": changed}


def write_cue(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cue = f'FILE "{BIN.name}" BINARY\n   TRACK 1 MODE1/2352\n      INDEX 1 00:00:00\n'
    (output_dir / CUE.name).write_text(cue, encoding="ascii", newline="")


def xdelta3_path() -> Path:
    result = ROOT / "tools/xdelta3.exe"
    if not result.is_file():
        raise FileNotFoundError(f"xdelta3 executable not found: {result}")
    return result


def create_patch(original_dir: Path, game_dir: Path, output_dir: Path,
                 patch: Path | None = None, manifest_path: Path | None = None) -> dict:
    """Create one IMG-to-BIN Xdelta patch and a matching BIN/CUE set."""
    patch = output_dir/PATCH.name if patch is None else patch
    manifest_path = output_dir/MANIFEST.name if manifest_path is None else manifest_path
    original = find_image(original_dir)
    tool = xdelta3_path()
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / BIN.name
    manifest = build_image(original, game_dir, target)
    manifest["game_dir"] = str(game_dir.resolve())
    patch.parent.mkdir(parents=True, exist_ok=True)
    # Input filenames must not affect the distributed patch bytes. The source
    # and output are supplied explicitly and verified by SHA-256.
    subprocess.run((str(tool), "-f", "-e", "-A", "-s", str(original),
                    str(target), str(patch)), check=True)
    verify = output_dir / f".{PRODUCT}.verify.bin"
    try:
        subprocess.run((str(tool), "-f", "-d", "-s", str(original),
                        str(patch), str(verify)), check=True)
        assert sha256(verify) == manifest["target_bin_sha256"], "Xdelta round trip mismatch"
    finally:
        verify.unlink(missing_ok=True)
    write_cue(output_dir)
    manifest["xdelta_patch"] = patch.name
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("create", "apply"))
    parser.add_argument("--original-dir", type=Path, default=ROOT / "img")
    parser.add_argument("--game-dir", type=Path, default=ROOT/"build/final-build"/GAME_SUBDIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    artifact_dir = args.output_dir if args.mode == 'create' else OUTPUT
    args.patch = args.patch or artifact_dir/PATCH.name
    args.manifest = args.manifest or artifact_dir/MANIFEST.name
    original = find_image(args.original_dir)
    target = args.output_dir / BIN.name
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "create":
        manifest = create_patch(args.original_dir, args.game_dir, args.output_dir,
                                args.patch, args.manifest)
    else:
        tool = xdelta3_path()
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        assert manifest["source_img_sha256"] == ORIGINAL_SHA256
        assert target.resolve() != original.resolve(), "Refusing to overwrite source IMG"
        subprocess.run((str(tool), "-f", "-d", "-s", str(original),
                        str(args.patch), str(target)), check=True)
        assert sha256(target) == manifest["target_bin_sha256"], "Patched BIN hash mismatch"
        write_cue(args.output_dir)
    assert target.stat().st_size == manifest["target_sectors"] * SECTOR
    print(json.dumps({"mode": args.mode, "target": str(target),
                      "sha256": sha256(target), "sectors": manifest["target_sectors"],
                      "patch": str(args.patch)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
