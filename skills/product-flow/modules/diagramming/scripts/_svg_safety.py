"""Shared input/resource and raster budget checks for every SVG entry point."""
import base64
import binascii
import math
import re
import xml.etree.ElementTree as ET


def safe_css_resource(url):
    if url.startswith(('#', 'data:image/')):
        return True
    match = re.fullmatch(r'data:(font/(?:woff2?|ttf|otf)|application/font-woff);base64,([A-Za-z0-9+/=]+)', url)
    if not match:
        return False
    try:
        raw = base64.b64decode(match[2], validate=True)
    except (ValueError, binascii.Error):
        return False
    signatures = {'font/woff': b'wOFF', 'application/font-woff': b'wOFF',
                  'font/woff2': b'wOF2', 'font/ttf': b'\x00\x01\x00\x00', 'font/otf': b'OTTO'}
    return len(raw) >= 12 and raw.startswith(signatures[match[1]])


def validated_svg(source, width):
    if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= 8192:
        raise ValueError('render width must be between 1 and 8192')
    if source.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('SVG input exceeds 8 MiB')
    text = source.read_text(encoding='utf-8')
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('external XML declarations are not allowed')
    root = ET.fromstring(text)
    for element in root.iter():
        if element.tag.split('}')[-1].lower() in {'script', 'iframe', 'object', 'embed'}:
            raise ValueError('active SVG content is not allowed')
        css = element.attrib.get('style', '')
        if element.tag.split('}')[-1].lower() == 'style':
            css += ''.join(element.itertext())
        if chr(92) in css:
            raise ValueError('escaped SVG CSS is unsupported; use explicit safe styles')
        for key, value in element.attrib.items():
            key = key.split('}')[-1].lower()
            if key.startswith('on') or (key in {'href', 'src'} and not value.startswith(('#', 'data:image/'))):
                raise ValueError('external/active SVG resource is not allowed')
    for url in re.findall(r'url\(\s*[\'"]?([^\)\'"]+)', text, re.I):
        if not safe_css_resource(url):
            raise ValueError('external SVG CSS resource is not allowed')
    if re.search(r'@import\b', text, re.I):
        raise ValueError('SVG CSS imports are not allowed')
    view = root.attrib.get('viewBox', '').replace(',', ' ').split()
    def number(value, fallback):
        if value is None:
            return fallback
        match = re.fullmatch(r'\s*([0-9.eE+\-]+)(?:px)?\s*', value)
        if not match:
            raise ValueError('SVG dimensions must use numeric pixels or viewBox')
        return float(match[1])
    if view:
        if len(view) != 4:
            raise ValueError('invalid viewBox')
        values = [float(v) for v in view]
        if not all(math.isfinite(v) for v in values):
            raise ValueError('nonfinite viewBox')
        w, h = values[2:]
    else:
        w = number(root.get('width'), width)
        h = number(root.get('height'), w * 0.625)
    if not all(math.isfinite(v) and v > 0 for v in (w, h)):
        raise ValueError('SVG width/height must be finite and positive')
    height = width * (h / w)
    if not math.isfinite(height) or height > 8192 or width * height > 32 * 1024 * 1024:
        raise ValueError('SVG raster budget exceeded (8192px per axis, 32 megapixels); split diagram')
    return width, max(1, round(height))
