"""Assemble the game's 16-bit x86 modules as OMF images.

All modules use the project's verified JWasm v2.20 executable.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import hashlib
import subprocess
import struct
from pathlib import Path

ASM: Path
ROOT = Path(__file__).resolve().parents[1]
JWASM = ROOT / 'import/asm/JWasm.exe'
JWASM_SHA256 = 'ce95d1a4e83b2cba74fadffdf1f009438e668a30f6314c93d7b044e55be7ecee'
_COMPILATIONS: list[dict] = []


@contextmanager
def build_context():
    """Collect JWasm provenance for one final game build."""
    global _COMPILATIONS
    previous_compilations = _COMPILATIONS
    _COMPILATIONS = []
    try:
        yield
    finally:
        _COMPILATIONS = previous_compilations


jwasm_editor_build = build_context  # Compatibility for archived verification tools.


def build_report() -> dict:
    """Return compiler provenance for the active build context."""
    return {
        'backend': 'JWasm v2.20',
        'jwasm_executable': str(JWASM),
        'jwasm_sha256': hashlib.sha256(JWASM.read_bytes()).hexdigest() if JWASM.is_file() else None,
        'reference_compiler_invocations': 0,
        'compilations': [dict(item) for item in _COMPILATIONS],
    }


def _image_from_omf(obj: bytes, name: str, minimum: int) -> tuple[bytes, dict]:
    chunks: list[tuple[int, bytes]] = []
    record_types: Counter[str] = Counter()
    at = 0
    while at < len(obj):
        if len(obj) - at < 3:
            raise ValueError(f'Truncated OMF record header in {name}.obj at {at:#x}.')
        kind = obj[at]
        length = struct.unpack_from('<H', obj, at + 1)[0]
        end = at + 3 + length
        if length < 1 or end > len(obj):
            raise ValueError(f'Invalid OMF record length in {name}.obj at {at:#x}.')
        record = obj[at + 3:end]
        record_types[f'{kind:02X}'] += 1
        if kind in (0x9C, 0x9D):
            raise ValueError(f'Unexpected OMF fixup record {kind:02X} in {name}.')
        if kind == 0xA0:
            if len(record) < 4 or record[0] != 1:
                raise ValueError(
                    f'Unexpected OMF LEDATA segment layout in {name}: {record[:4].hex()}'
                )
            offset = struct.unpack_from('<H', record, 1)[0]
            chunks.append((offset, record[3:-1]))
        at = end

    if at != len(obj) or not chunks:
        raise ValueError(f'No usable OMF LEDATA records were produced for {name}.')
    image_size = max([minimum] + [offset + len(data) for offset, data in chunks])
    if image_size > 0x10000:
        raise ValueError(f'OMF output for {name} exceeds one 16-bit segment.')
    image = bytearray(image_size)
    occupied = bytearray(image_size)
    for offset, data in chunks:
        end = offset + len(data)
        if end > image_size or any(occupied[offset:end]):
            raise ValueError(f'Overlapping or out-of-range OMF data in {name}.')
        image[offset:end] = data
        occupied[offset:end] = b'\1' * len(data)
    return bytes(image), {
        'omf_record_types': dict(sorted(record_types.items())),
        'ledata_records': len(chunks),
        'ledata_bytes': sum(len(data) for _, data in chunks),
        'module_image_bytes': image_size,
    }


def _compile(source: str, name: str, minimum: int) -> tuple[bytes, dict]:
    path = ASM / (name + '.asm')
    path.write_text(source, encoding='ascii')
    obj = ASM / (name + '.obj')
    listing = ASM / (name + '.lst')
    if not JWASM.is_file():
        raise FileNotFoundError(f'JWasm executable not found: {JWASM}')
    actual_hash = hashlib.sha256(JWASM.read_bytes()).hexdigest()
    if actual_hash != JWASM_SHA256:
        raise RuntimeError(f'JWasm SHA-256 mismatch: expected {JWASM_SHA256}, got {actual_hash}')
    command = [str(JWASM), '/nologo', '/c', '/omf', f'/Fo{obj}', f'/Fl{listing}', str(path)]
    result = subprocess.run(command, cwd=ASM, capture_output=True)
    stdout = result.stdout.decode('utf-8', 'replace')
    stderr = result.stderr.decode('utf-8', 'replace')
    if result.returncode:
        raise RuntimeError(f'JWasm failed for {name} (exit {result.returncode}):\n{stdout}{stderr}')
    if not obj.is_file() or not listing.is_file():
        raise RuntimeError(f'JWasm did not produce both OBJ and LST for {name}.')
    object_bytes = obj.read_bytes()
    image, details = _image_from_omf(object_bytes, name, minimum)
    record = {
        'name': name,
        'compiler': 'JWasm',
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'object_sha256': hashlib.sha256(object_bytes).hexdigest(),
        'listing_sha256': hashlib.sha256(listing.read_bytes()).hexdigest(),
        **details,
        'compiler_output': stdout.strip(),
    }
    return image, record


def assemble(source: str, name: str, minimum=0):
    jwasm_image, jwasm_record = _compile(source, name, minimum)
    _COMPILATIONS.append(jwasm_record)
    return jwasm_image
