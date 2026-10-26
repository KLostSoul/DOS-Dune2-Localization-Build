"""Export original-size CG frames and encode edits into new Dune II PAKs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from cg_codec import (decode, load_pixels, encode_cps, encode_shp, encode_wsa,
                      encode_fnt, encode_icn, u16, u32, apply_xor_delta, decode_lcw)
from resources import unpack_pak, pack_pak, pak_entries as archive_entries

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = (ROOT / 'import/GFX').resolve()
DEFAULT_GFX_BASELINE = (ROOT / 'export/GFX').resolve()
DEFAULT_ARCHIVE_SOURCE = (ROOT / 'export/PAK').resolve()
CHAINS = {'INTRO7B.WSA': 'INTRO7A.WSA', 'INTRO8B.WSA': 'INTRO8A.WSA',
          'INTRO8C.WSA': 'INTRO8B.WSA', 'HFINALC.WSA': 'HFINALB.WSA',
          'OFINALB.WSA': 'OFINALA.WSA', 'OFINALC.WSA': 'OFINALB.WSA'}
# Keep the current DUNE.PAK edit scope to the three requested CPS screens.
DUNE_EDITABLE_NAMES = {'CHOAM.CPS', 'MAPMACH.CPS', 'SCREEN.CPS'}
# These PAK groups are omitted from editable snapshots and encoded output.
EXCLUDED_EDITABLE_PAKS = {'FRENCH.PAK', 'GERMAN.PAK', 'FINALE.PAK',
                          'MENTAT.PAK', 'INTRO.PAK'}


def sha(data):
    return hashlib.sha256(data).hexdigest()




def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path outside project: {relative}')
    return path


def default_game():
    source = DEFAULT_ARCHIVE_SOURCE
    missing = [name for name in ('DUNE.PAK', 'ENGLISH.PAK')
               if not (source / name).is_file()]
    if missing:
        raise ValueError('Specify --game: original CG source PAKs are missing from '
                         f'{source}: {", ".join(missing)}')
    return source.resolve()


def baseline_for(project, baseline=None):
    project = project.resolve()
    if baseline is not None:
        return Path(baseline).resolve()
    return DEFAULT_GFX_BASELINE if project == DEFAULT_PROJECT else project


def kind_of(name, raw):
    suffix = Path(name).suffix.upper()
    if suffix == '.WSA': return 'wsa'
    if suffix == '.SHP': return 'shp'
    if suffix == '.CPS': return 'cps'
    if suffix == '.ICN': return 'icn'
    if suffix == '.FNT' and raw[2:4] == b'\0\x05': return 'fnt'
    if suffix in ('.ENG', '.FRE', '.GER'):
        if Path(name).stem.upper() in ('BTTN', 'CHOAM', 'MENTAT'):
            return 'embedded_shp'
        if len(raw) >= 10 and u16(raw, 2) in (0, 4) and u32(raw, 4) == 64000:
            return 'cps'
    return None


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def export_project(game, project, baseline=None):
    project = project.resolve()
    baseline = baseline_for(project, baseline)
    if project.exists() and any(project.iterdir()):
        raise ValueError(f'Export directory is not empty: {project}')
    if baseline != project and baseline.exists() and any(baseline.iterdir()):
        raise ValueError(f'GFX baseline directory is not empty: {baseline}')
    project.parent.mkdir(parents=True, exist_ok=True)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cg-export-', dir=ROOT) as temporary:
        stage_root = Path(temporary)
        stage_project = stage_root / 'project'
        stage_baseline = stage_project if baseline == project else stage_root / 'GFX'
        manifest = export_assets(game, stage_project, stage_baseline)
        if project.exists():
            project.rmdir()  # Only an empty directory may be replaced.
        if baseline != project and baseline.exists():
            baseline.rmdir()  # Only an empty directory may be replaced.
        os.rename(stage_project, project)
        if baseline != project:
            try:
                os.rename(stage_baseline, baseline)
            except Exception:
                os.rename(project, stage_project)
                raise
    print(f'Exported {len(manifest["resources"])} resources: {project}')
    return manifest


def export_assets(game, project, baseline=None):
    game, project = game.resolve(), project.resolve()
    baseline = baseline_for(project, baseline)
    if project.exists() and any(project.iterdir()):
        raise ValueError(f'Export directory is not empty: {project}')
    if baseline != project and baseline.exists() and any(baseline.iterdir()):
        raise ValueError(f'GFX baseline directory is not empty: {baseline}')
    project.mkdir(parents=True, exist_ok=True)
    baseline.mkdir(parents=True, exist_ok=True)
    archives, records, lookup, palettes = [], [], {}, {}
    for pak in sorted(game.glob('*.PAK')):
        raw = pak.read_bytes()
        members = archive_entries(raw)
        first_record = len(records)
        for name, value in members:
            if name.upper().endswith('.PAL'):
                palettes[(pak.name.upper(), name.upper())] = value
            kind = kind_of(name, value)
            if kind:
                if pak.name.upper() in EXCLUDED_EDITABLE_PAKS:
                    continue
                if (pak.name.upper() == 'DUNE.PAK' and
                        name.upper() not in DUNE_EDITABLE_NAMES):
                    continue
                record = dict(pak=pak.name, name=name, kind=kind,
                              resource=f'resources/{pak.stem}/{name}', frames=[])
                path = inside(baseline, record['resource'])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value)
                records.append(record)
                lookup[(pak.name.upper(), name.upper())] = record
        if len(records) != first_record:
            archives.append(dict(name=pak.name, sha256=sha(raw)))
    bene = palettes[('DUNE.PAK', 'BENE.PAL')]
    cache = {}

    def images_for(record):
        key = (record['pak'].upper(), record['name'].upper())
        if key in cache:
            return cache[key]
        palette = palettes.get(('INTRO.PAK', 'INTRO.PAL'), bene) if key[0] == 'INTRO.PAK' else bene
        if key[1] == 'WESTWOOD.WSA':
            palette = palettes[('INTRO.PAK', 'WESTWOOD.PAL')]
        record['palette'] = palette.hex()
        initial = None
        raw = inside(baseline, record['resource']).read_bytes()
        if record['kind'] == 'wsa' and u32(raw, 10) == 0:
            predecessor = CHAINS.get(key[1])
            if not predecessor or (key[0], predecessor) not in lookup:
                raise ValueError(f'Missing WSA predecessor: {key}')
            parent = lookup[(key[0], predecessor)]
            record['predecessor'] = parent['resource']
            initial = images_for(parent)[-1].tobytes()
        images = decode(inside(baseline, record['resource']), record['kind'], palette, initial)
        cache[key] = images
        return images

    for record in records:
        images = images_for(record)
        directory = project / 'images' / Path(record['pak']).stem / record['name']
        original_directory = baseline / 'images' / Path(record['pak']).stem / record['name']
        directory.mkdir(parents=True, exist_ok=True)
        original_directory.mkdir(parents=True, exist_ok=True)
        for i, image in enumerate(images):
            path = directory / f'frame_{i:03d}.png'
            original_path = original_directory / f'frame_{i:03d}.png'
            image.save(path)
            image.save(original_path)
            record['frames'].append(dict(path=path.relative_to(project).as_posix(),
                                         original_path=original_path.relative_to(baseline).as_posix(),
                                         size=list(image.size), pixels_sha256=sha(image.tobytes())))
        record['sha256'] = sha(inside(baseline, record['resource']).read_bytes())
    archive_source = game.relative_to(ROOT).as_posix() if game.is_relative_to(ROOT) else str(game)
    manifest = dict(version=1, source_game=archive_source, archive_source=archive_source,
                    archives=archives, resources=records)
    write_json(baseline / 'manifest.json', manifest)
    write_json(baseline / 'export-report.json', dict(resources=len(records),
               frames=sum(len(r['frames']) for r in records), kinds=dict(Counter(r['kind'] for r in records))))
    return manifest


def encode_project(project, output, *, baseline=None, force_all=False, allow_buffer_growth=False):
    project, output = project.resolve(), output.resolve()
    baseline = baseline_for(project, baseline)
    if output.exists():
        raise ValueError(f'Output already exists: {output}')
    if output.is_relative_to(project) or output.is_relative_to(baseline):
        raise ValueError('Output must be outside the editing project and GFX baseline')
    manifest = json.loads(inside(baseline, 'manifest.json').read_text(encoding='utf-8'))
    if manifest['version'] != 1:
        raise ValueError('Unsupported project version')
    archive_source = Path(manifest.get('archive_source', DEFAULT_ARCHIVE_SOURCE))
    archive_source = (archive_source if archive_source.is_absolute() else ROOT/archive_source).resolve()
    records = manifest['resources']
    lookup = {r['resource']: r for r in records}
    originals, edits, encoded, stats, memory = {}, {}, {}, [], []
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cg-encode-', dir=output.parent) as temporary:
        stage = Path(temporary)

        def process(record):
            key = record['resource']
            if key in encoded:
                return
            raw = inside(baseline, key).read_bytes()
            if sha(raw) != record['sha256']:
                raise ValueError(f'Original resource changed: {key}')
            palette = bytes.fromhex(record['palette'])
            initial_original = initial_edit = None
            parent_changed = False
            if record.get('predecessor'):
                parent = lookup[record['predecessor']]
                process(parent)
                initial_original = originals[parent['resource']][-1].tobytes()
                initial_edit = edits[parent['resource']][-1]
                parent_changed = initial_original != initial_edit
            references = decode(inside(baseline, key), record['kind'], palette, initial_original)
            if len(record['frames']) != len(references):
                raise ValueError(f'Frame count changed: {key}')
            pixels = [load_pixels(inside(project, frame['path']), ref)
                      for frame, ref in zip(record['frames'], references)]
            for frame, ref in zip(record['frames'], references):
                if sha(ref.tobytes()) != frame['pixels_sha256']:
                    raise ValueError(f'Original frame mismatch: {key}')
            # A continuation's first displayed frame comes from its predecessor.
            if parent_changed:
                if pixels[0] != initial_original and pixels[0] != initial_edit:
                    raise ValueError(f'Conflicting WSA chain frame 0 edit: {key}')
                pixels[0] = initial_edit
            originals[key], edits[key] = references, pixels
            changed = any(value != image.tobytes() for value, image in zip(pixels, references))
            kind = record['kind']
            if not changed and not force_all:
                result = raw
            elif kind == 'cps': result = encode_cps(raw, pixels[0])
            elif kind in ('shp', 'embedded_shp'):
                result = encode_shp(raw, pixels, references, kind == 'embedded_shp')
            elif kind == 'wsa':
                initial = initial_edit or bytes(len(pixels[0]))
                result = encode_wsa(raw, pixels, initial,
                                    [image.tobytes() for image in references],
                                    initial_original or bytes(len(pixels[0])),
                                    allow_buffer_growth)
                memory.append(dict(resource=key, original_buffer=u16(raw, 6), encoded_buffer=u16(result, 6)))
            elif kind == 'fnt': result = encode_fnt(raw, pixels)
            elif kind == 'icn': result = encode_icn(raw, pixels)
            else: raise ValueError(f'Unsupported resource: {key}')
            target = inside(stage, key)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(result)
            if kind in ('shp', 'embedded_shp') and result != raw:
                # Match the game's loader format discriminator, independently
                # of the preview decoder which also accepts older tables.
                count = u16(result, 0)
                if u32(result, 2) == 4 + count * 4:
                    if u32(result, 2 + count * 4) != len(result) - 2:
                        raise ValueError(f'SHP loader sentinel mismatch: {key}')
                elif kind == 'embedded_shp':
                    raise ValueError(f'SHP loader first offset mismatch: {key}')
            verified = decode(target, kind, palette, initial_edit)
            if len(verified) != len(pixels) or any(image.tobytes() != value for image, value in zip(verified, pixels)):
                raise ValueError(f'Encoded pixel verification failed: {key}')
            if any(a.size != b.size or a.getpalette() != b.getpalette() or
                   a.info.get('transparency') != b.info.get('transparency')
                   for a, b in zip(verified, references)):
                raise ValueError(f'Encoded geometry/palette verification failed: {key}')
            if kind == 'wsa':
                count = u16(result, 0)
                palette_bytes = 768 if u16(result, 8) & 1 else 0
                start = u32(result, 10 + count * 4)
                end = u32(result, 10 + (count + 1) * 4)
                if end:
                    loop = bytearray(pixels[-1])
                    delta = decode_lcw(result[start + palette_bytes:end + palette_bytes])
                    apply_xor_delta(loop, delta)
                    old_start = u32(raw, 10 + count * 4)
                    old_end = u32(raw, 10 + (count + 1) * 4)
                    old_loop = bytearray(references[-1].tobytes())
                    apply_xor_delta(old_loop, decode_lcw(raw[old_start + palette_bytes:old_end + palette_bytes]))
                    expected_loop = bytes(a ^ b ^ c for a, b, c in
                                          zip(old_loop, references[0].tobytes(), pixels[0]))
                    if loop != expected_loop:
                        raise ValueError(f'WSA loop verification failed: {key}')
            encoded[key] = result
            if changed or force_all:
                stats.append(dict(resource=key, edited=changed, before_bytes=len(raw), after_bytes=len(result)))

        for record in records:
            process(record)
        archive_report = []
        for archive in manifest['archives']:
            path = inside(archive_source, archive['name'])
            original = path.read_bytes()
            if sha(original) != archive['sha256']:
                raise ValueError(f'Original PAK changed: {archive["name"]}')
            matching = [record for record in records if record['pak'] == archive['name']]
            if not matching:
                (stage / archive['name']).write_bytes(original)
                archive_report.append(dict(pak=archive['name'], changed_members=[], sha256=sha(original)))
                continue
            names, members = unpack_pak(original)
            expected = dict(members)
            for record in records:
                if record['pak'] == archive['name']:
                    if members[record['name']] != inside(baseline, record['resource']).read_bytes():
                        raise ValueError('Original PAK/member mismatch')
                    expected[record['name']] = encoded[record['resource']]
            changed_names = [name for name in names if expected[name] != members[name]]
            result = pack_pak(names, expected) if changed_names else original
            actual_names, actual = unpack_pak(result)
            if actual_names != names or actual != expected:
                raise ValueError(f'PAK member verification failed: {archive["name"]}')
            # Ready to copy: PAKs are placed at the output root.
            (stage / archive['name']).write_bytes(result)
            archive_report.append(dict(pak=archive['name'], changed_members=changed_names, sha256=sha(result)))
        report = dict(pixel_roundtrip=True, wsa_loops_verified=True,
                      game_executed=False, archives=archive_report,
                      resources=stats, wsa_buffers=memory,
                      buffer_growth=[item for item in memory if item['encoded_buffer'] > item['original_buffer']])
        write_json(stage / 'encode-report.json', report)
        # Publish only after every resource and archive has passed verification.
        os.rename(stage, output)
    print(f'Encoded {len(stats)} resources; all pixels and PAK members verified: {output}')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export', help='Export editable original-size frames')
    export.add_argument('--game', type=Path)
    export.add_argument('--project', type=Path, default=ROOT / 'import/GFX')
    export.add_argument('--baseline', type=Path)
    encode = sub.add_parser('encode', help='Encode edits and create new PAKs')
    encode.add_argument('--project', type=Path, default=ROOT / 'import/GFX')
    encode.add_argument('--baseline', type=Path)
    encode.add_argument('--out', type=Path)
    encode.add_argument('--allow-buffer-growth', action='store_true',
                        help='Explicitly permit larger WSA decoding buffers; see encode-report.json')
    args = parser.parse_args()
    if args.command == 'export':
        export_project(args.game or default_game(), args.project, args.baseline)
    else:
        output = args.out or ROOT / 'build' / ('cg-encoded-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        encode_project(args.project, output, baseline=args.baseline,
                       allow_buffer_growth=args.allow_buffer_growth)


if __name__ == '__main__':
    main()
