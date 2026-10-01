"""Converte texto em <path> SVG (sem depender de fontes no browser/GitHub)."""
from functools import lru_cache
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
import os

FONT = os.path.join(os.path.dirname(__file__), "bricolage.ttf")


@lru_cache(None)
def instance(wght=400, wdth=100, opsz=24):
    return instantiateVariableFont(TTFont(FONT), {"wght": wght, "wdth": wdth, "opsz": opsz})


def text_path(text, x, y, size, wght=400, wdth=100, opsz=None, tracking=0.0, anchor="start"):
    """Devolve (d, largura). tracking em em."""
    f = instance(wght, wdth, opsz or max(12, min(96, size)))
    upm = f["head"].unitsPerEm
    cmap = f.getBestCmap()
    gs = f.getGlyphSet()
    hmtx = f["hmtx"]
    s = size / upm
    names = [cmap.get(ord(c), ".notdef") for c in text]
    width = sum(hmtx[n][0] for n in names) * s + tracking * size * (len(names) - 1)
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    pen = SVGPathPen(gs)
    cx = x
    for n in names:
        tp = TransformPen(pen, (s, 0, 0, -s, cx, y))
        gs[n].draw(tp)
        cx += hmtx[n][0] * s + tracking * size
    import re as _re
    return _re.sub(r'(\d+\.\d)\d+', lambda m: m.group(1), pen.getCommands()), width
