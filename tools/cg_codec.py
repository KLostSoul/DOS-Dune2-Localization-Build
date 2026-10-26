"""Dune II CG codecs. Preserve dimensions, indexed colours and resource metadata."""
from __future__ import annotations

import struct
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]

def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]

def decode_lcw(source: bytes, limit: int = 2_000_000, expected_size: int | None = None) -> bytes:
    """Decode Westwood LCW (Format 80), stopping at its 0x80 end marker."""
    src = 1 if source[:1] == b"\x00" else 0
    relative = src == 1
    out = bytearray()

    def complete() -> bool:
        if expected_size is None:
            return False
        if len(out) > expected_size:
            raise ValueError(f"LCW output exceeded expected size {expected_size}")
        return len(out) == expected_size

    def copy_from(position: int, count: int) -> None:
        if position < 0 or position >= len(out):
            raise ValueError(f"LCW back-reference outside output: {position}")
        for _ in range(count):
            out.append(out[position])
            position += 1
            if len(out) > limit:
                raise ValueError("LCW output exceeded safety limit")

    while src < len(source):
        if complete():
            return bytes(out)
        command = source[src]
        src += 1
        if command < 0x80:
            if src >= len(source):
                raise ValueError("truncated LCW short copy")
            count = ((command & 0x70) >> 4) + 3
            distance = ((command & 0x0F) << 8) | source[src]
            src += 1
            copy_from(len(out) - distance, count)
        elif command < 0xC0:
            count = command & 0x3F
            if count == 0:
                return bytes(out)
            if src + count > len(source):
                raise ValueError("truncated LCW literal")
            out.extend(source[src:src + count])
            src += count
        elif command < 0xFE:
            count = (command & 0x3F) + 3
            if src + 2 > len(source):
                raise ValueError("truncated LCW medium copy")
            position = u16(source, src)
            src += 2
            copy_from(len(out) - position if relative else position, count)
        elif command == 0xFE:
            if src + 3 > len(source):
                raise ValueError("truncated LCW fill")
            count = u16(source, src)
            value = source[src + 2]
            src += 3
            out.extend(bytes((value,)) * count)
        else:  # 0xFF: long copy
            if src + 4 > len(source):
                raise ValueError("truncated LCW long copy")
            count = u16(source, src)
            position = u16(source, src + 2)
            src += 4
            copy_from(len(out) - position if relative else position, count)
        if len(out) > limit:
            raise ValueError("LCW output exceeded safety limit")
        if complete():
            return bytes(out)
    if expected_size is not None and len(out) == expected_size:
        return bytes(out)
    return bytes(out)

def apply_xor_delta(canvas: bytearray, delta: bytes) -> None:
    src = 0
    dst = 0

    def skip(count: int) -> None:
        nonlocal dst
        dst += count
        if dst > len(canvas):
            raise ValueError("WSA XOR skip exceeds frame")

    def xor_bytes(count: int) -> None:
        nonlocal src, dst
        if src + count > len(delta) or dst + count > len(canvas):
            raise ValueError("WSA XOR literal exceeds buffer")
        for i in range(count):
            canvas[dst + i] ^= delta[src + i]
        src += count
        dst += count

    while src < len(delta):
        command = delta[src]
        src += 1
        if command & 0x80:
            if command != 0x80:
                skip(command & 0x7F)
                continue
            if src + 2 > len(delta):
                raise ValueError("truncated WSA extended XOR command")
            value = u16(delta, src)
            src += 2
            if value == 0:
                return
            kind = value >> 14
            count = value & 0x3FFF
            if kind < 2:
                skip(value)
            elif kind == 2:
                xor_bytes(count)
            else:
                if src >= len(delta) or dst + count > len(canvas):
                    raise ValueError("truncated WSA repeated XOR command")
                repeat = delta[src]
                src += 1
                for i in range(count):
                    canvas[dst + i] ^= repeat
                dst += count
        elif command == 0:
            if src + 2 > len(delta):
                raise ValueError("truncated WSA short repeated XOR")
            count, repeat = delta[src], delta[src + 1]
            src += 2
            if dst + count > len(canvas):
                raise ValueError("WSA repeated XOR exceeds frame")
            for i in range(count):
                canvas[dst + i] ^= repeat
            dst += count
        else:
            xor_bytes(command)

@dataclass
class Wsa:
    path: Path
    width: int
    height: int
    frames: list[bytes]

def decode_wsa(path: Path, palette: bytes, initial: bytes | None = None) -> Wsa:
    data = path.read_bytes()
    if len(data) < 10:
        raise ValueError("WSA header is too short")
    frame_count, width, height, _delta_size, flags = struct.unpack_from("<5H", data, 0)
    if not frame_count or not width or not height or width * height > 1_000_000:
        raise ValueError("invalid WSA dimensions/header")
    table_start = 10
    table_end = table_start + (frame_count + 2) * 4
    if table_end > len(data):
        raise ValueError("truncated WSA frame table")
    offsets = list(struct.unpack_from("<" + "I" * (frame_count + 2), data, table_start))
    embedded_palette = bool(flags & 1)
    palette_bytes = 768 if embedded_palette else 0
    if embedded_palette:
        palette_start = table_end
        if palette_start + palette_bytes > len(data):
            raise ValueError("truncated WSA palette")
        palette = data[palette_start:palette_start + palette_bytes]
    # Dune II offsets address the stream before the optional palette adjustment.
    offsets = [off + palette_bytes if off else 0 for off in offsets]
    last_data_end = offsets[-1] if offsets[-1] else offsets[-2]
    if last_data_end > len(data):
        raise ValueError("WSA end offset exceeds file")
    canvas = bytearray(initial or bytes(width * height))
    if len(canvas) != width * height:
        raise ValueError(f"WSA chain dimensions mismatch for {path.name}")
    frames: list[bytes] = []
    for i in range(frame_count):
        start, end = offsets[i], offsets[i + 1]
        if i == 0 and start == 0:
            frames.append(bytes(canvas))
            continue
        if start == 0 or end < start or end > len(data):
            raise ValueError(f"invalid WSA frame offsets {start}..{end} at {i}")
        delta = decode_lcw(data[start:end], limit=max(width * height * 3, 65536))
        apply_xor_delta(canvas, delta)
        frames.append(bytes(canvas))
    return Wsa(path, width, height, frames)

def palette_to_rgb(raw: bytes) -> list[int]:
    if len(raw) < 768:
        raise ValueError("palette must have at least 768 bytes")
    rgb: list[int] = []
    for value in raw[:768]:
        rgb.append((value * 255 + 31) // 63 if value <= 63 else value)
    return rgb

def indexed_image(pixels: bytes, size: tuple[int, int], palette: bytes) -> Image.Image:
    image = Image.frombytes("P", size, pixels)
    image.putpalette(palette_to_rgb(palette))
    return image

def decode_cps(path: Path, palette: bytes) -> Image.Image:
    data = path.read_bytes()
    if len(data) < 10:
        raise ValueError("CPS header is too short")
    _file_size, method, uncompressed_size, palette_size = struct.unpack_from("<HHIH", data, 0)
    if uncompressed_size > 2_000_000:
        raise ValueError("unreasonable CPS uncompressed size")
    offset = 10
    if palette_size:
        if palette_size < 768 or offset + palette_size > len(data):
            raise ValueError("unexpected CPS embedded palette size")
        palette = data[offset:offset + 768]
        offset += palette_size
    packed = data[offset:]
    if method == 0:
        pixels = packed[:uncompressed_size]
    elif method == 4:
        pixels = decode_lcw(packed, limit=uncompressed_size + 1, expected_size=uncompressed_size)
    else:
        raise ValueError(f"unsupported CPS compression type {method}")
    if len(pixels) != uncompressed_size:
        raise ValueError(f"CPS decoded {len(pixels)} bytes; expected {uncompressed_size}")
    if uncompressed_size != 320 * 200:
        raise ValueError(f"CPS dimensions are not 320x200 ({uncompressed_size} pixels)")
    return indexed_image(pixels, (320, 200), palette)

def decode_rle_zero(data: bytes, width: int, height: int) -> bytes:
    out = bytearray(width * height)
    src = 0
    for y in range(height):
        x = 0
        while x < width:
            if src >= len(data):
                raise ValueError("truncated SHP RLE-zero row")
            value = data[src]
            src += 1
            if value == 0:
                if src >= len(data):
                    raise ValueError("truncated SHP RLE-zero run")
                count = data[src]
                src += 1
                if count == 0:
                    continue
                x += count
            else:
                out[y * width + x] = value
                x += 1
    return bytes(out)

def decode_shp(path: Path, palette: bytes) -> list[Image.Image]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError("SHP file is too short")
    count = u16(data, 0)
    if count == 0 or count > 4096:
        raise ValueError("invalid SHP frame count")
    # Dune II v1.07 uses DWORD offsets relative to the table at byte 2;
    # the older v1.00 form uses WORD offsets absolute from the file start.
    table_end32 = 2 + (count + 1) * 4
    use_v107 = table_end32 <= len(data)
    if use_v107:
        offsets = [u32(data, 2 + i * 4) for i in range(count + 1)]
        use_v107 = offsets[-1] == len(data) - 2 and 2 + offsets[0] >= table_end32
    if use_v107:
        ranges = [(2 + offsets[i], 2 + offsets[i + 1]) for i in range(count)]
    else:
        table_end16 = 2 + (count + 1) * 2
        if table_end16 > len(data):
            raise ValueError("truncated SHP offset table")
        offsets = [u16(data, 2 + i * 2) for i in range(count + 1)]
        if offsets[-1] != len(data) or offsets[0] < table_end16:
            raise ValueError("unrecognized SHP offset table")
        ranges = [(offsets[i], offsets[i + 1]) for i in range(count)]
    frames: list[Image.Image] = []
    for i, (start, end) in enumerate(ranges):
        if start == end:
            raise ValueError(f"empty SHP frame {i}")
        flags = u16(data, start)
        rows = data[start + 2]
        width = u16(data, start + 3)
        height = data[start + 5]
        frame_size = u16(data, start + 6)
        zero_size = u16(data, start + 8)
        if not width or not height or rows != height or width * height > 1_000_000:
            raise ValueError(f"invalid SHP dimensions on frame {i}")
        cursor = start + 10
        remap_size = 16
        if flags & 0x04:
            remap_size = data[cursor]
            cursor += 1
        remap = None
        if flags & 0x01:
            remap = data[cursor:cursor + remap_size]
            if len(remap) != remap_size:
                raise ValueError("truncated SHP remap table")
            cursor += remap_size
        if start + frame_size > end:
            raise ValueError("SHP frame size extends past next frame")
        packed = data[cursor:start + frame_size]
        if flags & 0x02:
            zero_data = packed
        else:
            zero_data = decode_lcw(packed, limit=max(zero_size + 1, 65536), expected_size=zero_size)
            if zero_size and len(zero_data) != zero_size:
                raise ValueError(f"SHP LCW size mismatch on frame {i}")
        pixels = decode_rle_zero(zero_data, width, height)
        if remap:
            pixels = bytes(remap[v] if v < len(remap) else v for v in pixels)
        image = indexed_image(pixels, (width, height), palette)
        image.info["transparency"] = 0
        frames.append(image)
    return frames

def decode_embedded_shp_table(path: Path, palette: bytes) -> list[Image.Image]:
    """Decode language PAK tables that wrap one SHP frame per offset entry."""
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError("embedded SHP table is too short")
    count = u16(data, 0)
    table_end = 2 + count * 4
    if count == 0 or count > 512 or table_end > len(data):
        raise ValueError("invalid embedded SHP table count")
    offsets = [u32(data, 2 + i * 4) for i in range(count)]
    if offsets[0] < table_end or offsets != sorted(offsets) or offsets[-1] >= len(data):
        raise ValueError("invalid embedded SHP table offsets")
    frames: list[Image.Image] = []
    for i, entry in enumerate(offsets):
        block_end = offsets[i + 1] if i + 1 < count else len(data)
        start = entry + 2  # two-byte wrapper precedes each Dune II frame header
        if start + 10 > block_end:
            raise ValueError(f"short embedded SHP frame {i}")
        flags = u16(data, start)
        rows = data[start + 2]
        width = u16(data, start + 3)
        height = data[start + 5]
        frame_size = u16(data, start + 6)
        zero_size = u16(data, start + 8)
        if not width or not height or rows != height or width * height > 1_000_000:
            raise ValueError(f"invalid embedded SHP dimensions on frame {i}")
        # Frame offsets point two bytes before each header. The previous frame's
        # size can consume those two bytes as its final LCW operand.
        frame_end = min(len(data), start + frame_size)
        if frame_end > block_end + 2:
            raise ValueError(f"embedded SHP frame {i} extends past its block")
        cursor = start + 10
        remap_size = 16
        if flags & 0x04:
            remap_size = data[cursor]
            cursor += 1
        remap = None
        if flags & 0x01:
            remap = data[cursor:cursor + remap_size]
            if len(remap) != remap_size:
                raise ValueError("truncated embedded SHP remap table")
            cursor += remap_size
        packed = data[cursor:frame_end]
        if flags & 0x02:
            zero_data = packed
        else:
            zero_data = decode_lcw(packed, limit=max(zero_size + 1, 65536), expected_size=zero_size)
            if zero_size and len(zero_data) != zero_size:
                raise ValueError(f"embedded SHP LCW size mismatch on frame {i}")
        pixels = decode_rle_zero(zero_data, width, height)
        if remap:
            pixels = bytes(remap[value] if value < len(remap) else value for value in pixels)
        image = indexed_image(pixels, (width, height), palette)
        image.info["transparency"] = 0
        frames.append(image)
    return frames

def font_glyphs(path: Path) -> tuple[list[Image.Image], int, int, int]:
    data = path.read_bytes()
    if len(data) < 20 or data[2] != 0 or data[3] != 5:
        raise ValueError("unsupported Westwood FNT version/header")
    info, offsets_pos, widths_pos, _data_pos, heights_pos = struct.unpack_from("<5H", data, 4)
    last_code = data[info + 3]
    count = last_code + 1
    glyphs: list[Image.Image] = []
    max_width = max_height = 0
    for i in range(count):
        offset = u16(data, offsets_pos + i * 2)
        width = data[widths_pos + i]
        yoff, height = data[heights_pos + i * 2:heights_pos + i * 2 + 2]
        max_width = max(max_width, width)
        max_height = max(max_height, height)
        pixels = bytearray(width * height)
        if width and height:
            stride = (width + 1) // 2
            if offset + stride * height > len(data):
                raise ValueError(f"truncated glyph {i}")
            for y in range(height):
                row = data[offset + y * stride:offset + (y + 1) * stride]
                for x in range(width):
                    byte = row[x // 2]
                    pixels[y * width + x] = ((byte & 0x0F) if x % 2 == 0 else (byte >> 4)) * 17
        if not pixels:
            pixels = bytearray(max(width, 1) * max(height, 1))
        image = Image.frombytes("L", (max(width, 1), max(height, 1)), bytes(pixels))
        image.info["y_offset"] = yoff
        glyphs.append(image)
    return glyphs, count, max_width, max_height


def lcw(data):
    """Format 80 with literals, fills and absolute copies (DOS-compatible)."""
    out, literal = bytearray(), bytearray()
    positions = defaultdict(lambda: deque(maxlen=24))

    def flush():
        if literal:
            out.append(0x80 | len(literal))
            out.extend(literal)
            literal.clear()

    at = 0
    while at < len(data):
        run = 1
        while at + run < len(data) and run < 65535 and data[at + run] == data[at]:
            run += 1
        best, location = 0, 0
        key = data[at:at + 3]
        if run < 8 and len(key) == 3:
            for previous in reversed(positions.get(key, ())):
                if previous > 65535:
                    continue
                count = 3
                limit = min(len(data) - at, 65535)
                while count < limit and data[previous + count] == data[at + count]:
                    count += 1
                if count > best:
                    best, location = count, previous
        if run >= 4 and run >= best:
            flush()
            out.extend(b'\xfe' + struct.pack('<H', run) + bytes([data[at]]))
            count = run
        elif best >= 4:
            flush()
            if best <= 64:
                out.extend(bytes([0xc0 + best - 3]) + struct.pack('<H', location))
            else:
                out.extend(b'\xff' + struct.pack('<HH', best, location))
            count = best
        else:
            literal.append(data[at])
            if len(literal) == 63:
                flush()
            count = 1
        for pos in range(at, at + count):
            if pos <= 65535:
                positions[data[pos:pos + 3]].append(pos)
        at += count
    flush()
    out.append(0x80)
    result = bytes(out)
    if decode_lcw(result, limit=len(data) + 1) != data:
        raise ValueError('LCW round trip failed')
    return result


def xor_delta(before, after):
    delta = bytes(a ^ b for a, b in zip(before, after))
    out = bytearray()
    at = 0
    while at < len(delta):
        if delta[at] == 0:
            end = at + 1
            while end < len(delta) and delta[end] == 0:
                end += 1
            count = end - at
            if end == len(delta):
                break
            while count:
                size = min(count, 32767)
                if size <= 127:
                    out.append(0x80 | size)
                else:
                    out.extend(b'\x80' + struct.pack('<H', size))
                count -= size
        else:
            end = at + 1
            while end < len(delta) and delta[end] == delta[at] and end - at < 16383:
                end += 1
            count = end - at
            if count >= 3:
                if count <= 255:
                    out.extend((0, count, delta[at]))
                else:
                    out.extend(b'\x80' + struct.pack('<H', 0xc000 | count) + bytes([delta[at]]))
            else:
                end = at + 1
                while end < len(delta) and delta[end] and end - at < 127:
                    if end + 2 < len(delta) and delta[end] == delta[end + 1] == delta[end + 2]:
                        break
                    end += 1
                out.append(end - at)
                out.extend(delta[at:end])
        at = end
    return bytes(out + b'\x80\x00\x00')


def load_pixels(path, reference):
    """Reject silent quantization/resizing; retain palette indices when possible."""
    with Image.open(path) as image:
        image.load()
        if image.size != reference.size:
            raise ValueError(f'{path}: expected {reference.size}, got {image.size}')
        if reference.mode == 'L':
            gray = image.convert('L')
            if image.convert('RGB').tobytes() != gray.convert('RGB').tobytes():
                raise ValueError(f'{path}: font must be grayscale')
            pixels = gray.tobytes()
            if any(value % 17 for value in pixels):
                raise ValueError(f'{path}: font levels must be multiples of 17')
            return pixels
        palette = reference.getpalette()[:768]
        if image.mode == 'P' and image.getpalette()[:768] == palette:
            if image.info.get('transparency') != reference.info.get('transparency'):
                raise ValueError(f'{path}: transparency index changed')
            return image.tobytes()
        colours = defaultdict(list)
        for index in range(256):
            colours[tuple(palette[index * 3:index * 3 + 3])].append(index)
        original = reference.tobytes()
        pixels = bytearray()
        transparent = reference.info.get('transparency')
        for position, colour in enumerate(image.convert('RGBA').getdata()):
            if colour[3] not in (0, 255):
                raise ValueError(f'{path}: partial alpha is not supported')
            if colour[3] == 0:
                if transparent is None:
                    raise ValueError(f'{path}: this image has no transparent colour')
                pixels.append(transparent)
                continue
            candidates = colours.get(colour[:3], [])
            if transparent is not None:
                candidates = [value for value in candidates if value != transparent]
            old = original[position]
            if old in candidates:
                pixels.append(old)
            elif len(candidates) == 1:
                pixels.append(candidates[0])
            else:
                raise ValueError(f'{path}: colour {colour[:3]} is absent or ambiguous; use indexed PNG')
        return bytes(pixels)


def encode_cps(raw, pixels):
    palette_size = u16(raw, 8)
    palette = raw[10:10 + palette_size]
    packed = lcw(pixels)
    # The original loader reads compressed bytes into the end of a 64K screen.
    if len(packed) + 8 > 64000:
        raise ValueError('CPS compressed stream exceeds original screen buffer')
    result = struct.pack('<HHIH', 8 + len(palette) + len(packed), 4,
                         len(pixels), len(palette)) + palette + packed
    return result


def shp_blocks(raw, embedded):
    count = u16(raw, 0)
    if embedded:
        offsets = [u32(raw, 2 + i * 4) for i in range(count)]
        return [raw[offset + 2:offset + 2 + u16(raw, offset + 8)] for offset in offsets], 'embedded'
    end32 = 2 + (count + 1) * 4
    if end32 <= len(raw) and u32(raw, 2 + count * 4) == len(raw) - 2:
        offsets = [2 + u32(raw, 2 + i * 4) for i in range(count + 1)]
        kind = 'dword'
    else:
        offsets = [u16(raw, 2 + i * 2) for i in range(count + 1)]
        kind = 'word'
    return [raw[start:start + u16(raw, start + 6)] for start in offsets[:-1]], kind


def rle_zero(pixels, width):
    out = bytearray()
    for row in range(0, len(pixels), width):
        at, end = row, row + width
        while at < end:
            if pixels[at]:
                out.append(pixels[at])
                at += 1
            else:
                stop = at + 1
                while stop < end and pixels[stop] == 0 and stop - at < 255:
                    stop += 1
                out.extend((0, stop - at))
                at = stop
    return bytes(out)


def encode_shape(block, pixels):
    flags = u16(block, 0)
    cursor, size = 10, 16
    if flags & 4:
        size = block[cursor]
        cursor += 1
    if flags & 1:
        remap = block[cursor:cursor + size]
        inverse = {value: index for index, value in reversed(list(enumerate(remap)))}
        if any(value not in inverse for value in pixels):
            raise ValueError('SHP edit uses a colour outside its original remap palette')
        pixels = bytes(inverse[value] for value in pixels)
        cursor += size
    zero = rle_zero(pixels, u16(block, 3))
    packed = zero if flags & 2 else lcw(zero)
    header = bytearray(block[:cursor])
    if len(zero) > 65535 or cursor + len(packed) > 65535:
        raise ValueError('SHP frame exceeds 16-bit size')
    struct.pack_into('<HH', header, 6, cursor + len(packed), len(zero))
    return bytes(header) + packed


def encode_shp(raw, images, original_images, embedded):
    blocks, kind = shp_blocks(raw, embedded)
    blocks = [encode_shape(block, pixels) if pixels != image.tobytes() else block
              for block, pixels, image in zip(blocks, images, original_images)]
    count = len(blocks)
    if kind == 'embedded':
        # Language tables use the same v1.07 count+1 DWORD offsets as SHP.
        # Offsets address two bytes before the header, not a per-frame wrapper.
        kind = 'dword'
    step = 4 if kind == 'dword' else 2
    start = 2 + (count + 1) * step
    offsets, body = [], bytearray()
    for block in blocks:
        offsets.append(start + len(body) - (2 if step == 4 else 0))
        body.extend(block)
    offsets.append(start + len(body) - (2 if step == 4 else 0))
    result = struct.pack('<H', count) + struct.pack('<' + ('I' if step == 4 else 'H') * (count + 1), *offsets) + body
    if len(result) > 65535:
        raise ValueError('SHP resource exceeds the DOS 16-bit file-size limit')
    return result


def lcw_buffer_size(packed):
    """Space needed when the compressed source occupies the buffer's tail."""
    source = produced = peak = 0
    while source < len(packed):
        command = packed[source]
        source += 1
        if command < 0x80:
            source += 1
            count = ((command & 0x70) >> 4) + 3
        elif command < 0xc0:
            count = command & 63
            if not count:
                break
            source += count
        elif command < 0xfe:
            source += 2
            count = (command & 63) + 3
        elif command == 0xfe:
            count = u16(packed, source)
            source += 3
        else:
            count = u16(packed, source)
            source += 4
        produced += count
        peak = max(peak, produced - source)
    return len(packed) + peak + 33


def encode_wsa(raw, frames, initial, original_frames=None, original_initial=None,
               allow_buffer_growth=False):
    count, width, height, buffer_size, flags = struct.unpack_from('<5H', raw)
    old_offsets = struct.unpack_from('<' + 'I' * (count + 2), raw, 10)
    no_first = old_offsets[0] == 0
    if no_first and frames[0] != initial:
        raise ValueError('WSA continuation frame 0 must equal the preceding sequence last frame')
    palette_size = 768 if flags & 1 else 0
    table_end = 10 + 4 * (count + 2)
    palette = raw[table_end:table_end + palette_size]
    body, offsets = bytearray(), []
    previous = initial
    required = buffer_size
    for i in range(count + (1 if old_offsets[-1] else 0)):
        if i == 0 and no_first:
            offsets.append(0)
            continue
        current = frames[0] if i == count else frames[i]
        if i == count and original_frames:
            # Some shipped WSA loop deltas intentionally do not reconstruct
            # frame 0 exactly. Preserve that existing residual, too.
            old_loop = bytearray(original_frames[-1])
            start, end = old_offsets[-2:]
            apply_xor_delta(old_loop, decode_lcw(raw[start + palette_size:end + palette_size]))
            current = bytes(a ^ b ^ c for a, b, c in zip(old_loop, original_frames[0], frames[0]))
        old_current = bytes(old_loop) if i == count and original_frames else original_frames[i] if original_frames else None
        old_previous = (original_initial if i == 0 else original_frames[i - 1]) if original_frames else None
        if current == old_current and previous == old_previous:
            start, end = old_offsets[i:i + 2]
            packed = raw[start + palette_size:end + palette_size]
        else:
            delta = xor_delta(previous, current)
            packed = lcw(delta)
            required = max(required, lcw_buffer_size(packed))
        offsets.append(table_end + len(body))
        body.extend(packed)
        previous = current
    offsets.append(table_end + len(body))
    if not old_offsets[-1]:
        offsets.append(0)
    if required > 65535:
        raise ValueError('WSA delta buffer exceeds 16-bit DOS limit')
    if required > buffer_size and not allow_buffer_growth:
        raise ValueError(f'WSA edit needs buffer {required} bytes; original is {buffer_size}. '
                         'Reduce changed pixels or explicitly use --allow-buffer-growth.')
    return struct.pack('<5H', count, width, height, required, flags) + struct.pack('<' + 'I' * (count + 2), *offsets) + palette + body


def encode_fnt(raw, images):
    result = bytearray(raw)
    _, offsets, widths, _, heights = struct.unpack_from('<5H', raw, 4)
    for i, pixels in enumerate(images):
        width = raw[widths + i]
        height = raw[heights + i * 2 + 1]
        if not width or not height:
            continue
        old_at = u16(raw, offsets + i * 2)
        stride = (width + 1) // 2
        glyph = bytearray(raw[old_at:old_at + stride * height])
        for y in range(height):
            for x in range(width):
                pos, shift = y * stride + x // 2, (x % 2) * 4
                glyph[pos] = (glyph[pos] & ~(15 << shift)) | ((pixels[y * width + x] // 17) << shift)
        if glyph != raw[old_at:old_at + stride * height]:
            # Original fonts share bitmap storage between characters. Allocate
            # changed glyph data separately instead of corrupting its aliases.
            at = len(result)
            if at + len(glyph) > 65535:
                raise ValueError('FNT exceeds its original 16-bit offset limit')
            struct.pack_into('<H', result, offsets + i * 2, at)
            result.extend(glyph)
    struct.pack_into('<H', result, 0, len(result))
    return bytes(result)


def icn_parts(raw):
    if raw[:4] != b'FORM' or raw[8:12] != b'ICON':
        raise ValueError('Unsupported ICN container')
    parts, at = [], 12
    while at + 8 <= len(raw):
        size = struct.unpack_from('>I', raw, at + 4)[0]
        parts.append((raw[at:at + 4], raw[at + 8:at + 8 + size]))
        at += 8 + size + size % 2
    return parts


def decode_icn(raw, palette):
    parts = dict(icn_parts(raw))
    sset = parts[b'SSET']
    method, length, palette_size = struct.unpack_from('<HIH', sset)
    data = sset[8 + palette_size:]
    pixels = data[:length] if method == 0 else decode_lcw(data, expected_size=length)
    sinf = parts[b'SINF']
    width, height = sinf[0] * 8, sinf[1] * 8
    stride = width * height // 2
    images = []
    for i, mapping in enumerate(parts[b'RTBL']):
        remap = parts[b'RPAL'][mapping * 16:mapping * 16 + 16]
        tile = pixels[i * stride:(i + 1) * stride]
        values = bytes(value for byte in tile for value in (remap[byte >> 4], remap[byte & 15]))
        image = indexed_image(values, (width, height), palette)
        if remap[0] == 0:
            image.info['transparency'] = 0
        images.append(image)
    return images


def encode_icn(raw, images):
    parts = icn_parts(raw)
    lookup = dict(parts)
    sset = lookup[b'SSET']
    method, length, palette_size = struct.unpack_from('<HIH', sset)
    old = sset[8 + palette_size:]
    pixels = bytearray(old[:length] if method == 0 else decode_lcw(old, expected_size=length))
    for i, (values, mapping) in enumerate(zip(images, lookup[b'RTBL'])):
        remap = lookup[b'RPAL'][mapping * 16:mapping * 16 + 16]
        inverse = {value: index for index, value in reversed(list(enumerate(remap)))}
        if any(value not in inverse for value in values):
            raise ValueError(f'ICN tile {i}: colour outside original tile remap palette')
        indices = bytes(inverse[value] for value in values)
        packed = bytes((indices[x] << 4) | indices[x + 1] for x in range(0, len(indices), 2))
        pixels[i * len(packed):(i + 1) * len(packed)] = packed
    data = bytes(pixels) if method == 0 else lcw(bytes(pixels))
    lookup[b'SSET'] = sset[:8 + palette_size] + data
    body = bytearray(b'ICON')
    for name, original in parts:
        value = lookup[name] if name == b'SSET' else original
        body.extend(name + struct.pack('>I', len(value)) + value + b'\0' * (len(value) % 2))
    return b'FORM' + struct.pack('>I', len(body)) + body


def decode(path, kind, palette, initial=None):
    if kind == 'cps':
        return [decode_cps(path, palette)]
    if kind == 'shp':
        return decode_shp(path, palette)
    if kind == 'embedded_shp':
        return decode_embedded_shp_table(path, palette)
    if kind == 'wsa':
        seq = decode_wsa(path, palette, initial)
        raw = path.read_bytes()
        if u16(raw, 8) & 1:
            start = 10 + (len(seq.frames) + 2) * 4
            palette = raw[start:start + 768]
        return [indexed_image(frame, (seq.width, seq.height), palette) for frame in seq.frames]
    if kind == 'fnt':
        return font_glyphs(path)[0]
    if kind == 'icn':
        return decode_icn(path.read_bytes(), palette)
    raise ValueError(f'Unknown CG type: {kind}')
