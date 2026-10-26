"""Verify the final runnable build and its BIN/CUE/Xdelta distribution.

All check implementations live in this file. Checks read the final build,
current import sources and original CD; they never rebuild or launch the game.
Unicorn executes bounded instruction sequences with explicit service stubs.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import itertools
import json
import math
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'editor'),
               str(ROOT/'build/analysis-deps')]
import cd_source
import clonecd_xdelta
import build_game as model
import translation_data
import editor_model
import fonts as font_tools
import runtime_patches as runtime
import scenes
import apply_hitsquad107_fix as hitsquad
from runtime_patches import module_at
from resources import unpack_pak
from unit_edits import UnitEdits
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.x86_const import *

BUILD = ROOT/'build/final-build'
GAME = Path('source/VIRGIN/DUNE2')
HEADER = 0x4C00
LOAD, DATA, STACK, TEXT, FONT, PAGE = 0x75B, 0x3A9D, 0x9000, 0x7200, 0x7000, 0x8000
REGS = dict(zip('ax bx cx dx si di bp sp cs ds es ss'.split(), (
    UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX,
    UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_BP, UC_X86_REG_SP,
    UC_X86_REG_CS, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS)))
STYLES = {0x10: bytes([0, 0]), 0x20: bytes([12, 0]),
          0x30: bytes([12, 12]), 0x40: bytes([232, 0])}
LEGACY_BYTE_SLOTS = {chr(cp).encode('cp437')[0]: cp
                     for cp in font_tools.LEGACY_GLYPH_SLOTS if cp not in (40, 41)}


def digest(path):
    return clonecd_xdelta.sha256(Path(path))


def build_report(folder):
    return json.loads((folder/'build-report.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def original_files():
    return cd_source.cd_files()


def original_file(name):
    return original_files()['VIRGIN/DUNE2/'+name]


def image_end(exe):
    last, pages = struct.unpack_from('<HH', exe, 2)
    return (pages-1)*512+(last or 512)


@contextmanager
def scratch():
    """Remove this invocation's intermediates; remove temp/ only if empty."""
    parent = ROOT/'temp'
    parent.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='final-check-', dir=parent) as path:
            yield Path(path)
    finally:
        try:
            parent.rmdir()
        except OSError:
            pass


def model_for_build(folder):
    """Use saved CSV inputs and require their tokens to match this build."""
    m = model.BuildInputs()
    rows = model.read_csv(folder/'DUNEHAN.TBL.csv')
    assert [r['character'] for r in rows] == m.syllables, 'CSV/font table differs; rebuild first'
    assert all(bytes.fromhex(r['token_hex']) == m.codes[r['character']] for r in rows)
    return m


def iso_contents(image):
    """Parse the actual ISO directories, including sector padding and endian pairs."""
    assert len(image) % 2352 == 0
    sectors = len(image)//2352
    def read(lba, length):
        assert 0 <= lba and lba+math.ceil(length/2048) <= sectors
        return b''.join(image[n*2352+16:n*2352+2064]
                        for n in range(lba, lba+math.ceil(length/2048)))[:length]
    def pair(record, at):
        little = struct.unpack_from('<I', record, at)[0]
        assert little == struct.unpack_from('>I', record, at+4)[0], 'ISO endian pair mismatch'
        return little
    pvd = read(16, 2048)
    assert pvd[:7] == b'\x01CD001\x01'
    assert pair(pvd, 80) == sectors
    files, visited = {}, set()
    def walk(lba, length, parent=''):
        assert lba not in visited, 'ISO directory cycle'
        visited.add(lba)
        data = read(lba, length)
        at = 0
        while at < len(data):
            count = data[at]
            if not count:
                at = (at//2048+1)*2048
                continue
            assert count >= 34 and at+count <= len(data)
            record = data[at:at+count]
            assert 33+record[32] <= count
            name = record[33:33+record[32]]
            extent, size = pair(record, 2), pair(record, 10)
            if name not in (b'\0', b'\1'):
                name = name.decode('ascii').split(';')[0]
                assert '/' not in name and '\\' not in name and name not in ('.', '..')
                path = parent+'/'+name if parent else name
                if record[25] & 2:
                    walk(extent, size, path)
                else:
                    assert path not in files
                    files[path] = (read(extent, size), extent)
            at += count
    root = pvd[156:190]
    walk(pair(root, 2), pair(root, 10))
    return files


def check_package(folder):
    output = ROOT/'output'
    manifest = json.loads(clonecd_xdelta.MANIFEST.read_text(encoding='utf-8'))
    game = (folder/GAME).resolve()
    assert Path(manifest['game_dir']).resolve() == game and game.is_dir()
    original = cd_source.IMAGE.read_bytes()
    assert hashlib.sha256(original).hexdigest() == cd_source.IMAGE_SHA256 == manifest['source_img_sha256']
    image = clonecd_xdelta.BIN.read_bytes()
    assert hashlib.sha256(image).hexdigest() == manifest['target_bin_sha256']
    assert len(original)//2352 == manifest['source_sectors']
    assert len(image)//2352 == manifest['target_sectors']
    files = iso_contents(image)
    expected = dict(original_files())
    prefix = 'VIRGIN/DUNE2/'
    for name in clonecd_xdelta.NEW_FILES:
        expected[prefix+name] = (game/name).read_bytes()
    assert set(files) == set(expected), 'Unexpected/missing ISO files (including possible saves)'
    for path in expected:
        name = path.removeprefix(prefix)
        if path.startswith(prefix) and name not in clonecd_xdelta.SKIP_EXISTING:
            expected[path] = (game/name).read_bytes()
        assert files[path][0] == expected[path], ('BIN file differs', path)
    changed = {name for name, data in expected.items()
               if name not in original_files() or data != original_files()[name]}
    recorded = set()
    for item in manifest['files']:
        name = prefix+item['name']
        assert name not in recorded
        recorded.add(name)
        data, extent = files[name]
        assert extent == item['extent'] and len(data) == item['new_size']
        assert hashlib.sha256(data).hexdigest() == item['sha256']
    assert changed == recorded, 'Manifest does not describe every modified/new file'
    sector_checks = 0
    for number in range(len(image)//2352):
        sector = image[number*2352:(number+1)*2352]
        assert sector[:12] == b'\0'+b'\xff'*10+b'\0' and sector[15] == 1
        assert sector[12:15] == bytes(map(clonecd_xdelta.bcd, clonecd_xdelta.msf(number+150)))
        if sector != original[number*2352:(number+1)*2352]:
            repaired = bytearray(sector)
            clonecd_xdelta.fix_mode1(repaired)
            assert repaired == sector, ('EDC/ECC mismatch', number)
            sector_checks += 1
    cue = clonecd_xdelta.CUE.read_text(encoding='ascii').splitlines()
    assert [line.strip() for line in cue if line.strip()] == [
        f'FILE "{clonecd_xdelta.BIN.name}" BINARY', 'TRACK 1 MODE1/2352', 'INDEX 1 00:00:00']
    assert manifest['xdelta_patch'] == clonecd_xdelta.PATCH.name
    tool = clonecd_xdelta.xdelta3_path(None)
    with scratch() as temporary:
        decoded = temporary/'decoded.bin'
        subprocess.run([str(tool), '-f', '-d', '-s', str(cd_source.IMAGE),
                        str(clonecd_xdelta.PATCH), str(decoded)], check=True,
                       capture_output=True, timeout=120)
        assert decoded.read_bytes() == image, 'Xdelta decoded output differs from final BIN'
    return dict(iso_files=len(files), modified_files=len(changed),
                modified_sector_edc_ecc_checks=sector_checks,
                all_iso_files_match_final_or_original=True, no_save_files_added=True,
                cue_matches_bin=True, xdelta_applied_to_original_matches_bin=True,
                bin_sha256=manifest['target_bin_sha256'], xdelta_sha256=digest(clonecd_xdelta.PATCH))


def check_structure(folder):
    report = build_report(folder)
    exe = (folder/GAME/'DUNE2.EXE').read_bytes()
    fix = json.loads((folder/'hitsquad107-fix-report.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(exe).hexdigest() == fix['files']['DUNE2.EXE']['sha256']
    # build-report.json records the preceding localization stage. Reversing
    # only the declared HitSquad resident bytes must recover that stage.
    before_fix = bytearray(exe)
    for offset in fix['exe']['applied_exe_offsets']:
        at = int(offset, 16)
        before_fix[at] = original_file('DUNE2.EXE')[at]
    assert hashlib.sha256(before_fix).hexdigest() == report['exe_sha256'] == fix['source_exe_sha256']
    assert exe[:2] == b'MZ' and struct.unpack_from('<H', exe, 8)[0]*16 == HEADER
    end = image_end(exe)
    extra = report['extra_cheats']
    segment = int(extra['cheat_segment'], 16)
    cheat_at = HEADER+segment*16
    assert end == extra['new_mz_end'] == cheat_at+extra['cheat_module_bytes']
    font_report = report['font_build']
    assert font_tools.MODULE_FILE+font_report['module_bytes'] == cheat_at
    assert font_report['completed_font_generated_once'] is True
    assert font_report['initial_font_generated'] is False
    assert font_report['initial_character_table_required'] is False
    assert font_report['cheat_assembled_at_final_segment'] is True
    runtime_source = report['runtime_source']
    assert runtime_source['initial_font_generated'] is False
    assert runtime_source['initial_character_table_required'] is False
    assert runtime_source['initial_cheat_generated'] is False
    assert runtime_source['completed_font_sha256'] == font_report['completed_font_sha256']
    assert font_report['completed_font_sha256'] == digest(folder/GAME/'DUNEHAN.FNT')
    assert struct.unpack_from('<HH', exe, 10) == (0, 0xFFFF)
    count, table = struct.unpack_from('<H', exe, 6)[0], struct.unpack_from('<H', exe, 24)[0]
    assert count == extra['relocation_count_after'] and table+count*4 <= HEADER
    sites = [struct.unpack_from('<HH', exe, table+i*4) for i in range(count)]
    assert len(set(sites)) == len(sites) and tuple(extra['added_relocation']) in sites
    assert all(HEADER+seg*16+off+2 <= end for off, seg in sites)
    hook = extra['production_hook']
    assert exe[hook['file_offset']:hook['file_offset']+7] == bytes.fromhex(hook['after'])
    assert exe[end:end+4] == b'FBOV'
    checks = runtime.verify(exe)['checked_patches']
    assert all(checks.values())
    compiler = report['assembly_compiler']
    assert compiler['reference_compiler_invocations'] == 0
    assert all(item['compiler'] == 'JWasm' for item in compiler['compilations'])
    assert digest(ROOT/'import/asm/JWasm.exe') == compiler['jwasm_sha256']
    fixed = (ROOT/'import/patches/dune2eng1.07fix/V107UPG/HITSQUAD/DUNE2.EXE').read_bytes()
    for offset in fix['exe']['applied_exe_offsets']:
        at = int(offset, 16)
        assert exe[at] == fixed[at]
    # Keep the seven overlay bytes exactly as accepted for v1.01.
    original = original_file('DUNE2.EXE')
    for seg, off, size in ((0x32B8, 0xDE3, 6), (0x32DD, 0x1581, 1)):
        a, b = module_at(exe, seg)+off, module_at(original, seg)+off
        assert exe[a:a+size] == original[b:b+size]
    return dict(mz_relocations=count, resident_end=end, font_end=cheat_at,
                cheat_bytes=extra['cheat_module_bytes'],
                stack_segment=extra['new_stack_segment'], runtime_checks=checks,
                jwasm_compilations=len(compiler['compilations']),
                accepted_seven_overlay_bytes_preserved=True,
                complete_font_generated_once=True, initial_font_or_character_table_used=False,
                cheat_assembled_at_final_segment=True)


def check_scenes(folder):
    exe = (folder/GAME/'DUNE2.EXE').read_bytes()
    original = original_file('DUNE2.EXE')
    start, source = module_at(exe, 0x32B1), module_at(original, 0x32B1)
    stub = HEADER+0x32B1*16
    size, fixes = struct.unpack_from('<HH', exe, stub+8)
    old_size, old_fixes = struct.unpack_from('<HH', original, stub+8)
    assert old_size == 0x131 and fixes == old_fixes == 12
    code = exe[start:start+size]
    old = original[source:source+old_size]
    changes = set(range(0xB6, 0xB9)) | set(range(0xCF, 0xD2))
    assert all(code[i] == old[i] for i in range(old_size) if i not in changes)
    assert code[0xCF:0xD2] == b'\xe9'+struct.pack('<h', 0x131-0xD2)
    assert code[0xB6:0xB9] == b'\xe9'+struct.pack('<h', 0x177-0xB9)
    fixups = exe[start+size:start+size+fixes]
    assert fixups == original[source+old_size:source+old_size+old_fixes]
    sites = struct.unpack('<6H', fixups)
    assert not any(i in changes or i+1 in changes or i+2 > old_size for i in sites)
    for first, last in ((0x131, 0x177), (0x177, size)):
        instructions = list(Cs(CS_ARCH_X86, CS_MODE_16).disasm(code[first:last], first))
        assert sum(i.size for i in instructions) == last-first
        depth = 0
        for i in instructions:
            if i.mnemonic == 'push': depth -= 2
            elif i.mnemonic == 'pop': depth += 2
            elif i.mnemonic in ('add', 'sub') and i.op_str.startswith('sp, '):
                depth += (1 if i.mnemonic == 'add' else -1)*int(i.op_str.split(', ')[1], 0)
            elif i.mnemonic == 'call':
                assert int(i.op_str, 0) == 0xF0
                depth += 2  # Callee RETF consumes caller's manually pushed CS.
            elif i.mnemonic == 'jmp': assert int(i.op_str, 0) == 0xE8 and depth == 0
        assert depth == 0 and instructions[-1].mnemonic == 'jmp'
    assert bytes.fromhex('26c74714913026c747164100') in code[0x131:0x177]
    assert bytes.fromhex('26c74714873226c747164100') in code[0x177:]
    ds = HEADER+0x3342*16
    assert exe[ds+0x1C1A:ds+0x1EB3] == original[ds+0x1C1A:ds+0x1EB3]
    for load in (1, 0x75B, 0x1000, 0x2000):
        relocated = bytearray(code)
        for site in sites:
            struct.pack_into('<H', relocated, site, (struct.unpack_from('<H', code, site)[0]+load)&0xFFFF)
        assert relocated[old_size:] == code[old_size:]
    return dict(harkonnen_320=True, ordos_308=True, original_scene_caption_tables_preserved=True,
                other_house_branches_preserved=True, original_fixups_preserved=True,
                stack_balanced=True, native_wsa_loop_mode=1, additional_ticks_each=360)

# Bounded font, UI and cheat checks are defined below in this same module.
# BEGIN INTEGRATED CHECKS

class CPU:
    def __init__(self, exe, original_font):
        self.u = Uc(UC_ARCH_X86, UC_MODE_16)
        self.u.mem_map(0, 0x110000)
        header = struct.unpack_from('<H', exe, 8)[0]*16
        last, pages = struct.unpack_from('<HH', exe, 2)
        end = (pages-1)*512+(last or 512)
        self.u.mem_write(LOAD*16, exe[header:end])
        reloc = struct.unpack_from('<H', exe, 0x18)[0]
        for index in range(struct.unpack_from('<H', exe, 6)[0]):
            off, seg = struct.unpack_from('<HH', exe, reloc+index*4)
            at = (LOAD+seg)*16+off
            value = struct.unpack('<H', self.u.mem_read(at, 2))[0]
            self.word_at(at, value+LOAD)
        self.u.mem_write(FONT*16, original_font)
        self.word(DATA, 0x6CF8, -1)
        self.word(DATA, 0x6CFA, 0)
        self.word(DATA, 0x6CFE, struct.unpack_from('<H', original_font, 8)[0])
        self.word(DATA, 0x6D00, FONT)
        driver = LOAD+0x20AA
        for state, offset in ((0x7C, 4), (0x7E, 6), (0x80, 8), (0x82, 10), (0x84, 12)):
            self.word(driver, state, struct.unpack_from('<H', original_font, offset)[0])
        for offset, value in ((0x8A, 0), (0x8C, FONT), (0x15, 0),
                              (0x17, 0x7300), (0x19, 0x100), (0x1B, 0x7300)):
            self.word(driver, offset, value)
        self.word(0x7300, 0, PAGE)
        self.u.mem_write(0x73100, b'\0')
        for index in range(16):
            self.u.mem_write(driver*16+0x91+index, bytes((index,)))
            self.u.mem_write(driver*16+0x91+index*16, bytes((index,)))
        # A body-only fixture must install the real style-10 edge mapping.
        # Identity colours 2/3 are visible edges under the restored native
        # style rules; they are not a valid no-outline rendering state.
        for index in (2,3):
            for stride in (1,16):
                self.u.mem_write(driver*16+0x91+index*stride,b'\0')
        self.word(DATA, 0x66D8, 0x7BD)
        self.word(DATA, 0x66DA, driver)
        self.word(DATA, 0x675C, 0x110C)
        self.word(DATA, 0x675E, driver)
        for y in range(200):
            self.word(driver, 0x187+y*2, y*320)

    def word_at(self, at, value):
        self.u.mem_write(at, struct.pack('<H', value & 0xFFFF))

    def word(self, seg, off, value):
        self.word_at(seg*16+off, value)

    def call(self, offset, *, far=False, args=(), segment=font_tools.MODULE_SEG, **registers):
        values = dict(ax=0x1111, bx=0, cx=0x3333, dx=0x4444, si=0x5555,
                      di=0x6666, bp=0x7777, ds=DATA, es=TEXT, ss=STACK, sp=0xFD00)
        values.update(registers)
        for key, value in values.items():
            self.u.reg_write(REGS[key], value)
        self.u.reg_write(UC_X86_REG_EFLAGS, 0x202)
        cs = LOAD+segment
        stop_cs = 0x6000 if far else cs
        frame = [0xFFF0]+([stop_cs] if far else [])+list(args)
        self.u.mem_write(STACK*16+0xFD00, struct.pack('<'+'H'*len(frame), *frame))
        self.u.reg_write(UC_X86_REG_CS, cs)
        self.u.emu_start(cs*16+offset, stop_cs*16+0xFFF0, count=200000)
        assert (self.u.reg_read(UC_X86_REG_CS)*16+self.u.reg_read(UC_X86_REG_IP)
                == stop_cs*16+0xFFF0), ('did not return', hex(offset))
        result = {key: self.u.reg_read(reg) for key, reg in REGS.items()}
        assert result['sp'] == 0xFD00+(4 if far else 2), ('stack', hex(offset), result)
        return result

    def text(self, raw):
        self.u.mem_write(TEXT*16, raw+b'\0')


def check_resources(m, game, chars):
    _, english = model.unpack_pak((game/'ENGLISH.PAK').read_bytes())
    _, scenario = model.unpack_pak((game/'SCENARIO.PAK').read_bytes())
    tables, names, checked = {}, {}, 0
    for row in m.rows:
        if not model.editable(row):
            continue
        name, kind = row['file'], row['type']
        value = row['translation_ko'] or row['source_en']
        raw = scenario[name] if name.startswith('REGION') else english[name]
        if kind.startswith('mentat'):
            if name not in names:
                chunks = {key: data for key, _, data in model.iff_chunks(raw)}
                entries, at = [], 0
                while at < len(chunks[b'NAME']):
                    size = struct.unpack_from('<H', chunks[b'NAME'], at)[0]
                    entries.append(chunks[b'NAME'][at:at+size]); at += size
                names[name] = entries
            source_index = int(row['index'])
            removed = (37, 44) if name == 'MENTATH.ENG' else ()
            if source_index in removed:
                continue  # HitSquad intentionally removes these duplicate entries.
            entry = names[name][source_index-sum(i < source_index for i in removed)]
            if kind == 'mentat_label':
                actual = entry[7:-2]
            else:
                prefix = model.split_mentat(row['source_en'])[0]
                if prefix and not model.split_mentat(value)[0]:
                    value = prefix+value
                at = int.from_bytes(entry[2:5], 'big')
                actual = model.expand_compressed(raw[at:raw.index(0, at)])
        elif kind in ('credits_line', 'region_map_text'):
            if kind == 'credits_line' and row['source_en'] == '\0':
                continue
            if kind == 'region_map_text':
                # HitSquad changes INI line positions; section/key identity
                # stays stable, whereas the extraction line number does not.
                wanted = row['index'].split(':')[0].upper().encode('ascii')
                key = row['code'].encode('ascii')
                section, actual = b'', None
                for line in raw.splitlines():
                    if line.startswith(b'[') and b']' in line:
                        section = line[1:line.index(b']')].upper()
                    match = re.fullmatch(rb'\s*'+re.escape(key)+rb'\s*=\s*(.*?)\s*', line)
                    if section == wanted and match:
                        assert actual is None, ('duplicate region key', name, wanted, key)
                        actual = match[1]
                assert actual is not None, ('missing region key', name, wanted, key)
            else:
                actual = re.split(b'\r\n|\r|\n', raw)[int(row['index'])]
        else:
            at = struct.unpack_from('<H', raw, int(row['index'])*2)[0]
            actual = raw[at:raw.index(0, at)]
            if kind == 'compressed_mission_text':
                actual = model.expand_compressed(actual)
        expected = m.encode(value)
        if kind == 'mentat_description' and int(row['index']) in (8, 21):
            old, new = (b'20 ', b'10 ') if int(row['index']) == 8 else (b'80 ', b'50 ')
            caption, marker, body = expected.partition(b'\x0c')
            assert marker and caption.count(old) == 1
            expected = caption.replace(old, new)+marker+body
        if kind == 'region_map_text':
            key = (name, row['index'])
            if hashlib.sha256(row['translation_ko'].encode('utf-8')).hexdigest() == hitsquad.LEGACY_REGION_TEXT_SHA256.get(key):
                expected = m.encode(hitsquad.REGION_CORRECTIONS[key])
        assert actual == expected, (name, row['index'], 'resource round trip')
        at = 0
        while at < len(actual):
            if actual[at] in font_tools.LEADS:
                assert at+1 < len(actual) and 0x80 <= actual[at+1] <= 0xFE
                index = font_tools.LEADS.index(actual[at])*127+actual[at+1]-0x80
                assert index < len(chars)+len(m.latin_symbols)
                if index < len(chars):
                    assert actual[at:at+2] == m.codes[chars[index]]
                else:
                    assert actual[at:at+2] == font_tools.token(index)
                at += 2
            else:
                at += 1
        checked += 1
    _, original = model.unpack_pak(original_file('ENGLISH.PAK'))
    for name, index in model.EXCLUDED_ROWS:
        index = int(index)
        def entry(data):
            at = struct.unpack_from('<H', data, index*2)[0]
            return data[at:data.index(0, at)]
        assert entry(english[name]) == entry(original[name]), ('excluded DOS text', index)
    assert english['PROTECT.ENG'] == original['PROTECT.ENG']
    exe = (game/'DUNE2.EXE').read_bytes()
    offsets = (0xB3, 0xBA, 0xC7, 0xD0, 0xD7, 0x154)
    for house in m.houses:
        at = font_tools.MODULE_FILE+offsets[int(house['house_id'])]
        assert exe[at:exe.index(0, at)] == m.encode(house['translation_ko'])
    return checked


def check_hangul(folder):
    m = model_for_build(folder)
    game = folder/'source/VIRGIN/DUNE2' if (folder/'source').is_dir() else folder
    exe = (game/'DUNE2.EXE').read_bytes()
    font = (game/'DUNEHAN.FNT').read_bytes()
    rows = list(csv.DictReader((folder/'DUNEHAN.TBL.csv').open(encoding='utf-8-sig')))
    chars = [row['character'] for row in rows]
    assert chars == sorted(set(chars)) == m.syllables
    registered = json.loads(translation_data.REGISTRY.read_text(encoding='utf-8'))
    assert registered['version'] == 2 and registered['syllables'] == chars
    assert set(chars) == m.registered_syllables and m.new_syllables == []
    completed = font_tools.build_font(chars, m.glyph_source)
    assert completed['font'] == font
    assert completed['sha256'] == hashlib.sha256(font).hexdigest()
    codes = [bytes.fromhex(row['token_hex']) for row in rows]
    assert len(set(codes)) == len(chars) and all(len(code) == 2 for code in codes)
    assert all(code[0] in font_tools.LEADS and 0x80 <= code[1] <= 0xFE for code in codes)
    capacity = [font_tools.token(i) for i in range(len(font_tools.LEADS)*font_tools.TRAIL_COUNT)]
    assert len(set(capacity)) == len(capacity) and all(len(code) == 2 for code in capacity)
    for row in rows:
        index = int(row['glyph_index'])
        assert font[26+index*10:34+index*10] == m.glyph_source[row['character']]
    assert struct.unpack_from('<H', font, 14)[0] == len(chars)+33+font_tools.latin_package(ROOT, len(chars))['added_count']

    # A new glyph changes the complete sorted table; registration history
    # and a separate initial character CSV are not inputs to this plan.
    new_char = next(ch for ch in sorted(m.glyph_source) if ch not in m.codes)
    edited = copy.copy(m)
    row = dict(next(row for row in m.rows if model.editable(row)))
    row['translation_ko'] = ''.join(chars)+new_char
    edited.rows, edited.houses = [row], []
    edited.prepare_syllables()
    expected = sorted(chars+[new_char])
    assert edited.syllables == expected and edited.new_syllables == [new_char]
    assert edited.registered_syllables == m.registered_syllables
    assert all(edited.codes[ch] == font_tools.token(i) for i, ch in enumerate(expected))
    assert any(edited.codes[ch] != m.codes[ch] for ch in chars if ch > new_char)

    _, originals = model.unpack_pak(original_file('DUNE.PAK'))
    cpu = CPU(exe, originals['NEW8P.FNT'])
    old = CPU(original_file('DUNE2.EXE'), originals['NEW8P.FNT'])
    # Exercise every supported page, including the FAh gap, with a declared
    # synthetic count. The instruction body stays the assembled Reader.
    extended = CPU(exe, originals['NEW8P.FNT'])
    reader = exe[font_tools.MODULE_FILE+font_tools.MODULE_SIZE:font_tools.MODULE_FILE+font_tools.MODULE_SIZE+100]
    marker = b'\x3D'+struct.pack('<H', len(chars))
    assert reader.count(marker) == 1
    count_at = reader.index(marker)+font_tools.MODULE_SIZE+1
    extended.word(LOAD+font_tools.MODULE_SEG, count_at, len(capacity))
    for rank, code in enumerate(capacity):
        extended.text(code)
        result = extended.call(0x40)
        assert (result['ax'], result['dx']) == (0x100+font_tools.glyph_index(rank), 2)
    for rank, (char, code) in enumerate(zip(chars, codes)):
        cpu.text(code)
        result = cpu.call(0x40)
        assert result['ax'] == 0x100+font_tools.glyph_index(rank) and result['dx'] == 2
        for reg, expected_value in dict(bx=0, cx=0x3333, si=0x5555, di=0x6666,
                                        bp=0x7777, ds=DATA, es=TEXT).items():
            assert result[reg] == expected_value, (char, reg)
        result = cpu.call(0xB0, ax=result['ax'])
        assert result['ax'] == 9
        cpu.u.mem_write(PAGE*16, bytes(320*200))
        cpu.call(0x190, far=True, args=(0x100+font_tools.glyph_index(rank), 20, 20))
        pixels = bytes(cpu.u.mem_read(PAGE*16, 320*200))
        expected_pixels = bytearray(320*200)
        for y, bits in enumerate(m.glyph_source[char]):
            for x in range(8):
                if bits & (0x80 >> x):
                    expected_pixels[(20+y)*320+21+x] = 1
        assert pixels == expected_pixels, ('pixels', char, rank)

    for slot in range(226):
        new_width = cpu.call(0xB0, ax=slot)['ax']
        old_width = old.call(9, segment=0x2326, far=True, args=(slot,))['ax']
        expected_width = 5 if slot in LEGACY_BYTE_SLOTS else old_width
        assert new_width == expected_width, ('original/compatibility symbol width', slot)
    shortcut_labels = [('공격', 'A'), ('이동', 'M'), ('게임 재개', 'R'),
                       ('건설', 'B'), ('처음하기', 'P'), ('불러오기', 'L')]
    for label, key in shortcut_labels:
        raw = m.encode(label+'('+key+')')
        cpu.text(raw)
        result = cpu.call(0xDA, segment=0x27DE, far=True, args=(0xFF00 | raw[0],))
        original_key = old.call(0xDA, segment=0x27DE, far=True, args=(ord(key),))
        assert result['ax'] & 255 == original_key['ax'] & 255 != 0, ('shortcut', label)
    # FAh is deliberately not a lead: it remains the Dalmoori middle dot.
    for raw in (b'A', b'\xfa', b'\xff', b'\xe2A', b'\xe2\x7f', b'\xfe\xfe'):
        cpu.text(raw)
        got = cpu.call(0x40)
        assert (got['ax'], got['dx']) == (raw[0], 1), ('single/invalid', raw, got)
    text = m.encode('가나다라 공격(A) 이동(M) '+''.join(chars[630:645])+'!')
    cpu.text(text)
    boundaries, at, width = [], 0, 0
    while at < len(text):
        boundaries.append(at)
        result = cpu.call(0xE0, far=True, bx=at, si=width)
        count = 2 if text[at] in font_tools.LEADS else 1
        assert result['dx'] == count and result['bx'] == at+count
        width = result['si']; at = result['bx']
    boundaries.append(len(text))
    for i in range(1, len(boundaries)):
        at = boundaries[i]
        result = cpu.call(0x100, far=True, bx=at, si=1000)
        assert result['bx'] == boundaries[i-1], ('reverse', at, result)
        assert result['si'] == (1000-result['ax']) & 0xFFFF
    # Fixed-pitch output retains its original two-byte temporary buffer.
    assert exe[font_tools.MODULE_FILE+0x1EFF:font_tools.MODULE_FILE+0x1F04] == bytes.fromhex('C746FE0000')
    assert exe[font_tools.MODULE_FILE+0xF4:font_tools.MODULE_FILE+0xF7] == bytes.fromhex('80FBE2')
    resource_count = check_resources(m, game, chars) if (game/'ENGLISH.PAK').exists() else None
    report = dict(scope='bounded assembled x86 execution; whole game not launched',
                  exe_sha256=hashlib.sha256(exe).hexdigest(), syllables=len(chars),
                  token_capacity=len(capacity), token_bytes=2,
                  resource_rows_verified=resource_count,
                  checks=dict(sorted_table=True, glyph_bitmap_match=True,
                              added_syllable_retokens_existing=True,
                              complete_registry_is_sorted_and_persistent=True,
                              direct_complete_font_matches_file=True,
                              initial_character_csv_not_required=True,
                              all_assembled_readers_widths_pixels=True,
                              assembled_reader_all_3556_slots=True,
                              original_slots_and_legacy_symbol_widths=True,
                              forward_reverse_mixed_text=True,
                              original_symbols_preserved=True,
                              middle_dot_not_a_lead=True,
                              fixed_pitch_two_byte_buffer=True,
                              shortcut_lead_range_updated=True,
                              assembled_menu_unit_shortcut_mapper=True,
                              resource_payloads_match_saved_csv=True))
    return report


class Services:
    def __init__(self, cpu, files, *, xms=True, allocate=True):
        self.cpu, self.files = cpu, files
        self.available, self.allocate = xms, allocate
        self.open_files, self.memory = {}, {}
        self.reads, self.moves, self.allocations, self.releases = 0, 0, [], []
        cpu.u.mem_write(0x68000, b'\xCB')
        cpu.u.hook_add(UC_HOOK_INTR, self.interrupt)
        cpu.u.hook_add(UC_HOOK_CODE, self.entry, begin=0x68000, end=0x68000)

    @staticmethod
    def far(value):
        return (value >> 16)*16+(value & 65535)

    def carry(self, failed=False):
        u = self.cpu.u
        flags = u.reg_read(UC_X86_REG_EFLAGS)
        u.reg_write(UC_X86_REG_EFLAGS, (flags | 1) if failed else (flags & ~1))

    def interrupt(self, u, number, _):
        ax = u.reg_read(UC_X86_REG_AX)
        if number == 0x2F:
            if ax == 0x4300:
                u.reg_write(UC_X86_REG_AX, 0x80 if self.available else 0)
            elif ax == 0x4310:
                u.reg_write(UC_X86_REG_ES, 0x6800)
                u.reg_write(UC_X86_REG_BX, 0)
            else:
                raise AssertionError(('unexpected multiplex', hex(ax)))
            return
        assert number == 0x21, ('unexpected interrupt', number)
        function = ax >> 8
        address = u.reg_read(UC_X86_REG_DS)*16+u.reg_read(UC_X86_REG_DX)
        handle = u.reg_read(UC_X86_REG_BX)
        self.carry()
        if function == 0x3D:
            name = bytes(u.mem_read(address, 32)).split(b'\0', 1)[0].decode('ascii')
            if name not in self.files:
                self.carry(True); u.reg_write(UC_X86_REG_AX, 2); return
            handle = max([4, *self.open_files])+1
            self.open_files[handle] = [name, 0]
            u.reg_write(UC_X86_REG_AX, handle)
        elif function == 0x3F:
            name, at = self.open_files[handle]
            data = self.files[name][at:at+u.reg_read(UC_X86_REG_CX)]
            if data:
                u.mem_write(address, data)
            self.open_files[handle][1] += len(data)
            u.reg_write(UC_X86_REG_AX, len(data)); self.reads += 1
        elif function == 0x3E:
            del self.open_files[handle]
            u.reg_write(UC_X86_REG_AX, 0)
        else:
            raise AssertionError(('unexpected DOS function', hex(function)))

    def entry(self, u, address, size, _):
        function = u.reg_read(UC_X86_REG_AH)
        if function == 9:
            kib = u.reg_read(UC_X86_REG_DX)
            if not self.allocate:
                u.reg_write(UC_X86_REG_AX, 0); return
            self.memory[7] = bytearray(kib*1024)
            self.allocations.append(kib)
            u.reg_write(UC_X86_REG_DX, 7)
        elif function == 0xA:
            handle = u.reg_read(UC_X86_REG_DX)
            del self.memory[handle]; self.releases.append(handle)
        elif function == 0xB:
            pointer = u.reg_read(UC_X86_REG_DS)*16+u.reg_read(UC_X86_REG_SI)
            length, source, start, destination, end = struct.unpack('<IHIHI', u.mem_read(pointer, 16))
            assert length % 2 == 0
            if source:
                assert start+length <= len(self.memory[source])
                data = bytes(self.memory[source][start:start+length])
            else:
                data = bytes(u.mem_read(self.far(start), length))
            if destination:
                assert end+length <= len(self.memory[destination])
                self.memory[destination][end:end+length] = data
            else:
                u.mem_write(self.far(end), data)
            self.moves += 1
        else:
            raise AssertionError(('unexpected XMS function', function))
        u.reg_write(UC_X86_REG_AX, 1)


def check_unifont(folder):
    m = model_for_build(folder)
    game = folder/'source/VIRGIN/DUNE2' if (folder/'source').is_dir() else folder
    exe = (game/'DUNE2.EXE').read_bytes()
    package = font_tools.intro_build(m.rows, m.syllables, model.ROOT)
    for name, data in package['files'].items():
        assert (game/name).read_bytes() == data
    table = list(csv.DictReader((folder/'DUNEUNI.TBL.csv').open(encoding='utf-8-sig')))
    original_exe=original_file('DUNE2.EXE')
    data_start=0x4C00+0x3342*16
    intermission_ids=[]
    for start in (0x1C42,0x1CAD,0x1D16,0x1D81,0x1DEA,0x1E55):
        for at in range(start,start+100,10):
            value=struct.unpack_from('<H',original_exe,data_start+at)[0]
            if value==0xFFFF:break
            intermission_ids.append(value)
    assert intermission_ids==list(range(287,321))
    selected=font_tools.intro_selected_rows(m.rows)
    expected_used=set(font_tools.intro_used_characters(m.rows))
    assert {r['character'] for r in table}==expected_used
    assert '궁' in expected_used and '궁' in package['report']['characters']
    assert len(table) == len(set(row['character'] for row in table)) == package['report']['glyph_count']
    assert [r['character'] for r in table] == sorted(r['character'] for r in table)
    anchor=next(row for row in table if 0xAC00<=ord(row['character'])<=0xD7A3)
    _, fonts = model.unpack_pak(original_file('INTRO.PAK'))
    original_intro = fonts['INTRO.FNT']
    # Independently feed the complete generated FNT pages to the unmodified
    # original pixel routine, not just the one-glyph scratch used by the hook.
    for name, data in package['files'].items():
        if not name.endswith('.FNT'):
            continue
        native = CPU(exe, data)
        native.u.mem_write(0x50000, data)
        native.word(LOAD+0x20AA, 0x8C, 0x5000)
        for row in [r for r in table if r['fnt_file'] == name]:
            slot = int(row['fnt_slot'])
            native.u.mem_write(PAGE*16, bytes(64000))
            native.call(0x7BD, segment=0x20AA, far=True, args=(slot, 20, 20))
            bitmap = font_tools.intro_read_native_glyph(data, slot)
            expected = bytearray(64000)
            for y in range(16):
                bits = int.from_bytes(bitmap[y*2:y*2+2], 'big')
                for x in range(16):
                    expected[(20+y)*320+20+x] = (bits >> (15-x)) & 1
            assert bytes(native.u.mem_read(PAGE*16, 64000)) == expected, ('native FNT pixel', row['character'])
    cpu = CPU(exe, original_intro)
    services = Services(cpu, package['files'])
    for row in table:
        glyph = int(row['glyph_index'])+0x100
        result = cpu.call(0xB0, ax=glyph)
        advance=package['report']['punctuation_widths'].get(row['character'],16)
        assert result['ax'] == advance-1, ('intro width', row['character'], result['ax'])
        before = bytes(cpu.u.mem_read((LOAD+0x20AA)*16+0x7C, 18))
        cpu.u.mem_write(PAGE*16, bytes(64000))
        result = cpu.call(0x190, far=True, args=(glyph, 20, 20))
        assert bytes(cpu.u.mem_read((LOAD+0x20AA)*16+0x7C, 18)) == before
        data = font_tools.intro_read_native_glyph(package['files'][row['fnt_file']], int(row['fnt_slot']))
        expected = bytearray(64000)
        for y in range(16):
            bits = int.from_bytes(data[y*2:y*2+2], 'big')
            for x in range(16):
                expected[(20+y)*320+20+x] = (bits >> (15-x)) & 1
        assert bytes(cpu.u.mem_read(PAGE*16, 64000)) == expected, ('intro pixels', row['character'])
    assert services.allocations == [package['report']['font_xms_kib']]
    assert not services.open_files
    expected_xms = bytearray()
    for data in package['files'].values():
        expected_xms += data+bytes(len(data) % 2)
    assert services.memory[7][:len(expected_xms)] == expected_xms
    # The reported palace caption is stored in DUNE.ENG, not INTRO.ENG.
    # Run its full string through the real owner, reader and pixel driver;
    # compare every Hangul cell with its 16x16 native FNT bitmap.
    caption=next(r for r in m.rows if r['file']=='DUNE.ENG' and r['index']=='287')['translation_ko']
    caption_cpu=CPU(exe,original_intro)
    Services(caption_cpu,package['files'])
    caption_cpu.word(DATA,0x9A7F,0);caption_cpu.word(DATA,0x9A81,FONT)
    caption_cpu.text(m.encode(caption))
    caption_cpu.call(4,segment=0x29C7,far=True,args=(0,0x7200,20,20,1,0))
    expected_caption=bytearray(64000);x=20
    latin=font_tools.latin_package(model.ROOT,len(m.syllables))
    bychar={r['character']:r for r in table}
    reference=CPU(exe,original_intro)
    for ch in caption:
        if ch in bychar:
            row=bychar[ch];bitmap=font_tools.intro_read_native_glyph(package['files'][row['fnt_file']],int(row['fnt_slot']))
            for y in range(16):
                bits=int.from_bytes(bitmap[y*2:y*2+2],'big')
                for dx in range(16):
                    if bits&(1<<(15-dx)):expected_caption[(20+y)*320+x+dx]=1
            x+=package['report']['punctuation_widths'].get(ch,16)-1
        elif ch==' ':
            x+=reference.call(0,far=True,args=(32,))['ax']
        else:
            for y,bits in enumerate(bytes.fromhex(latin['source_records'][ord(ch)]['rows'])):
                for dx in range(8):
                    if bits&(128>>dx):expected_caption[(28+y)*320+x+1+dx]=1
            x+=5
    actual_caption=bytes(caption_cpu.u.mem_read(PAGE*16,64000))
    assert actual_caption==expected_caption,('palace caption native Unifont pixels',
        [(i%320,i//320,a,b) for i,(a,b) in enumerate(zip(actual_caption,expected_caption)) if a!=b][:20])
    original = CPU(exe, original_intro)
    cpu.word(DATA, 0x6CF8, 0)
    assert cpu.call(0xB0, ax=int(anchor['glyph_index'])+0x100)['ax'] == 16
    cpu.word(DATA, 0x6CF8, -1)
    for slot in range(32, 127):
        width = cpu.call(0xB0, ax=slot)['ax']
        reference = original.call(0, far=True, args=(slot,))['ax']
        assert width == reference, ('original intro Latin/punctuation', slot, width, reference)

    def install_font(data):
        cpu.u.mem_write(FONT*16, data)
        cpu.word(DATA, 0x6CFE, struct.unpack_from('<H', data, 8)[0])
        for state, offset in ((0x7C, 4), (0x7E, 6), (0x80, 8), (0x82, 10), (0x84, 12)):
            cpu.word(LOAD+0x20AA, state, struct.unpack_from('<H', data, offset)[0])

    # Switching the active font back to NEW8P restores the already confirmed
    # Dalmoori path, including font-specific widths and punctuation handling.
    _, game_fonts = model.unpack_pak(original_file('DUNE.PAK'))
    install_font(game_fonts['NEW8P.FNT'])
    assert cpu.call(0xB0, ax=int(anchor['glyph_index'])+0x100)['ax'] == 9
    assert not services.memory and services.releases == [7]
    install_font(original_intro)
    assert cpu.call(0xB0, ax=int(anchor['glyph_index'])+0x100)['ax'] == 15
    assert services.allocations == [package['report']['font_xms_kib']]*2
    normal = CPU(exe, game_fonts['NEW8P.FNT'])
    idle = Services(normal, package['files'])
    assert normal.call(0xB0, ax=int(anchor['glyph_index'])+0x100)['ax'] == 9
    assert not idle.allocations and not idle.reads

    # Missing XMS, allocation failure, a missing file and a truncated file
    # must return through the existing renderer without leaking DOS handles.
    cases = [(False, True, package['files']), (True, False, package['files']),
             (True, True, {}),
             (True, True, {**package['files'], 'DUNEUNI.FNT': package['files']['DUNEUNI.FNT'][:-1]})]
    for available, allocate, files in cases:
        failed = CPU(exe, original_intro)
        stub = Services(failed, files, xms=available, allocate=allocate)
        assert failed.call(0xB0, ax=int(anchor['glyph_index'])+0x100)['ax'] == 9
        assert not stub.open_files and not stub.memory

    # Rebuilding after an editor change adds exactly the new used syllable,
    # updates its shared two-byte token and leaves no unused glyphs in FNTs.
    edited = copy.copy(m)
    edited.rows = [dict(row) for row in m.rows]
    target = next(row for row in edited.rows if row['file']=='INTRO.ENG' and row['index']=='3')
    added = next(ch for ch in sorted(m.glyph_source) if ch not in m.codes)
    target['translation_ko'] += added
    edited.prepare_syllables()
    updated = font_tools.intro_build(edited.rows, edited.syllables, model.ROOT)
    assert updated['report']['glyph_count'] == len(table)+1
    assert updated['report']['characters'] == ''.join(sorted(package['report']['characters']+added))
    assert all(len(font_tools.token(i)) == 2 for i in range(len(edited.syllables)))
    edited=copy.copy(m);edited.rows=[dict(row) for row in m.rows]
    target=next(row for row in edited.rows if row['file']=='DUNE.ENG' and row['index']=='287')
    target['translation_ko']+=added;edited.prepare_syllables()
    updated=font_tools.intro_build(edited.rows,edited.syllables,model.ROOT)
    assert updated['report']['glyph_count']==len(table)+1 and added in updated['report']['characters']
    symbol_edit=[dict(row) for row in m.rows]
    target=next(row for row in symbol_edit if row['file']=='DUNE.ENG' and row['index']=='287')
    target['translation_ko']+=':'
    symbol_package=font_tools.intro_build(symbol_edit,m.syllables,model.ROOT)
    assert ':' in symbol_package['report']['punctuation_widths']
    assert symbol_package['report']['glyph_count']==len(table)+1
    # Native FNTs have 256 slots per page; further used characters are paged.
    page_chars = sorted(m.glyph_source)[:257]
    paged = font_tools.intro_build([dict(file='INTRO.ENG', index='3', translation_ko=''.join(page_chars), source_en='')],
                             sorted(set(m.syllables) | set(page_chars)), model.ROOT)
    assert len([name for name in paged['files'] if name.endswith('.FNT')]) == 2
    assert paged['report']['glyph_count'] == 257
    resource_count = check_resources(m, game, m.syllables) if (game/'ENGLISH.PAK').exists() else None
    report = dict(scope='assembled x86 with simulated DOS/XMS; original pixel renderer executed; full game not launched',
                  exe_sha256=hashlib.sha256(exe).hexdigest(), unifont_glyphs=len(table),
                  xms_allocated_kib=services.allocations[0], xms_payload_bytes=len(expected_xms),
                  simulated_DOS_reads=services.reads, simulated_XMS_moves=services.moves,
                  resource_rows_verified=resource_count,
                  checks=dict(native_FNT_round_trip=True, used_syllables_only=True,
                              full_native_FNT_rendered_by_original_pixel_routine=True,
                              all_used_intro_widths_and_original_pixels=True,
                              native_font_cache_restored=True, original_intro_ASCII_widths=True,
                              no_font_allocation_in_Dalmoori_sections=True,
                              XMS_bytes_match_native_files=True, even_XMS_transfer_padding=True,
                              font_switch_frees_XMS_and_later_reloads=True,
                              missing_XMS_and_file_failures_cleanup=True,
                              editor_added_syllable_auto_rebuild=True,
                              intermission_34_strings_covered=True,
                              palace_caption_all_native_16x16_pixels=True,
                              editor_intermission_added_syllable_auto_rebuild=True,
                              used_punctuation_native_Unifont_pixels_and_widths=True,
                              editor_added_punctuation_auto_rebuild=True,
                              more_than_256_native_slots_paged=True))
    return report


def check_latin(folder):
    m = model_for_build(folder)
    game = folder/'source/VIRGIN/DUNE2' if (folder/'source').is_dir() else folder
    report = build_report(folder)['font_build']
    exe = (game/'DUNE2.EXE').read_bytes()
    source = original_file('DUNE2.EXE')
    originals = model.unpack_pak(original_file('DUNE.PAK'))[1]
    originals.update(model.unpack_pak(original_file('INTRO.PAK'))[1])
    latin = font_tools.latin_package(ROOT, len(m.syllables))
    mode, module = report['latin']['mode_offset'], LOAD+font_tools.MODULE_SEG
    glyph_cases = 0
    for name in ('NEW6P.FNT', 'NEW8P.FNT', 'INTRO.FNT'):
        cpu = CPU(exe, originals[name])
        old = CPU(source, originals[name])
        if name == 'INTRO.FNT':
            intro_package=font_tools.intro_build(m.rows,m.syllables,ROOT)
            services = Services(cpu, intro_package['files'])
        cpu.word(module, mode, 1)
        for cp, slot in latin['slots'].items():
            if cp == 32:
                continue
            argument = cp if cp < 127 else 0x100+slot
            uni_punct=name=='INTRO.FNT' and chr(cp) in intro_package['report']['punctuation_widths']
            expected_width=intro_package['report']['punctuation_widths'][chr(cp)]-1 if uni_punct else 5
            assert cpu.call(0xB0, ax=argument)['ax'] == expected_width, ('width', name, cp)
            if cp<127:
                assert cpu.call(9,segment=0x2326,far=True,args=(cp,))['ax']==expected_width
            cpu.u.mem_write(PAGE*16, bytes(64000))
            cpu.call(0x190, far=True, args=(argument, 20, 20))
            pixels = bytes(cpu.u.mem_read(PAGE*16, 64000))
            expected = bytearray(64000)
            if uni_punct:
                slot=intro_package['report']['characters'].index(chr(cp))
                bitmap=font_tools.intro_read_native_glyph(intro_package['files']['DUNEUNI.FNT'],slot)
                for y in range(16):
                    bits=int.from_bytes(bitmap[y*2:y*2+2],'big')
                    for x in range(16):
                        if bits&(0x8000>>x):expected[(20+y)*320+20+x]=1
            else:
                for y, bits in enumerate(bytes.fromhex(latin['source_records'][cp]['rows'])):
                    for x in range(8):
                        if bits & (128 >> x):
                            expected[(20+y+(8 if name == 'INTRO.FNT' else 0))*320+21+x] = 1
            assert pixels == expected, ('pixels', name, cp)
            glyph_cases += 1
        cpu.word(module, mode, 0)
        # ASCII-only strings retain the verified input build's widths/pixels.
        for cp in range(32, 127):
            legacy_symbol = name != 'INTRO.FNT' and cp in LEGACY_BYTE_SLOTS
            reference_width = 5 if legacy_symbol else old.call(9, segment=0x2326, far=True, args=(cp,))['ax']
            actual_width = cpu.call(0xB0, ax=cp)['ax']
            assert actual_width == reference_width, (name, cp, actual_width, reference_width)
            for item in (cpu, old): item.u.mem_write(PAGE*16, bytes(64000))
            cpu.call(0x190, far=True, args=(cp, 20, 20))
            if name == 'INTRO.FNT':
                old.call(0x7BD, segment=0x20AA, far=True, args=(cp, 20, 20))
            else:
                old.call(0x7BD, segment=0x20AA, far=True, args=(cp, 20, 20))
            if legacy_symbol:
                expected = bytearray(64000)
                bitmap = font_tools.load_glyphs(ROOT)[chr(cp)]
                for y, bits in enumerate(bitmap):
                    for x in range(8):
                        if bits & (128 >> x): expected[(20+y)*320+21+x] = 1
                assert bytes(cpu.u.mem_read(PAGE*16, 64000)) == expected, ('compatibility symbol pixels', name, cp)
            else:
                assert cpu.u.mem_read(PAGE*16, 64000) == old.u.mem_read(PAGE*16, 64000), (name, cp)

    cpu = CPU(exe, originals['NEW8P.FNT'])
    old = CPU(source, originals['NEW8P.FNT'])
    def state():
        return struct.unpack('<H', cpu.u.mem_read(module*16+mode, 2))[0]
    def advance(ch):
        return (9 if ch in m.codes else 5 if ch != ' ' and ord(ch) in latin['slots']
                else old.call(9, segment=0x2326, far=True, args=(ord(ch),))['ax'])
    mixed = 'A1? 가 Z9!'
    cpu.text(m.encode(mixed))
    assert cpu.call(0x2F, segment=0x2326, far=True, args=(0, TEXT))['ax'] == sum(map(advance, mixed))
    assert state() == 0

    # Mixed INTRO text must keep the Unifont Hangul and native Dalmoori Latin
    # on the same lower baseline while restoring the original driver cache.
    intro = CPU(exe, originals['INTRO.FNT'])
    intro_package = font_tools.intro_build(m.rows, m.syllables, ROOT)
    Services(intro, intro_package['files'])
    intro.word(DATA, 0x9A7F, 0); intro.word(DATA, 0x9A81, FONT)
    intro.text(m.encode(mixed))
    intro.call(4, segment=0x29C7, far=True, args=(0, TEXT, 20, 20, 1, 0))
    reference = CPU(source, originals['INTRO.FNT'])
    expected = bytearray(64000)
    x = 20
    for ch in mixed:
        if ch in intro_package['report']['characters']:
            slot = intro_package['report']['characters'].index(ch)
            bitmap = font_tools.intro_read_native_glyph(intro_package['files']['DUNEUNI.FNT'], slot)
            for y in range(16):
                bits = int.from_bytes(bitmap[2*y:2*y+2], 'big')
                for dx in range(16):
                    if bits & (0x8000 >> dx): expected[(20+y)*320+x+dx] = 1
            x += intro_package['report']['punctuation_widths'].get(ch,16)-1
        elif ch == ' ':
            x += reference.call(9, segment=0x2326, far=True, args=(32,))['ax']
        else:
            for y, bits in enumerate(bytes.fromhex(latin['source_records'][ord(ch)]['rows'])):
                for dx in range(8):
                    if bits & (128 >> dx): expected[(28+y)*320+x+1+dx] = 1
            x += 5
    assert intro.u.mem_read(PAGE*16, 64000) == expected, 'mixed INTRO baseline/pixels'
    assert struct.unpack('<H', intro.u.mem_read(module*16+mode, 2))[0] == 0
    plain = b'A1? Z9!'
    cpu.text(plain); old.text(plain)
    expected_plain_width = sum(5 if cp in LEGACY_BYTE_SLOTS else
                               old.call(9, segment=0x2326, far=True, args=(cp,))['ax']
                               for cp in plain)
    assert cpu.call(0x2F, segment=0x2326, far=True, args=(0, TEXT))['ax'] == expected_plain_width
    assert state() == 0

    # Original printf code must expand raw directives before the scoped renderer.
    fmt = m.encode('크레딧 %d %s %d%%')
    assert b'%d %s %d%%' in fmt
    cpu.text(fmt)
    cpu.u.mem_write(TEXT*16+0x100, b'ABC\0')
    cpu.u.mem_write(STACK*16+0x100, struct.pack('<5H', 123, 0x100, TEXT, 45, 0))
    cpu.call(0x37AF, segment=0, far=True, args=(0x200, TEXT, 0, TEXT, 0x100, STACK))
    formatted = bytes(cpu.u.mem_read(TEXT*16+0x200, 128)).split(b'\0')[0]
    assert formatted == m.encode('크레딧 123 ABC 45%')
    expected_width = sum(map(advance, '크레딧 123 ABC 45%'))
    assert cpu.call(0x2F, segment=0x2326, far=True, args=(0x200, TEXT))['ax'] == expected_width
    assert state() == 0

    # Full text owner: leading/trailing ASCII must use the same scoped glyphs.
    cpu.word(DATA, 0x9A7F, 0); cpu.word(DATA, 0x9A81, FONT)
    cpu.text(m.encode(mixed))
    cpu.u.mem_write(PAGE*16, bytes(64000))
    cpu.call(4, segment=0x29C7, far=True, args=(0, TEXT, 20, 20, 1, 0))
    expected = bytearray(64000)
    x = 20
    for ch in mixed:
        rows = (m.glyph_source[ch] if ch in m.codes else
                bytes.fromhex(latin['source_records'][ord(ch)]['rows']))
        for y, bits in enumerate(rows):
            for dx in range(8):
                if bits & (128 >> dx): expected[(20+y)*320+x+1+dx] = 1
        x += advance(ch)
    assert cpu.u.mem_read(PAGE*16, 64000) == expected
    assert state() == 0

    # Load the actual overlay bodies at an explicit emulated runtime address.
    runtime = 0x4800
    def load_overlay(segment):
        at = module_at(exe, segment)
        size = struct.unpack_from('<H', exe, 0x4C00+segment*16+8)[0]
        raw = bytearray(exe[at:at+size])
        for gateway in (0xE, 0x13):
            old_call = b'\x9A'+struct.pack('<HH', gateway, 0x198)
            new_call = b'\x9A'+struct.pack('<HH', gateway, LOAD+0x2326)
            raw = raw.replace(old_call, new_call)
        cpu.u.mem_write((LOAD+runtime)*16, bytes(raw))
    load_overlay(0x3298)
    cpu.text(m.encode(mixed))
    cpu.u.mem_write(PAGE*16, bytes(64000))
    cpu.call(0x854, segment=runtime, far=True, args=(0, TEXT, 20, 20, 1, 0, 12))
    fixed = bytearray(64000)
    for i, ch in enumerate(mixed):
        rows = m.glyph_source[ch] if ch in m.codes else bytes.fromhex(latin['source_records'][ord(ch)]['rows'])
        for y, bits in enumerate(rows):
            for dx in range(8):
                if bits & (128 >> dx): fixed[(20+y)*320+21+i*12+dx] = 1
    assert cpu.u.mem_read(PAGE*16, 64000) == fixed, 'fixed-pitch ASCII inheritance'
    assert state() == 0
    for segment, offset, args in ((0x0EED, 0x1B8, (0, TEXT, 80, 13)),
                                  (runtime, 0x1893, (0, TEXT, 80))):
        if segment == runtime: load_overlay(0x32DD)
        cpu.text(m.encode('A1? 가 Z9! 가나다라 ABC 123. 다음 문장입니다.'))
        cpu.call(offset, segment=segment, far=True, args=args)
        assert state() == 0

    # All currently listed shortcut strings retain literal ASCII suffixes and
    # return the original game's keyboard mapping, including title/production.
    shortcut_count = 0
    by_index = {row['index']: row for row in m.rows if row['file'] == 'DUNE.ENG'}
    for index, key in m.keys.items():
        text = by_index[index]['translation_ko']
        if not text: continue
        raw = m.encode(text)
        assert raw.endswith(('('+key['shortcut']+')').encode('ascii'))
        cpu.text(raw)
        value = cpu.call(0xDA, segment=0x27DE, far=True, args=(raw[0],))['ax'] & 255
        expected_key = old.call(0xDA, segment=0x27DE, far=True, args=(ord(key['shortcut']),))['ax'] & 255
        assert value == expected_key != 0, ('shortcut', index)
        shortcut_count += 1
    for cp in latin['symbols']:
        raw = m.encode('가'+chr(cp))
        cpu.text(raw[2:])
        value = cpu.call(0x40)
        assert (value['ax'], value['dx']) == (0x100+latin['slots'][cp], 2)
    result = dict(scope='bounded x86 execution; original formatter and pixel renderer; whole game not launched',
        exe_sha256=hashlib.sha256(exe).hexdigest(), glyph_pixel_cases=glyph_cases,
        font_contexts=['NEW6P', 'NEW8P', 'INTRO'], shortcut_strings=shortcut_count,
        checks=dict(ASCII_bytes_and_printf_directives_preserved=True,
            original_printf_d_s_percent_executed=True, formatted_numbers_and_letters_use_Dalmoori=True,
            leading_and_trailing_ASCII_scoped=True, unscoped_ASCII_and_compatibility_symbols_verified=True,
            full_text_pixels=True, fixed_pitch_pixels_and_scope_inheritance=True,
            mixed_intro_Unifont_Dalmoori_baseline=True,
            wrap_and_description_owners_return=True, scope_restored_after_calls=True,
            non_ASCII_symbol_tokens=True, all_listed_shortcut_mappings=True))
    return result


def normalize_subtitle(cpu, raw, *, inplace=False):
    cpu.text(raw)
    destination = TEXT if inplace else 0x7600
    if not inplace:
        cpu.u.mem_write(destination*16, b'\xA5'*(len(raw)+1))
    result = cpu.call(scenes.SUBTITLE_START, segment=0x6000-LOAD, far=True,
                      args=(0, TEXT, 0, destination))
    return bytes(cpu.u.mem_read(destination*16, len(raw)+1)), result


def subtitle_cpu(exe, original_font):
    cpu = CPU(exe, original_font)
    at = module_at(exe, scenes.SUBTITLE_SEGMENT)
    size = struct.unpack_from('<H', exe, 0x4C00+scenes.SUBTITLE_SEGMENT*16+8)[0]
    # This function has no far references; no overlay relocation is required.
    cpu.u.mem_write(0x60000, exe[at:at+size])
    return cpu


def check_subtitles(folder):
    m = model_for_build(folder)
    game = folder/'source/VIRGIN/DUNE2' if (folder/'source').is_dir() else folder
    exe = (game/'DUNE2.EXE').read_bytes()
    original = original_file('DUNE2.EXE')
    _, fonts = model.unpack_pak(original_file('DUNE.PAK'))
    old, fixed = (subtitle_cpu(data, fonts['NEW8P.FNT']) for data in (original, exe))
    sentence = '정해진 영토도 없고,'
    # Sorted token reassignment means E1h is not permanently assigned to 토.
    corruption_char = next(ch for ch, code in m.codes.items() if code[1] == 0xE1)
    raw = m.encode(sentence+' '+corruption_char)
    old_output, _ = normalize_subtitle(old, raw)
    assert old_output == raw.replace(b'\xE1', b'\x01')+b'\0'
    assert old_output != raw+b'\0'
    texts = [m.encode(row['translation_ko'] or row['source_en']) for row in m.rows
             if row['file']=='INTRO.ENG' and 1 <= int(row['index']) <= 37]
    texts += [b''.join(m.codes[ch] for ch in m.syllables), raw]
    texts += [m.encode('가'+''.join(map(chr, m.latin_symbols)))]
    checks = 0
    for text in texts:
        for inplace in (False, True):
            output, regs = normalize_subtitle(fixed, text, inplace=inplace)
            assert output == text+b'\0'
            assert (regs['si'], regs['di'], regs['bp']) == (0x5555, 0x6666, 0x7777)
            checks += 1
    legacy = b'English\xE1 text\rnext'
    output, _ = normalize_subtitle(fixed, legacy)
    assert output == legacy.replace(b'\xE1', b'\x01')+b'\0'
    token = m.codes[corruption_char]
    report = dict(scope='real original and repaired 16-bit subtitle normalizers; no DOS/game launch',
                  exe_sha256=hashlib.sha256(exe).hexdigest(), sentence=sentence,
                  corruption_character=corruption_char, token=token.hex().upper(),
                  original_corrupted_token=token.replace(b'\xE1', b'\x01').hex().upper(),
                  original_corruption_reproduced=True, normalizer_cases=checks,
                  opening_and_all_house_ending_texts_preserved=True,
                  every_registered_syllable_preserved=True,
                  every_Dalmoori_symbol_token_preserved=True,
                  same_and_separate_buffers=True, legacy_single_byte_conversion_preserved=True)
    return report


def parse_region(exe,font,raw,section,key,poison=()):
    cpu=CPU(exe,font);base=module_at(exe,0x32FF)
    size=struct.unpack_from('<H',exe,0x4C00+0x32FF*16+8)[0]
    code=bytearray(exe[base:base+size]);md=Cs(CS_ARCH_X86,CS_MODE_16)
    for i in md.disasm(code,0):
        if i.bytes[0]==0x9A and len(i.bytes)==5:
            off,seg=struct.unpack_from('<HH',i.bytes,1)
            if seg==0:struct.pack_into('<H',code,i.address+3,LOAD)
            elif seg==0x2A0 and off==0xCA:struct.pack_into('<HH',code,i.address+1,0,0x7400)
    cpu.u.mem_write(0x60000,bytes(code))
    # Only FAR-pointer canonicalization is a bounded identity service. The
    # original INI parser, ctype lookups, strlen/copy/compare code execute.
    cpu.u.mem_write(0x74000,bytes.fromhex('558bec8b46068b56085dcb'))
    cpu.u.mem_write(TEXT*16,raw+b'\0')
    cpu.u.mem_write(TEXT*16+0x6000,section+b'\0')
    cpu.u.mem_write(TEXT*16+0x6100,key+b'\0')
    for byte in poison:
        signed=byte-256 if byte>=128 else byte
        cpu.u.mem_write(DATA*16+0x7749+signed,b'\x01')
    cpu.call(0x3C8,segment=0x6000-LOAD,far=True,
             args=(0x6000,TEXT,0x6100,TEXT,0,0,0x6200,TEXT,1024,0,TEXT))
    return bytes(cpu.u.mem_read(TEXT*16+0x6200,1024)).split(b'\0')[0]


def check_region(folder):
    game=folder/'source/VIRGIN/DUNE2';exe=(game/'DUNE2.EXE').read_bytes()
    old=bytearray(exe);at=module_at(exe,0x32FF)
    for off in runtime.REGION_SITES:old[at+off:at+off+3]=runtime.REGION_OLD
    old=bytes(old)
    scenario=model.unpack_pak((game/'SCENARIO.PAK').read_bytes())[1]
    font=model.unpack_pak((game/'DUNE.PAK').read_bytes())[1]['NEW6P.FNT']
    raw=scenario['REGIONA.INI']
    line=next(x for x in raw.splitlines() if x.startswith(b'ENGTXT13'))
    expected=line.split(b'=',1)[1].strip(b' \t')
    # The source's actual first syllable is wrongly tested against mutable
    # bytes before ctype[0]. Simulate those two runtime bytes being whitespace.
    before=parse_region(old,font,raw,b'GROUP1',b'ENGTXT13',expected[:2])
    after=parse_region(exe,font,raw,b'GROUP1',b'ENGTXT13',expected[:2])
    assert before==expected[2:] and after==expected,(before,after,expected)
    checked=0
    for name,raw in scenario.items():
        if not name.startswith('REGION') or not name.endswith('.INI'):continue
        section=b''
        for line in raw.splitlines():
            if line.startswith(b'[') and b']' in line:section=line[1:line.index(b']')]
            match=re.match(rb'(ENGTXT\d+)\s*=\s*(.*)',line)
            if match:
                key,value=match.groups()
                value=value.rstrip(b' \t')
                got=parse_region(exe,font,raw,section,key,tuple(range(128,256)))
                assert got==value,(name,section,key,got,value)
                checked+=1
    byte_cases=0
    for value in range(128,256):
        for text in (bytes([value])+b'X',b'X'+bytes([value])):
            sample=b'\r\n[TEST]\r\nVALUE =  '+text+b' \t\r\n'
            got=parse_region(exe,font,sample,b'TEST',b'VALUE',tuple(range(128,256)))
            assert got==text,(value,got,text)
            byte_cases+=1
    assert parse_region(exe,font,b'\r\n[TEST]\r\nVALUE = \t ASCII text \t\r\n',b'TEST',b'VALUE')==b'ASCII text'
    report=dict(passed=True,original_bug_reproduced=True,first_syllable_removed_before=True,
                corrected_full_value_preserved=True,region_english_values_checked=checked,
                all_high_byte_boundary_cases=byte_cases,ASCII_whitespace_preserved=True,
                simulated_negative_index_bytes='all high-bit signed ctype indices marked as whitespace',
                original_strcpy_strlen_compare_and_parser_executed=True,
                pointer_normalization_stubbed=True,game_execution=False,
                sample_original=expected.hex(),sample_before=before.hex(),sample_after=after.hex())
    return report


def check_houses(folder):
    m=model_for_build(folder);game=folder/'source/VIRGIN/DUNE2';exe=(game/'DUNE2.EXE').read_bytes()
    dune=model.unpack_pak((game/'ENGLISH.PAK').read_bytes())[1]['DUNE.ENG']
    original_font=model.unpack_pak((game/'DUNE.PAK').read_bytes())[1]['NEW6P.FNT']
    overlay=module_at(exe,0x331B);code=exe[overlay:overlay+0x1500]
    results=[]
    for house in m.houses:
        for rank in range(12):
            cpu=CPU(exe,original_font);u=cpu.u;cs=0x6000;record=0x7800
            u.mem_write(cs*16,code)
            for off in (0x1301,0x1313,0x1336,0x1348,0x136C):
                assert u.mem_read(cs*16+off,1)==b'\x9a'
                cpu.word(cs,off+3,LOAD)
            # Resource lookup is bounded to the actual generated PAK. All
            # strcpy/strcat and the display-name lookup execute original x86.
            cpu.word(cs,0x135F+1,0);cpu.word(cs,0x135F+3,0x7400)
            u.mem_write(0x74000,b'\xcb')
            def resource(u,address,size,user):
                if address==0x74000:
                    index=struct.unpack('<H',u.mem_read(STACK*16+u.reg_read(REGS['sp'])+4,2))[0]
                    pos=struct.unpack_from('<H',dune,index*2)[0]
                    text=dune[pos:dune.index(0,pos)]+b'\0';u.mem_write(TEXT*16,text)
                    u.reg_write(REGS['ax'],0);u.reg_write(REGS['dx'],TEXT)
            u.hook_add(UC_HOOK_CODE,resource)
            values=dict(ax=0x1234,bx=0,cx=0x3456,dx=0x4567,si=90,di=1,bp=0xE00,sp=0xD80,ss=STACK,ds=DATA,es=record,cs=cs)
            for k,v in values.items():u.reg_write(REGS[k],v)
            u.mem_write(record*16,b'a\0'+b'\0'*14);cpu.word(record,6,57);cpu.word(record,8,rank);cpu.word(record,12,int(house['house_id']))
            cpu.word(STACK,0xE06,0);cpu.word(STACK,0xE08,record)
            def string(seg,offset):return bytes(u.mem_read(seg*16+offset,180)).split(b'\0')[0]
            rankid=struct.unpack('<H',u.mem_read(DATA*16+0x37B4+rank*4,2))[0]
            pos=struct.unpack_from('<H',dune,rankid*2)[0];ranktext=dune[pos:dune.index(0,pos)]
            expected=b'a'+string(DATA,0x2C4B)+m.encode(house['translation_ko'])+string(DATA,0x2C4C)+ranktext
            u.emu_start(cs*16+0x12F6,cs*16+0x1374,count=50000)
            actual=string(DATA,0x99C5)
            assert actual==expected,(house['house_id'],rank,actual,expected)
            assert u.reg_read(REGS['sp'])==0xD80
            assert u.reg_read(REGS['bp'])==0xE00 and u.reg_read(REGS['si'])==90 and u.reg_read(REGS['di'])==1
            assert u.mem_read(record*16,16)==b'a\0'+b'\0'*4+struct.pack('<HHHHH',57,rank,0,int(house['house_id']),0)
            results.append(dict(house=house['translation_ko'],rank=rank,display_bytes=actual.hex()))
    result=dict(passed=True,scope='bounded x86; original strcpy/strcat and CSV display lookup; PAK lookup stubbed',
                cases=len(results),houses=[h['translation_ko'] for h in m.houses],all_12_ranks=True,
                record_bytes_and_stack_preserved=True,exe_sha256=hashlib.sha256(exe).hexdigest(),game_execution=False,rows=results)
    return result


def question_copy_calls(code,language,house):
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,0x100000);cs=0x6000;ds=0x3000;ss=0x8000
    u.mem_write(cs*16+runtime.QUESTION_START,code)
    for reg,val in ((UC_X86_REG_CS,cs),(UC_X86_REG_DS,ds),(UC_X86_REG_SS,ss),(UC_X86_REG_SP,0xF000),(UC_X86_REG_SI,house),(UC_X86_REG_AX,0xABCD),(UC_X86_REG_DX,0xDCBA)):
        u.reg_write(reg,val)
    u.mem_write(ds*16+0x37AA,struct.pack('<H',language));out=[]
    def capture(u,address,size,data):
        ip=address-cs*16
        if ip in (0x13B3,0x13DF):
            sp=u.reg_read(UC_X86_REG_SP)
            out.append(list(struct.unpack('<8H',u.mem_read(ss*16+sp,16))))
            u.reg_write(UC_X86_REG_IP,ip+5)
            u.reg_write(UC_X86_REG_AX,0xA55A);u.reg_write(UC_X86_REG_DX,0x5AA5)
    u.hook_add(UC_HOOK_CODE,capture)
    u.emu_start(cs*16+runtime.QUESTION_START,cs*16+runtime.QUESTION_END,count=100)
    assert u.reg_read(UC_X86_REG_SP)==0xF000 and u.reg_read(UC_X86_REG_SI)==house
    return out


def check_question_rows(folder):
    x=(folder/'source/VIRGIN/DUNE2/DUNE2.EXE').read_bytes();a=module_at(x,0x3314)
    code=x[a+runtime.QUESTION_START:a+runtime.QUESTION_END]
    records=[]
    for language in (0,1,2):
        for house in (0,1,2):
            actual=question_copy_calls(code,language,house)
            expected=([[0,((house+2)%3)*24,0,0,39,24,2,0]] if language==0 else
                      [[0,0,0,0,26,24,2,0],[0,(house+1)*24,26,0,13,24,2,0]])
            assert actual==expected,(language,house,actual,expected)
            if language:assert actual==question_copy_calls(runtime.QUESTION_OLD,language,house)
            records.append(dict(language=language,house_id=house,copy_arguments=actual))
    result=dict(passed=True,scope='bounded 16-bit x86 argument execution; whole game not launched',
                editable_rows=['Atreides','Ordos','Harkonnen'],native_id_to_row=[2,0,1],
                all_9_cases=records,FRE_GER_original_arguments_preserved=True,
                SI_and_argument_stack_preserved=True,exe_sha256=hashlib.sha256(x).hexdigest())
    return result


def setmap(cpu,edge):
    for index,value in enumerate(bytes([0,6])+edge):
        for step in (1,16):cpu.u.mem_write((LOAD+0x20AA)*16+0x91+index*step,bytes([value]))


def check_styles(folder):
    baseline=original_file('DUNE2.EXE');candidate=(folder/GAME/'DUNE2.EXE').read_bytes();original=baseline
    editor=folder/'build-report.json'
    syllables=json.loads(editor.read_text(encoding='utf-8'))['font_build']['syllable_count'] if editor.exists() else 0
    # Establish the class geometry directly from the original NEW6P pixels.
    source_font=unpack_pak(original_file('DUNE.PAK'))[1]['NEW6P.FNT']
    _,op,wp,_,hp=struct.unpack_from('<5H',source_font,4)
    geometry_pixels=0
    for code in range(33,127):
        offset=struct.unpack_from('<H',source_font,op+code*2)[0]
        w=source_font[wp+code];h=source_font[hp+code*2+1]
        pixels={(x,y):source_font[offset+y*((w+1)//2)+x//2]>>(4*(x%2))&15 for y in range(h) for x in range(w)}
        body={p for p,c in pixels.items() if c==1}
        edge2={(x+dx,y+dy) for x,y in body for dx,dy in ((1,0),(0,1),(1,1))}-body
        edge3={(x+dx,y+dy) for x,y in body for dx in (-1,0,1) for dy in (-1,0,1)}-body-edge2
        for p,c in pixels.items():
            assert c==(1 if p in body else 2 if p in edge2 else 3 if p in edge3 else 0),(code,p)
            geometry_pixels+=1
    # Real formatter installs its driver mapping. Render all valid ASCII,
    # including shortcut parentheses/letters, with the unmodified FNT driver.
    latin_cases=0;style_results=[]
    for name in ('NEW6P.FNT','NEW8P.FNT','NEW10P.FNT','STD3P.FNT','INTRO.FNT'):
        pak='INTRO.PAK' if name=='INTRO.FNT' else 'DUNE.PAK'
        font=unpack_pak(original_file(pak))[1][name]
        for style,edge in STYLES.items():
            a=CPU(original,font);b=CPU(candidate,font)
            for cpu in (a,b):
                cpu.word(DATA,0x3A28,2)
                cpu.call(0x1E65,segment=0x0EED,far=True,args=(0,0,0,0,6,0,style|2))
                assert bytes(cpu.u.mem_read(DATA*16+0x8B6C,2))==edge,(name,style)
            for code in range(33,min(127,font[17]+1)):
                images=[]
                for cpu in (a,b):
                    cpu.u.mem_write(PAGE*16,b'\0'*64000)
                    cpu.call(0x7BD,segment=0x20AA,far=True,args=(code,100,50))
                    images.append(bytes(cpu.u.mem_read(PAGE*16,64000)))
                assert images[0]==images[1],(name,style,chr(code))
                latin_cases+=1
            style_results.append(dict(font=name,style=hex(style),edge_mapping=edge.hex()))
    # Test all Hangul bodies under every original edge style. Directional
    # edge 2 takes priority; edge 3 is the remaining 8-neighbour boundary.
    hangul_cases=0
    for name in ('NEW6P.FNT','NEW8P.FNT'):
        font=unpack_pak(original_file('DUNE.PAK'))[1][name]
        cpu=CPU(candidate,font)
        for code in range(0x100,0x100+syllables):
            setmap(cpu,bytes([0,0]));cpu.u.mem_write(PAGE*16,b'\0'*64000)
            cpu.call(0x190,far=True,args=(code,100,50))
            plain=bytes(cpu.u.mem_read(PAGE*16,64000));body={i for i,p in enumerate(plain) if p==6}
            assert body
            edge2={i+d for i in body for d in (1,320,321)}-body
            edge3={i+dy*320+dx for i in body for dx in (-1,0,1) for dy in (-1,0,1)}-body-edge2
            for style,edge in STYLES.items():
                setmap(cpu,edge);cpu.u.mem_write(PAGE*16,b'\0'*64000)
                cpu.call(0x190,far=True,args=(code,100,50))
                expected=bytearray(64000)
                for i in edge3:expected[i]=edge[1]
                for i in edge2:expected[i]=edge[0]
                for i in body:expected[i]=6
                assert bytes(cpu.u.mem_read(PAGE*16,64000))==expected,(name,style,hex(code))
                hangul_cases+=1
    # A real variadic numeric format remains intact (production percentages).
    latin_cases_scoped=0
    if editor.exists():
        details=json.loads(editor.read_text(encoding='utf-8'))['font_build']
        latin=font_tools.latin_package(ROOT,syllables)
        for name in ('NEW6P.FNT','NEW8P.FNT'):
            font=unpack_pak(original_file('DUNE.PAK'))[1][name]
            cpu=CPU(candidate,font)
            cpu.word(LOAD+0x3D02,details['latin']['mode_offset'],1)
            for cp,slot in latin['slots'].items():
                if cp==32:continue
                code=cp if cp<127 else 0x100+slot
                setmap(cpu,bytes([0,0]));cpu.u.mem_write(PAGE*16,b'\0'*64000)
                cpu.call(0x190,far=True,args=(code,100,50))
                body={i for i,p in enumerate(cpu.u.mem_read(PAGE*16,64000)) if p==6}
                assert body
                edge2={i+d for i in body for d in (1,320,321)}-body
                edge3={i+dy*320+dx for i in body for dx in (-1,0,1) for dy in (-1,0,1)}-body-edge2
                for style,edge in STYLES.items():
                    setmap(cpu,edge);cpu.u.mem_write(PAGE*16,b'\0'*64000)
                    cpu.call(0x190,far=True,args=(code,100,50))
                    expected=bytearray(64000)
                    for i in edge3:expected[i]=edge[1]
                    for i in edge2:expected[i]=edge[0]
                    for i in body:expected[i]=6
                    assert bytes(cpu.u.mem_read(PAGE*16,64000))==expected,(name,style,cp,'scoped Latin edge')
                    latin_cases_scoped+=1
    font=unpack_pak(original_file('DUNE.PAK'))[1]['NEW8P.FNT']
    for value in (0,1,25,50,99,100):
        outputs=[]
        for exe in (baseline,candidate):
            cpu=CPU(exe,font);cpu.word(DATA,0x3A28,1);cpu.text(b'%u%%')
            result=cpu.call(0x1E65,segment=0x0EED,far=True,args=(0,0x7200,20,20,1,0,0x11,value))
            text=bytes(cpu.u.mem_read(DATA*16+0x8B7A,32)).split(b'\0')[0]
            assert text==f'{value}%'.encode();outputs.append((result,text))
        assert outputs[0]==outputs[1]
    report=dict(passed=True,scope='bounded x86 execution; game not launched',
        original_ascii_pixel_cases=latin_cases,hangul_pixel_cases=hangul_cases,
        scoped_dalmoori_latin_style_cases=latin_cases_scoped,
        original_new6p_edge_geometry_pixels=geometry_pixels,
        original_styles=style_results,percentage_cases=6,original_style_code_restored=True,
        no_screen_allowlist=True,all_original_font_regions_including_title=True,
        mz_layout_verified_by_structure_section=True)
    return report


def check_spacing(folder):
    new=(folder/GAME/'DUNE2.EXE').read_bytes()
    base=bytearray(new)
    original=original_file('DUNE2.EXE')
    panel=HEADER+0x0EED*16
    for a,b in ((0xF22,0xF90),(0x1B02,0x1B08)):
        base[panel+a:panel+b]=original[panel+a:panel+b]
    base=bytes(base)
    font=unpack_pak(original_file('DUNE.PAK'))[1]['NEW6P.FNT']
    for initial in (-2,0,2):
        states=[]
        for exe in (base,new):
            cpu=CPU(exe,font);u=cpu.u
            values=dict(ax=0x1234,bx=0x2345,cx=0x3456,dx=0x4567,si=0x5678,di=0x6789,bp=0x8000,sp=0x7FAC,ss=STACK,ds=DATA,es=TEXT)
            for k,v in values.items():u.reg_write(REGS[k],v)
            cpu.word(DATA,0x6CFA,initial);cpu.word(STACK,0x7FAC,values['di']);cpu.word(STACK,0x7FAE,values['si'])
            u.mem_write(STACK*16+0x8000,struct.pack('<3H',0x7777,0xFFF0,0x6000))
            u.reg_write(UC_X86_REG_EFLAGS,0x246);u.reg_write(REGS['cs'],LOAD+0xEED)
            u.emu_start((LOAD+0xEED)*16+0xF22,(LOAD+0xEED)*16+0xF90,count=200)
            assert u.reg_read(UC_X86_REG_IP)==0xF90
            spacing=struct.unpack('<h',u.mem_read(DATA*16+0x6CFA,2))[0]
            assert spacing==initial+(exe is new)
            states.append((bytes(u.mem_read(STACK*16+0x7FB0,0x50)),u.reg_read(UC_X86_REG_EFLAGS)))
            u.emu_start((LOAD+0xEED)*16+0x1B02,0x6FFF0,count=100)
            assert u.reg_read(REGS['cs'])==0x6000 and u.reg_read(UC_X86_REG_IP)==0xFFF0
            assert u.reg_read(REGS['sp'])==0x8006 and u.reg_read(REGS['bp'])==0x7777
            assert u.reg_read(REGS['di'])==values['di'] and u.reg_read(REGS['si'])==values['si']
            assert struct.unpack('<h',u.mem_read(DATA*16+0x6CFA,2))[0]==initial
        assert states[0]==states[1]
    ys=[]
    for spacing in (0,1):
        cpu=CPU(new,font);cpu.text(b'A\rA');cpu.word(DATA,0x9A7F,0);cpu.word(DATA,0x9A81,FONT);cpu.word(DATA,0x6CFA,spacing)
        for index,value in enumerate((0,15,0,0)):
            for step in (1,16):cpu.u.mem_write((LOAD+0x20AA)*16+0x91+index*step,bytes([value]))
        seen=[]
        def record(u,address,size,data):
            if address==(LOAD+0x20AA)*16+0x7BD:
                sp=u.reg_read(REGS['sp']);ss=u.reg_read(REGS['ss']);seen.append(struct.unpack('<3H',u.mem_read(ss*16+sp+4,6)))
        cpu.u.hook_add(UC_HOOK_CODE,record)
        cpu.call(4,segment=0x29C7,far=True,args=(0,TEXT,259,84,15,0))
        assert len(seen)==2,seen
        ys.append([v[2] for v in seen])
    assert ys[0][0]==ys[1][0] and ys[1][1]==ys[0][1]+1,ys
    dune=unpack_pak((folder/GAME/'ENGLISH.PAK').read_bytes())[1]['DUNE.ENG']
    at=struct.unpack_from('<H',dune,84*2)[0];raw=dune[at:dune.index(0,at)]
    actual_rows=[]
    for spacing in (0,1):
        cpu=CPU(new,font);cpu.text(raw);cpu.word(DATA,0x9A7F,0);cpu.word(DATA,0x9A81,FONT);cpu.word(DATA,0x6CFA,spacing)
        for index,value in enumerate((0,15,0,0)):
            for step in (1,16):cpu.u.mem_write((LOAD+0x20AA)*16+0x91+index*step,bytes([value]))
        drawn=[]
        def capture(u,address,size,data):
            if address==(LOAD+0x20AA)*16+0x7BD:
                drawn.append(struct.unpack('<3H',u.mem_read(u.reg_read(REGS['ss'])*16+u.reg_read(REGS['sp'])+4,6)))
        cpu.u.hook_add(UC_HOOK_CODE,capture)
        cpu.call(4,segment=0x29C7,far=True,args=(0,TEXT,259,84,15,0))
        actual_rows.append(sorted({v[2] for v in drawn}))
    assert actual_rows==[[84,92],[84,93]],actual_rows
    report=dict(passed=True,scope='bounded original x86 execution',entry_exit_cases=6,previous_spacing_restored=True,
                original_line_y=ys[0],new_line_y=ys[1],translated_string_84_line_y=actual_rows,first_line_unchanged=True,extra_line_spacing=1,game_execution=False)
    return report


CHEAT_EXE = CHEAT_ORIGINAL = CHEAT_REPORT = CHEAT_SEGMENT = CHEAT_ENTRIES = None
CHEAT_REGS = dict(REGS, ip=UC_X86_REG_IP, flags=UC_X86_REG_EFLAGS)


class CheatCPU:
    def __init__(self, exe=None, load=0x75b):
        exe = CHEAT_EXE if exe is None else exe
        self.exe, self.load, self.ds = exe, load, load+0x3342
        self.cs, self.ss = load+CHEAT_SEGMENT, 0x9000
        self.u = Uc(UC_ARCH_X86, UC_MODE_16)
        self.u.mem_map(0,0x110000)
        header = struct.unpack_from('<H',exe,8)[0]*16
        last,pages = struct.unpack_from('<HH',exe,2)
        end = (pages-1)*512+(last or 512)
        self.u.mem_write(load*16,exe[header:end])
        count,table = struct.unpack_from('<H',exe,6)[0],struct.unpack_from('<H',exe,0x18)[0]
        for i in range(count):
            off,seg = struct.unpack_from('<HH',exe,table+4*i)
            self.w(load+seg,off,(self.rw(load+seg,off)+load)&0xffff)
        for name,value in dict(ax=0x500,bx=0x1234,cx=0x2345,dx=0x3456,si=0x100,
                               di=0x5678,bp=0xd000,sp=0xcfc0,ds=self.ds,es=0x7200,
                               ss=self.ss,flags=0x202).items():
            self.set(name,value)
        self.w(self.ds,0x38ec,1)
        self.w(self.ds,0x3c1a,0x100)
        self.w(self.ds,0x3c1c,0x8000)
        self.w(self.ds,0x1902,0x100)
        self.w(self.ds,0x1904,0x8000)
        self.w(self.ds,0x3a2c,1)
        self.b(self.cs,0x98d,1)
        self.stops = set()
        self.actions = {}
        self.u.hook_add(UC_HOOK_CODE,self.hook)

    def get(self,name): return self.u.reg_read(CHEAT_REGS[name])
    def set(self,name,value): self.u.reg_write(CHEAT_REGS[name],value)
    def b(self,seg,off,value): self.u.mem_write(seg*16+off,bytes([value]))
    def w(self,seg,off,value): self.u.mem_write(seg*16+off,struct.pack('<H',value))
    def rb(self,seg,off): return self.u.mem_read(seg*16+off,1)[0]
    def rw(self,seg,off): return struct.unpack('<H',self.u.mem_read(seg*16+off,2))[0]
    def hook(self,u,address,size,user):
        if address in self.stops:
            self.hit=address
            u.emu_stop()
        elif address in self.actions:
            self.actions[address](self)
    def run(self,seg,off,stops,count=2000000):
        self.stops={s*16+o for s,o in stops}
        self.set('cs',seg);self.set('ip',off);self.hit=None
        self.u.emu_start(seg*16+off,0x10fff0,count=count)
        assert self.hit in self.stops, ('instruction budget or missing return',hex(self.get('cs')),hex(self.get('ip')))
    def frame(self,far=False,seg=None,off=0xf000):
        sp=self.get('sp');self.w(self.ss,sp,off)
        if far:self.w(self.ss,sp+2,self.cs if seg is None else seg)
        return sp
    def ret(self,far=False):
        sp=self.get('sp');ip=self.rw(self.ss,sp)
        if far:self.set('cs',self.rw(self.ss,sp+2))
        self.set('sp',sp+(4 if far else 2));self.set('ip',ip)
    def native_math_overlay(self):
        exe=self.exe;header=struct.unpack_from('<H',exe,8)[0]*16
        last,pages=struct.unpack_from('<HH',exe,2);end=(pages-1)*512+(last or 512)
        stub=header+0x32c4*16
        rel,size,fixup_bytes,entries=struct.unpack_from('<IHHH',exe,stub+4)
        at=end+16+rel;code=bytearray(exe[at:at+size])
        directory,total=struct.unpack_from('<II',exe,end+8)
        for i in range(fixup_bytes//2):
            off=struct.unpack_from('<H',exe,at+size+2*i)[0]
            sel=struct.unpack_from('<H',code,off)[0]
            assert sel%8==0 and sel//8<total
            seg=struct.unpack_from('<H',exe,directory+sel)[0]
            struct.pack_into('<H',code,off,seg+self.load)
        self.u.mem_write(0x70000,bytes(code))
        for i in range(entries):
            off=0x20+5*i
            entry=struct.unpack_from('<H',exe,stub+off+2)[0]
            self.u.mem_write((self.load+0x32c4)*16+off,b'\xea'+struct.pack('<HH',entry,0x7000))


def production(exe,human,owner,enabled,kind,step,remaining,load=0x75b,money=10000):
    c=CheatCPU(exe,load);c.native_math_overlay()
    c.set('flags',0x602) # Stress DF preservation in the new production hook.
    c.w(c.ds,0x3a2c,human);c.w(c.ds,0x84c0,0x100);c.w(c.ds,0x84c2,0x8000)
    c.b(0x8000,0x108,owner);c.b(0x8000,0x102,kind)
    c.w(0x8000,0x150,remaining);c.w(0x8000,0x152,37)
    c.w(c.ds,0x35ee,0);c.w(c.ds,0x35f0,0x8500)
    c.w(0x8500,owner*0x42+4,1);c.w(0x8500,owner*0x42+0x12,money)
    c.w(c.ds,0x393e,owner*0x42);c.w(c.ds,0x3940,0x8500)
    c.w(c.ss,c.get('bp')-0x18,0x100);c.w(c.ss,c.get('bp')-0x16,0x8400)
    c.w(0x8400,0x116,600);c.w(0x8400,0x118,120)
    c.b(c.cs,0xc41,enabled);c.set('si',step)
    c.run(load+0x77b,0x4d2,[(load+0x77b,0x578),(load+0x77b,0x716)])
    return dict(regs={n:c.get(n) for n in 'ax bx cx dx si di bp sp ds es ss flags'.split()},
                money=c.rw(0x8500,owner*0x42+0x12),remaining=c.rw(0x8000,0x150),
                fraction=c.rw(0x8000,0x152),local=c.rw(c.ss,c.get('bp')-0x10),exit=c.hit)


def check_production():
    cases=0
    for human,owner,enabled,kind,step,remaining in itertools.product(
            range(3),range(3),range(2),(8,3,13),(0x40,0x100),(0x30,0x1000)):
        expected=min(step*5,remaining) if enabled and human==owner and kind!=13 else step
        actual=production(CHEAT_EXE,human,owner,enabled,kind,step,remaining)
        reference=production(CHEAT_ORIGINAL,human,owner,0,kind,expected,remaining)
        assert actual==reference,(human,owner,enabled,kind,step,remaining,actual,reference)
        cases+=1
    for load in (0x1000,0x1800):
        assert production(CHEAT_EXE,1,1,1,8,0x100,0x1000,load)==production(CHEAT_ORIGINAL,1,1,0,8,0x500,0x1000,load)
        cases+=1
    poor=production(CHEAT_EXE,1,1,1,8,0x100,0x1000,money=0)
    assert poor['money']==0 and poor['remaining']==0x1000 and poor['fraction']==37
    return cases+1


def install_map_calls(c,bounds=(1,1,62,62),require_restored=None):
    visited=[];revealed=[]
    def valid(q):
        sp=q.get('sp');tile=q.rw(q.ss,sp+4);visited.append(tile)
        x,y=tile&63,tile>>6;bx,by,w,h=bounds
        q.set('ax',int(bx<=x<bx+w and by<=y<by+h))
        q.set('bx',0x3344);q.set('cx',0x7788);q.set('dx',0x5566);q.set('es',0x6000)
        q.ret(True)
    def reveal(q):
        if require_restored is not None:assert require_restored[0]
        sp=q.get('sp');tile=q.rw(q.ss,sp+4);house=q.rw(q.ss,sp+6)
        assert house==q.rw(q.ds,0x3a2c)
        revealed.append(tile);q.set('ax',1);q.set('cx',0x6633);q.set('dx',0x2200);q.set('es',0x6100)
        q.ret(True)
    c.actions[(c.load+0x32d0)*16+0x57]=valid
    c.actions[(c.load+0x32d0)*16+0xca]=reveal
    return visited,revealed


def check_map_wrapper():
    for load,bounds in [(0x75b,(1,1,62,62)),(0x1800,(16,16,32,32))]:
        c=CheatCPU(load=load);visited,revealed=install_map_calls(c,bounds)
        initial={n:c.get(n) for n in 'ax bx cx dx si di bp ds es ss'.split()}
        sp=c.frame();c.run(c.cs,CHEAT_ENTRIES['RevealNativeMap'],[(c.cs,0xf000)])
        assert visited==list(range(4096))
        bx,by,w,h=bounds
        assert revealed==[y*64+x for y in range(by,by+h) for x in range(bx,bx+w)]
        assert c.get('sp')==sp+2
        assert initial=={n:c.get(n) for n in initial}
    return 2


def check_commands():
    # The verified IRQ hook saves FLAGS after its displaced SUB SP,4 prologue.
    # Compare that existing contract rather than demanding pre-prologue FLAGS.
    reference=CheatCPU();reference.b(reference.cs,0x816,1)
    rg=reference.load+0x27ec;reference.w(rg,0x25e,1);reference.b(rg,0x24c,0x1c)
    reference.frame(True,rg,0xf0b);reference.run(reference.cs,0x40,[(rg,0xf0b)])
    original_flags=reference.get('flags')
    cases=0
    for command in ('FASTBUILD','REVEAL','CREDITS','WIN','LOSE','WRONG',''):
        c=CheatCPU();c.b(c.cs,0x816,1);c.b(c.cs,0x818,len(command))
        if command:c.u.mem_write(c.cs*16+0x824,command.encode('ascii'))
        game=c.load+0x27ec;c.w(game,0x25e,1);c.b(game,0x24c,0x1c)
        c.w(c.ds,0x3a2e,0x100);c.w(c.ds,0x3a30,0x8000);c.w(0x8000,0x112,100)
        initial={n:c.get(n) for n in 'ax bx cx dx si di bp ds es ss flags'.split()}
        sp=c.frame(True,game,0xf0b);c.run(c.cs,0x40,[(game,0xf0b)])
        assert c.get('sp')==sp+4
        expected=dict(initial,flags=original_flags)
        assert expected=={n:c.get(n) for n in initial}
        expected={'FASTBUILD':4,'REVEAL':5}.get(command,0)
        assert c.rb(c.cs,0xc40)==expected
        assert c.rb(c.cs,0xc41)==0 # IRQ queues FASTBUILD; it does not apply it.
        assert c.rw(0x8000,0x112)==(10100 if command=='CREDITS' else 100)
        assert c.rb(c.cs,0x81b)=={'WIN':1,'LOSE':2}.get(command,0)
        assert c.rb(c.cs,0x816)==int(command=='WRONG')
        if command=='WRONG':assert c.rb(c.cs,0x818)==0 and c.rb(c.cs,0x819)==1
        cases+=1
    return cases


def check_modal_and_reset():
    for command in (4,5):
        c=CheatCPU();restored=[False]
        visited,revealed=install_map_calls(c,require_restored=restored)
        messages=[]
        def status(q):
            assert restored[0]
            sp=q.get('sp');off=q.rw(q.ss,sp+4);seg=q.rw(q.ss,sp+6)
            assert q.rw(q.ss,sp+8)==2
            text=bytes(q.u.mem_read(seg*16+off,32)).split(b'\0')[0].decode('ascii')
            messages.append(text)
            assert text==('FASTBUILD ON' if q.rb(q.cs,0xc41) else 'FASTBUILD OFF')
            q.ret(True)
        c.actions[(c.load+0xeed)*16+0x9ab]=status
        c.b(c.cs,0x816,1);c.w(c.ds,0x6d1d,2)
        def save(q):q.b(q.cs,0x973,1);q.ret()
        def draw(q):q.b(q.cs,0xc40,command);q.b(q.cs,0x816,0);q.ret()
        def restore(q):restored[0]=True;q.ret()
        for name,fn in [('SavePanel',save),('DrawPanel',draw),('RestorePanel',restore)]:
            c.actions[c.cs*16+find_label(name)]=fn
        initial={n:c.get(n) for n in 'bx cx dx si di bp ds es ss flags'.split()}
        sp=c.frame(True,c.load+0x44b,0x30e)
        c.run(c.cs,0x2a0,[(c.load+0x44b,0x30e)])
        assert restored[0] and c.rb(c.cs,0xc40)==0 and c.rb(c.cs,0x98d)==1
        assert c.get('sp')==sp+4 and c.get('ax')==2 and c.rw(c.ds,0x6d1d)==0
        assert initial=={n:c.get(n) for n in initial}
        assert c.rb(c.cs,0xc41)==int(command==4)
        if command==5:assert len(visited)==4096 and len(revealed)==62*62
        if command==4:
            assert messages==['FASTBUILD ON']
            c.b(c.cs,0xc40,4);sp=c.frame();c.run(c.cs,CHEAT_ENTRIES['ApplyExtraPending'],[(c.cs,0xf000)])
            assert c.rb(c.cs,0xc41)==0 and c.get('sp')==sp+2
            assert messages==['FASTBUILD ON','FASTBUILD OFF']
        else:assert messages==[]
    for result,target in [(1,0x32f),(2,0x48d)]:
        c=CheatCPU();c.b(c.cs,0x81b,result);c.b(c.cs,0xc41,1);c.b(c.cs,0xc40,5);c.w(c.ds,0x3792,1)
        sp=c.frame(True,c.load+0x1223,0x32d)
        c.run(c.cs,0x300,[(c.load+0x1223,target)])
        assert c.get('sp')==sp+4
        assert all(c.rb(c.cs,o)==0 for o in (0x81b,0x98d,0xc40,0xc41))
        assert c.rw(c.ds,0x3792)==0
    return 4


def check_native_status_queue():
    for enabled,message in [(1,b'FASTBUILD ON'),(0,b'FASTBUILD OFF')]:
        c=CheatCPU();c.b(c.cs,0xc41,enabled)
        for off in (0x3728,0x372a,0x372c):c.w(c.ds,off,0xffff)
        for off in (0x3638,0x3688,0x36d8):c.b(c.ds,off,0)
        c.w(c.ds,0x372e,0)
        before={n:c.get(n) for n in 'ax bx cx dx si di bp ds es ss'.split()}
        sp=c.frame();c.run(c.cs,CHEAT_ENTRIES['ShowFastStatus'],[(c.cs,0xf000)])
        queues=[bytes(c.u.mem_read(c.ds*16+off,80)).split(b'\0')[0] for off in (0x3638,0x3688,0x36d8)]
        assert message in queues,queues
        assert c.get('sp')==sp+2 and before=={n:c.get(n) for n in before}
        assert c.rw(c.ds,0x372a)==2 and c.rw(c.ds,0x372e)==1
    return 2


def check_startup_layout():
    for load in (0x75b,0x1000,0x1800):
        c=CheatCPU(load=load);c.set('bp',0x9000)
        c.w(c.ds,0x7b,load-0x10)
        requested=max(c.rw(c.ds,0x7af4),0x200)
        stack_paragraphs=(requested>>4)+1
        c.actions[c.cs*16+find_label('InitializeXms')]=lambda q:q.ret()
        resize=[]
        def dos(u,number,user):
            assert number==0x21 and c.get('ax')>>8==0x4a
            resize.append((c.get('es'),c.get('bx')))
            c.set('flags',c.get('flags')&~1)
        c.u.hook_add(UC_HOOK_INTR,dos)
        c.run(load,0x5d,[(load,0xa2)])
        ss=load+CHEAT_REPORT['layout']['new_stack']
        assert c.get('ss')==ss and c.get('sp')==stack_paragraphs*16
        assert ss*16==load*16+CHEAT_REPORT['new_mz_end']-0x4c00
        assert c.rw(c.ds,0x89)==ss+stack_paragraphs
        assert resize==[(load-0x10,ss+stack_paragraphs-(load-0x10))]
        assert c.get('bp')==0x9000-(CHEAT_REPORT['layout']['new_stack']-0x3cfa)
    return 3


def find_label(name):
    if name in CHEAT_ENTRIES:
        return CHEAT_ENTRIES[name]
    code = CHEAT_EXE[HEADER+CHEAT_SEGMENT*16:CHEAT_REPORT['new_mz_end']]
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    if name == 'InitializeXms':
        return next(int(i.op_str, 0) for i in md.disasm(code[:0x40], 0) if i.mnemonic == 'call')
    start = CHEAT_ENTRIES['ExtraGameInputBegin']
    calls = []
    for i in md.disasm(code[start:], start):
        if i.mnemonic == 'call': calls.append(int(i.op_str, 0))
        if i.mnemonic == 'retf': break
    # The modal also retains a game-input poll call before pending commands.
    assert len(calls) == 5 and calls[-1] == CHEAT_ENTRIES['ApplyExtraPending']
    return dict(zip(('SavePanel', 'DrawPanel', 'RestorePanel'), calls[:3]))[name]


def check_cheats(folder):
    global CHEAT_EXE, CHEAT_ORIGINAL, CHEAT_REPORT, CHEAT_SEGMENT, CHEAT_ENTRIES
    info = build_report(folder)['extra_cheats']
    CHEAT_EXE = (folder/GAME/'DUNE2.EXE').read_bytes()
    CHEAT_ORIGINAL = original_file('DUNE2.EXE')
    CHEAT_SEGMENT = int(info['cheat_segment'], 16)
    CHEAT_ENTRIES = {name: int(value, 16) for name, value in info['entries'].items()}
    CHEAT_REPORT = dict(info, layout=dict(cheat_segment=CHEAT_SEGMENT,
                       new_stack=int(info['new_stack_segment'],16), entries=CHEAT_ENTRIES))
    return dict(production_cases=check_production(), command_cases=check_commands(),
                map_wrapper_cases=check_map_wrapper(), modal_and_reset_cases=check_modal_and_reset(),
                startup_stack_and_heap_cases=check_startup_layout(),
                native_status_message_cases=check_native_status_queue(),
                speed_multiplier=5, credits_increase=10000,
                bounded_x86_execution=True, native_fixed_point_math_executed=True,
                map_engine_calls='stubbed; native wrapper iteration/house arguments checked',
                background_io='stubbed; restore-before-command order checked')


@contextmanager
def isolated_editor():
    """Redirect both pure CSV data and editor state into scratch."""
    keys = ('ROOT', 'DRAFT', 'KEYS', 'UNIT_KEYS', 'HOUSES', 'REVIEW', 'REGISTRY', 'TRACKED')
    saved_data = {key: getattr(translation_data, key) for key in keys}
    saved_editor = {key: getattr(editor_model, key) for key in (*keys, 'SESSION')}
    originals = {path: digest(path) for path in [*translation_data.TRACKED, editor_model.SESSION] if path.is_file()}
    with scratch() as fixture:
        shutil.copytree(ROOT/'font', fixture/'font')
        for relative, _ in cd_source.EXPORTS.values():
            target = fixture/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/relative, target)
        for path in dict.fromkeys([*translation_data.TRACKED, editor_model.SESSION]):
            target = fixture/path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.is_file(): shutil.copyfile(path, target)
        for module, saved in ((translation_data, saved_data), (editor_model, saved_editor)):
            for key, value in saved.items():
                if key == 'TRACKED':
                    value = [fixture/path.relative_to(ROOT) for path in value]
                else:
                    value = fixture/value.relative_to(ROOT)
                setattr(module, key, value)
        try:
            yield fixture, originals
        finally:
            for key, value in saved_data.items(): setattr(translation_data, key, value)
            for key, value in saved_editor.items(): setattr(editor_model, key, value)
            assert all(digest(path) == before for path, before in originals.items()), 'Editor touched project inputs'


def check_component_boundaries():
    """Import each application in a fresh process and check the command handoff."""
    script = r"""
from pathlib import Path
import json, sys
root = Path(sys.argv[1])
component = sys.argv[2]
patch_modules = ('assembler', 'cheats', 'fonts', 'runtime_patches', 'scenes')
build_modules = ('build_game',)
forbidden_files = set()
forbidden_directory = None
if component == 'editor':
    sys.path[:0] = [str(root/'tools'), str(root/'editor')]
    import editor_model, desktop, build_runner
    data = editor_model.EditorModel(read_only=True, use_session=False)
    assert not any(hasattr(data, name) for name in ('build', 'rebuild_mentat', 'validate_build'))
    forbidden_files = {(root/'tools'/(name+'.py')).resolve()
                       for name in (*patch_modules, *build_modules)}
    assert not any(name in sys.modules for name in (*patch_modules, *build_modules))
    count = len(data.entries())
else:
    sys.path[:0] = [str(root/'tools')]
    from build_game import BuildInputs, editable
    data = BuildInputs()
    data.validate_build([row for row in data.rows if editable(row)])
    assert not any(hasattr(data, name) for name in ('catalog', 'session', 'editing_units', 'write_session', 'save'))
    forbidden_directory = (root/'editor').resolve()
    count = len(data.rows)
for name, module in sys.modules.items():
    source = getattr(module, '__file__', None)
    if source:
        source = Path(source).resolve()
        assert source not in forbidden_files, (component, name, str(source))
        assert forbidden_directory is None or not source.is_relative_to(forbidden_directory), (component, name)
print(json.dumps({'component': component, 'count': count, 'imports_separate': True}))
"""
    imports = []
    for component in ('editor', 'builder'):
        process = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(ROOT), component],
                                 cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        assert process.returncode == 0, process.stdout+process.stderr
        imports.append(json.loads(process.stdout))
    import build_runner
    actual_run = build_runner.subprocess.run
    calls = []
    expected = {'build': str(BUILD), 'published': True, 'changed': 925}
    def child(command, **kwargs):
        assert command[:2] == [sys.executable, str(ROOT/'tools/build_game.py')], command
        assert command[2] == '--result-json' and kwargs['cwd'] == ROOT
        Path(command[3]).write_text(json.dumps(expected), encoding='utf-8')
        calls.append(command[:3])
        return subprocess.CompletedProcess(command, 0, '', '')
    try:
        build_runner.subprocess.run = child
        assert build_runner.run() == expected
    finally:
        build_runner.subprocess.run = actual_run
    assert len(calls) == 1
    return dict(imports=imports, editor_invokes_independent_build_command=True,
                builder_result_json_returned=True, game_build_for_handoff_check='stubbed')


def check_editor(folder):
    boundaries = check_component_boundaries()
    with isolated_editor() as (fixture, originals):
        m = editor_model.EditorModel()
        entries = {entry['id']: entry for entry in m.entries()}
        ident = 'TEXTA.ENG|compressed_mission_text|4|text'
        other = 'TEXTA.ENG|compressed_mission_text|8|text'
        entry = entries[ident]
        units = UnitEdits()
        initial = units.open(ident, entry['text'], lambda text: m.editing_units(entry, text))
        values = [value for value, separator in initial]
        values[1] = '다시 만나 반갑습니다. 임무를 시작합니다.'
        edited = units.replace_fields(ident, values)
        legacy = m.editing_units(entry, edited)
        # Same operations as the editor: retain draft text, open another item,
        # then open the edited item using that draft.
        for _ in range(10):
            units.open(other, entries[other]['text'], lambda text: m.editing_units(entries[other], text))
            returned = units.open(ident, edited, lambda text: m.editing_units(entry, text))
            assert [value for value, separator in returned] == values
            assert units.text(ident) == edited
        repeated = '반갑습니다.'
        for _ in range(10):
            values[1] = repeated
            edited = units.replace_fields(ident, values)
            returned = units.open(ident, edited, lambda text: m.editing_units(entry, text))
            assert [value for value, separator in returned] == values
            assert edited.count(repeated) == 1
        saved = m.save({ident: edited}, m.revision, {ident: entry['text']})
        saved_entry = next(item for item in saved['catalog']['entries'] if item['id'] == ident)
        assert saved_entry['text'] == edited
        current = m.read_current_catalog()
        current_entry = next(item for item in current['entries'] if item['id'] == ident)
        after_save = units.open(ident, current_entry['text'], lambda text: m.editing_units(current_entry, text))
        assert [value for value, separator in after_save] == values
        assert units.text(ident).count(repeated) == 1
        # Register one truly new syllable through the real CSV save path.
        # The second editor and builder input must read it as registered.
        before_registry = set(m.registered_syllables)
        new_char = next(ch for ch in sorted(m.glyph_source) if ch not in before_registry)
        new_entry = next(item for item in m.entries() if item['id'] == other)
        new_text = new_entry['text']+' '+new_char
        assert any(new_char in warning for warning in m.warnings(new_entry, new_text))
        registered_save = m.save({other: new_text}, m.revision, {other: new_entry['text']})
        stored_registry = json.loads(translation_data.REGISTRY.read_text(encoding='utf-8'))
        assert stored_registry == {'version': 2, 'syllables': sorted(before_registry | {new_char})}
        assert registered_save['added_syllables'] == new_char
        assert new_char in m.registered_syllables and m.new_syllables == []
        saved_new_entry = next(item for item in m.entries() if item['id'] == other)
        assert saved_new_entry['text'] == new_text
        assert not any(new_char in warning for warning in m.warnings(saved_new_entry, new_text))
        reopened = editor_model.EditorModel(read_only=True, use_session=False)
        second_build_inputs = model.BuildInputs()
        assert reopened.registered_syllables == second_build_inputs.registered_syllables == m.registered_syllables
        assert reopened.new_syllables == second_build_inputs.new_syllables == []
        assert reopened.codes == second_build_inputs.codes == m.codes
        second_build_inputs.prepare_syllables()
        assert second_build_inputs.new_syllables == []
        assert not (fixture/'tools/assets').exists()
        registry_checks = dict(new_character=new_char, registered_on_csv_save=True,
                               complete_table_sorted=True, reopened_editor_new_count=0,
                               second_build_input_new_count=0, editor_and_builder_tokens_match=True,
                               no_initial_character_table=True)
        unchanged = all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in originals.items())
        assert unchanged
        report = dict(
            scope='Real UnitEdits and Model CSV save/reload in an isolated file copy. Native Tk callbacks not exercised.',
            legacy_reproduced=dict(initial_count=len(initial), edited_field_count=len(initial),
                                   returned_count=len(legacy), returned_values=[value for value, separator in legacy]),
            checks=dict(unsaved_navigation_10_cycles=True, repeated_field_replacement_no_append=True,
                        saved_csv_equals_edited_text=True, saved_reload_keeps_same_field_values=True,
                        original_csvs_unchanged=unchanged),
            component_boundaries=boundaries,
            persistent_registry=registry_checks,
            final_fields=[value for value, separator in after_save])
        return report


def check_editor_gui(folder):
    import tkinter as tk
    from tkinter import messagebox
    from desktop import Editor
    with isolated_editor() as (fixture, originals):
        original_error = messagebox.showerror
        try:
            report = {'scope': 'Real Tk widgets, real Treeview selection events and <<Modified>> events, actual Editor and Model code; all CSV writes redirected to a file copy.',
                      'python': sys.executable, 'checks': [], 'errors': []}
            errors = report['errors']
            messagebox.showerror = lambda *args, **kwargs: errors.append(str(args))
            root = tk.Tk()
            root.withdraw()
            root.report_callback_exception = lambda *args: errors.append(''.join(traceback.format_exception(*args)))
            try:
                editor = Editor(root, editor_model.EditorModel())
                root.update()
                load_button = editor.entries['DUNE.ENG|uncompressed_table|32|text']
                shared_load = editor.entries['DUNE.ENG|uncompressed_table|92|text']
                assert load_button['group'] == '저장·불러오기', load_button
                assert shared_load['group'] == '타이틀 메뉴', shared_load
                assert '게임 중 메뉴에서도 공유' in shared_load['detail'], shared_load
                report['shared_title_and_in_game_load_classifications'] = True
                first = 'TEXTA.ENG|compressed_mission_text|4|text'
                other = 'TEXTA.ENG|compressed_mission_text|8|text'

                def choose(ident):
                    editor.table.selection_set(ident)
                    root.update()
                    assert editor.selected == ident, (ident, editor.selected, errors)

                def fields():
                    return [field.get('1.0', 'end-1c') for field in editor.target_fields]

                choose(first)
                report['original_fields'] = fields()
                for replacement in ('수정한 문장입니다.', '다시 만나 반갑습니다. 임무를 시작합니다.'):
                    target = editor.target_fields[1]
                    target.delete('1.0', 'end')
                    target.insert('1.0', replacement)
                    root.update()
                    expected = fields()
                    expected_text = editor.target_text()
                    assert editor.drafts[first] == expected_text, errors
                    assert 'changed' in editor.table.item(first, 'tags')
                    assert editor.table.item(first, 'values')[1].startswith('● ')
                    for cycle in range(10):
                        choose(other)
                        choose(first)
                        actual = fields()
                        assert actual == expected, {'cycle': cycle, 'expected': expected, 'actual': actual, 'errors': errors}
                        assert editor.drafts[first] == expected_text
                        assert 'changed' in editor.table.item(first, 'tags')
                    report['checks'].append({'replacement': replacement, 'unsaved_round_trips': 10,
                                             'draft_equals_edited_text': True, 'displayed_fields': fields(),
                                             'unsaved_marker_and_color_retained': True})
                editor.undo_button.invoke()
                root.update()
                assert fields()[1] == '수정한 문장입니다.'
                assert editor.drafts[first] == editor.target_text()
                undo_expected = fields()
                choose(other)
                choose(first)
                assert fields() == undo_expected
                editor.redo_button.invoke()
                root.update()
                assert fields() == expected
                assert editor.target_fields[1].bind('<Control-z>')
                assert editor.target_fields[1].bind('<Control-y>')
                report['undo_redo_buttons_and_history_across_navigation'] = True
                report['ctrl_z_and_ctrl_y_bindings_installed'] = True
                def group(label):
                    labels = list(editor.groups.get(0, 'end'))
                    index = labels.index(label)
                    editor.groups.selection_clear(0, 'end')
                    editor.groups.selection_set(index)
                    editor.groups.event_generate('<<ListboxSelect>>')
                    root.update()
                for _ in range(10):
                    group('게임 메뉴')
                    choose(editor.table.get_children()[0])
                    group('임무 설명')
                    choose(first)
                    assert fields() == expected
                    assert editor.drafts[first] == expected_text
                    assert 'changed' in editor.table.item(first, 'tags')
                report['category_and_item_round_trips_10_cycles'] = True
                choose(other)
                second_field = editor.target_fields[0]
                second_field.delete('1.0', 'end')
                second_field.insert('1.0', '두 번째 항목의 수정입니다.')
                root.update()
                other_expected = fields()
                other_text = editor.target_text()
                choose(first)
                assert fields() == expected
                choose(other)
                assert fields() == other_expected
                assert editor.drafts[first] == expected_text
                assert editor.drafts[other] == other_text
                choose(first)
                report['two_independent_items_keep_unsaved_fields'] = True
                editor.reload()
                root.update()
                assert fields() == expected
                choose(other)
                assert fields() == other_expected
                assert editor.drafts[other] == other_text
                choose(first)
                assert editor.drafts[first] == expected_text
                report['reload_keeps_unsaved_fields'] = True
                editor.save()
                root.update()
                assert not errors, errors
                assert first not in editor.drafts
                assert 'changed' not in editor.table.item(first, 'tags')
                assert fields() == expected
                choose(other)
                assert fields() == other_expected
                assert other not in editor.drafts
                choose(first)
                assert fields() == expected
                report['save_then_navigation_keeps_fields'] = True
                report['marker_removed_after_successful_save'] = True
                saved_csv_hash = hashlib.sha256(editor_model.DRAFT.read_bytes()).hexdigest()
                editor.undo_button.invoke()
                root.update()
                assert fields() == undo_expected
                assert first in editor.drafts
                assert 'changed' in editor.table.item(first, 'tags')
                assert hashlib.sha256(editor_model.DRAFT.read_bytes()).hexdigest() == saved_csv_hash
                editor.redo_button.invoke()
                root.update()
                assert fields() == expected
                assert first not in editor.drafts
                assert hashlib.sha256(editor_model.DRAFT.read_bytes()).hexdigest() == saved_csv_hash
                report['undo_after_save_changes_only_edit_fields_not_csv'] = True
                report['final_fields'] = fields()
                choose(other)
                greeting = '어서 오십시오. 이렇게 다시 뵙게 되어 영광입니다. 입니다'
                target = editor.target_fields[0]
                target.delete('1.0', 'end')
                target.insert('1.0', greeting)
                root.update()
                greeting_fields = fields()
                editor.save()
                root.update()
                report['greeting_after_save_in_same_editor'] = fields()[0]
                reopened_window = tk.Toplevel(root)
                reopened_window.withdraw()
                reopened = Editor(reopened_window, editor_model.EditorModel())
                reopened.table.selection_set(other)
                root.update()
                reopened_fields = [field.get('1.0', 'end-1c') for field in reopened.target_fields]
                report['greeting_after_opening_new_editor'] = reopened_fields[0]
                report['greeting_fields_preserved_after_new_editor'] = reopened_fields == greeting_fields
                reopened_window.destroy()
                assert reopened_fields == greeting_fields
                report['result'] = 'passed'
            except Exception:
                report['result'] = 'failed'
                report['traceback'] = traceback.format_exc()
            finally:
                root.destroy()
                report['original_csvs_unchanged'] = all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in originals.items())
            if report['result'] != 'passed' or not report['original_csvs_unchanged']:
                raise AssertionError(report)
            return report
        finally:
            messagebox.showerror = original_error


SECTIONS = {
    'package': ('BIN files, sector EDC/ECC, CUE and actual Xdelta decoding', check_package),
    'structure': ('MZ/relocations, memory boundaries, runtime patches and HitSquad', check_structure),
    'hangul': ('Two-byte Hangul tokens, glyph pixels, widths, resources and shortcuts', check_hangul),
    'latin': ('Scoped Dalmoori alphabet/digits/symbols and original printf', check_latin),
    'unifont': ('Opening/ending font pixels and simulated XMS lifecycle', check_unifont),
    'subtitles': ('Subtitle token preservation in same/separate buffers', check_subtitles),
    'region': ('Mission-map INI text and high-bit whitespace regression', check_region),
    'houses': ('Hall row house/rank text and original string builder', check_houses),
    'question': ('English house-question rows; original French/German behavior', check_question_rows),
    'styles': ('Original font edges, Dalmoori edges and production percentages', check_styles),
    'spacing': ('Unit/building panel line spacing and state restoration', check_spacing),
    'cheats': ('All five commands, human-only 5x production, map and stack', check_cheats),
    'scenes': ('Harkonnen #320/Ordos #308 branches, native looping and stack', check_scenes),
    'editor': ('Editor navigation, saved CSV and editing field retention on copies', check_editor),
    'editor-gui': ('Actual hidden Tk widgets, undo/redo, save/reopen on copies', check_editor_gui),
}


def main():
    if not __debug__:
        raise SystemExit('Run without -O: assertions are required by these checks.')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', nargs='+', choices=SECTIONS, help='Run selected sections')
    parser.add_argument('--editor-gui', action='store_true', help='Also run actual Tk widget checks')
    parser.add_argument('--list', action='store_true', help='List check sections')
    args = parser.parse_args()
    if args.list:
        for name, (description, _) in SECTIONS.items(): print(f'{name}: {description}')
        return 0
    names = args.only or [name for name in SECTIONS if name != 'editor-gui']
    if args.editor_gui and 'editor-gui' not in names: names.append('editor-gui')
    protected = [*translation_data.TRACKED, editor_model.SESSION]
    protected += [path for path in (BUILD/GAME).rglob('*') if path.is_file()]
    protected += [clonecd_xdelta.BIN, clonecd_xdelta.CUE, clonecd_xdelta.PATCH, clonecd_xdelta.MANIFEST]
    before = {path: digest(path) for path in protected if path.is_file()}
    report = dict(build=str(BUILD), created_utc=datetime.now(timezone.utc).isoformat(),
                  whole_game_launched=False, scope='final build/package + bounded x86 + isolated editor',
                  selected_sections=names, sections={})
    for name in names:
        print(f'[{name}] checking...', flush=True)
        started = time.monotonic()
        try:
            result = SECTIONS[name][1](BUILD)
            report['sections'][name] = dict(status='passed', result=result)
            print(f'[{name}] PASS ({time.monotonic()-started:.1f}s)', flush=True)
        except Exception as error:
            report['sections'][name] = dict(status='failed', error=str(error), traceback=traceback.format_exc())
            print(f'[{name}] FAIL: {error}', flush=True)
        report['sections'][name]['seconds'] = round(time.monotonic()-started, 3)
    changed = [str(path.relative_to(ROOT)) for path, value in before.items()
               if not path.is_file() or digest(path) != value]
    report['protected_inputs_and_products_unchanged'] = not changed
    report['changed_files'] = changed
    report['passed'] = not changed and all(item['status'] == 'passed' for item in report['sections'].values())
    report['full_default_suite'] = set(SECTIONS)-{'editor-gui'} <= set(names)
    target = ROOT/'build/checks/final-build-check.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+chr(10), encoding='utf-8')
    print(f'{"PASS" if report["passed"] else "FAIL"}: {target}', flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
