"""Build Dalmoori/Unifont glyphs and apply the original game's font styles.

The sorted two-byte table, Latin owner scopes, native intro FNT pages and
style patches share one implementation. Game layout and ASM bytes are kept
unchanged. Character metadata is provided by translation_data.
"""
from __future__ import annotations

import csv
import hashlib
import io
import struct
import unicodedata
from pathlib import Path

from translation_data import (LEADS, TRAIL_COUNT, token, load_glyphs,
                              load_syllables, LEGACY_GLYPH_SLOTS,
                              load_latin_records)
import runtime_patches
from runtime_patches import module_at

ROOT = Path(__file__).resolve().parents[1]
_encode_token = token

# Completed Dalmoori font and native resident layout

# Original Dune fonts end at slot E1h. FAh remains the original middle-dot
# symbol. Both token bytes stay above ASCII and below FFh, so resource
# delimiters, formatting codes and compression escapes cannot split a token.
INLINE_SYLLABLE_SLOTS = 639
SYMBOL_COUNT = 33
INLINE_GLYPH_SLOTS = 672
MODULE_FILE = 0x41C20
MODULE_SEG = 0x3D02
MODULE_SIZE = 0x1FD0
HEADER = 0x4C00




def glyph_index(syllable_index):
    # ASCII punctuation resolves to the verified fixed slots 639..671.
    return syllable_index + (SYMBOL_COUNT if syllable_index >= INLINE_SYLLABLE_SLOTS else 0)






def table_bytes(syllables):
    """Describe the current complete registered syllable table."""
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['syllable_index', 'glyph_index', 'character', 'unicode', 'token_hex', 'kind'])
    for index, char in enumerate(syllables):
        writer.writerow([index, glyph_index(index), char, f'U+{ord(char):04X}',
                         token(index).hex().upper(), 'registered_syllable'])
    return out.getvalue().encode('utf-8-sig')


def build_font(syllables, glyphs):
    """Generate the completed FNT once from the unified registered table.

    Slots 639..671 are the native renderer's fixed symbol ABI. They are not
    a separate initial character list or an intermediate font.
    """
    if list(syllables) != sorted(set(syllables)):
        raise ValueError('한글 문자표는 중복 없이 가나다순이어야 합니다.')
    if len(syllables) < INLINE_SYLLABLE_SLOTS:
        raise ValueError('등록 한글 문자표가 고정 글리프 구간보다 작습니다.')
    missing = set(syllables)-glyphs.keys()
    if missing:
        raise ValueError('달무리 HEX에 등록 음절이 없습니다: '+''.join(sorted(missing)))
    latin = latin_package(ROOT, len(syllables))
    token(len(syllables)+len(latin['symbols'])-1)
    total = len(syllables)+SYMBOL_COUNT+latin['added_count']
    syllable_records = [struct.pack('<H', glyph_index(i))+glyphs[ch]
                        for i, ch in enumerate(syllables)]
    symbols = b''.join(struct.pack('<H', slot)+bytes.fromhex(latin['source_records'][cp]['rows'])
                       for cp, slot in sorted(LEGACY_GLYPH_SLOTS.items(), key=lambda item: item[1]))
    header = struct.pack('<8s8H', b'D2DHAN2\0', 1, 8, 8, total, 10, 0, 0, 0xffff)
    font = (header+b''.join(syllable_records[:INLINE_SYLLABLE_SLOTS])+symbols+
            b''.join(syllable_records[INLINE_SYLLABLE_SLOTS:])+latin['records'])
    prefix_bytes = 24+INLINE_GLYPH_SLOTS*10
    if len(font) != 24+total*10 or len(symbols) != SYMBOL_COUNT*10:
        raise ValueError('완성 FNT의 레코드 크기가 다릅니다.')
    return dict(font=font, prefix=font[:prefix_bytes], records=font[prefix_bytes:],
                syllables=tuple(syllables), total_glyphs=total, latin=latin,
                sha256=hashlib.sha256(font).hexdigest())


def install(exe, package, assembly_folder, *, intro=None, new_syllables=()):
    """Construct final font hooks and the cheat module from the completed FNT."""
    font = package['font']
    syllables = package['syllables']
    latin = package['latin']
    total = package['total_glyphs']
    records = package['records']
    module = bytearray(exe[MODULE_FILE:MODULE_FILE+MODULE_SIZE])
    fixed_gateway = HEADER+0x2326*16+0x18
    if exe[fixed_gateway:fixed_gateway+5] != bytes.fromhex('eae01e023d'):
        raise ValueError('고정 간격 출력의 검증된 진입점이 다릅니다.')
    if module[0x480:0x480+len(package['prefix'])] != package['prefix']:
        raise ValueError('폰트 후크에 완성 FNT의 동일한 레코드가 적용되지 않았습니다.')
    if hashlib.sha256(font).hexdigest() != package['sha256']:
        raise ValueError('완성 FNT가 생성 이후 변경되었습니다.')
    # The suffix-aware key mapper must recognize the same lead range.
    if module[0xF4:0xF7] != bytes.fromhex('80FBF8'):
        raise ValueError('단축키 한글 판별 코드가 기준과 다릅니다.')
    module[0xF6] = LEADS[0]

    # Append helpers after the existing module, preserving every later menu,
    # shortcut, layout and cheat patch in the verified binary.
    source = r'''.386
KOREAN SEGMENT PARA PUBLIC USE16 'CODE'
ASSUME CS:KOREAN
ORG 0
LatinSegmentZero LABEL BYTE
OriginalByteWidth LABEL NEAR
ORG 00B0h
ExistingWidth LABEL NEAR
ORG 0182h
ExistingSymbol LABEL NEAR
ORG 01CCh
DrawContinue LABEL NEAR
ORG 03FEh
ExistingHouseDisplay LABEL NEAR
ORG 1FA0h
ExistingSymbolWidth LABEL NEAR
ORG 1EE0h
ExistingFixedPitch LABEL NEAR
ORG 1FD0h
Reader PROC NEAR
    push cx
    push di
    xor ax, ax
    mov al, byte ptr es:[bx]
    cmp al, 0E2h
    jb Single
    cmp al, 0FEh
    ja Single
    cmp al, 0FAh
    je Single
    xor cx, cx
    mov cl, byte ptr es:[bx+1]
    cmp cx, 80h
    jb Single
    cmp cx, 0FEh
    ja Single
    sub al, 0E2h
    cmp al, 24
    jb PageReady
    dec al
PageReady:
    sub cx, 80h
    mov di, cx
    mov cx, 127
    mul cx
    add ax, di
    cmp ax, SYLLABLE_COUNT
    jb HangulRank
    cmp ax, TOKEN_COUNT
    jae Single
    sub ax, SYLLABLE_COUNT
    mov di, ax
    shl di, 1
    mov ax, word ptr cs:[LatinSymbolTokens+di-LatinSegmentZero]
    jmp SyllableReady
HangulRank:
    cmp ax, 639
    jb SyllableReady
    add ax, 33
SyllableReady:
    add ax, 0100h
    mov dx, 2
    jmp ReaderDone
Single:
    xor ax, ax
    mov al, byte ptr es:[bx]
    mov dx, 1
ReaderDone:
    pop di
    pop cx
    ret
Reader ENDP
NewWidth PROC NEAR
    call MapLatin
    cmp ax, 0100h
    jb NewWidthFontDispatch
    push ax
    sub ax, 0100h
    call IsLatinGlyph
    pop ax
    jc LatinCellWidth
NewWidthFontDispatch LABEL NEAR
    cmp ax, 0100h+672
    jb ExistingSymbolWidth
    mov ax, 10
    add ax, word ptr ds:[6CF8h]
    ret
LatinCellWidth:
    mov ax, 6
    add ax, word ptr ds:[6CF8h]
    ret
NewWidth ENDP
Previous PROC FAR
    call Reader
    call ExistingWidth
    sub si, ax
    push ax
    push dx
    push bx
    sub bx, 2
    call Reader
    cmp dx, 2
    pop bx
    je BackTwo
    dec bx
    jmp PreviousDone
BackTwo:
    sub bx, 2
PreviousDone:
    pop dx
    pop ax
    retf
Previous ENDP
DrawRecord PROC NEAR
    mov byte ptr cs:[0446h], 10
    cmp ax, LATIN_GLYPH_START
    jb DrawRecordOldKind
    mov byte ptr cs:[0446h], 6
DrawRecordOldKind:
    cmp ax, 672
    jae ExtraRecord
    cmp ax, 639
    jb OldRecord
    mov byte ptr cs:[0446h], 6
OldRecord:
    mov dx, 10
    mul dx
    add ax, 049Ah
    jmp RecordReady
ExtraRecord:
    sub ax, 672
    mov dx, 10
    mul dx
    add ax, EXTRA_RECORDS+2
RecordReady:
    mov si, ax
    jmp DrawContinue
DrawRecord ENDP
HelperEnd LABEL BYTE
KOREAN ENDS
END
'''
    latin_source = (Path(__file__).resolve().parents[1]/'import/asm/font/dalmoori-latin-hook.asm').read_text(encoding='ascii')
    source = source.replace('HelperEnd LABEL BYTE', latin_source+'\n'
                            +latin_scope_assembly()+'\n'+latin['declarations']+'\n'
                            +runtime_patches.hall_assembly()+'\nHelperEnd LABEL BYTE')
    if intro is not None:
        source = intro_instrument(source, intro)
    import assembler
    assembler.ASM = Path(assembly_folder)
    assembler.ASM.mkdir(parents=True, exist_ok=True)

    def assemble(data_offset):
        defines = (f'SYLLABLE_COUNT EQU {len(syllables)}\nEXTRA_RECORDS EQU {data_offset}\n'
                   f'TOKEN_COUNT EQU {len(syllables)+len(latin["symbols"])}\n'
                   f'LATIN_GLYPH_START EQU {latin["glyph_start"]}\n')
        if intro is not None:
            defines += (f'UNI_XMS_KIB EQU {(intro["xms_bytes"]+1023)//1024}\n'
                        f'UNI_FILE_COUNT EQU {intro["file_count"]}\n')
        return assembler.assemble(defines+source, 'automatic-syllable-helpers')

    helpers = assemble(0)
    record_offset = (len(helpers)+15) & ~15
    helpers = assemble(record_offset)
    new_size = (record_offset+len(records)+15) & ~15
    if new_size > 0xFFF0:
        raise ValueError('추가 음절이 DOS 단일 글리프 세그먼트의 64KB 범위를 초과합니다.')
    # Find named entries from the assembler listing, avoiding fixed helper
    # offsets that depend on branch sizes or the number of new syllables.
    import re
    listing = (assembler.ASM/'automatic-syllable-helpers.lst').read_text(encoding='ascii', errors='replace')
    def address(label):
        found = re.search(r'^\s*([0-9A-Fa-f]{4,8})\s+.*\b'+label+r'\s+PROC\b', listing, re.M)
        if not found:
            raise ValueError('자동 음절 코드의 진입점을 찾지 못했습니다: '+label)
        return int(found[1], 16)
    def jump(at, target, expected):
        if bytes(module[at:at+len(expected)]) != expected:
            raise ValueError(f'기준 글리프 코드가 예상과 다릅니다: {at:04X}')
        module[at:at+3] = b'\xE9'+struct.pack('<h', (target-(at+3)+32768)%65536-32768)
    jump(0x40, address('Reader'), bytes.fromhex('515733C0'))
    jump(0xB0, address('NewWidth'), bytes.fromhex('E9ED1E'))
    jump(0x100, address('Previous'), bytes.fromhex('E83DFF'))
    jump(0x1B1, address('DrawRecord'), bytes.fromhex('2EC60646040A'))
    if intro is not None:
        if module[0x3D3:0x3DC] != bytes.fromhex('83C402071F619D5DCB'):
            raise ValueError('원본 글리프 복귀 프레임이 다릅니다.')
        jump(0x182, address('IntroSymbol'), bytes.fromhex('3D2800'))
        jump(0x16E, address('LatinEffectiveY'), bytes.fromhex('8B460A2E803E42040A75050BC07401488946E8C3'))
    if module[0x1EFF:0x1F04] != bytes.fromhex('C746FE0000'):
        raise ValueError('고정 간격 출력의 문자 버퍼 배치가 다릅니다.')
    if module[0x1AA:0x1AD] != bytes.fromhex('3DA002'):
        raise ValueError('기준 글리프 개수 비교 코드가 다릅니다.')
    struct.pack_into('<H', module, 0x1AB, total)
    struct.pack_into('<H', module, 0x48E, total)
    module.extend(helpers[MODULE_SIZE:])
    module.extend(bytes(record_offset-len(module)))
    module.extend(records)
    module.extend(bytes(new_size-len(module)))

    last, pages = struct.unpack_from('<HH', exe, 2)
    old_end = (pages-1)*512+(last or 512)
    old_cheat_seg = MODULE_SEG+MODULE_SIZE//16
    new_cheat_seg = MODULE_SEG+len(module)//16
    cheat_source = (Path(__file__).resolve().parents[1]/'import/asm/cheat/cheat-hook-build.asm').read_text(encoding='ascii')
    def cheat(segment, source=cheat_source):
        text = source.replace('HOOK_SEGMENT_ID EQU 3D64h', f'HOOK_SEGMENT_ID EQU {segment:04X}h')
        text = text.replace('STACK_SEGMENT_ID EQU 3DFDh', f'STACK_SEGMENT_ID EQU {segment+0x99:04X}h')
        return assembler.assemble(text, f'font-cheat-{segment:04X}', 0x990)
    # The code template ends after its font module. The cheat is assembled
    # once at the final segment after all font code/data sizes are known.
    if old_end != MODULE_FILE+MODULE_SIZE or exe[old_end:old_end+4] != b'FBOV':
        raise ValueError('완성 폰트 코드 템플릿의 MZ 경계가 다릅니다.')
    new_cheat = cheat(new_cheat_seg)
    new_end = MODULE_FILE+len(module)+len(new_cheat)
    new = bytearray(exe[:MODULE_FILE]+bytes(module)+new_cheat+exe[old_end:])
    reloc_at = struct.unpack_from('<H', exe, 0x18)[0]
    reloc_count = struct.unpack_from('<H', exe, 6)[0]
    sites = []
    for i in range(reloc_count):
        off, seg = struct.unpack_from('<HH', exe, reloc_at+i*4)
        at = HEADER+seg*16+off
        if struct.unpack_from('<H', exe, at)[0] == old_cheat_seg:
            struct.pack_into('<H', new, at, new_cheat_seg)
            sites.append(at)
    if len(sites) != 5 or len(new_cheat) != 0x990 or new[new_end:] != exe[old_end:]:
        raise ValueError('FNT 확장 후 치트·스택·오버레이 배치가 기준과 다릅니다.')
    struct.pack_into('<HH', new, 2, new_end%512, (new_end+511)//512)
    scope_entries = {name: address(name) for name, *_ in LATIN_SCOPES}
    new, scope_changes = latin_patch_scopes(bytes(new), scope_entries)
    new, hall_report = runtime_patches.hall_patch(new,address('HallHouseName'))
    # Reuse the existing relocated resident gateway; only its target offset changes.
    new = bytearray(new)
    single_width = HEADER+0x2326*16+9
    if new[single_width:single_width+5] != bytes.fromhex('ea0000023d'):
        raise ValueError('원본 단일 문자 폭 게이트웨이가 다릅니다.')
    struct.pack_into('<H', new, single_width+1, address('LatinSingleWidth'))
    report = dict(
        added_syllables=''.join(sorted(set(new_syllables))), added_count=len(set(new_syllables)), total_glyphs=total,
        font_bytes=len(font), resident_increase_bytes=new_end-(MODULE_FILE+MODULE_SIZE+0x990),
        module_bytes=len(module), cheat_segment=hex(new_cheat_seg), stack_segment=hex(new_cheat_seg+0x99),
        completed_font_sha256=package['sha256'], completed_font_generated_once=True,
        initial_font_generated=False, initial_character_table_required=False,
        cheat_assembled_at_final_segment=True,
        input_cheat_validation='assembled once from source at the final font-module segment',
        separate_DOS_allocations=0, overlay_bytes_preserved=False,
        overlay_bytes_preserved_except_latin_scope_entries=True,
        syllable_count=len(syllables), token_bytes=2, sorted_syllables=True,
        token_capacity=len(LEADS)*TRAIL_COUNT, token_reassigned=True,
        hangul_token_capacity=len(LEADS)*TRAIL_COUNT-len(latin['symbols']),
        symbol_token_count=len(latin['symbols']),
        helper_entries={label: address(label) for label in ('Reader', 'NewWidth', 'Previous', 'DrawRecord')},
        token_format='Hangul sorted by Unicode from E280, followed by 23 non-ASCII symbols; ASCII stays one byte',
        fixed_pitch_original_two_byte_buffer_preserved=True)
    report['latin'] = dict(added_glyphs=latin['added_count'],
        translated_text_detection='valid Hangul tokens in the original owner input string',
        ASCII_bytes_preserved=True, format_and_shortcut_bytes_preserved=True,
        space_uses_original_width=True, cell_width=6, bitmap_size='8x8',
        intro_Latin_baseline_offset=8,
        glyph_start=latin['glyph_start'], symbols=latin['symbols'],
        slots={str(cp): slot for cp, slot in latin['slots'].items()},
        scope_changes=scope_changes)
    report['hall_house_names']=hall_report
    report['helper_entries'].update(scope_entries)
    report['helper_entries'].update({name: address(name) for name in
        ('MapLatin', 'DetectLatinString', 'LatinSingleWidth')})
    # The listing data definition is also available before its symbol-table row.
    mode_code = re.search(r'^\s*([0-9A-F]{4,8})\s+.*?\bLatinMode\s+dw\s+0', listing, re.M)
    if not mode_code:
        raise ValueError('달무리 문자열 상태 주소를 찾지 못했습니다.')
    report['latin']['mode_offset'] = int(mode_code[1], 16)
    if intro is not None:
        report['unifont_xms_bytes'] = intro['xms_bytes']
        report['unifont_font_data_resident_bytes'] = 0
        report['helper_entries'].update({name: address(name)
            for name in ('IsIntroFont', 'IntroSymbol', 'IntroDraw', 'EnsureUniFont', 'UniMoveBlock')})
    return bytes(new), font, report


# Latin glyphs and native string scopes

# Preserve the original DUNEHAN.FNT slots 639..671 for its 33 fixed glyphs.




def latin_package(root, syllable_count):
    records = load_latin_records(root)
    start = syllable_count+33
    added = sorted(cp for cp, r in records.items() if r['added'])
    slots = {cp: (start+added.index(cp) if r['added'] else r['glyph_index'])
             for cp, r in records.items()}
    extra = b''.join(struct.pack('<H', slots[cp])+bytes.fromhex(records[cp]['rows'])
                     for cp in added)
    lookup = [0xFFFF]*256
    for cp, slot in slots.items():
        if cp == 32:  # Preserve the existing word-space advance.
            continue
        try:
            raw = chr(cp).encode('cp437')
        except UnicodeEncodeError:
            continue
        lookup[raw[0]] = 0x100+slot
    symbols = sorted(cp for cp in records if cp > 127)
    declarations = ['LatinMode dw 0', 'LatinFixedDepth dw 0', 'LatinLookup LABEL WORD']
    declarations += ['    dw '+','.join(f'{v:05X}h' for v in lookup[i:i+16])
                     for i in range(0, 256, 16)]
    declarations += ['LatinSymbolTokens LABEL WORD',
                     '    dw '+','.join(str(slots[cp]) for cp in symbols)]
    return dict(records=extra, added_count=len(added), glyph_start=start,
                symbols=symbols, slots=slots, declarations='\n'.join(declarations),
                source_records=records)


def latin_table_bytes(root, syllable_count):
    data = latin_package(root, syllable_count)
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['character', 'unicode', 'glyph_index', 'input', 'cell_width'])
    for cp, slot in sorted(data['slots'].items()):
        encoded = (_encode_token(syllable_count+data['symbols'].index(cp)).hex().upper()
                   if cp > 127 else f'ASCII {cp:02X}')
        writer.writerow([chr(cp), f'U+{cp:04X}', slot, encoded,
                         'original space width' if cp == 32 else 6])
    return out.getvalue().encode('utf-8-sig')


# Complete, position-independent instruction prefixes from the confirmed
# runtime. Original bodies, loops, return values and argument order remain.
LATIN_SCOPES = (
    ('LatinWidthScope', 0x2326, 0x002F, 2, '558bec83ec02565733f6ff7608'),
    ('LatinTextScope', 0x29C7, 0x0004, 6, '558bec83ec0a50535152065756'),
    ('LatinWrapScope', 0x0EED, 0x01B8, 4, '558bec565733ff8b46060b4608'),
    ('LatinDescriptionScope', 0x32DD, 0x1893, 3, '558bec83ec02565733ffc746fe0000'),
    ('LatinFixedScope', 0x3298, 0x0854, 7, 'e92a0083ec02568b760aa18018'),
)


def latin_scope_assembly():
    result = []
    for name, segment, offset, argc, raw in LATIN_SCOPES:
        fixed = name == 'LatinFixedScope'
        result += [f'{name} PROC NEAR', '    pop ax',
                   f'    pop word ptr cs:[{name}Continue+2-LatinSegmentZero]',
                   '    push bp', '    mov bp, sp',
                   '    push word ptr cs:[LatinMode-LatinSegmentZero]']
        if fixed:
            result += ['    push word ptr cs:[LatinFixedDepth-LatinSegmentZero]']
        result += ['    pushf', '    pusha', '    push es',
                   '    les bx, dword ptr ss:[bp+6]', '    call DetectLatinString']
        if fixed:
            result += ['    inc word ptr cs:[LatinFixedDepth-LatinSegmentZero]']
        result += ['    pop es', '    popa', '    popf']
        result += [f'    push word ptr ss:[bp+{6+2*i}]' for i in reversed(range(argc))]
        result += ['    push cs', f'    call {name}Thunk',
                   f'    lea sp, [bp-{4 if fixed else 2}]',
                   '    pushf', '    push ax',
                   '    mov ax, word ptr ss:[bp-2]',
                   '    mov word ptr cs:[LatinMode-LatinSegmentZero], ax']
        if fixed:
            result += ['    mov ax, word ptr ss:[bp-4]',
                       '    mov word ptr cs:[LatinFixedDepth-LatinSegmentZero], ax']
        result += ['    pop ax', '    popf', '    mov sp, bp', '    pop bp',
                   '    retf', f'{name} ENDP', f'{name}Thunk LABEL NEAR']
        if fixed:
            result += ['    jmp ExistingFixedPitch']
        else:
            result += ['    db '+','.join(f'0{b:02X}h' for b in bytes.fromhex(raw)),
                       f'    jmp dword ptr cs:[{name}Continue-LatinSegmentZero]']
        result += [f'{name}Continue dw {offset+len(bytes.fromhex(raw))}, 0']
    return '\n'.join(result)


def latin_patch_scopes(exe, entries):
    result = bytearray(exe)
    changes = []
    for name, segment, offset, _, expected in LATIN_SCOPES:
        at = (module_at(result, segment)+offset if segment >= 0x3200
              else 0x4C00+segment*16+offset)
        old = bytes.fromhex(expected)
        if result[at:at+len(old)] != old:
            raise ValueError(f'달무리 문자열 진입 코드가 기준과 다릅니다: {name}')
        # Capture the actual owner CS, preserve AX, and enter the extension via
        # the original game's DS. No overlay selector/fixup table is changed.
        code = bytes.fromhex('0e508cd805c0095068')+struct.pack('<H', entries[name])+b'\xcb'
        result[at:at+len(old)] = code.ljust(len(old), b'\x90')
        changes.append(dict(name=name, segment=hex(segment), offset=hex(offset),
                            file_offset=hex(at), bytes_before=old.hex(),
                            bytes_after=bytes(result[at:at+len(old)]).hex()))
    return bytes(result), changes


# Native intro and ending FNT pages

# 32B1 calls the same INTRO.FNT animation initializer as opening/endings.
# Its six original text tables at DS:1C42,1CAD,1D16,1D81,1DEA,1E55 contain
# the following DUNE.ENG ranges (10-byte entries, FFFF terminator).
INTRO_INTERMISSION_RANGES=((287,292),(293,297),(298,303),(304,308),(309,314),(315,320))

def intro_selected_rows(rows):
    return [r for r in rows if
            (r['file']=='INTRO.ENG' and 1<=int(r['index'])<=37) or
            (r['file']=='DUNE.ENG' and r['index'].isdigit() and
             any(first<=int(r['index'])<=last for first,last in INTRO_INTERMISSION_RANGES))]

def intro_used_characters(rows):
    text=''.join((r['translation_ko'] or r['source_en']).replace('\\r','\r').replace('\\n','\n') for r in intro_selected_rows(rows))
    return sorted({ch for ch in text if 0xAC00<=ord(ch)<=0xD7A3 or unicodedata.category(ch)[0] in 'PS'})


def intro_native_font(bitmaps):
    count = len(bitmaps)
    if not 1 <= count <= 256:
        raise ValueError('Westwood FNT 한 페이지는 1~256글리프여야 합니다.')
    offsets, widths, heights = 20, 20+count*2, 20+count*3
    pixels = 20+count*5
    data = bytearray(struct.pack('<7H', pixels+count*128, 0x0500,
                                 14, offsets, widths, pixels, heights))
    data += bytes((0x12, 0x10, 0, count-1, 16, 16))
    data += struct.pack('<'+'H'*count, *(pixels+i*128 for i in range(count)))
    data += bytes((16,))*count+bytes((0, 16))*count
    for bitmap in bitmaps:
        if len(bitmap) != 32:
            raise ValueError('유니폰트 한글 비트맵은 16×16이어야 합니다.')
        for y in range(16):
            row = int.from_bytes(bitmap[y*2:y*2+2], 'big')
            for x in range(0, 16, 2):
                data.append(((row >> (15-x)) & 1) | (((row >> (14-x)) & 1) << 4))
    return bytes(data)


def intro_read_native_glyph(font, slot):
    """Decode the generated FNT through its native offset/metric tables."""
    _, offsets, widths, _, heights = struct.unpack_from('<5H', font, 4)
    assert font[widths+slot] == 16 and font[heights+slot*2:heights+slot*2+2] == b'\0\x10'
    at = struct.unpack_from('<H', font, offsets+slot*2)[0]
    result = bytearray()
    for y in range(16):
        value = 0
        for x in range(16):
            byte = font[at+y*8+x//2]
            pixel = (byte >> ((x % 2)*4)) & 15
            assert pixel in (0, 1)
            value = (value << 1) | pixel
        result += value.to_bytes(2, 'big')
    return bytes(result)


def intro_build(rows, syllables, root):
    selected = intro_selected_rows(rows)
    used = intro_used_characters(rows)
    source = root/'font/unifont-16.0.04.hex'
    wanted = set(used)
    bitmaps = {}
    widths = {}
    for line in source.read_text(encoding='ascii').splitlines():
        if not line:
            continue
        cp, value = line.split(':', 1)
        ch = chr(int(cp, 16))
        if ch in wanted:
            if ch in bitmaps:
                raise ValueError('유니폰트 소스에 중복 음절이 있습니다: '+ch)
            raw = bytes.fromhex(value)
            widths[ch]=len(raw)//2
            if len(raw)==16:
                # Unifont half-width punctuation is 8x16. Store in the left
                # half of a native 16x16 scratch cell; advance stays 8px.
                raw=b''.join(bytes((value,0)) for value in raw)
            elif len(raw)!=32:
                raise ValueError('유니폰트 글리프 크기가 8×16 또는 16×16이 아닙니다: '+ch)
            bitmaps[ch] = raw
    missing = wanted-bitmaps.keys()
    if missing:
        raise ValueError('유니폰트 HEX에 없는 음절: '+''.join(sorted(missing)))
    ranks = {ch: i for i, ch in enumerate(syllables)}
    hangul={ch for ch in wanted if 0xAC00<=ord(ch)<=0xD7A3}
    punctuation=wanted-hangul
    latin=latin_package(root,len(syllables))
    if any(ord(ch) not in latin['slots'] for ch in punctuation):
        raise ValueError('공통 부호 문자표에 없는 글자: '+''.join(ch for ch in punctuation if ord(ch) not in latin['slots']))
    if hangul-ranks.keys():
        raise ValueError('공통 2바이트 문자표에 오프닝·엔딩 음절이 누락됐습니다.')
    pages, locations = {}, {}
    physical={ch:glyph_index(ranks[ch]) if ch in hangul else latin['slots'][ord(ch)] for ch in wanted}
    total_glyphs=len(syllables)+SYMBOL_COUNT+latin['added_count']
    map_size = total_glyphs*4
    xms_offset = map_size
    table = io.StringIO(newline='')
    writer = csv.writer(table)
    writer.writerow(['character', 'unicode', 'token_hex', 'syllable_index', 'glyph_index',
                     'fnt_file', 'fnt_slot'])
    for start in range(0, len(used), 256):
        chars = used[start:start+256]
        name = 'DUNEUNI.FNT' if start == 0 else f'DUNEUN{start//256}.FNT'
        font = intro_native_font([bitmaps[ch] for ch in chars])
        pages[name] = font
        for slot, ch in enumerate(chars):
            decoded = intro_read_native_glyph(font, slot)
            assert decoded == bitmaps[ch]
            offsets = struct.unpack_from('<H', font, 6)[0]
            locations[ch] = xms_offset+struct.unpack_from('<H', font, offsets+slot*2)[0]
            rank = ranks.get(ch)
            token=(_encode_token(rank) if rank is not None else
                   bytes((ord(ch),)) if ord(ch)<128 else
                   _encode_token(len(syllables)+latin['symbols'].index(ord(ch))))
            writer.writerow([ch, f'U+{ord(ch):04X}', token.hex().upper(),
                             '' if rank is None else rank, physical[ch], name, slot])
        xms_offset += (len(font)+1) & ~1
    offsets={physical[ch]:offset for ch,offset in locations.items()}
    lookup = struct.pack('<'+'I'*total_glyphs,
                         *(offsets.get(i,0xFFFFFFFF) for i in range(total_glyphs)))
    files = {'DUNEUNI.MAP': lookup, **pages}
    declarations = ['UniFiles LABEL WORD']
    offset = 0
    for index, (name, raw) in enumerate(files.items()):
        declarations += [f'    dw OFFSET UniName{index}', f'    dd {len(raw)}, {offset}']
        offset += (len(raw)+1) & ~1
    for index, name in enumerate(files):
        declarations += [f"UniName{index} db '{name}', 0"]
    declarations += [f'UNI_PUNCT_COUNT EQU {len(punctuation)}','UniPunctSlots LABEL WORD']
    declarations += ['    dw '+','.join(str(physical[ch]) for ch in sorted(punctuation))] if punctuation else ['    dw 0']
    declarations += ['UniPunctWidths LABEL WORD',
                     '    dw '+','.join(str(widths[ch]) for ch in sorted(punctuation)) if punctuation else '    dw 0']
    return dict(files=files, xms_bytes=offset, file_count=len(files),
                declarations='\n'.join(declarations),
                table=table.getvalue().encode('utf-8-sig'),
                report=dict(source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                            resources=['INTRO.ENG','DUNE.ENG'], opening_indices=[1, 19], ending_indices=[20, 37],
                            intermission_ranges=[list(r) for r in INTRO_INTERMISSION_RANGES],
                            selected_string_count=len(selected),
                            characters=''.join(used), glyph_count=len(used), bitmap_size='16x16',
                            hangul_count=len(hangul),punctuation_count=len(punctuation),
                            punctuation=''.join(sorted(punctuation)),punctuation_widths={ch:widths[ch] for ch in sorted(punctuation)},
                            format='Westwood FNT v3; 4bpp; native offset/width/height tables',
                            token_bytes=2, sorted_syllables=True, unused_syllables_stored=0,
                            files={name: dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                                   for name, data in files.items()},
                            font_xms_bytes=offset, font_xms_kib=(offset+1023)//1024,
                            resident_bitmap_bytes=0, resident_lookup_bytes=0,
                            separate_DOS_allocations=0,
                            runtime_source='native FNT files and lookup loaded into XMS; selected 4bpp glyph copied into a resident 128-byte scratch'))


def intro_instrument(source, package):
    from pathlib import Path
    import re
    assembly = (Path(__file__).resolve().parents[1]/'import/asm/font/unifont-intro-hook.asm').read_text(encoding='ascii')
    assembly += '\n'+package['declarations']+'\n'
    data_labels = re.findall(r'^(\w+)\s+(?:dw|dd|db|LABEL BYTE|LABEL WORD)\b', assembly, re.M)
    for name in data_labels:
        assembly = assembly.replace('OFFSET '+name, '('+name+'-UniSegmentZero)')
    def absolute_memory(match):
        value = match[1]
        for name in data_labels:
            value = re.sub(r'\b'+name+r'\b', '('+name+'-UniSegmentZero)', value)
        return '['+value+']'
    assembly = re.sub(r'\[([^\]]+)\]', absolute_memory, assembly)
    source = source.replace('ASSUME CS:KOREAN',
                            'ASSUME CS:KOREAN\nORG 0\nUniSegmentZero LABEL BYTE')
    source = source.replace('ORG 1FD0h',
        'ORG 03D3h\nOriginalDrawReturn LABEL NEAR\n'
        'ORG 1F40h\nLegacySymbol LABEL NEAR\nORG 1FD0h')
    source = source.replace('NewWidthFontDispatch LABEL NEAR\n',
        'NewWidthFontDispatch LABEL NEAR\n    cmp ax, 0100h\n    jb IntroWidthLegacy\n'
        '    call IsIntroFont\n    jne IntroWidthNormal\n'
        '    call EnsureUniFont\n    cmp word ptr cs:[UniStatus-UniSegmentZero], 1\n    jne IntroWidthLegacy\n'
        '    mov ax, 16\n    add ax, word ptr ds:[6CF8h]\n    ret\n'
        'IntroWidthNormal:\n    call ReleaseUniFont\nIntroWidthLegacy:\n')
    source = source.replace('NewWidth PROC NEAR\n    call MapLatin\n',
        'NewWidth PROC NEAR\n    call MapLatin\n    call UniSymbolWidth\n    jnc UniWidthContinue\n    ret\nUniWidthContinue:\n')
    source = source.replace('    call MapLatin\n    cmp ax, 0100h\n    jb LatinSingleOriginal',
        '    call MapLatin\n    call UniSymbolWidth\n    jc LatinSingleReturn\n    cmp ax, 0100h\n    jb LatinSingleOriginal')
    source = source.replace('DrawRecord PROC NEAR\n',
        'DrawRecord PROC NEAR\n    call IsIntroFont\n    jne DalmuriRecord\n'
        '    call IsLatinGlyph\n    jnc IntroDraw\n    call IsUniPunct\n    jc IntroDraw\nDalmuriRecord::\n')
    return source.replace('HelperEnd LABEL BYTE', assembly+'\nHelperEnd LABEL BYTE')


# Original font edges and panel line spacing

STYLE_FONT=0x41C20
STYLE_CONFIRMED_TEST_SHA256='f081744ba19b25f75b1dbb2e1a3c6bac0ea3bddd7d2469540d211d86af55b00a'

def style_apply(exe):
    base=bytes(exe)
    original=(ROOT/'export/DUNE2.EXE').read_bytes()
    new=bytearray(base);changes=[];allowed=set()
    def patch(at,before,after,label):
        assert len(before)==len(after) and base[at:at+len(before)]==before,(label,hex(at))
        new[at:at+len(after)]=after;allowed.update(range(at,at+len(after)))
        changes.append(dict(label=label,file_offset=hex(at),before=before.hex(),after=after.hex()))
    # Restore original 20h (one-side), preserve original 30h (both sides)
    # and 40h (coloured one-side). The previous trial changed 30h globally.
    at=HEADER+0x0EED*16+0x1F3D
    patch(at,bytes.fromhex('c6066c8b00'),original[at:at+5],'original style 20 edge colour')
    style=HEADER+0x0EED*16+0x1F27
    assert new[style:style+0x3D]==original[style:style+0x3D]
    patch(STYLE_FONT+0xA5,bytes.fromhex('3d0c0cc300000000000000'),bytes.fromhex('85c0740339c0c30c01c390'),
          'generate edge classes whenever original style has a visible edge')
    patch(STYLE_FONT+0x26D,bytes.fromhex('8bc8d1e10bc1c1e9020bc18bcbd1e90bc1'),
          bytes.fromhex('8bc8d1e10bd1c1e9020bc18bcbd1e90bc1'),
          'original edge 2 lower-right / edge 3 remaining neighbours')
    patch(STYLE_FONT+0x294,bytes.fromhex('f7c200027404b003eb08f7c600027402b002'),
          bytes.fromhex('f7c600027404b002eb08f7c200027402b003'),
          'original body then edge 2 then edge 3 priority')
    # Scope vertical spacing to the original unit/building information
    # function. Compact its unchanged zero initializers to make room for
    # saving/restoring the existing line-spacing word, without growing MZ.
    panel=HEADER+0x0EED*16
    init_start,init_end,exit_at=0xF22,0xF90,0x1B02
    old_init=base[panel+init_start:panel+init_end]
    stores=[]
    for i in range(0,len(old_init),5):
        insn=old_init[i:i+5]
        assert insn[:2]==bytes.fromhex('c746') and insn[3:]==b'\0\0'
        stores.append(bytes.fromhex('8946')+insn[2:3])
    entry=bytes.fromhex('ff36fa6c9cff06fa6c33c0')+b''.join(stores)+b'\x9d'
    helper=init_start+len(entry)+2
    entry+=bytes([0xEB,init_end-helper])
    old_exit=bytes.fromhex('5f5e8be55dcb')
    new_init=entry+bytes.fromhex('8f06fa6c')+old_exit
    new_init+=b'\x90'*(len(old_init)-len(new_init))
    patch(panel+init_start,old_init,new_init,'unit/building information line spacing +1, scoped save')
    patch(panel+exit_at,old_exit,b'\xe9'+struct.pack('<h',helper-(exit_at+3))+b'\x90'*3,
          'restore previous line spacing before original panel return')
    # These five Hall calls had been changed to 30h in the localization.
    # Return their style nibble to the original game, without changing fonts,
    # alignment, text lookup or call positions.
    oa=module_at(original,0x331B);ba=module_at(base,0x331B)
    for off in (0xD75,0x1276,0x129A,0x12BD,0x13A3):
        before=base[ba+off:ba+off+4];after=original[oa+off:oa+off+4]
        assert before[0]==after[0]==0xB8 and before[3]==after[3]==0x50
        assert before[1]^after[1]==0x10 and before[2]==after[2]
        patch(ba+off,before,after,'Hall original style at '+hex(off))
    assert len(new)==len(base) and new[:HEADER]==base[:HEADER]
    changed=[i for i,(a,b) in enumerate(zip(base,new)) if a!=b]
    assert set(changed)<=allowed
    report=dict(confirmed_test_sha256=STYLE_CONFIRMED_TEST_SHA256,
        original_font_styles_all_regions=True,unit_building_extra_line_spacing=1,
        source_changes=changes,changed_bytes=len(changed),extra_resident_bytes=0,
        new_memory_allocations=0,mz_relocation_entries_unchanged=True)
    return bytes(new),report

def style_verify(exe):
    original=(ROOT/'export/DUNE2.EXE').read_bytes()
    start=HEADER+0x0EED*16+0x1F27
    checks=dict(original_style_code=exe[start:start+0x3D]==original[start:start+0x3D],
        hangul_edge_detection=exe[STYLE_FONT+0xA5:STYLE_FONT+0xB0]==bytes.fromhex('85c0740339c0c30c01c390'),
        hangul_edge_geometry=exe[STYLE_FONT+0x26D:STYLE_FONT+0x27E]==bytes.fromhex('8bc8d1e10bd1c1e9020bc18bcbd1e90bc1'),
        hangul_edge_priority=exe[STYLE_FONT+0x294:STYLE_FONT+0x2A6]==bytes.fromhex('f7c600027404b002eb08f7c200027402b003'),
        panel_spacing_save=exe[HEADER+0x0EED*16+0xF22:HEADER+0x0EED*16+0xF2D]==bytes.fromhex('ff36fa6c9cff06fa6c33c0'))
    if not all(checks.values()):raise ValueError('Font style integration check failed: '+str(checks))
    return checks

