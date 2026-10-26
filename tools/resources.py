"""PAK/IFF containers, game text compression and original text extraction."""
from __future__ import annotations
import argparse
import csv
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAIRS = (" etainosrlhcdupm" + "tasio wb" + " rnsdalm" + "h ieoras" + "nrtlc sy" +
         "nstcloer" + " dtgesio" + "nr ufmsw" + " tep.ica" + "e oiadur" +
         " laeiyod" + "eia otru" + "etoakhlr" + " eiu,.oa" + "nsrctlai" +
         "leoiratp" + "eaoip bm")

def pak_entries(raw):
    """Audio PAKs may repeat names; keep their archive untouched."""
    entries, at = [], 0
    while True:
        offset = struct.unpack_from('<I', raw, at)[0]
        at += 4
        if not offset:
            break
        end = raw.index(0, at)
        entries.append((raw[at:end].decode('ascii'), offset))
        at = end + 1
    result = []
    for i, (name, start) in enumerate(entries):
        end = entries[i + 1][1] if i + 1 < len(entries) else len(raw)
        if not at <= start <= end <= len(raw):
            raise ValueError('Invalid PAK offsets')
        result.append((name, raw[start:end]))
    return result

def unpack_pak(raw):
    entries = pak_entries(raw)
    names = [name for name, _ in entries]
    assert len(set(names)) == len(names)
    return names, dict(entries)

def pack_pak(names,files):
    head=bytearray();body=bytearray()
    start=sum(5+len(n) for n in names)+4
    for n in names:
        head+=struct.pack('<I',start+len(body))+n.encode('ascii')+b'\0'
        body+=files[n]
    return bytes(head+b'\0\0\0\0'+body)

def expand_pairs(raw):
    first=bytearray()
    for b in raw:
        if b&128:
            code=b&127
            first.extend((ord(PAIRS[code>>3]),ord(PAIRS[code+16])))
        else:first.append(b)
    return bytes(first)

def expand_compressed(raw):
    first=expand_pairs(raw)
    out=bytearray();at=0
    while at<len(first):
        b=first[at];at+=1
        if b==27:
            assert at<len(first)
            b=first[at]+127;at+=1
        out.append(b)
    return bytes(out)

def stored(raw):
    out=bytearray()
    for b in raw:
        assert b not in (0,27,255)
        out.extend((27,b-127) if b>=128 else (b,))
    assert expand_compressed(out)==raw
    return bytes(out)

def display(raw):
    parts=[]
    for b in raw:
        parts.append({13:r'\r',10:r'\n',9:r'\t'}.get(b,
                     f'\\x{b:02X}' if b<32 or b==127 else chr(b)))
    return ''.join(parts)

def iff_chunks(raw):
    assert raw[:4]==b'FORM' and raw[8:12]==b'MENT'
    assert int.from_bytes(raw[4:8],'big')+8==len(raw)
    chunks=[];at=12
    while at<len(raw):
        name=raw[at:at+4];size=int.from_bytes(raw[at+4:at+8],'big')
        assert len(name)==4 and at+8+size<=len(raw),(name,at,size,len(raw))
        chunks.append((name,at+8,raw[at+8:at+8+size]))
        at+=8+size+(size&1)
    assert at==len(raw)
    return chunks

ENGLISH = ROOT / "export" / "PAK" / "ENGLISH.PAK"

STRINGS_OUTPUT = ROOT / "export" / "strings" / "source_strings_complete.csv"

SCENARIOS = ROOT / "export" / "PAK" / "SCENARIO.PAK"

COUPLES = PAIRS

def display_character(value: int) -> str:
    if value == 0x0D:
        return r"\r"
    if value == 0x0A:
        return r"\n"
    if value == 0x09:
        return r"\t"
    if value < 0x20 or value == 0x7F:
        return f"\\x{value:02X}"
    return chr(value)

def decode_bytes(data: bytes, compressed: bool) -> str:
    out: list[str] = []
    pos = 0
    while pos < len(data) and data[pos] != 0:
        value = data[pos]
        pos += 1
        if compressed and value & 0x80:
            pair = value & 0x7F
            left, right = pair >> 3, pair + 16
            if left >= len(COUPLES) or right >= len(COUPLES):
                out.append(f"\\x{value:02X}")
            else:
                out.append(COUPLES[left])
                out.append(COUPLES[right])
        elif compressed and value == 0x1B:
            if pos >= len(data):
                out.append(r"\x1B")
            else:
                out.append(display_character(0x7F + data[pos]))
                pos += 1
        else:
            out.append(display_character(value))
    return "".join(out)

def read_offset_table(path: Path, compressed: bool, kind: str, *, data: bytes | None = None) -> list[dict[str, str]]:
    data = path.read_bytes() if data is None else data
    if len(data) < 2:
        raise ValueError(f"short string table: {path.name}")
    count = struct.unpack_from("<H", data, 0)[0] // 2
    rows: list[dict[str, str]] = []
    for index in range(count):
        offset = struct.unpack_from("<H", data, index * 2)[0]
        if offset < count * 2 or offset >= len(data):
            raise ValueError(f"invalid offset {offset} in {path.name}[{index}]")
        end = data.find(b"\x00", offset)
        if end < 0:
            end = len(data)
        rows.append({
            "file": path.name,
            "type": kind,
            "index": str(index),
            "code": "",
            "source_en": decode_bytes(data[offset:end], compressed),
            "translation_ko": "",
        })
    return rows

def read_credits(path: Path, *, data: bytes | None = None) -> list[dict[str, str]]:
    data = path.read_bytes() if data is None else data
    text = data.decode("cp1252", "replace")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    rows = []
    for index, line in enumerate(lines):
        if line:
            rows.append({
                "file": path.name,
                "type": "credits_line",
                "index": str(index),
                "code": "",
                "source_en": line,
                "translation_ko": "",
            })
    return rows

def read_region_text(path: Path, *, data: bytes | None = None) -> list[dict[str, str]]:
    """Export English region-map story lines, ignoring gameplay data and comments."""
    data = path.read_bytes() if data is None else data
    rows: list[dict[str, str]] = []
    group = ""
    text_pattern = re.compile(r"^\s*ENGTXT(\d+)\s*=\s*(.*?)\s*$")
    group_pattern = re.compile(r"^\s*\[GROUP(\d+)\]\s*$", re.IGNORECASE)
    for line_number, line in enumerate(data.decode("cp1252", "replace").splitlines(), 1):
        group_match = group_pattern.match(line)
        if group_match:
            group = group_match.group(1)
            continue
        text_match = text_pattern.match(line)
        if text_match:
            rows.append({
                "file": path.name,
                "type": "region_map_text",
                "index": f"group{group}:line{line_number}",
                "code": f"ENGTXT{text_match.group(1)}",
                "source_en": text_match.group(2),
                "translation_ko": "",
            })
    return rows

def read_mentat(path: Path, *, data: bytes | None = None) -> list[dict[str, str]]:
    data = path.read_bytes() if data is None else data
    if data[:4] != b"FORM" or data[8:16] != b"MENTNAME":
        raise ValueError(f"unexpected Mentat FORM header: {path.name}")
    name_chunk_size = int.from_bytes(data[16:20], "big")
    pos = 20
    records_end = pos + name_chunk_size
    if records_end > len(data):
        raise ValueError(f"invalid MENTNAME chunk size: {path.name}")
    rows: list[dict[str, str]] = []
    index = 0
    while pos + 7 <= records_end:
        record_size = struct.unpack_from("<H", data, pos)[0]
        if record_size < 8 or pos + record_size > records_end:
            raise ValueError(f"invalid Mentat record at {pos} in {path.name}")
        text_offset = int.from_bytes(data[pos + 2:pos + 5], "big")
        raw_label = data[pos + 5:pos + record_size - 2]
        raw_label = raw_label.split(b"\x00", 1)[0]
        label = raw_label.decode("cp1252", "replace")
        code, visible_label = (label[:2], label[2:]) if len(label) >= 2 else ("", label)
        rows.append({
            "file": path.name,
            "type": "mentat_label",
            "index": str(index),
            "code": code,
            "source_en": visible_label,
            "translation_ko": "",
        })
        if text_offset >= len(data):
            raise ValueError(f"Mentat description offset outside file at {pos}: {text_offset}")
        text_end = data.find(b"\x00", text_offset)
        if text_end < 0:
            raise ValueError(f"unterminated Mentat description at {text_offset} in {path.name}")
        rows.append({
            "file": path.name,
            "type": "mentat_description",
            "index": str(index),
            "code": code,
            "source_en": decode_bytes(data[text_offset:text_end], compressed=True),
            "translation_ko": "",
        })
        pos += record_size
        index += 1
    if pos != records_end:
        raise ValueError(f"unparsed bytes remain in MENTNAME chunk: {path.name} at {pos}/{records_end}")
    return rows

def read_resources(source: Path, names: list[str]) -> dict[str, bytes]:
    """Read the requested members from a PAK or an extracted directory."""
    if source.is_dir():
        return {name: (source / name).read_bytes() for name in names}
    members = unpack_pak(source.read_bytes())[1]
    missing = [name for name in names if name not in members]
    if missing:
        raise ValueError(f"missing resources in {source}: {', '.join(missing)}")
    return {name: members[name] for name in names}

def export_strings_main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--english", type=Path, default=ENGLISH,
                        help="ENGLISH.PAK or an extracted ENGLISH.files directory (default: export/PAK/ENGLISH.PAK)")
    parser.add_argument("--scenarios", type=Path, default=SCENARIOS,
                        help="SCENARIO.PAK or an extracted SCENARIO.files directory (default: export/PAK/SCENARIO.PAK)")
    parser.add_argument("--output", type=Path, default=STRINGS_OUTPUT, help="output CSV")
    args = parser.parse_args(argv)
    english_source, scenario_source = args.english.resolve(), args.scenarios.resolve()
    defaults = [source for source, default in ((english_source, ENGLISH), (scenario_source, SCENARIOS))
                if source == default.resolve()]
    if any(not source.is_file() for source in defaults):
        from cd_source import prepare_exports
        prepare_exports()
    rows: list[dict[str, str]] = []
    table_specs = [
        ("DUNE.ENG", False, "uncompressed_table"),
        ("MESSAGE.ENG", False, "uncompressed_table"),
        ("INTRO.ENG", False, "intro_transcript"),
        ("TEXTA.ENG", True, "compressed_mission_text"),
        ("TEXTH.ENG", True, "compressed_mission_text"),
        ("TEXTO.ENG", True, "compressed_mission_text"),
        ("PROTECT.ENG", True, "compressed_security_text"),
    ]
    mentat_names = ("MENTATA.ENG", "MENTATH.ENG", "MENTATO.ENG")
    region_names = ("REGIONA.INI", "REGIONH.INI", "REGIONO.INI")
    english = read_resources(english_source, [name for name, _, _ in table_specs] +
                             ["CREDITS.ENG", *mentat_names])
    scenarios = read_resources(scenario_source, list(region_names))
    for name, compressed, kind in table_specs:
        rows.extend(read_offset_table(Path(name), compressed, kind, data=english[name]))
    rows.extend(read_credits(Path("CREDITS.ENG"), data=english["CREDITS.ENG"]))
    for name in mentat_names:
        rows.extend(read_mentat(Path(name), data=english[name]))
    for name in region_names:
        rows.extend(read_region_text(Path(name), data=scenarios[name]))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["file", "type", "index", "code", "source_en", "translation_ko"]
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} rows to {output}")
    for file_name in sorted({row['file'] for row in rows}):
        print(file_name, sum(row['file'] == file_name for row in rows))
    return 0

DEFAULT_EXE = ROOT / "export" / "DUNE2.EXE"

EXE_OUTPUT = ROOT / "export" / "strings" / "executable_strings_review.csv"

PRINTABLE_RUN = re.compile(rb"[ -~]{6,}")

def exe_candidates(data: bytes) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for match in PRINTABLE_RUN.finditer(data):
        text = match.group().decode("ascii")
        # Dune II stores a few byte controls next to text in this executable.
        # Remove the known printable marker so the actual sentence is readable.
        if text.startswith("+B3"):
            text = text[3:]
        alpha = sum(char.isalpha() for char in text)
        # Keep likely sentences and labels. Skip binary patterns and the
        # adjacent pair-compression dictionary embedded in this executable.
        if " " not in text or alpha < 7 or alpha / len(text) < 0.42:
            continue
        if len(re.findall(r"B3", text)) >= 2:
            continue
        if "etainosrlhcdupmtasio" in text:
            continue
        rows.append({
            "file": "DUNE2.EXE",
            "offset_hex": f"0x{match.start():06X}",
            "type": "embedded_ascii_candidate",
            "source_en_or_literal": text,
            "review_note": "문자열 스캔 후보; 표시 여부와 호출 문맥은 미확인",
            "translation_ko": "",
        })
    return rows

def export_exe_main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE, help="DUNE2.EXE path")
    parser.add_argument("--output", type=Path, default=EXE_OUTPUT, help="output CSV")
    args = parser.parse_args(argv)
    executable = args.exe.resolve()
    if executable == DEFAULT_EXE.resolve() and not executable.is_file():
        from cd_source import prepare_exports
        prepare_exports()
    rows = exe_candidates(executable.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["file", "offset_hex", "type", "source_en_or_literal", "review_note", "translation_ko"]
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} executable string exe_candidates to {args.output}")
    return 0

def main(argv=None):
    import sys
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('strings', 'exe'),
                        help='Export complete source text or executable ASCII candidates')
    args = parser.parse_args(argv[:1])
    return (export_strings_main if args.command == 'strings' else export_exe_main)(argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
