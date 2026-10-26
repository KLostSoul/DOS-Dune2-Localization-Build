"""Final-game cheat patches and the original-game comparison command."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
import struct
from pathlib import Path

import assembler

ROOT = Path(__file__).resolve().parents[1]
OLD_SIZE = 0x990
NEW_SIZE = 0xC50
HEADER = 0x4C00
PRODUCTION_SEG, PRODUCTION_OFF = 0x077B, 0x04D2
PRODUCTION_OLD = bytes.fromhex('8946f081fe0001')


def image_end(exe):
    last, pages = struct.unpack_from('<HH', exe, 2)
    return (pages-1)*512+(last or 512)


def assemble(exe, assembly_folder):
    old_end = image_end(exe)
    cheat_at = old_end-OLD_SIZE
    if cheat_at < HEADER or (cheat_at-HEADER) % 16:
        raise ValueError('MZ 치트 모듈의 기준 위치가 문단 경계와 맞지 않습니다.')
    segment = (cheat_at-HEADER)//16
    old_stack, new_stack = segment+OLD_SIZE//16, segment+NEW_SIZE//16
    original = (ROOT/'import/asm/cheat/cheat-hook-build.asm').read_text(encoding='ascii')
    assembler.ASM = Path(assembly_folder)
    assembler.ASM.mkdir(parents=True, exist_ok=True)

    def located(text, stack):
        text = text.replace('HOOK_SEGMENT_ID EQU 3D64h', f'HOOK_SEGMENT_ID EQU {segment:04X}h')
        text = text.replace('STACK_SEGMENT_ID EQU 3DFDh', f'STACK_SEGMENT_ID EQU {stack:04X}h')
        return text

    baseline = assembler.assemble(located(original, old_stack), 'verified-input-cheat', OLD_SIZE)
    if baseline != exe[cheat_at:old_end]:
        raise ValueError('현재 EXE의 치트 모듈이 검증된 에디터 기준 소스와 다릅니다.')

    source = located(original, new_stack)
    source = source.replace('COMMAND_TABLE EQU 0834h', 'COMMAND_TABLE EQU 0C00h')
    branch = source[source.index('SubmitNonEmptyCommand:'):source.index('DoCredits:')]
    source = source.replace(branch, 'SubmitNonEmptyCommand:\n    call FindCommand\n    jmp ExtraDispatch\n\n', 1)
    for label in ('DoCredits', 'DoWin', 'DoLose', 'UnknownCommand', 'Intercept'):
        source = source.replace(label+':\n', label+'::\n', 1)

    modal = source[source.index('GameInputBegin PROC FAR'):source.index('GameInputBegin ENDP')+len('GameInputBegin ENDP')]
    source = source.replace(modal, 'GameInputBegin PROC FAR\n    jmp ExtraGameInputBegin\nGameInputBegin ENDP', 1)
    modal = modal.replace('GameInputBegin', 'ExtraGameInputBegin').replace(
        'ModalDone:\n', 'ModalDone:\n    call ApplyExtraPending\n')

    reset = 'TransferResult:\n'
    at = source.index(reset)+len(reset)
    tail = source[at:]
    old_reset = '    mov  byte ptr cs:[GAME_INPUT_ACTIVE_VAR], 0'
    if tail.count(old_reset) != 1:
        raise ValueError('승패 전환의 치트 상태 초기화 위치가 달라졌습니다.')
    tail = tail.replace(old_reset, '    call ResetExtraState\n    nop\n    nop\n    nop', 1)
    source = source[:at]+tail

    extra = (ROOT/'import/asm/cheat/cheat-extra.asm').read_text(encoding='ascii')
    if extra.count('; @@GAME_INPUT_BEGIN@@') != 1:
        raise ValueError('추가 치트의 게임 입력 처리 삽입 위치가 잘못되었습니다.')
    extra = extra.replace('; @@GAME_INPUT_BEGIN@@', modal, 1)
    definitions = (
        'EXTRA_PENDING EQU 0C40h\nFAST_ENABLED EQU 0C41h\n'
        'MAP_VALID_PTR EQU 0C42h\nMAP_REVEAL_PTR EQU 0C46h\n'
        'STATUS_MESSAGE_PTR EQU 0C4Ah\n'
    )
    source = definitions+source.replace('CHEAT ENDS', extra+'\nCHEAT ENDS', 1)
    module = assembler.assemble(source, 'cheat-fastbuild-reveal', NEW_SIZE)
    if len(module) != NEW_SIZE:
        raise ValueError(f'추가 치트 모듈 크기가 예상과 다릅니다: {len(module):X}')

    listing = (assembler.ASM/'cheat-fastbuild-reveal.lst').read_text(encoding='ascii', errors='replace')
    labels = {}
    names = ('ExtraDispatch', 'ResetExtraState', 'ApplyExtraPending', 'RevealNativeMap',
             'ScaleProduction', 'ExtraGameInputBegin', 'ShowFastStatus')
    for name in names:
        match = re.search(r'^\s*([0-9A-Fa-f]{4,8})\s+.*\b'+name+r'\s+PROC\b', listing, re.M)
        if not match:
            raise ValueError('조립된 추가 치트 진입점을 찾지 못했습니다: '+name)
        labels[name] = int(match[1], 16)
    return module, dict(cheat_segment=segment, old_stack=old_stack, new_stack=new_stack,
                        cheat_file_offset=cheat_at, entries=labels)


def patch_module(exe, module, layout):
    old_end = image_end(exe)
    at = layout['cheat_file_offset']
    if at != old_end-OLD_SIZE:
        raise ValueError('치트 모듈과 MZ 이미지 끝 위치가 맞지 않습니다.')
    new = bytearray(exe[:at]+module+exe[old_end:])
    production_at = HEADER+PRODUCTION_SEG*16+PRODUCTION_OFF
    if exe[production_at:production_at+7] != PRODUCTION_OLD:
        raise ValueError('건물·유닛 생산 처리 원본 바이트가 다릅니다.')
    new[production_at:production_at+7] = (
        b'\x9a'+struct.pack('<HH', layout['entries']['ScaleProduction'], layout['cheat_segment'])
        + b'\x90\x90'
    )

    count = struct.unpack_from('<H', exe, 6)[0]
    table = struct.unpack_from('<H', exe, 0x18)[0]
    relocation = (PRODUCTION_OFF+3, PRODUCTION_SEG)
    entries = [struct.unpack_from('<HH', exe, table+4*i) for i in range(count)]
    if relocation in entries:
        raise ValueError('생산 처리 후크의 재배치 항목이 이미 존재합니다.')
    if table+(count+1)*4 > HEADER or any(exe[table+count*4:table+(count+1)*4]):
        raise ValueError('MZ 재배치 표에 추가 후크 공간이 없습니다.')
    struct.pack_into('<HH', new, table+count*4, *relocation)
    struct.pack_into('<H', new, 6, count+1)

    new_end = at+len(module)
    struct.pack_into('<HH', new, 2, new_end%512, (new_end+511)//512)
    if image_end(new) != new_end or new[new_end:] != exe[old_end:]:
        raise ValueError('추가 치트 뒤의 MZ 오버레이가 보존되지 않았습니다.')
    if exe[old_end:old_end+4] != b'FBOV':
        raise ValueError('원본 FBOV 오버레이를 찾지 못했습니다.')

    # The only pre-module changes are the MZ size, relocation, and production hook.
    allowed = (set(range(2, 8)) | set(range(table+count*4, table+(count+1)*4))
               | set(range(production_at, production_at+7)))
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(exe[:at], new[:at]))):
        raise ValueError('추가 치트가 허용된 범위 밖의 상주 코드를 변경했습니다.')
    if struct.unpack_from('<HH', new, 0x0E) != struct.unpack_from('<HH', exe, 0x0E):
        raise ValueError('추가 치트가 기존 MZ 메모리 최소·최대값을 변경했습니다.')

    report = dict(
        commands={
            'FASTBUILD': '게임 내 전환식 5배 생산 가속; 내 가문의 건물·유닛만 적용',
            'REVEAL': '현재 임무의 유효 지도 영역 공개',
        },
        fastbuild_messages=['FASTBUILD ON', 'FASTBUILD OFF'],
        extra_resident_bytes=NEW_SIZE-OLD_SIZE,
        extra_DOS_allocations=0,
        extra_XMS_allocations=0,
        cheat_module_bytes=len(module),
        cheat_segment=f'{layout["cheat_segment"]:04X}',
        old_stack_segment=f'{layout["old_stack"]:04X}',
        new_stack_segment=f'{layout["new_stack"]:04X}',
        old_mz_end=old_end,
        new_mz_end=new_end,
        relocation_count_before=count,
        relocation_count_after=count+1,
        added_relocation=list(relocation),
        production_hook=dict(address='077B:04D2', file_offset=production_at,
                             before=PRODUCTION_OLD.hex(), after=new[production_at:production_at+7].hex()),
        overlay_preserved_byte_for_byte=True,
        entries={name: f'{offset:04X}' for name, offset in layout['entries'].items()},
        game_execution='not run',
    )
    return bytes(new), report


def patch(exe, assembly_folder):
    module, layout = assemble(exe, assembly_folder)
    return patch_module(exe, module, layout)


ORIGINAL_SOURCE = ROOT / "build/source"
ORIGINAL_SOURCE_GAME = ORIGINAL_SOURCE / "VIRGIN/DUNE2"
ORIGINAL_OUTPUT = ROOT / "build/cheat-runtime"
ORIGINAL_OUTPUT_TREE = ORIGINAL_OUTPUT / "source"
ORIGINAL_OUTPUT_GAME = ORIGINAL_OUTPUT_TREE / "VIRGIN/DUNE2"
ORIGINAL_VERIFIED_ARCHIVE = ROOT / "archives/builds/verified/recovered-verified-dalmuri-cheat-baseline.zip"
ORIGINAL_VERIFIED_ARCHIVE_SHA256 = "802207e21b7d18d4a82f3613bfe7c8f949feab67fabe94ee0ebfcf2d190deee9"
ORIGINAL_VERIFIED_HOOK_MEMBER = "recovered-verified-dalmuri-cheat-baseline/cheat-hook-build.asm"
ORIGINAL_VERIFIED_HOOK_SHA256 = "2de32400ababcfe0b73e45cc08f3ac7ccf9c40ac36375dcca7ca2a5aaa830591"
ORIGINAL_VERIFIED_BASELINE_EXE_SHA256 = "cff1fbca859634321b798acbd26ac7f16752fe020d61ba542a888badc108a32c"
ORIGINAL_SOURCE_EXE_SHA256 = "99f44e83b309dd826f3dbc5068c61679bb68047eed8d738dcef594ba0eef7552"
ORIGINAL_HEADER_BYTES = 0x4C00
ORIGINAL_BASE_IMAGE_END = 0x41C20
ORIGINAL_MODULE_SIZE = 0x0990
ORIGINAL_MODULE_SEGMENT = (ORIGINAL_BASE_IMAGE_END - ORIGINAL_HEADER_BYTES) // 16
ORIGINAL_NEW_IMAGE_END = ORIGINAL_BASE_IMAGE_END + ORIGINAL_MODULE_SIZE
ORIGINAL_STACK_SEGMENT = (ORIGINAL_NEW_IMAGE_END - ORIGINAL_HEADER_BYTES) // 16
ORIGINAL_STARTUP_RELOCATION_OLD = (0x005E, 0x0000)
ORIGINAL_STARTUP_RELOCATION_NEW = (0x0060, 0x0000)
ORIGINAL_ADDED_RELOCATIONS = (
    (0x0A57, 0x27EC), (0x0F0E, 0x27EC), (0x032B, 0x1223),
)


def original_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def original_mz_image_end(exe: bytes) -> int:
    last, pages = struct.unpack_from("<HH", exe, 2)
    if not pages:
        raise ValueError("DUNE2.EXE has no MZ pages")
    return (pages - 1) * 512 + (last or 512)


def original_assemble_module() -> bytes:
    assembler.ASM = ORIGINAL_OUTPUT / "assembly"
    assembler.ASM.mkdir(parents=True, exist_ok=True)
    archive_bytes = ORIGINAL_VERIFIED_ARCHIVE.read_bytes()
    if original_sha256(archive_bytes) != ORIGINAL_VERIFIED_ARCHIVE_SHA256:
        raise ValueError("Verified cheat archive hash changed")
    with zipfile.ZipFile(ORIGINAL_VERIFIED_ARCHIVE) as archive:
        source_bytes = archive.read(ORIGINAL_VERIFIED_HOOK_MEMBER)
    if original_sha256(source_bytes) != ORIGINAL_VERIFIED_HOOK_SHA256:
        raise ValueError("Archived verified cheat-hook source hash changed")
    source = source_bytes.decode("ascii").replace("\r\n", "\n").replace("\r", "\n")
    startup = """    call InitializeXms
    mov  dx, cs
    sub  dx, HOOK_SEGMENT_ID
    add  dx, STACK_SEGMENT_ID
"""
    if source.count(startup) != 1 or "    mov  ss, dx" in source:
        raise ValueError("Cheat hook startup no longer follows the documented DX handoff")
    substitutions = {
        "HOOK_SEGMENT_ID EQU 3D64h": f"HOOK_SEGMENT_ID EQU {ORIGINAL_MODULE_SEGMENT:04X}h",
        "STACK_SEGMENT_ID EQU 3DFDh": f"STACK_SEGMENT_ID EQU {ORIGINAL_STACK_SEGMENT:04X}h",
    }
    for old, new in substitutions.items():
        if source.count(old) != 1:
            raise ValueError(f"Expected one cheat segment marker: {old}")
        source = source.replace(old, new)
    module = assembler.assemble(source, "original-cheat-hook", ORIGINAL_MODULE_SIZE)
    if len(module) != ORIGINAL_MODULE_SIZE:
        raise ValueError(f"Cheat hook size changed: {len(module):#x}")
    return module


def original_patch_exe(source: bytes, module: bytes) -> tuple[bytes, dict]:
    if original_sha256(source) != ORIGINAL_SOURCE_EXE_SHA256:
        raise ValueError("Original DUNE2.EXE hash does not match the recorded source")
    if len(source) < ORIGINAL_BASE_IMAGE_END or original_mz_image_end(source) != ORIGINAL_BASE_IMAGE_END:
        raise ValueError("Original MZ load image end changed")
    if struct.unpack_from("<H", source, 8)[0] * 16 != ORIGINAL_HEADER_BYTES:
        raise ValueError("Original MZ header size changed")
    if source[ORIGINAL_BASE_IMAGE_END:ORIGINAL_BASE_IMAGE_END + 4] != b"FBOV":
        raise ValueError("Original Borland overlay marker is missing")
    if struct.unpack_from("<HH", source, 0x0E) != (0x3CFA, 0x80):
        raise ValueError("Original stack initialization differs from the analyzed EXE")
    if ORIGINAL_STACK_SEGMENT != ORIGINAL_MODULE_SEGMENT + ORIGINAL_MODULE_SIZE // 16:
        raise ValueError("Cheat stack does not follow the resident module")

    # These five sites are the exact cheat-hook patch set in the archived,
    # user-verified baseline report. Do not add later experimental hooks here.
    sites = [
        ("startup_bridge", 0x0000, 0x005D, "BF 42 33 8E C7", "EA 00 00", ""),
        ("keyboard_entry", 0x27EC, 0x0A54, "55 8B EC 83 EC 04", "EA 40 00", "90"),
        ("keyboard_isr", 0x27EC, 0x0F0B, "58 3C 6E 75 0F", "EA 00 02", ""),
        ("mission_result", 0x1223, 0x0328, "0B C0 75 03 E9 5E 01", "9A 00 03", "90 90"),
        ("game_input_context_begin", 0x044B, 0x0309, "9A 0A 00 9C 23", "9A A0 02", ""),
    ]
    header = ORIGINAL_HEADER_BYTES
    reloc_count = struct.unpack_from("<H", source, 6)[0]
    reloc_at = struct.unpack_from("<H", source, 0x18)[0]
    relocations = [struct.unpack_from("<HH", source, reloc_at + 4 * i)[0:2] for i in range(reloc_count)]
    for required in ((0x030C, 0x044B),):
        if relocations.count(required) != 1:
            raise ValueError(f"Original call relocation changed: {required}")

    patched = bytearray(source[:ORIGINAL_BASE_IMAGE_END] + module + source[ORIGINAL_BASE_IMAGE_END:])
    sites_report, added = [], []
    for name, segment, offset, old_hex, prefix_hex, suffix_hex in sites:
        old = bytes.fromhex(old_hex)
        at = header + segment * 16 + offset
        if patched[at:at + len(old)] != old:
            raise ValueError(f"Original bytes changed at {segment:04X}:{offset:04X} ({name})")
        replacement = (bytes.fromhex(prefix_hex) + struct.pack("<H", ORIGINAL_MODULE_SEGMENT)
                       + bytes.fromhex(suffix_hex))
        if len(replacement) != len(old):
            raise AssertionError(f"Patch length mismatch at {name}")
        patched[at:at + len(old)] = replacement
        reused = False
        if name != "startup_bridge":
            entry = (offset + 3, segment)
            reused = entry in relocations
            if not reused:
                added.append(entry)
        sites_report.append({"name": name, "address": f"{segment:04X}:{offset:04X}",
                             "before": old.hex(" ").upper(),
                             "after": replacement.hex(" ").upper(),
                             "existing_relocation_reused": reused})
    if tuple(added) != ORIGINAL_ADDED_RELOCATIONS:
        raise ValueError(f"Unexpected relocation additions: {added}")

    start_indices = [i for i, item in enumerate(relocations) if item == ORIGINAL_STARTUP_RELOCATION_OLD]
    if len(start_indices) != 1 or ORIGINAL_STARTUP_RELOCATION_NEW in relocations:
        raise ValueError("Original startup relocation is missing or already patched")
    reloc_end = reloc_at + reloc_count * 4
    if reloc_end + 4 * len(added) > header or any(source[reloc_end:reloc_end + 4 * len(added)]):
        raise ValueError("MZ relocation table has no clean space for the cheat hooks")
    struct.pack_into("<HH", patched, reloc_at + start_indices[0] * 4, *ORIGINAL_STARTUP_RELOCATION_NEW)
    for i, item in enumerate(added):
        struct.pack_into("<HH", patched, reloc_end + i * 4, *item)
    struct.pack_into("<H", patched, 6, reloc_count + len(added))
    struct.pack_into("<HH", patched, 2, ORIGINAL_NEW_IMAGE_END % 512, (ORIGINAL_NEW_IMAGE_END + 511) // 512)
    if original_mz_image_end(patched) != ORIGINAL_NEW_IMAGE_END or patched[ORIGINAL_NEW_IMAGE_END:] != source[ORIGINAL_BASE_IMAGE_END:]:
        raise ValueError("MZ image boundary or original overlay preservation failed")
    return bytes(patched), {
        "source_sha256": original_sha256(source), "patched_sha256": original_sha256(patched),
        "base_mz_image_end": hex(ORIGINAL_BASE_IMAGE_END), "new_mz_image_end": hex(ORIGINAL_NEW_IMAGE_END),
        "module_sha256": original_sha256(module), "module_segment": hex(ORIGINAL_MODULE_SEGMENT),
        "module_bytes": len(module), "stack_segment": hex(ORIGINAL_STACK_SEGMENT),
        "relocations_before": reloc_count, "relocations_after": reloc_count + len(added),
        "overlay_preserved_byte_for_byte": True, "patched_sites": sites_report,
    }


def original_main() -> None:
    if ORIGINAL_OUTPUT.exists():
        raise FileExistsError(f"Build already exists; preserving it: {ORIGINAL_OUTPUT}")
    source_exe = ORIGINAL_SOURCE_GAME / "DUNE2.EXE"
    source_bytes = source_exe.read_bytes()
    module = original_assemble_module()
    patched_exe, patch_report = original_patch_exe(source_bytes, module)
    shutil.copytree(ORIGINAL_SOURCE, ORIGINAL_OUTPUT_TREE)
    (ORIGINAL_OUTPUT_GAME / "DUNE2.EXE").write_bytes(patched_exe)

    report = {
        "build": str(ORIGINAL_OUTPUT.relative_to(ROOT)),
        "base_game": str(ORIGINAL_SOURCE.relative_to(ROOT)),
        "verified_cheat_archive": str(ORIGINAL_VERIFIED_ARCHIVE.relative_to(ROOT)),
        "verified_cheat_archive_sha256": ORIGINAL_VERIFIED_ARCHIVE_SHA256,
        "verified_cheat_baseline_exe_sha256": ORIGINAL_VERIFIED_BASELINE_EXE_SHA256,
        "verified_cheat_hook_source_sha256": ORIGINAL_VERIFIED_HOOK_SHA256,
        "verified_patch_site_count": 5,
        "source_exe_sha256": patch_report["source_sha256"],
        "patched_exe_sha256": patch_report["patched_sha256"],
        "only_game_executable_modified": True,
        "game_resources_and_configuration_copied_from_original": True,
        "added_cheat_commands": ["CREDITS", "WIN", "LOSE"],
        "startup_stack_handoff_to_original_borland_initializer": True,
        "runtime_verified": False,
        "patch": patch_report,
    }
    (ORIGINAL_OUTPUT / "original-cheat-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('original',),
                        help='Create the original-game copy with the verified CREDITS/WIN/LOSE hook')
    args = parser.parse_args()
    if args.command == 'original':
        original_main()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
