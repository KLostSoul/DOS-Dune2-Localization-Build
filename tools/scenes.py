"""Opening/ending token preservation and the two missing final scene captions."""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import assembler
from runtime_patches import module_at

def _append_scene_overlay(exe, stub, relative, size, fixup_bytes, code, fixups):
    """Append the changed scene overlay while preserving original disk bodies."""
    last, pages = struct.unpack_from('<HH', exe, 2)
    overlay = (pages-1)*512+(last or 512)
    if exe[overlay:overlay+4] != b'FBOV':
        raise ValueError('FBOV 디스크 영역을 찾을 수 없습니다.')
    body_size = struct.unpack_from('<I', exe, overlay+4)[0]
    end = overlay+16+body_size
    if end > len(exe) or relative+size+fixup_bytes > body_size:
        raise ValueError('FBOV 디스크 영역의 크기가 다릅니다.')
    pad = (-body_size)%16
    new_relative = body_size+pad
    block = bytes(code)+fixups
    block = block.ljust((len(block)+15)&~15, b'\0')
    result = bytearray(exe[:end]+bytes(pad)+block+exe[end:])
    struct.pack_into('<IH', result, stub+4, new_relative, len(code))
    struct.pack_into('<I', result, overlay+4, new_relative+len(block))
    assert result[:stub+4] == exe[:stub+4]
    assert result[stub+10:overlay+4] == exe[stub+10:overlay+4]
    assert result[overlay+8:end] == exe[overlay+8:end]
    assert result[end+pad+len(block):] == exe[end:]
    return bytes(result), new_relative


# Harkonnen second emperor scene.
HARKONNEN_SEGMENT = 0x32B1
HARKONNEN_OLD_SIZE = 0x131
HARKONNEN_BRANCH = 0xCF
HARKONNEN_ORIGINAL_BRANCH = bytes.fromhex(
    'b82200501eb89e1e501eb89b1e501eb8551e501eb8351eebc3')
HARKONNEN_SOURCE = Path(__file__).resolve().parents[1]/'import/asm/scene/harkonnen-second-scene.asm'


def harkonnen_patch(exe, assembly_folder):
    header = struct.unpack_from('<H', exe, 8)[0]*16
    stub = header+HARKONNEN_SEGMENT*16
    relative, size, fixup_bytes = struct.unpack_from('<IHH', exe, stub+4)
    if size != HARKONNEN_OLD_SIZE or fixup_bytes != 12:
        raise ValueError('하코넨 중간 영상 호출 모듈의 원본 배치가 다릅니다.')
    at = module_at(exe, HARKONNEN_SEGMENT)
    original = exe[at:at+size]
    if original[HARKONNEN_BRANCH:HARKONNEN_BRANCH+len(HARKONNEN_ORIGINAL_BRANCH)] != HARKONNEN_ORIGINAL_BRANCH:
        raise ValueError('하코넨 두 번째 영상의 전용 호출 인자가 다릅니다.')
    fixups = exe[at+size:at+size+fixup_bytes]
    if list(struct.unpack('<6H',fixups)) != [0x12D,0x128,0x123,0x11D,0x112,6]:
        raise ValueError('중간 영상 호출 모듈의 원본 FBOV 재배치 표가 다릅니다.')
    assembler.ASM = Path(assembly_folder).resolve()
    assembler.ASM.mkdir(parents=True,exist_ok=True)
    compiled = assembler.assemble(HARKONNEN_SOURCE.read_text(encoding='ascii'), 'harkonnen-second-scene')
    added = compiled[HARKONNEN_OLD_SIZE:]
    code = bytearray(original+added)
    code[HARKONNEN_BRANCH:HARKONNEN_BRANCH+3] = b'\xE9'+struct.pack('<h',HARKONNEN_OLD_SIZE-(HARKONNEN_BRANCH+3))
    result, new_relative = _append_scene_overlay(
        exe, stub, relative, size, fixup_bytes, code, fixups)
    return bytes(result),dict(
        scope='Harkonnen second emperor intermission only; native house 0, mission 8',
        overlay_segment='32B1',branch_offset=hex(HARKONNEN_BRANCH),entry_offset=hex(HARKONNEN_OLD_SIZE),
        original_code_size=size,new_code_size=len(code),
        original_fixup_bytes=fixups.hex(), original_fixups_preserved=True,
        original_module_sha256=hashlib.sha256(original).hexdigest(),
        original_disk_offset=at,new_disk_offset=module_at(result,HARKONNEN_SEGMENT),
        original_disk_relative=relative,new_disk_relative=new_relative,
        appended_disk_bytes=len(result)-len(exe),
        private_scene_table_stack_bytes=32,saved_register_stack_bytes=6,
        final_scene=dict(native_mode=1,original_duration_units=85,duration_units=145,
            additional_duration_ticks=360,nominal_updates=48,
            WSA='EFINALA',native_looping=True,WSA_reloaded_between_loops=False,
            original_nominal_frame_ticks=18,new_nominal_frame_ticks=18),
        original_caption_table_preserved=True,original_player_preserved=True,
        font_module_and_MZ_layout_preserved=True,resident_increase_bytes=0,
        extra_DOS_allocations=0,extra_XMS_allocations=0,
        game_execution='not run')


# Ordos second emperor scene.
ORDOS_SEGMENT, ORDOS_BRANCH = 0x32B1, 0xB6
ORDOS_ORIGINAL_BRANCH = bytes.fromhex('b82200501eb8c01d501eb8bd1d501eb8811d501eb8611debdc')
ORDOS_SOURCE=Path(__file__).resolve().parents[1]/'import/asm/scene/ordos-second-scene.asm'


def ordos_patch(exe,assembly_folder):
    header=struct.unpack_from('<H',exe,8)[0]*16
    stub=header+ORDOS_SEGMENT*16
    relative,size,fixup_bytes=struct.unpack_from('<IHH',exe,stub+4)
    if size!=0x177 or fixup_bytes!=12:
        raise ValueError('오르도스 수정 전 하코넨 검증 모듈의 배치가 다릅니다.')
    at=module_at(exe,ORDOS_SEGMENT)
    original=exe[at:at+size]
    if original[ORDOS_BRANCH:ORDOS_BRANCH+len(ORDOS_ORIGINAL_BRANCH)]!=ORDOS_ORIGINAL_BRANCH:
        raise ValueError('오르도스 두 번째 영상의 전용 호출 인자가 다릅니다.')
    if original[0xCF:0xD2]!=bytes.fromhex('e95f00'):
        raise ValueError('검증된 하코넨 전용 분기가 다릅니다.')
    fixups=exe[at+size:at+size+fixup_bytes]
    if fixups!=bytes.fromhex('2d01280123011d0112010600'):
        raise ValueError('원본 중간 영상 FBOV 재배치 표가 다릅니다.')
    ds=header+0x3342*16
    scene=exe[ds+0x1D61:ds+0x1D81]
    if scene[16:24]!=bytes.fromhex('aa1e42334b004200') or scene[28]!=0:
        raise ValueError('오르도스 원본 마지막 장면이 다릅니다.')
    if struct.unpack_from('<H',exe,ds+0x1DA9)[0]!=308:
        raise ValueError('오르도스 마지막 자막 ID가 다릅니다.')
    assembler.ASM=Path(assembly_folder).resolve()
    assembler.ASM.mkdir(parents=True,exist_ok=True)
    compiled=assembler.assemble(f'ORIGINAL_CODE_SIZE EQU {size}\n'+ORDOS_SOURCE.read_text(encoding='ascii'),
                                'ordos-second-scene')
    code=bytearray(original+compiled[size:])
    code[ORDOS_BRANCH:ORDOS_BRANCH+3]=b'\xE9'+struct.pack('<h',size-ORDOS_BRANCH-3)
    result, _ = _append_scene_overlay(
        exe, stub, relative, size, fixup_bytes, code, fixups)
    assert code[0x131:size]==original[0x131:]
    return bytes(result),dict(
        scope='Ordos second emperor intermission only; native house 2, mission 8',
        overlay_segment='32B1',branch_offset=hex(ORDOS_BRANCH),entry_offset=hex(size),
        previous_code_size=size,new_code_size=len(code),
        input_module_sha256=hashlib.sha256(original).hexdigest(),
        original_fixup_bytes=fixups.hex(),original_fixups_preserved=True,
        verified_Harkonnen_branch_and_scene_code_unchanged=True,
        private_scene_table_stack_bytes=32,saved_register_stack_bytes=6,
        final_scene=dict(native_mode=1,original_duration_units=75,duration_units=135,
            additional_duration_ticks=360,nominal_updates=50,WSA='EFINALA',
            native_looping=True,WSA_reloaded_between_loops=False,
            original_nominal_frame_ticks=16,new_nominal_frame_ticks=16),
        original_caption_table_preserved=True,original_player_preserved=True,
        font_module_and_MZ_layout_preserved=True,resident_increase_bytes=0,
        appended_disk_bytes=len(result)-len(exe),extra_DOS_allocations=0,extra_XMS_allocations=0,
        game_execution='not run')


# Opening/ending subtitle normalization.
SUBTITLE_SEGMENT, SUBTITLE_START, SUBTITLE_END = 0x32F0, 0xCB5, 0xD06
SUBTITLE_ORIGINAL = bytes.fromhex(
    '558bec8b46060b460874448b460a0b460c743ceb2ac45e0626803fe1750f'
    'c45e0a26c60701ff460aff4606eb12c45e06268a07c45e0a268807ff4606'
    'ff460ac45e0626803f0075cdc45e0a26c607005dcb')


def subtitle_patch(exe, assembly_folder):
    at = module_at(exe, SUBTITLE_SEGMENT)+SUBTITLE_START
    if exe[at:at+len(SUBTITLE_ORIGINAL)] != SUBTITLE_ORIGINAL:
        raise ValueError('오프닝·엔딩 자막의 원본 전처리 코드가 기준과 다릅니다.')
    assembler.ASM = Path(assembly_folder).resolve()
    assembler.ASM.mkdir(parents=True, exist_ok=True)
    source = (Path(__file__).resolve().parents[1]/'import/asm/scene/subtitle-normalize.asm').read_text(encoding='ascii')
    compiled = assembler.assemble(source, 'subtitle-normalize')
    code = compiled[SUBTITLE_START:]
    if len(code) > SUBTITLE_END-SUBTITLE_START:
        raise ValueError('자막 전처리 코드가 원본 함수 공간을 초과합니다.')
    replacement = code.ljust(SUBTITLE_END-SUBTITLE_START, b'\x90')
    new = bytearray(exe)
    new[at:at+len(replacement)] = replacement
    assert len(new) == len(exe)
    return bytes(new), dict(
        overlay_segment=f'{SUBTITLE_SEGMENT:04X}', function_offset=f'{SUBTITLE_START:04X}',
        allocated_bytes=SUBTITLE_END-SUBTITLE_START, code_bytes=len(code),
        original_sha256=hashlib.sha256(SUBTITLE_ORIGINAL).hexdigest(),
        patched_sha256=hashlib.sha256(replacement).hexdigest(),
        original_single_byte_E1_to_01_preserved=True,
        two_byte_token_copy=True, resident_increase_bytes=0,
        extra_DOS_allocations=0, extra_XMS_allocations=0)
