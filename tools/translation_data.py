"""Saved translation inputs and text validation shared by CLI and editing tools.

This module handles CSVs and character metadata only. It never assembles or
patches an executable, generates a font, or imports an editor or game patch.
"""
from __future__ import annotations
import csv
import hashlib
import json
import os
import re
import tempfile
import struct
from datetime import datetime
from contextlib import contextmanager
from collections import Counter
from pathlib import Path


LEADS = tuple(value for value in range(0xE2, 0xFF) if value != 0xFA)

TRAIL_COUNT = 127

LEGACY_GLYPH_SLOTS = {
    33:639, 34:640, 35:641, 36:642, 37:643, 38:644, 39:645,
    40:646, 41:647, 42:648, 43:649, 44:650, 45:651, 46:652,
    47:653, 58:654, 59:655, 60:656, 61:657, 62:658, 63:659,
    64:660, 91:661, 92:662, 93:663, 94:664, 95:665, 96:666,
    123:667, 124:668, 125:669, 126:670, 183:671,
}

def token(index):
    if not 0 <= index < len(LEADS) * TRAIL_COUNT:
        raise ValueError(f'2바이트 문자 토큰 공간({len(LEADS) * TRAIL_COUNT}개)을 초과했습니다.')
    page, trail = divmod(index, TRAIL_COUNT)
    return bytes((LEADS[page], 0x80 + trail))

def load_glyphs(root):
    """Read every 8x8 Dalmoori record from the shared HEX source."""
    result = {}
    for line in (root / 'font/composed-hangul.hex').read_text(encoding='ascii').splitlines():
        if not line.strip():
            continue
        code, value = line.split(':', 1)
        raw = bytes.fromhex(value)
        if len(raw) != 18 or raw[:2] != b'\0\0' or any(raw[3::2]):
            raise ValueError('달무리 글리프 HEX 형식이 다릅니다: '+code)
        character = chr(int(code, 16))
        if character in result:
            raise ValueError('달무리 HEX에 중복 코드포인트가 있습니다: '+code)
        result[character] = raw[2::2]
    return result

def load_syllables(root):
    """Return only Hangul syllables; ASCII and symbols share the same HEX."""
    return {character: rows for character, rows in load_glyphs(root).items()
            if 0xAC00 <= ord(character) <= 0xD7A3}

def load_latin_records(root):
    glyphs = load_glyphs(root)
    codepoints = {ord(ch) for ch in glyphs}
    ascii_glyphs = set(range(32, 127))
    symbols = {cp for cp in codepoints
               if cp > 127 and not 0xAC00 <= cp <= 0xD7A3}
    missing_ascii = ascii_glyphs-codepoints
    if missing_ascii:
        raise ValueError('composed-hangul.hex에 달무리 ASCII 글리프가 없습니다.')
    missing_legacy = set(LEGACY_GLYPH_SLOTS)-codepoints
    if missing_legacy:
        raise ValueError('composed-hangul.hex에 원본 고정 부호 글리프가 없습니다.')
    selected = ascii_glyphs | symbols
    records = {}
    for cp in sorted(selected):
        records[cp] = dict(codepoint=cp, character=chr(cp),
                           glyph_index=LEGACY_GLYPH_SLOTS.get(cp, 0),
                           native_advance=4, cell_width=6,
                           rows=glyphs[chr(cp)].hex().upper(),
                           added=cp not in LEGACY_GLYPH_SLOTS)
    return records

FACTIONS = {'A': '아트레이데스', 'H': '하코넨', 'O': '오르도스'}

EXCLUDED_FILES = frozenset({'PROTECT.ENG'})

EXCLUDED_ROWS = frozenset({
    ('DUNE.ENG', '15'), ('DUNE.ENG', '17'), ('DUNE.ENG', '18'),
    ('DUNE.ENG', '321'),
})

EXCLUDED_OUTPUT_GROUP = 'DOS 창 메시지 (편집 제외)'

GROUPS = [
    '가문 소개', '임무 설명', '임무 승리·패배', '임무 조언',
    '멘타트 화면·버튼', '멘타트 목록 이름', '멘타트 그림 설명', '멘타트 본문',
    '임무 선택 지도', '황제 중간 영상', '타이틀 메뉴', '게임 메뉴',
    '저장·불러오기', '공통 버튼·확인창', '게임 설정', '유닛 명령',
    '생산·건설 선택', '유닛·건물 정보', '게임 상단 메시지', '게임 도움말',
    '지형 이름', '유닛 이름', '건물 이름', '전투 결과·계급', '명예의 전당',
    '오프닝 대사', '엔딩 대사', '크레딧',
    'EXE 가문 이름', '내부·예약 데이터',
]

def editable(row):
    return (row['file'] not in EXCLUDED_FILES and
            (row['file'], str(row['index'])) not in EXCLUDED_ROWS)

def _dune_groups():
    groups = {}

    def assign(group, *parts):
        for part in parts:
            for index in (part if isinstance(part, range) else (part,)):
                if index in groups:
                    raise ValueError(f'DUNE.ENG #{index}: 중복 분류')
                groups[index] = group

    assign('내부·예약 데이터', 0, 339)
    assign('유닛 명령', range(1, 13))
    assign('유닛·건물 정보', 13, 14, 45, 46, 49, range(84, 90),
           range(121, 129), 144, 146, 160, 161, 335)
    assign(EXCLUDED_OUTPUT_GROUP, 15, 17, 18, 321)
    assign('저장·불러오기', 16, 32, 36, range(97, 101), 337, 338)  # #32 Load dialog button
    assign('게임 상단 메시지', 19, 20, range(50, 82), 90,
           range(129, 142), 145, range(147, 153), range(154, 160),
           range(162, 168), 270, 322, range(331, 334))
    assign('전투 결과·계급', range(21, 27), range(271, 283), 329, 330)
    assign('타이틀 메뉴', 27, 28, 29, 92, 334)  # #92 Load a game is shared with the game menu
    assign('공통 버튼·확인창', 30, 33, 102, 107, 108)
    assign('생산·건설 선택', 31, 34, 35, range(37, 45), 142, 143, 153,
           range(177, 194))
    assign('멘타트 화면·버튼', 47, 48, 175, 176)
    assign('임무 승리·패배', 82, 83)
    assign('게임 메뉴', 91, range(93, 97), 101, 103, 104, 118, 119)
    assign('게임 설정', 105, 106, range(109, 118), 120)
    assign('지형 이름', range(168, 175))
    assign('유닛 이름', range(194, 232))
    assign('건물 이름', range(232, 270))
    assign('임무 선택 지도', range(283, 287))
    assign('황제 중간 영상', range(287, 321))
    assign('명예의 전당', range(323, 329), 336)
    if set(groups) != set(range(340)):
        raise ValueError('DUNE.ENG 분류 범위가 전체 340행과 다릅니다.')
    return groups

DUNE_GROUPS = _dune_groups()

def classify(row):
    name, typ, index = row['file'], row['type'], row['index']
    faction = '공통'
    if name in EXCLUDED_FILES:
        return '보안 질문 (편집 제외)', faction, '원문 유지'
    if name in ('TEXTA.ENG', 'TEXTH.ENG', 'TEXTO.ENG'):
        faction = FACTIONS[name[4]]
        i = int(index)
        if not 0 <= i < 40:
            raise ValueError(f'{name} #{index}: 임무 문자열 범위 밖')
        if i == 0:
            return '가문 소개', faction, '가문 선택 · 행성·가문 설명'
        role = ('임무 설명', '임무 승리·패배', '임무 승리·패배', '임무 조언')[i % 4]
        detail = ('설명', '승리', '패배', '조언')[i % 4]
        if i < 4:
            return '내부·예약 데이터', faction, '시험 시나리오 · ' + detail
        return role, faction, f'임무 {i // 4} · {detail}'
    if name in ('MENTATA.ENG', 'MENTATH.ENG', 'MENTATO.ENG'):
        faction = FACTIONS[name[6]]
        code = row['code']
        topic = {'0': '브리핑', '1': '가문', '2': '건물', '3': '유닛', '4': '특수 병기·유닛'}.get(code[:1])
        if topic is None:
            raise ValueError(f'{name} #{index}: 알 수 없는 멘타트 주제 코드 {code}')
        if typ == 'mentat_label':
            detail = topic + (' · 대주제' if code.endswith('0') else ' · 항목')
            return '멘타트 목록 이름', faction, detail
        if typ == 'mentat_description':
            if row['source_en'].lower().rstrip().endswith('no desc'):
                return '내부·예약 데이터', faction, f'멘타트 {topic} · 목록용 연결·빈 설명'
            return '멘타트 본문', faction, topic
    if name in ('REGIONA.INI', 'REGIONH.INI', 'REGIONO.INI'):
        faction = FACTIONS[name[6]]
        match = re.fullmatch(r'group(\d+):line(\d+)', index)
        if not match:
            raise ValueError(f'{name} #{index}: 지도 문구 위치 형식이 다릅니다.')
        return '임무 선택 지도', faction, f'지도 단계 {match[1]} · {row["code"]}'
    if name == 'INTRO.ENG':
        i = int(index)
        if i in (0, 38):
            return '내부·예약 데이터', faction, '오프닝·엔딩 빈 슬롯'
        for start, end, house in ((20, 24, 'A'), (25, 31, 'H'), (32, 37, 'O')):
            if start <= i <= end:
                return '엔딩 대사', FACTIONS[house], f'엔딩 대사 {i - start + 1}'
        if 1 <= i <= 19:
            return '오프닝 대사', faction, f'오프닝 자막 {i}'
    if name == 'MESSAGE.ENG':
        i = int(index)
        if i in (0, 29):
            return '내부·예약 데이터', faction, '도움말 빈 슬롯'
        if 1 <= i <= 28:
            detail = ('건물 설명' if 2 <= i <= 19 else
                      '지형 설명' if 21 <= i <= 25 else '건설·채취 안내')
            return '게임 도움말', faction, detail
    if name == 'CREDITS.ENG':
        visible = row['source_en'].translate({i: None for i in range(32)}).strip()
        if not visible:
            if row['source_en'] == '\0':
                return '내부·예약 데이터', faction, '크레딧 종료 바이트'
            return '크레딧', faction, '빈 행'
        first = row['source_en'][:1]
        detail = {'\x01': '저작권·상표', '\x02': '제목·종료 인사',
                  '\x03': '제작 역할·이름', '\x04': '제작진 이름'}.get(first, '제작진')
        return '크레딧', faction, detail
    if name == 'DUNE.ENG' and typ == 'uncompressed_table':
        i = int(index)
        group = DUNE_GROUPS.get(i)
        if group is None:
            raise ValueError(f'{name} #{index}: 분류가 등록되지 않았습니다.')
        if 287 <= i <= 320:
            for start, end, house, scene in ((287, 292, 'A', 1), (293, 297, 'A', 2),
                                          (298, 303, 'O', 1), (304, 308, 'O', 2),
                                          (309, 314, 'H', 1), (315, 320, 'H', 2)):
                if start <= i <= end:
                    return group, FACTIONS[house], f'황제 장면 {scene} · 대사 {i - start + 1}'
        if group in ('유닛 이름', '건물 이름'):
            detail = '짧은 이름' if i % 2 == 0 else '긴 이름'
        elif 271 <= i <= 282:
            detail = f'전투 평가 계급 {i - 270}'
        elif 21 <= i <= 26 or i in (329, 330):
            detail = '전투 결과 · 점수·통계'
        elif 283 <= i <= 285:
            detail = f'지도 도입 문구 {i - 282}'
        elif i == 286:
            detail = '다음 점령지 선택 안내'
        elif i == 32:
            detail = '불러오기 화면 버튼'
        elif i == 92:
            detail = '타이틀 메뉴 · 게임 중 메뉴에서도 공유'
        elif i in (82, 83):
            detail = '공통 임무 완료 안내' if i == 82 else '공통 임무 실패 안내'
        elif group == '내부·예약 데이터':
            detail = '빈 슬롯'
        else:
            detail = ''
        return group, faction, detail
    raise ValueError(f'{name} ({typ}) #{index}: 분류가 등록되지 않았습니다.')

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT/'import/strings/source_strings_complete_ko_draft.csv'
HOUSES = ROOT/'import/strings/executable_house_names.csv'
REVIEW = ROOT/'export/strings/executable_strings_review.csv'
REGISTRY = ROOT/'import/fnt/glyph_registry.json'
TRACKED = [DRAFT, HOUSES, REVIEW, REGISTRY]

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def csv_bytes(rows):
    import io
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=list(dict.fromkeys(key for row in rows for key in row)))
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode('utf-8-sig')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def registry_bytes(syllables):
    """Serialize the complete persistent Hangul table in token order."""
    values = sorted(set(syllables))
    return (json.dumps(dict(version=2, syllables=values), ensure_ascii=False,
                       indent=2)+'\n').encode('utf-8')

def row_key(row):
    return '|'.join((row['file'], row['type'], row['index']))

def shortcut_key(text):
    match = re.search(r'\(([A-Z])\)$', text)
    return match[1] if match else ''


def shortcut_rows(rows):
    """Read literal hotkey suffixes from the saved translation rows."""
    result = {}
    for row in rows:
        if row['file'] != 'DUNE.ENG' or row['type'] != 'uncompressed_table':
            continue
        key = shortcut_key(row['translation_ko'])
        if key:
            result[row['index']] = dict(row, shortcut=key)
    return result

def split_mentat(text):
    # Only the ASCII resource prefix before the first * / ? is immutable.
    match = re.match(r'^([\x20-\x7e]*?[*?])', text)
    prefix = match[0] if match else ''
    rest = text[len(prefix):]
    marker = re.search(r'\\x0[cC]|\x0c', rest)
    if marker:
        return prefix, rest[:marker.start()], marker[0], rest[marker.end():]
    return prefix, '', '', rest

def display_lines(text):
    return text.replace('\\r\\n', '\n').replace('\\r', '\n').replace('\\n', '\n')

def storage_lines(text):
    return text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\r')

def formats(text):
    return Counter(re.findall(r'%(?!%)[-+ #0]*\d*(?:\.\d+)?[hlL]?[diuoxXfFeEgGcs]',
                              text.replace('%%', '')))

class TranslationData:
    def __init__(self):
        self.game_files = ROOT/'export'
        self.game = self.game_files/'PAK'
        self.glyph_source = load_syllables(ROOT)
        self.latin_records = load_latin_records(ROOT)
        self.latin_symbols = sorted(cp for cp in self.latin_records if cp > 127)
        self.reload()

    def reload(self):
        self.rows = read_csv(DRAFT)
        self.houses = read_csv(HOUSES)
        self.prepare_syllables()
        self.keys = shortcut_rows(self.rows)
        self.hashes = {str(p): digest(p) for p in TRACKED}
        self.revision = hashlib.sha256(json.dumps(self.hashes, sort_keys=True).encode()).hexdigest()

    def prepare_syllables(self):
        registered = self.read_registered_syllables()
        self.registered_syllables = frozenset(registered)
        self.syllables = self._plan_syllables(self.rows, self.houses, registered)
        self.new_syllables = sorted(set(self.syllables)-self.registered_syllables)
        self.codes = {ch: token(i) for i, ch in enumerate(self.syllables)}

    def read_registered_syllables(self):
        data = json.loads(REGISTRY.read_text(encoding='utf-8'))
        values = data.get('syllables')
        if (data.get('version') != 2 or not isinstance(values, list) or
                any(not isinstance(ch, str) or len(ch) != 1 or
                    not 0xAC00 <= ord(ch) <= 0xD7A3 for ch in values) or
                values != sorted(set(values))):
            raise ValueError('저장된 한글 문자표의 형식·정렬이 올바르지 않습니다.')
        missing = set(values)-self.glyph_source.keys()
        if missing:
            raise ValueError('등록된 한글이 달무리 완성 음절 소스에 없습니다: '+''.join(sorted(missing)))
        return values

    def _plan_syllables(self, rows, houses, registered):
        needed = {ch for row in [*(r for r in rows if editable(r)), *houses] for ch in row['translation_ko']
                  if 0xAC00 <= ord(ch) <= 0xD7A3}
        missing = needed-self.glyph_source.keys()
        if missing:
            raise ValueError('달무리 완성 음절 소스에 없는 글자: '+''.join(sorted(missing)))
        syllables = sorted(set(registered) | needed)
        token(len(syllables)+len(self.latin_symbols)-1)
        return syllables

    def plan_syllables(self, rows, houses):
        return self._plan_syllables(rows, houses, self.read_registered_syllables())

    @contextmanager
    def save_lock(self):
        # Coordinate writes to the shared translation inputs across processes.
        import msvcrt
        path = ROOT/'import/strings/.translation-inputs.lock'
        with path.open('a+b') as handle:
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b'\0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError('다른 프로세스가 번역 자료를 저장하거나 빌드 중입니다. 잠시 후 다시 시도하세요.') from None
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

    @staticmethod
    def temporary_csv(path, data):
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name+'.', suffix='.editor-tmp', delete=False) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            except Exception:
                handle.close()
                temporary.unlink(missing_ok=True)
                raise
        return temporary

    def unchanged_on_disk(self):
        if any(digest(Path(p)) != h for p, h in self.hashes.items()):
            raise ValueError('CSV가 다른 프로그램에서 변경되었습니다. 입력 내용을 복사한 뒤 에디터를 다시 열어 주세요.')

    def encode(self, text):
        # Match the proven resource builder's legacy-font substitutions.
        # Keep the CSV/editor text intact; normalize only the game byte stream.
        korean = any(0xAC00 <= ord(ch) <= 0xD7A3 for ch in text)
        if not korean:
            text = text.replace('©', '(C)').replace('×', 'x')
        result = bytearray()
        at = 0
        while at < len(text):
            if text[at] == '\\' and at + 1 < len(text):
                esc = text[at+1]
                if esc in 'rnt':
                    result.append({'r': 13, 'n': 10, 't': 9}[esc]); at += 2; continue
                if esc == 'x' and re.fullmatch('[0-9a-fA-F]{2}', text[at+2:at+4]):
                    value = int(text[at+2:at+4], 16)
                    if value == 0 or value in LEADS:
                        raise ValueError('문자열 안에 사용할 수 없는 제어 바이트입니다.')
                    result.append(value); at += 4; continue
            char = text[at]
            if char in self.codes:
                result.extend(self.codes[char])
            elif korean and ord(char) in self.latin_symbols:
                result.extend(token(len(self.syllables)+self.latin_symbols.index(ord(char))))
            else:
                try:
                    raw = char.encode('cp437')
                except UnicodeEncodeError:
                    raise ValueError('현재 게임 폰트에 없는 글자: ' + char) from None
                if raw[0] == 0 or raw[0] in LEADS:
                    raise ValueError('현재 게임 문자 코드와 충돌하는 글자: ' + char)
                result.extend(raw)
            at += 1
        return bytes(result)

    def classify(self, row):
        return classify(row)

    def classify_rows(self, rows):
        """Keep the CSV's readable classification aligned with the editor."""
        for row in rows:
            row['category'], row['faction'], row['detail'] = self.classify(row)


def restore_security(rows):
    import cd_source
    from resources import unpack_pak, expand_compressed, display
    raw = unpack_pak(cd_source.validate_exports()['ENGLISH.PAK'])[1]['PROTECT.ENG']
    count = struct.unpack_from('<H', raw)[0] // 2
    security = {int(row['index']): row for row in rows if row['file'] == 'PROTECT.ENG'}
    if set(security) != set(range(count)):
        raise ValueError('보안 질문 CSV와 원본 문자열표의 범위가 다릅니다.')
    changed = 0
    for index, row in security.items():
        position = struct.unpack_from('<H', raw, index * 2)[0]
        original = display(expand_compressed(raw[position:raw.index(0, position)]))
        if row['source_en'] != original:
            raise ValueError(f'PROTECT.ENG #{index}: CSV 원문과 원본 게임이 다릅니다.')
        changed += row['translation_ko'] != original
        row['translation_ko'] = original
        row['editor_layout'] = ''
    return changed

def restore_dos_output(rows):
    """Keep DOS-console output in English and discard obsolete editor layouts."""
    changed = 0
    for row in rows:
        if (row['file'], str(row['index'])) not in EXCLUDED_ROWS:
            continue
        changed += row['translation_ko'] != row['source_en'] or bool(row.get('editor_layout'))
        row['translation_ko'] = row['source_en']
        row['editor_layout'] = ''
    return changed

def classification_main():
    model = TranslationData.__new__(TranslationData)
    with model.save_lock():
        original = DRAFT.read_bytes()
        rows = read_csv(DRAFT)
        columns = list(rows[0])
        previous = [dict(row) for row in rows]
        restored = restore_security(rows) + restore_dos_output(rows)
        model.classify_rows(rows)
        for before, after in zip(previous, rows):
            allowed = {'category', 'faction', 'detail'}
            if (before['file'], str(before['index'])) in EXCLUDED_ROWS:
                allowed |= {'translation_ko', 'editor_layout'}
            if before['file'] == 'PROTECT.ENG':
                allowed |= {'translation_ko', 'editor_layout'}
            if any(after[key] != before[key] for key in columns if key not in allowed):
                raise ValueError('분류 외의 번역 데이터가 바뀌었습니다: '+str(before['index']))
        payload = csv_bytes(rows)
        if payload == original:
            print('Classification already current.')
            return
        backup = ROOT / 'editor/backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup.mkdir(parents=True)
        (backup / DRAFT.name).write_bytes(original)
        temporary = model.temporary_csv(DRAFT, payload)
        try:
            if DRAFT.read_bytes() != original:
                raise RuntimeError('CSV changed during classification; no replacement made.')
            os.replace(temporary, DRAFT)
        finally:
            temporary.unlink(missing_ok=True)
        saved = read_csv(DRAFT)
        assert len(saved) == len(previous)
        assert saved == rows
        print(f'Classified {len(saved)} rows; restored {restored} security translations.')
        for category, count in Counter(row['category'] for row in saved).items():
            print(category, count)
        print('Backup:', backup)

def main():
    import argparse
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Manage translation CSV metadata')
    parser.add_argument('command', choices=('classify',))
    parser.parse_args()
    classification_main()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
