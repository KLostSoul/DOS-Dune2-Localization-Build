"""Build the final Korean game from the original CD and current saved inputs."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile
from pathlib import Path
from collections import defaultdict
import cd_source
import assembler
import fonts
import cheats
import runtime_patches
import scenes
from translation_data import (TranslationData, ROOT, DRAFT, REGISTRY, TRACKED,
    EXCLUDED_ROWS, editable, row_key, digest, read_csv, formats, split_mentat, registry_bytes)
from resources import (unpack_pak, pack_pak, iff_chunks, expand_pairs,
                       expand_compressed, stored)

class BuildInputs(TranslationData):
    def __init__(self):
        cd_source.validate_exports()
        super().__init__()

    def validate_build(self, changed):
        errors = []
        for row in changed:
            if row['file'] == 'CREDITS.ENG' and row['source_en'] == '\0':
                if row['translation_ko'] not in ('', '\0'):
                    errors.append(f"{row['file']} #{row['index']}: 원본 파일 종료 데이터는 번역할 수 없습니다.")
                continue
            text = row['translation_ko'] or row['source_en']
            try: self.encode(text)
            except ValueError as error: errors.append(f"{row['file']} #{row['index']}: {error}")
            if formats(text) != formats(row['source_en']):
                errors.append(f"{row['file']} #{row['index']}: 원문과 치환 기호가 다릅니다.")
        if errors: raise ValueError('\n'.join(errors[:30]))

    def rebuild_mentat(self, raw, changes):
        chunks = iff_chunks(raw); payload = {kind: data for kind, _, data in chunks}
        names = payload[b'NAME']; desc = payload[b'DESC']
        old_desc_start = next(at for kind, at, _ in chunks if kind == b'DESC')
        labels = {r['index']: r for r in changes if r['type'] == 'mentat_label'}
        texts = {r['index']: r for r in changes if r['type'] == 'mentat_description'}
        records = []; changed_desc = {}; at = 0
        while at < len(names):
            size = struct.unpack_from('<H', names, at)[0]; rec = names[at:at+size]
            index = str(len(records)); ptr = int.from_bytes(rec[2:5], 'big')
            label = self.encode(labels[index]['translation_ko'] or labels[index]['source_en']) if index in labels else rec[7:-2]
            if len(label)+9 > 65535: raise ValueError('멘타트 이름이 너무 깁니다.')
            records.append((ptr, rec[5:7], label, rec[-2:])); at += size
            if index in texts:
                row = texts[index]
                value = row['translation_ko'] or row['source_en']
                source_prefix = split_mentat(row['source_en'])[0]
                if source_prefix and not split_mentat(value)[0]:
                    value = source_prefix+value
                decoded = self.encode(value)
                if any(b in decoded for b in (0, 27, 255)):
                    raise ValueError('멘타트 본문에 사용할 수 없는 제어 바이트가 있습니다.')
                value = stored(decoded)
                if ptr in changed_desc and changed_desc[ptr] != value: raise ValueError('공유 멘타트 본문의 번역이 서로 다릅니다.')
                changed_desc[ptr] = value
        new_desc = bytearray(); pointers = {}; at = 0; max_stored = 0; max_expanded = 0
        while at < len(desc):
            end = desc.index(0, at); ptr = old_desc_start+at
            value = changed_desc.get(ptr, desc[at:end]); pointers[ptr] = len(new_desc)
            new_desc += value+b'\0'; at = end+1
            max_stored = max(max_stored, len(value)+1)
            max_expanded = max(max_expanded, len(expand_pairs(value))+1, len(expand_compressed(value))+1)
        name_size = sum(9+len(label) for _, _, label, _ in records)
        sizes = {b'NAME': name_size, b'DESC': len(new_desc), b'INFO': 12}
        pos = 12; desc_start = None
        for kind, _, _ in chunks:
            if kind == b'DESC': desc_start = pos+8
            pos += 8+sizes[kind]+(sizes[kind]&1)
        new_names = bytearray()
        for ptr, code, label, tail in records:
            absolute = desc_start+pointers[ptr]
            new_names += struct.pack('<H', 9+len(label))+absolute.to_bytes(3, 'big')+code+label+tail
        bodies = {b'NAME': new_names, b'DESC': new_desc,
                  b'INFO': struct.pack('>3I', len(records), max_expanded, max_stored)}
        body = bytearray(b'MENT')
        for kind, _, _ in chunks:
            data = bodies[kind]; body += kind+len(data).to_bytes(4, 'big')+data+bytes(len(data)&1)
        return b'FORM'+len(body).to_bytes(4, 'big')+body, dict(records=len(records), expanded=max_expanded, stored=max_stored)

def install_final_tree(source, destination, backup_root):
    """Transactionally replace generated files in the stable final-build directory.

    Keep unrelated files (for example a user-added save) intact. If any file
    replacement fails, restore every file already replaced in this operation.
    """
    source = source.resolve()
    destination = destination.resolve()
    backup_root = backup_root.resolve()
    if not destination.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('최종 빌드 경로가 build/ 밖을 가리킵니다.')
    destination.mkdir(parents=True, exist_ok=True)
    changed = []
    try:
        for item in source.rglob('*'):
            relative = item.relative_to(source)
            if relative.parts[0] in {'assembly', 'translation-snapshot', 'output'}:
                continue
            target = destination/relative
            if not target.resolve().is_relative_to(destination):
                raise ValueError(f'최종 빌드 내부의 링크가 경로를 벗어납니다: {target}')
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if target.is_file():
                backup = backup_root/relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            temporary = target.with_name(target.name+'.publish.tmp')
            try:
                shutil.copyfile(item, temporary)
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
            changed.append((target, backup))
    except Exception:
        for target, backup in reversed(changed):
            if backup is None:
                if target.exists():
                    target.unlink()
            else:
                temporary = target.with_name(target.name+'.restore.tmp')
                shutil.copy2(backup, temporary)
                os.replace(temporary, target)
        raise

def build(self, *, publish=True, original_files=None):
    temp_root = ROOT/'temp'
    temp_root.mkdir(parents=True, exist_ok=True)
    stage_root = Path(tempfile.mkdtemp(prefix='final-build-', dir=temp_root))
    try:
        result = _build_with_stage(self, publish=publish, stage_root=stage_root, original_files=original_files)
    finally:
        # Remove only this invocation's dedicated intermediate directory.
        # Remove this build's scratch data and the temp/ root when it is empty.
        if stage_root.exists():
            if stage_root.resolve().parent != temp_root.resolve():
                raise RuntimeError(f'빌드 임시 경로가 temp/ 밖으로 이동했습니다: {stage_root}')
            shutil.rmtree(stage_root)
        if temp_root.exists() and not temp_root.is_symlink():
            try:
                temp_root.rmdir()
            except OSError:
                pass
    result['temporary_cleaned'] = True
    if not publish:
        result.update(build=None, cd_image=None, xdelta=None, cd_cue=None,
                      message='검토 빌드를 생성했고 temp 작업 자료를 정리했습니다. 최종 빌드에는 게시하지 않았습니다.')
    return result

def _build_with_stage(self, *, publish, stage_root, original_files=None):
    self.unchanged_on_disk()
    changed = [row for row in self.rows if editable(row)]
    self.prepare_syllables()
    self.validate_build(changed)
    english_names, english = unpack_pak((self.game/'ENGLISH.PAK').read_bytes())
    # Preserve the skipped security resource byte-for-byte from the original CD.
    security = runtime_patches.original_security()
    english['PROTECT.ENG'] = security
    dune_names, dune = unpack_pak((self.game/'DUNE.PAK').read_bytes())
    scenario_names, scenario = unpack_pak((self.game/'SCENARIO.PAK').read_bytes())
    grouped = defaultdict(list)
    for row in changed: grouped[row['file']].append(row)
    details = {}
    # DOS messages retain their original CD bytes when the token table changes.
    original_dune = unpack_pak((ROOT/'export/PAK/ENGLISH.PAK').read_bytes())[1]['DUNE.ENG']
    for name, rows in grouped.items():
        raw = scenario[name] if name.startswith('REGION') else english[name]
        if name.startswith('MENTAT'):
            rebuilt, info = self.rebuild_mentat(raw, rows)
            details[name] = info
        elif name.startswith('REGION') or name == 'CREDITS.ENG':
            parts = re.split(b'(\r\n|\r|\n)', raw)
            for row in rows:
                if name == 'CREDITS.ENG' and row['source_en'] == '\0':
                    # This is the file terminator, not a drawable string.
                    # Preserve it in place instead of passing NUL to encode.
                    line = int(row['index'])
                    if parts[line*2] != b'\0':
                        raise ValueError(name+': 원본 파일 종료 데이터가 다릅니다.')
                    continue
                value = self.encode(row['translation_ko'] or row['source_en'])
                if any(b in value for b in (0, 10, 13)): raise ValueError(name+': 줄바꿈 바이트와 충돌합니다.')
                line = int(row['index']) if name == 'CREDITS.ENG' else int(row['index'].rsplit('line', 1)[1])-1
                if name.startswith('REGION'):
                    match = re.fullmatch(rb'(\s*ENGTXT\d+\s*=\s*)(.*?)(\s*)', parts[line*2])
                    if not match: raise ValueError(name+': ENGTXT 행을 찾을 수 없습니다.')
                    parts[line*2] = match[1]+value+match[3]
                else: parts[line*2] = value
            rebuilt = b''.join(parts)
        else:
            count = struct.unpack_from('<H', raw)[0]//2
            offsets = struct.unpack_from('<'+'H'*count, raw)
            values = []
            for i, pos in enumerate(offsets):
                bound = offsets[i+1] if i+1 < count else len(raw)
                end = raw.index(0, pos, bound)
                values.append((raw[pos:end], raw[end+1:bound]))
            for file_name, index in EXCLUDED_ROWS:
                if name == file_name:
                    index = int(index)
                    start = struct.unpack_from('<H', original_dune, index*2)[0]
                    end = original_dune.index(0, start)
                    values[index] = (original_dune[start:end], values[index][1])
            for row in rows:
                value = self.encode(row['translation_ko'] or row['source_en'])
                if name.startswith('TEXT'):
                    if any(b in value for b in (0, 27, 255)):
                        raise ValueError(name+' #'+row['index']+': 압축 문구 안에 사용할 수 없는 제어 바이트가 있습니다.')
                    value = stored(value)
                i = int(row['index']); values[i] = (value, values[i][1])
            body = bytearray(); positions = []
            for value, tail in values:
                positions.append(count*2+len(body)); body += value+b'\0'+tail
            if count*2+len(body) > 65535: raise ValueError(name+': 문자열표 크기가 64KB를 넘습니다.')
            rebuilt = struct.pack('<'+'H'*count, *positions)+body
        if name.startswith('REGION'): scenario[name] = rebuilt
        else: english[name] = rebuilt
    build_root = ROOT/'build'
    build_root.mkdir(parents=True, exist_ok=True)
    out = stage_root/'base'
    out.mkdir()
    try:
        font_package = fonts.build_font(self.syllables, self.glyph_source)
        runtime_exe, runtime_report = cd_source.prepare_runtime(out/'assembly', font_package)
        exe = runtime_patches.apply_question(runtime_exe)
    except Exception:
        (out/'BUILD-INCOMPLETE.txt').write_text('CD 기본 패치 생성에 실패했습니다.', encoding='utf-8')
        raise
    capacities = [(0xB3, 7), (0xBA, 13), (0xC7, 9), (0xD0, 7), (0xD7, 9), (0x154, 5)]
    changed_houses = []
    for house in self.houses:
        raw = self.encode(house['translation_ko'])+b'\0'
        off, capacity = capacities[int(house['house_id'])]
        if len(raw) > capacity:
            raise ValueError(house['source_en']+f': 현재 이름 공간은 {capacity-1}바이트입니다. 더 긴 이름은 별도 엔진 수정이 필요합니다.')
        exe[0x41C20+off:0x41C20+off+capacity] = raw.ljust(capacity, b'\0')
        changed_houses.append(house['house_id'])
    try:
        cd_report = cd_source.extract_source(out/'source', files=original_files)
        game = out/'source/VIRGIN/DUNE2'
        cg_report = runtime_patches.merge_artwork(english, dune, out)
        exe, subtitle_report = scenes.subtitle_patch(bytes(exe), out/'assembly')
        exe, region_report = runtime_patches.region_patch(exe)
        exe, style_report = fonts.style_apply(exe)
        unifont = fonts.intro_build(changed, self.syllables, ROOT)
        exe, font, font_report = fonts.install(bytes(exe), font_package, out/'assembly',
            intro=unifont, new_syllables=self.new_syllables)
        exe, cheat_report = cheats.patch(bytes(exe), out/'assembly')
        features = runtime_patches.verify(exe)
        exe, final_caption_report = scenes.harkonnen_patch(exe, out/'assembly')
        exe, ordos_caption_report = scenes.ordos_patch(exe, out/'assembly')
        exe, invoice_spacing_report = runtime_patches.invoice_patch(exe)
        (game/'DUNE2.EXE').write_bytes(exe)
        # Materialize generated fonts in import/fnt first, then apply those
        # exact bytes to the new game tree.
        generated_fonts = {'DUNEHAN.FNT': font, **unifont['files']}
        font_import = ROOT/'import/fnt'
        font_import.mkdir(parents=True, exist_ok=True)
        for name, data in generated_fonts.items():
            imported = font_import/name
            imported.write_bytes(data)
            applied = imported.read_bytes()
            if applied != data:
                raise ValueError(f'생성 폰트와 import/fnt 파일이 다릅니다: {name}')
            (game/name).write_bytes(applied)
        character_table = fonts.table_bytes(self.syllables)
        (game/'DUNEHAN.TBL').write_bytes(character_table)
        (out/'DUNEHAN.TBL.csv').write_bytes(character_table)
        (out/'DUNEHAN.LATIN.csv').write_bytes(fonts.latin_table_bytes(ROOT, len(self.syllables)))
        (out/'DUNEUNI.TBL.csv').write_bytes(unifont['table'])
        if grouped:
            (game/'ENGLISH.PAK').write_bytes(pack_pak(english_names, english))
            (game/'SCENARIO.PAK').write_bytes(pack_pak(scenario_names, scenario))
            for folder, files in [('ENGLISH.files', english), ('SCENARIO.files', scenario)]:
                if (game/folder).is_dir():
                    for name in grouped:
                        if name in files: (game/folder/name).write_bytes(files[name])
        (game/'DUNE.PAK').write_bytes(pack_pak(dune_names, dune))
        for folder, files in [('ENGLISH.files', english), ('DUNE.files', dune)]:
            if (game/folder).is_dir():
                for name in files:
                    if (game/folder/name).exists():
                        (game/folder/name).write_bytes(files[name])
        report = dict(translation_source=str(DRAFT), written_rows=[row_key(r) for r in changed],
                      original_security_sha256=hashlib.sha256(security).hexdigest(),
                      changed_houses=changed_houses, mentat_info=details, font_build=font_report,
                      exe_sha256=digest(game/'DUNE2.EXE'), game_execution='not run',
                      runtime_features=features, cg=cg_report,
                      harkonnen_second_scene=final_caption_report,
                      ordos_second_scene=ordos_caption_report,
                      choam_invoice_spacing=invoice_spacing_report,
                      subtitle_tokens=subtitle_report,
                      region_ini_tokens=region_report,
                      font_styles=style_report,
                      extra_cheats=cheat_report,
                      source_cd=cd_report, runtime_source=runtime_report, previous_build_required=False,
                      build_profile='Dalmoori two-byte Hangul and scoped Latin; Unifont opening/ending in XMS; FASTBUILD and REVEAL cheats',
                      unifont_intro=unifont['report'])
        assembly = assembler.build_report()
        if assembly['compilations']:
            report['assembly_compiler'] = assembly
        (out/'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        (out/'BUILD-INCOMPLETE.txt').write_text('생성 도중 오류가 발생했습니다. 이 폴더는 실행하지 마세요.', encoding='utf-8')
        raise
    fixed_out = stage_root/'hitsquad107'
    try:
        import apply_hitsquad107_fix
        import clonecd_xdelta
        apply_hitsquad107_fix.apply_build(out, fixed_out, translation_rows=self.rows)
        staged_output = fixed_out/'output'
        cd_manifest = clonecd_xdelta.create_patch(
            ROOT/'img', fixed_out/'source/VIRGIN/DUNE2', staged_output,
            patch=staged_output/clonecd_xdelta.PATCH.name,
            manifest_path=staged_output/clonecd_xdelta.MANIFEST.name)
    except Exception:
        (out/'BUILD-INCOMPLETE.txt').write_text(
            'HitSquad/CD 패치 생성 중 오류가 발생했습니다. 이 폴더는 최종 빌드가 아닙니다.',
            encoding='utf-8')
        if fixed_out.is_dir():
            (fixed_out/'BUILD-INCOMPLETE.txt').write_text(
                'CD 패치 생성 중 오류가 발생했습니다. 이 폴더는 최종 빌드가 아닙니다.',
                encoding='utf-8')
        raise
    self.unchanged_on_disk()
    if publish:
        stable_out = build_root/'final-build'
        install_final_tree(fixed_out, stable_out, stage_root/'rollback')
        # Publish the installed game location rather than the staging path,
        # which is deleted when this build finishes.
        cd_manifest['game_dir'] = str((stable_out/'source/VIRGIN/DUNE2').resolve())
        (staged_output/clonecd_xdelta.MANIFEST.name).write_text(
            json.dumps(cd_manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        output_dir = ROOT/'output'
        output_dir.mkdir(exist_ok=True)
        for path in staged_output.iterdir():
            temporary = output_dir/(path.name+'.tmp')
            shutil.copyfile(path, temporary)
            os.replace(temporary, output_dir/path.name)
        latest = dict(build=str(stable_out.relative_to(ROOT)), source_cd_sha256=cd_source.IMAGE_SHA256)
        (ROOT/'build/latest-build.json').write_text(json.dumps(latest, indent=2)+'\n', encoding='utf-8')
        registry_temp = REGISTRY.with_suffix('.json.tmp')
        registry_temp.write_bytes(registry_bytes(self.syllables))
        os.replace(registry_temp, REGISTRY)
        fixed_out = stable_out
    else:
        output_dir = staged_output
    return dict(build=str(fixed_out), game_dir=str(fixed_out/'source/VIRGIN/DUNE2'), changed=len(changed),
                added_syllables=font_report['added_syllables'], syllable_count=len(self.syllables),
                font_sha256=font_package['sha256'],
                game_file_sha256={path.name: digest(path) for path in (fixed_out/'source/VIRGIN/DUNE2').iterdir() if path.is_file()},
                resident_increase_bytes=font_report['resident_increase_bytes'],
                cheat_resident_bytes=cheat_report['extra_resident_bytes'],
                unifont_glyphs=unifont['report']['glyph_count'],
                cd_image=str(output_dir/'Dune2-Battle-for-Arrakis-Korean-v1.01.bin'),
                xdelta=str(output_dir/'Dune2-Battle-for-Arrakis-Korean-v1.01.bin.xdelta'),
                cd_cue=str(output_dir/'Dune2-Battle-for-Arrakis-Korean-v1.01.cue'),
                cd_sha256=cd_manifest['target_bin_sha256'],
                published=publish, message='원본 CD 기반 최종 게임 빌드와 BIN/CUE·Xdelta를 생성했습니다.')

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-publish', action='store_true', help='Do not update final-build or output; temporary files are deleted on exit')
    parser.add_argument('--result-json', type=Path)
    args = parser.parse_args()
    import cd_source
    originals = cd_source.prepare_exports()
    cd_source.prepare_build_references()
    import assembler
    data = BuildInputs()
    with data.save_lock():
        data.reload()
        with assembler.build_context():
            result = build(data, publish=not args.no_publish, original_files=originals)
    if args.result_json:
        args.result_json.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
