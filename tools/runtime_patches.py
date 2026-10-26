"""Final game screen patches, shared overlay access and feature checks."""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# English editable rows: Atreides, Ordos, Harkonnen. Native house IDs are
# Harkonnen=0, Atreides=1, Ordos=2: select rows 2,0,1 respectively.
QUESTION_START, QUESTION_END = 0x1398, 0x13E7
QUESTION_OLD = bytes.fromhex(
    '33c050b8020050b8180050b81a005033c05033c05033c05033c050'
    '9a0700600183c41033c050b8020050b8180050b80d005033c050b81a0050'
    '8bc6ba1800f7ea0518005033c0509a0700600183c410')
QUESTION_FIRST = bytes.fromhex('6bc6180430d4489833d23916aa377413526a026a186a1a52525252')
QUESTION_SECOND = bytes.fromhex(
    '6a006a026a1833d23916aa37740d6bc618'
    '6a0d526a1a83c018eb046a2752525052' + '90'*3)
QUESTION_NEW = (QUESTION_FIRST + QUESTION_OLD[0x13B3-QUESTION_START:0x13BB-QUESTION_START]
                + QUESTION_SECOND + QUESTION_OLD[0x13DF-QUESTION_START:])
PALETTE_GUARD = bytes.fromhex('a1b2384874060ee8a703eb55')


def original_security():
    """Keep the unedited security resource byte-for-byte from the original game."""
    from resources import unpack_pak

    original = ROOT/'export/PAK/ENGLISH.PAK'
    return unpack_pak(original.read_bytes())[1]['PROTECT.ENG']


def module_at(exe, segment):
    header = struct.unpack_from('<H', exe, 8)[0]*16
    last, pages = struct.unpack_from('<HH', exe, 2)
    overlay = (pages-1)*512+(last or 512)
    if exe[overlay:overlay+4] != b'FBOV':
        raise ValueError('게임의 FBOV 오버레이 헤더를 찾을 수 없습니다.')
    stub = header+segment*16
    relative, size = struct.unpack_from('<IH', exe, stub+4)
    at = overlay+16+relative
    if not 0 < size <= len(exe)-at:
        raise ValueError('게임의 FBOV 모듈 범위가 다릅니다.')
    return at


def apply_question(exe):
    exe = bytearray(exe)
    start = module_at(exe, 0x3314)+QUESTION_START
    if exe[start:start+len(QUESTION_OLD)] != QUESTION_OLD:
        raise ValueError('가문 질문의 원본 복사 호출 구조가 다릅니다.')
    if len(QUESTION_NEW) != len(QUESTION_OLD):
        raise ValueError('가문 질문 패치 길이가 다릅니다.')
    exe[start:start+len(QUESTION_NEW)] = QUESTION_NEW
    return exe


def merge_artwork(english, dune, output):
    """Merge selected image members, preserving all translated text members."""
    from edit_cg import encode_project
    from resources import unpack_pak

    project = ROOT/'import/GFX'
    baseline = ROOT/'export/GFX'
    report = encode_project(project, output/'cg-assets', baseline=baseline)
    targets = {'ENGLISH.PAK': english, 'DUNE.PAK': dune}
    for archive in report['archives']:
        if archive['pak'] not in targets:
            raise ValueError('허용되지 않은 CG PAK입니다: '+archive['pak'])
        _, encoded = unpack_pak((output/'cg-assets'/archive['pak']).read_bytes())
        for name in archive['changed_members']:
            targets[archive['pak']][name] = encoded[name]
    manifest = json.loads((baseline/'manifest.json').read_text(encoding='utf-8'))
    image_hashes = {frame['path']: hashlib.sha256((project/frame['path']).read_bytes()).hexdigest()
                    for record in manifest['resources'] for frame in record['frames']}
    report['input_png_sha256'] = image_hashes
    report['house_question_layout'] = 'ENG rows: Atreides, Ordos, Harkonnen; native IDs 0/1/2 select rows 2/0/1; FRE/GER original copies'
    return report


def verify(exe):
    mentat = module_at(exe, 0x32DD)
    question = module_at(exe, 0x3314)+QUESTION_START
    # Overlay addresses follow font expansion; resident palette guard does not.
    checks = {
        'pending_briefing_preserves_fade': exe[0x9258:0x9264] == PALETTE_GUARD,
        'security_scene_skipped': exe[mentat+0x10AA:mentat+0x10B3]
            == bytes.fromhex('c746e00100e9060690'),
        'first_description_delay_removed': exe[mentat+0x0BD8:mentat+0x0BDB] == bytes.fromhex('83c200'),
        'english_house_question_three_rows': exe[question:question+len(QUESTION_NEW)] == QUESTION_NEW,
    }
    last, pages = struct.unpack_from('<HH', exe, 2)
    overlay = (pages-1)*512+(last or 512)
    original_end = 0x44580
    subtitle = 0x54051+overlay-original_end
    checks['english_subtitles_with_voice'] = exe[subtitle:subtitle+2] == b'\x90\x90'
    import fonts
    checks.update({'font_styles_'+name: value for name,value in fonts.style_verify(exe).items()})
    checks['hall_csv_house_names']=hall_verify(exe)
    checks['region_ini_unsigned_whitespace']=region_verify(exe)
    if not all(checks.values()):
        raise ValueError('최종 빌드 기능 보존 검사 실패: '+', '.join(k for k,v in checks.items() if not v))
    return dict(source_exe='export/DUNE2.EXE',
                source_exe_sha256=hashlib.sha256((ROOT/'export/DUNE2.EXE').read_bytes()).hexdigest(),
                checked_patches=checks,
                inherited_features=['달무리 한글·부호', '치트·게임 중 Enter 제한',
                    '원본 멘타트 출력·INFO 길이', '메뉴·설명 간격·테두리',
                    '대문자 단축키·원본 괄호', '영어 자막·음성',
                    '보안 질문 생략·페이드 전환', 'CG 편집 반영·가문 질문 세 줄'])


# Hall of Fame display-name lookup.
HALL_START,HALL_END=0x1322,0x1331
HALL_OLD=bytes.fromhex('ba1e00f7ea8bd8ffb7ee37ffb7ec37')

def hall_assembly():
    # Return with the two original source-pointer arguments on the caller's
    # stack. The following original strcat call consumes them as before.
    return '''HallHouseName PROC NEAR
    push cs
    call ExistingHouseDisplay
    pop bx
    pop cx
    push ax
    push dx
    push cx
    push bx
    retf
HallHouseName ENDP
'''

def hall_patch(exe,entry):
    new=bytearray(exe);at=module_at(exe,0x331B)+HALL_START
    if new[at:at+len(HALL_OLD)]!=HALL_OLD:raise ValueError('Hall house-name source differs from the original row builder.')
    # An FBOV overlay cannot receive an ordinary new MZ relocation. Derive
    # the resident extension segment from the original DS, as existing Latin
    # owner gateways already do, retaining the actual overlay CS on return.
    code=bytes.fromhex('0e68')+struct.pack('<H',HALL_END)+bytes.fromhex('8cda81c2c0095268')+struct.pack('<H',entry)+b'\xcb'
    assert len(code)==len(HALL_OLD)
    new[at:at+len(HALL_OLD)]=code
    return bytes(new),dict(segment='0x331B',offset=hex(HALL_START),file_offset=hex(at),
        bytes_before=HALL_OLD.hex(),bytes_after=code.hex(),helper_entry=entry,
        house_source='executable_house_names.csv via existing 3D02:03FE lookup',
        source_pointer_stack_preserved=True,savefame_format_unchanged=True,
        new_DOS_or_XMS_allocations=0)

def hall_verify(exe):
    at=module_at(exe,0x331B)+HALL_START
    code=exe[at:at+15]
    assert code[:12]==bytes.fromhex('0e6831138cda81c2c0095268') and code[14:]==b'\xcb'
    entry=struct.unpack_from('<H',code,12)[0]
    helper=exe[0x41C20+entry:0x41C20+entry+11]
    assert helper[:2]==bytes.fromhex('0ee8') and helper[4:]==bytes.fromhex('5b5950525153cb')
    assert (entry+4+struct.unpack_from('<h',helper,2)[0])&0xFFFF==0x3FE
    return True


# CHOAM invoice row and divider spacing.
INVOICE_SEGMENT, INVOICE_OFFSET = 0x3298, 0x646
INVOICE_ORIGINAL = bytes.fromhex('83c6088346fc0b47')


def invoice_patch(exe):
    module = module_at(exe, INVOICE_SEGMENT)
    at = module+INVOICE_OFFSET
    if exe[at:at+len(INVOICE_ORIGINAL)] != INVOICE_ORIGINAL:
        raise ValueError('CHOAM 주문 내역의 원본 행 증가 코드가 다릅니다.')
    new = bytearray(exe)
    new[at+2] = 9
    # SI=48 at the header. Draw its horizontal divider at 48+8 instead of
    # 48+7, then advance by one instead of two to keep the first row at 57.
    if exe[module+0x57B:module+0x57E] != bytes.fromhex('83c607'):
        raise ValueError('CHOAM 품목명 구분선의 원본 Y 계산이 다릅니다.')
    if exe[module+0x599:module+0x59C] != bytes.fromhex('83c602'):
        raise ValueError('CHOAM 첫 품목 행의 원본 Y 계산이 다릅니다.')
    new[module+0x57D] = 8
    new[module+0x59B] = 1
    assert len(new) == len(exe)
    assert [i for i,(a,b) in enumerate(zip(exe,new)) if a!=b] == [module+0x57D,module+0x59B,at+2]
    return bytes(new), dict(
        scope='CHOAM invoice rows and header divider only',
        overlay_segment='3298', instruction_offset='0646',
        file_offset=at+2, before=8, after=9, changed_bytes=3,
        first_row_y=57, header_y=48, extra_row_spacing_pixels=1,
        divider_y_before=55,divider_y_after=56,
        divider_instruction_offset='057B',first_row_compensation_offset='0599',
        original_first_row_and_columns_preserved=True,
        source_exe_sha256=hashlib.sha256(exe).hexdigest(),
        resident_increase_bytes=0, extra_DOS_allocations=0, extra_XMS_allocations=0,
        game_execution='not run')


# Unsigned INI whitespace indexing for two-byte font tokens.
REGION_SEGMENT=0x32FF
# Every CBW/MOV BX,AX preceding a ctype whitespace lookup in INI_GetString
# and its trim helper. Ctype has 256 entries; font bytes must index 0..255.
REGION_SITES=(0x4D8,0x5F7,0x67F,0x825,0x85A)
REGION_OLD=bytes.fromhex('988bd8')
REGION_NEW=bytes.fromhex('0fb6d8')  # MOVZX BX,AL; same three bytes of code space

def region_patch(exe):
    new=bytearray(exe);base=module_at(exe,REGION_SEGMENT);changes=[]
    for offset in REGION_SITES:
        at=base+offset
        if new[at:at+3]!=REGION_OLD:raise ValueError(f'Original INI ctype index differs at {offset:04X}')
        new[at:at+3]=REGION_NEW
        changes.append(dict(segment=hex(REGION_SEGMENT),offset=hex(offset),file_offset=hex(at),
                            bytes_before=REGION_OLD.hex(),bytes_after=REGION_NEW.hex()))
    return bytes(new),dict(unsigned_ctype_index=True,token_bytes_unchanged=True,
        source_changes=changes,resident_increase_bytes=0,new_memory_allocations=0)

def region_verify(exe):
    at=module_at(exe,REGION_SEGMENT)
    return all(exe[at+offset:at+offset+3]==REGION_NEW for offset in REGION_SITES)
