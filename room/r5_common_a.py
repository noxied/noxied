"""Ronda 5 (01-03): utilitarios partilhados por r5_01_sala_servidores, r5_02_switch_52, r5_03_farol."""
import json
import math
from collections import OrderedDict
from datetime import date


def load(path="data/contrib.json"):
    d = json.load(open(path, encoding="utf-8"))
    weeks = d["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(date.fromisoformat(x["date"]), x["contributionCount"]) for w in weeks for x in w["contributionDays"]]


def months_ending(ref):
    """os 12 meses (ano, mes) por ordem cronologica que acabam no mes de `ref` (date/datetime), inclusive."""
    y, m = ref.year, ref.month
    keys = []
    for _ in range(12):
        keys.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return keys[::-1]


def last12(days, ref=None):
    """OrderedDict (ano, mes) -> [(date, count)] para os 12 meses que acabam no mes de `ref` (omissao: o mes do
    ultimo dia dos dados). O ultimo mes e o corrente (parcial)."""
    out = OrderedDict((k, []) for k in months_ending(ref or days[-1][0]))
    for d, c in days:
        if (d.year, d.month) in out:
            out[(d.year, d.month)].append((d, c))
    return out


def grain(fid="grain", amount=0.07, freq=0.85, seed=3):
    """Filtro de grao: ruido monocromatico com alfa baixo (usar num <rect> por cima de tudo)."""
    return (f'<filter id="{fid}" x="0" y="0" width="100%" height="100%">'
            f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" seed="{seed}" stitchTiles="stitch"/>'
            f'<feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  {amount * 4:.3f} 0 0 0 {-amount * 1.6:.3f}"/>'
            f'</filter>'
            f'<filter id="{fid}d" x="0" y="0" width="100%" height="100%">'
            f'<feTurbulence type="fractalNoise" baseFrequency="{freq * 1.1:.2f}" numOctaves="2" seed="{seed + 7}" stitchTiles="stitch"/>'
            f'<feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  {amount * 4:.3f} 0 0 0 {-amount * 1.6:.3f}"/>'
            f'</filter>')


def lv(c, peak=130, n=4):
    if c <= 0:
        return 0
    return max(1, min(n, 1 + int((n - 1) * math.log1p(c) / math.log1p(peak) + 0.35)))


def f(x):
    return f"{x:.1f}".rstrip("0").rstrip(".")
