"""Recolour a logo for dark backgrounds, with the standard library only.

The bundled logo is dark artwork on transparency — invisible on the dark rail.
There is no image library here (no pip), so this decodes the PNG by hand
(zlib + the five PNG scanline filters), flips its **dark** pixels to a light ink
while leaving any coloured/light pixels and the alpha channel untouched, and
re-encodes it. That keeps a brand accent intact if the mark has one, and only
lifts the black text/marks so they read on a dark surface.

Only the format the app's own logos use is supported: 8-bit, colour type 6
(RGBA), non-interlaced. Anything else raises ``Unsupported`` and the caller
falls back to the original file.
"""

import struct
import zlib

_SIG = b'\x89PNG\r\n\x1a\n'


class Unsupported(Exception):
    pass


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _read_chunks(raw):
    if raw[:8] != _SIG:
        raise Unsupported('not a PNG')
    i, ihdr, idat = 8, None, bytearray()
    while i < len(raw):
        (length,) = struct.unpack('>I', raw[i:i + 4])
        ctype = raw[i + 4:i + 8]
        data = raw[i + 8:i + 8 + length]
        if ctype == b'IHDR':
            ihdr = data
        elif ctype == b'IDAT':
            idat += data
        i += 12 + length
    if ihdr is None:
        raise Unsupported('no IHDR')
    return ihdr, bytes(idat)


def _unfilter(raw_lines, width, height, bpp):
    stride = width * bpp
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _y in range(height):
        ftype = raw_lines[pos]; pos += 1
        line = bytearray(raw_lines[pos:pos + stride]); pos += stride
        if ftype == 1:                       # Sub
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 0xFF
        elif ftype == 2:                     # Up
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif ftype == 3:                     # Average
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif ftype == 4:                     # Paeth
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                c = prev[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + _paeth(a, prev[x], c)) & 0xFF
        elif ftype != 0:
            raise Unsupported('filter %d' % ftype)
        out += line
        prev = line
    return out


def _encode(pixels, width, height, bpp):
    stride = width * bpp
    raw = bytearray()
    for y in range(height):
        raw.append(0)                        # filter 0 (None)
        raw += pixels[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    return _SIG + chunk(b'IHDR', ihdr) + chunk(b'IDAT', comp) + chunk(b'IEND', b'')


def tint_dark_to_light(src_path, dst_path, ink=(237, 239, 243),
                       threshold=128):
    """Write a dark-mode copy of ``src_path`` to ``dst_path``.

    Pixels darker than ``threshold`` (luminance) become ``ink`` (a near-white by
    default), keeping their alpha; lighter/coloured pixels pass through. Returns
    the number of pixels lifted."""
    return recolor_opaque(src_path, dst_path, ink=ink, mode='dark_only',
                          threshold=threshold)


def recolor_opaque(src_path, dst_path, ink=(255, 79, 24), mode='all',
                   threshold=128):
    """Recolour opaque pixels to ``ink``, preserving alpha.

    ``mode='all'`` — every opaque pixel becomes ``ink`` (keeps the mark shape,
    swaps the fill — used for the ACO Radiant-Orange brand mark).
    ``mode='dark_only'`` — only pixels darker than ``threshold`` luminance
    (legacy dark→light rail lift).

    Returns the number of pixels recoloured.
    """
    with open(src_path, 'rb') as fh:
        raw = fh.read()
    ihdr, idat = _read_chunks(raw)
    width, height, bd, ct, comp, filt, inter = struct.unpack('>IIBBBBB', ihdr)
    if bd != 8 or ct != 6 or inter != 0:
        raise Unsupported('need 8-bit RGBA, non-interlaced')
    bpp = 4
    pixels = _unfilter(zlib.decompress(idat), width, height, bpp)

    ir, ig, ib = ink
    changed = 0
    for i in range(0, len(pixels), 4):
        r, g, b, a = pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3]
        if a == 0:
            continue
        if mode == 'dark_only':
            lum = (r * 299 + g * 587 + b * 114) // 1000
            if lum >= threshold:
                continue
        pixels[i], pixels[i + 1], pixels[i + 2] = ir, ig, ib
        changed += 1
    with open(dst_path, 'wb') as fh:
        fh.write(_encode(pixels, width, height, bpp))
    return changed


def write_ico_png(png_path, ico_path):
    """Write a modern ICO that embeds the PNG payload (Vista+)."""
    with open(png_path, 'rb') as fh:
        png = fh.read()
    ihdr, _ = _read_chunks(png)
    width, height = struct.unpack('>II', ihdr[:8])
    # ICO directory stores 0 for 256; clamp reported size to 255 otherwise.
    w_byte = 0 if width >= 256 else width
    h_byte = 0 if height >= 256 else height
    # ICONDIR (6) + one ICONDIRENTRY (16) + PNG bytes
    offset = 6 + 16
    header = struct.pack('<HHH', 0, 1, 1)
    entry = struct.pack('<BBBBHHII',
                        w_byte, h_byte, 0, 0, 1, 32,
                        len(png), offset)
    with open(ico_path, 'wb') as fh:
        fh.write(header + entry + png)


def sample_colors(src_path, step=7):
    """A coarse histogram of opaque pixel colours — for deciding the rule."""
    with open(src_path, 'rb') as fh:
        raw = fh.read()
    ihdr, idat = _read_chunks(raw)
    width, height, bd, ct, comp, filt, inter = struct.unpack('>IIBBBBB', ihdr)
    pixels = _unfilter(zlib.decompress(idat), width, height, 4)
    hist = {}
    for i in range(0, len(pixels), 4 * step):
        r, g, b, a = pixels[i:i + 4]
        if a < 32:
            continue
        key = (r // 48 * 48, g // 48 * 48, b // 48 * 48)
        hist[key] = hist.get(key, 0) + 1
    return sorted(hist.items(), key=lambda kv: -kv[1])[:8]
