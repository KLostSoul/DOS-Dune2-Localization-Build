"""Read the original CD and prepare the native localization code template."""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT/'img/DUNE2CD.img'
IMAGE_SHA256 = 'edcdce3de2e4d986421d99cc11be424277317fc3e8cd71cf78f8ed544bce81bf'
EXPORTS = {
    'DUNE2.EXE': ('export/DUNE2.EXE', '99f44e83b309dd826f3dbc5068c61679bb68047eed8d738dcef594ba0eef7552'),
    'DUNE.PAK': ('export/PAK/DUNE.PAK', '1ddde583b834fa0ea2a4c75defca5eab24be2dfc2cf1c78bc6a56e59471de3b7'),
    'ENGLISH.PAK': ('export/PAK/ENGLISH.PAK', '576a7bea7826a0c47605c9b3c3abc7e24c74cc834c1b74fd997b2783a011cb74'),
    'SCENARIO.PAK': ('export/PAK/SCENARIO.PAK', 'ca09fed27dfd052f4a2c37a811d3a3e1d549fc5949b4c40424764b56638944a6'),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_exports():
    result = {}
    for name, (relative, expected) in EXPORTS.items():
        path = ROOT/relative
        raw = path.read_bytes()
        if sha(raw) != expected:
            raise ValueError(f'원본 CD 추출 파일의 SHA-256이 다릅니다: {path}')
        result[name] = raw
    return result


def cd_files():
    raw = IMAGE.read_bytes()
    if sha(raw) != IMAGE_SHA256 or len(raw) % 2352:
        raise ValueError('원본 DUNE2CD.img의 SHA-256 또는 섹터 크기가 다릅니다.')

    def read(extent, size):
        result = bytearray()
        for offset in range(0, size, 2048):
            at = (extent+offset//2048)*2352+16
            result.extend(raw[at:at+min(2048, size-offset)])
        if len(result) != size:
            raise ValueError('CD ISO 파일 범위가 이미지 밖입니다.')
        return bytes(result)

    pvd = read(16, 2048)
    if pvd[:7] != b'\x01CD001\x01':
        raise ValueError('Mode 1 ISO9660 CD가 아닙니다.')
    files = {}
    visited = set()

    def directory(extent, size, parent=''):
        if extent in visited:
            raise ValueError('ISO 디렉터리 순환 참조입니다.')
        visited.add(extent)
        data = read(extent, size)
        at = 0
        while at < len(data):
            length = data[at]
            if not length:
                at = (at//2048+1)*2048
                continue
            if length < 34 or at+length > len(data):
                raise ValueError('ISO 디렉터리 레코드 길이가 다릅니다.')
            record = data[at:at+length]
            name = record[33:33+record[32]]
            if name not in (b'\0', b'\1'):
                name = name.decode('ascii').split(';')[0]
                path = PurePosixPath(parent)/name
                if path.is_absolute() or '..' in path.parts or '\\' in name:
                    raise ValueError('ISO 파일 경로가 안전하지 않습니다.')
                lba, count = struct.unpack_from('<I', record, 2)[0], struct.unpack_from('<I', record, 10)[0]
                if record[25] & 2:
                    directory(lba, count, path.as_posix())
                else:
                    files[path.as_posix()] = read(lba, count)
            at += length

    directory(struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0])
    return files


def prepare_exports():
    files = cd_files()
    for name, (relative, expected) in EXPORTS.items():
        raw = files['VIRGIN/DUNE2/'+name]
        if sha(raw) != expected:
            raise ValueError(f'원본 CD 내부 파일의 SHA-256이 다릅니다: {name}')
        path = ROOT/relative
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    validate_exports()
    return files


def extract_source(destination, *, files=None, runtime_settings=True):
    # Reuse the original-CD map already verified by this build invocation.
    files = prepare_exports() if files is None else files
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    for relative, raw in files.items():
        path = destination/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    settings_path = ROOT/'import/runtime-settings.json'
    if runtime_settings:
        settings = json.loads(settings_path.read_text(encoding='utf-8'))['files']
        if set(settings) != {'DUNE.CFG', 'OPTIONS.CFG', 'ONETIME.DAT'}:
            raise ValueError('로컬 게임 설정 파일 목록이 다릅니다.')
        for name, value in settings.items():
            (destination/'VIRGIN/DUNE2'/name).write_bytes(bytes.fromhex(value))
    return dict(image=str(IMAGE), image_sha256=IMAGE_SHA256, extracted_files=len(files),
                local_runtime_settings=str(settings_path.relative_to(ROOT)) if runtime_settings else None,
                patch_inputs={name: dict(path=relative, sha256=expected)
                              for name, (relative, expected) in EXPORTS.items()})


def _edits(raw, changes):
    result = bytearray(raw)
    for change in changes:
        at = change['offset']
        before, after = bytes.fromhex(change['before']), bytes.fromhex(change['after'])
        if len(before) != len(after) or result[at:at+len(before)] != before:
            raise ValueError(f'CD 기본 후크의 원본 바이트가 다릅니다: {at:06X}')
        result[at:at+len(after)] = after
    return bytes(result)


def _include(raw):
    return '\n'.join('db '+','.join(f'0{x:02X}h' for x in raw[i:i+16])
                     for i in range(0, len(raw), 16))+'\n'


def prepare_runtime(assembly_folder, font_package):
    """Prepare native code using the already completed FNT's inline prefix.

    No initial font, initial character table or temporary cheat module is
    generated. The font installer assembles the cheat at its final address.
    """
    import assembler
    inputs = validate_exports()
    original = inputs['DUNE2.EXE']
    patch_path = ROOT/'import/cd-runtime-base.json'
    patch = json.loads(patch_path.read_text(encoding='utf-8'))
    if patch['version'] != 2 or sha(original) != patch['original_exe_sha256']:
        raise ValueError('CD 기본 후크 패치의 입력 버전이 다릅니다.')
    prefix = font_package['prefix']
    data_offset = patch['font_inline_data_offset']
    data_bytes = patch['font_inline_data_bytes']
    if (data_offset != 0x480 or data_bytes != 24+672*10 or
            len(prefix) != data_bytes or sha(font_package['font']) != font_package['sha256']):
        raise ValueError('완성 FNT의 고정 메모리 구간 크기 또는 해시가 다릅니다.')
    folder = Path(assembly_folder)
    folder.mkdir(parents=True, exist_ok=True)
    assembler.ASM = folder
    (folder/'original-width.inc').write_text(_include(original[0x27e69:0x27e8f]), encoding='ascii')
    (folder/'font-table.inc').write_text(_include(prefix), encoding='ascii')
    source = (ROOT/'import/asm/font/dalmoori-base.asm').read_bytes()
    if sha(source) != patch['font_source_sha256']:
        raise ValueError('폰트 코드 ASM이 CD 후크 패치와 다릅니다.')
    module = assembler.assemble(source.decode('ascii'), 'completed-font-code', patch['font_module_bytes'])
    module = _edits(module, patch['font_module_edits'])
    if len(module) != patch['font_module_bytes'] or module[data_offset:data_offset+len(prefix)] != prefix:
        raise ValueError('폰트 후크의 코드·완성 글리프 배치가 다릅니다.')
    end = patch['original_image_end']
    resident = _edits(original[:end], patch['resident_edits'])
    overlay = _edits(original[end:], patch['overlay_edits'])
    if sha(resident) != patch['resident_sha256'] or sha(overlay) != patch['overlay_sha256']:
        raise ValueError('원본 EXE의 상주 코드·오버레이 패치 결과가 다릅니다.')
    exe = bytearray(resident+module+overlay)
    template_end = end+len(module)
    struct.pack_into('<HH', exe, 2, template_end%512, (template_end+511)//512)
    if exe[template_end:template_end+4] != b'FBOV':
        raise ValueError('폰트 코드 템플릿의 MZ 이미지 경계가 다릅니다.')
    code = module[:data_offset]+module[data_offset+len(prefix):]
    return bytes(exe), dict(original_exe_sha256=sha(original),
        reconstructed_exe_sha256=sha(exe), template_mz_end=template_end,
        patch=str(patch_path.relative_to(ROOT)), patch_sha256=sha(patch_path.read_bytes()),
        font_module_sha256=sha(module), font_code_sha256=sha(code),
        completed_font_sha256=font_package['sha256'],
        initial_font_generated=False, initial_character_table_required=False,
        initial_cheat_generated=False, previous_build_required=False)


def main():
    """Expose the original-CD extraction used by the final builder."""
    import argparse
    import sys
    from resources import pak_entries
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('exports', help='Extract/validate the four original build inputs in export/')
    extract = commands.add_parser('extract', help='Extract an untouched original CD tree into a new directory')
    extract.add_argument('--output', type=Path, required=True)
    extract.add_argument('--unpack-paks', action='store_true', help='Also write .files members for analysis tools')
    args = parser.parse_args()
    if args.command == 'exports':
        prepare_exports()
        result = dict(image=str(IMAGE), image_sha256=IMAGE_SHA256,
                      files={name: dict(path=str(ROOT/relative), sha256=expected)
                             for name, (relative, expected) in EXPORTS.items()})
    else:
        destination = args.output.resolve()
        result = extract_source(destination, runtime_settings=False)
        result['output'] = str(destination)
        if args.unpack_paks:
            archives = members = 0
            for archive in sorted(destination.rglob('*.PAK')):
                folder = archive.with_suffix('.files')
                folder.mkdir()
                for name, raw in pak_entries(archive.read_bytes()):
                    path = folder/name
                    if Path(name).name != name or not path.resolve().is_relative_to(folder.resolve()):
                        raise ValueError('PAK 멤버 경로가 안전하지 않습니다: '+name)
                    path.write_bytes(raw)
                    members += 1
                archives += 1
            result.update(unpacked_paks=archives, unpacked_members=members)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
