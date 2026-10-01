"""Sala de servidores, versao final (r9): relogio de luz com a hora real em Portugal.

Copia de tools/final_sala.py para o pacote room (imports relativos; acrescentado mode='fallback':
relogio de 12 h so com o ponteiro das horas, posto com um avanco de FALLBACK_LEAD minutos, para compensar a idade media da imagem).

Evolucao de tools/clock_sala.py + tools/r6_01_sala-servidores.py (copiados, nao importados).
"""
import argparse
import importlib.util
import math
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
from .r5_common_a import load, last12, grain, lv  # noqa: E402
from .txt import text_path  # noqa: E402
from .clock_common import (LAT, LON, lisbon_offset, to_utc, now_local, solar,  # noqa: E402,F401
                          hx, hexc, mixc, lerpc, ss, keyed, blend, moon_phase, events)

W, H = 830, 360

# ---------------- camara ----------------
CAM = (9.3, 1.3, -4.6)      # x, y, z (m)
YAW = math.radians(19)      # rodada para a esquerda
FOC = 600.0
CX, HZ = 606.0, 162.0       # centro optico / linha do horizonte (px)
_ca, _sa = math.cos(YAW), math.sin(YAW)

ZF = 0.0                    # plano das frentes
ZB = 0.95                   # parede do fundo
CEIL = 2.72
XEND = -0.55                # parede do topo (esquerda)
UH = 0.0445                 # 1U
GAP = 0.04
WGAP = 0.20                 # folga extra de cada lado das estantes de arame (a janela respira)
WIN = (3.80, 4.95, 1.60, 2.48)      # janela alta: x0, x1, y0, y1 (por cima das estantes de arame baixas)
DOOR = (8.86, 9.58, 1.98)           # porta na parede do fundo: x0, x1, altura
CLOCK = (9.15, 2.265, .186)          # relogio de 12 h por cima da porta: x, y, raio
NP = 3                              # vidros da janela
WD = 0.28                           # espessura da parede na janela
SUN = (0.8, -0.9, -1.0)           # direcao da luz que entra

# estilo, largura, altura, receita (1 = 1U/dia, 2 = 2U/2 dias, 4 = prateleira de 4 mini PCs;
# m = mini PC, t = NAS de 4 baias, nas estantes de arame)
# Fixo por POSICAO (da esquerda para a direita). Os meses sao dinamicos: a posicao i mostra o i-esimo dos ultimos
# 12 meses ate ao mes corrente (hora de Lisboa); o corrente (parcial) e o ultimo, o mais perto. Um mes com < 5
# contribuicoes fica "parado" (rack vazio / estante com caixas), decidido pelos dados.
KIND = [
    ("glass", 0.62, 1.9, "1121"),
    ("open", 0.60, 2.00, "2214"),
    ("open", 0.60, 2.00, "1112"),
    ("glass", 0.62, 1.84, "2141"),
    ("open", 0.60, 2.00, "2141"),
    ("glass", 0.64, 2.06, "1211"),
    ("wire", 0.80, 1.52, "tmmm"),   # } estantes baixas por baixo da janela
    ("wire", 0.80, 1.52, "mmtm"),   # }
    ("open", 0.60, 2.00, "1112"),
    ("glass", 0.62, 1.9, "4121"),
    ("open", 0.60, 2.00, "2214"),
    ("glass", 0.64, 2.06, "2114"),
]
PEAK = 130     # contagem do dia maximo dos dados (recalculada em build): cor "hot" e escala dos niveis


def cam(p):
    x, y, z = p[0] - CAM[0], p[1] - CAM[1], p[2] - CAM[2]
    return x * _ca + z * _sa, y, -x * _sa + z * _ca


def P(x, y, z):
    xc, yc, zc = cam((x, y, z))
    zc = max(zc, 0.05)
    return (CX + FOC * xc / zc, HZ - FOC * yc / zc)


def scale(x, z):
    return FOC / cam((x, 0, z))[2]


def pts(ps):
    return " ".join(f"{a:.1f},{b:.1f}" for a, b in ps)


def poly(ps3, fill, extra=""):
    return f'<polygon points="{pts([P(*p) for p in ps3])}" fill="{fill}"{extra}/>'


def fr(x0, y0, x1, y1, fill, extra="", z=ZF):
    return poly([(x0, y1, z), (x1, y1, z), (x1, y0, z), (x0, y0, z)], fill, extra)


def sx(x0, x1, y0, y1, z0, z1, fill, extra=""):
    """quad lateral (x constante = x0; z de z0 a z1)."""
    return poly([(x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0)], fill, extra)


def hz(x0, x1, y, z0, z1, fill, extra=""):
    return poly([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], fill, extra)


def dot(x, y, r, fill, extra="", z=ZF):
    sx_, sy_ = P(x, y, z)
    rr = r * scale(x, z)
    return f'<circle cx="{sx_:.1f}" cy="{sy_:.1f}" r="{max(rr, .4):.2f}" fill="{fill}"{extra}/>'


def ell(x, y, rx, ry, fill, extra="", z=ZF):
    sx_, sy_ = P(x, y, z)
    s = scale(x, z)
    return f'<ellipse cx="{sx_:.1f}" cy="{sy_:.1f}" rx="{rx * s:.1f}" ry="{ry * s:.1f}" fill="{fill}"{extra}/>'


def line3(p0, p1, col, wd, extra=""):
    a, b = P(*p0), P(*p1)
    return f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{col}" stroke-width="{wd}"{extra}/>'


def path3(ps3, col, wd, extra=""):
    q = [P(*p) for p in ps3]
    d = f"M{q[0][0]:.1f} {q[0][1]:.1f}" + "".join(f"L{a:.1f} {b:.1f}" for a, b in q[1:])
    return f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{wd}" stroke-linecap="round" stroke-linejoin="round"{extra}/>'


def affine(x, y, z):
    """matriz afim local do plano z=const em (x,y): 1 unidade = 1 m, y local para baixo."""
    o = P(x, y, z)
    ex = P(x + 0.01, y, z)
    ey = P(x, y - 0.01, z)
    return (f"matrix({(ex[0] - o[0]) * 100:.3f} {(ex[1] - o[1]) * 100:.4f} "
            f"{(ey[0] - o[0]) * 100:.4f} {(ey[1] - o[1]) * 100:.3f} {o[0]:.2f} {o[1]:.2f})")


def box(x0, x1, y0, y1, z0, z1, top, front, side, extra=""):
    o = []
    if CAM[0] > x1:
        o.append(sx(x1, x1, y0, y1, z0, z1, side, extra))
    elif CAM[0] < x0:
        o.append(sx(x0, x0, y0, y1, z0, z1, side, extra))
    if CAM[1] > y1:
        o.append(hz(x0, x1, y1, z0, z1, top, extra))
    o.append(fr(x0, y0, x1, y1, front, extra, z=z0))
    return "".join(o)


# ---------------- temas ----------------
T = {
    "dark": dict(
        wall0="#111926", wall1="#0b111a", joint="#070b12", endw="#0d1420", ceil="#080c13",
        beam_side="#0c121c", beam_bot="#0f1622", fl0="#0c1119", fl1="#05080d", fjoint="#141b27",
        frame="#07090d", frame_hi="#232c3b", post="#1c2330", side="#0c1017", inner="#040507",
        face0="#1d232e", face1="#12161d", bay="#0b0e14", bay_hi="#2c3442", blank="#0f1319",
        pwr="#4fc79a", act=["#b8763a", "#e39a4a", "#ffbb68", "#ffdca6"], hot="#fff6e6",
        glass="#9fb8e0", glass_op=0.06, wire="#2f3643", wire_hi="#4b5568",
        win0="#132646", win1="#2c4a7c", grass="#05080e", reveal="#121a27", sill="#18202d",
        outglow="#ffae5c", outglow_op=0.35,
        beam="#8fb0e8", beam_op=0.07, patch_op=0.13, dust_op=0.25,
        amb_led=1.0, bloom=1.0, halo=1.0, refl=0.62, ceilglow=0.55,
        cable=["#2a4a78", "#6f6030", "#35603c", "#6a343a", "#4a505b", "#2a2f38"],
        tray="#131a25", tray_hi="#202938", pipe="#141b26", pipe2="#111720", pipe_hi="#2a3445",
        box="#2c261e", box_top="#3a3227", box_side="#221d17", tape="#4a4034",
        cart="#1b212c", cart_top="#262e3b", cart_side="#151a23", steel="#3a4352",
        screen0="#dfe9ff", screen1="#9fb6e6", screen_glow=1.0, kb="#0d1117", mug="#c9c1b3", mug_dark="#8e877b",
        steam="#aab4c8", label="#d9d3c4", label_ink="#1b1d22", ups_lcd="#6fb6ff",
        door_in="#ffbe78", door_leaf="#101722", door_edge="#1a2230", door_step="#6b4a2a", door_op=0.45,
        pipe_warm=0.6, sky_op=0.0, patch="#9db8e6", shelf_sh=0.25, ao=0.55, device_w="#1d2430", ap_led="#9cc4ff", ap_glow=0.35,
        grade=None, rim="#6d8fcf", rim_op=0.35, vig=0.5, velcro="#22304a",
    ),
    "light": dict(
        wall0="#7f7a76", wall1="#67625f", joint="#57524f", endw="#6a6461", ceil="#524d4b",
        beam_side="#433f3d", beam_bot="#5c5754", fl0="#86807b", fl1="#4d4946", fjoint="#67615d",
        frame="#15171c", frame_hi="#4d525c", post="#2b2f37", side="#22252c", inner="#0c0d10",
        face0="#3a3f49", face1="#2a2e36", bay="#1b1e24", bay_hi="#505662", blank="#262a31",
        pwr="#48c291", act=["#c07a36", "#ea9a42", "#ffb85c", "#ffdca2"], hot="#fff8ea",
        glass="#ffe2b6", glass_op=0.09, wire="#7f8189", wire_hi="#e8dcc8",
        win0="#ffe6b8", win1="#fff6e2", grass="#5d6a3c", reveal="#b39c83", sill="#e2c49c",
        outglow="#fff0cc", outglow_op=0.0,
        beam="#ffcf85", beam_op=0.5, patch_op=0.85, dust_op=0.8,
        amb_led=0.4, bloom=0.36, halo=0.4, refl=0.4, ceilglow=0.0,
        cable=["#35649e", "#c79b3c", "#4f7f4a", "#9a4540", "#7c8089", "#2b2f36"],
        tray="#45403d", tray_hi="#66605b", pipe="#56504c", pipe2="#635c57", pipe_hi="#b3a598",
        box="#a07c52", box_top="#c29a6a", box_side="#86663f", tape="#d8c7a0",
        cart="#2c3038", cart_top="#40454f", cart_side="#23262d", steel="#8e9099",
        screen0="#f1f5ff", screen1="#c9d6ef", screen_glow=0.45, kb="#1a1d23", mug="#f1ebe0", mug_dark="#c9bfb0",
        steam="#ffffff", label="#f3eee2", label_ink="#1b1d22", ups_lcd="#8fd0ff",
        door_in="#ffe3b6", door_leaf="#7e7064", door_edge="#9a8a7a", door_step="#b08a60", door_op=0.12,
        pipe_warm=0.0, sky_op=0.0, patch="#ffd494", shelf_sh=0.28, ao=0.4, device_w="#e9e5de", ap_led="#9cc4ff", ap_glow=0.0,
        grade="#1d2230", rim="#ffc77a", rim_op=0.6, vig=0.3, velcro="#2a3850",
    ),
}


def layout():
    xs, x = [], -0.10
    for i, k in enumerate(KIND):
        if i in (6, 8):
            x += WGAP + (.07 if i == 8 else 0)
        xs.append(x)
        x += k[1] + GAP
    return xs


# ---------------- luzes de dia ----------------
def blink(rnd, c):
    dur = max(.45, 2.4 / (1 + math.log(max(c, 1))))
    return f' class="{rnd.choice(["b1", "b2", "b3"])}" style="--d:{dur:.2f}s;animation-delay:-{rnd.uniform(0, 3):.2f}s"'


def day_bar(G, Hs, t, rnd, xa, xb, yc, c, uh):
    if c <= 0:
        return
    L = lv(c, peak=PEAK)
    peak = c >= PEAK
    col = t["hot"] if peak else t["act"][L - 1]
    ln = (xb - xa) if peak else (xb - xa) * (.2 + .2 * L)
    G.append(fr(xa, yc - uh * .13, xa + ln, yc + uh * .13, col, f' opacity="{.8 + .05 * L:.2f}"'))
    hk = .5 + .5 * t.get("halo", 1)
    Hs.append(ell(xa + ln / 2, yc, (ln * .75 + .03) * hk, uh * (1.1 + .55 * L + (2 if peak else 0)) * hk, f"url(#h{4 if peak else L - 1})"))
    if not peak:
        G.append(dot(xb + .028, yc, .0036, t["act"][3], blink(rnd, c)))


def mini_light(G, Hs, t, rnd, x, y, c, w):
    if c <= 0:
        G.append(dot(x - w * .3, y, .0026, t["pwr"], ' opacity=".55"'))
        return
    L = lv(c, peak=PEAK)
    col = t["hot"] if c >= PEAK else t["act"][L - 1]
    G.append(fr(x - w * .4, y - .0045, x - w * .4 + w * (.22 + .15 * L), y + .0045, col))
    hk = .5 + .5 * t.get("halo", 1)
    Hs.append(ell(x - w * .2, y, w * .5 * hk, (.02 + .009 * L) * hk, f"url(#h{L - 1})"))
    G.append(dot(x + w * .36, y, .0036, t["act"][3], blink(rnd, c)))


def bay_light(G, Hs, t, rnd, x, y0, y1, c):
    if c <= 0:
        G.append(dot(x, y1 - .012, .0026, t["pwr"], ' opacity=".5"'))
        return
    L = lv(c, peak=PEAK)
    col = t["hot"] if c >= PEAK else t["act"][L - 1]
    hgt = (y1 - y0) * (.25 + .18 * L)
    G.append(fr(x - .005, y1 - .008 - hgt, x + .005, y1 - .008, col, ' opacity=".9"'))
    hk = .5 + .5 * t.get("halo", 1)
    Hs.append(ell(x, y1 - .008 - hgt / 2, .035 * hk, (hgt * .8 + .02) * hk, f"url(#h{L - 1})"))
    G.append(dot(x, y1 + .006, .0032, t["act"][3], blink(rnd, c)))


# ---------------- moveis ----------------
def rack(t, rnd, style, x0, wdt, top, recipe, md, paused, tot, R, G, Hs):
    x1 = x0 + wdt
    D = .8
    by = {d.day: c for d, c in md}
    nd = len(md)
    ix0, ix1 = x0 + .05, x1 - .05
    skeleton = style == "open" and paused
    if style == "glass":
        R.append(sx(x1, x1, 0, top, ZF, ZF + D, t["side"]))
        R.append(fr(x0, 0, x1, top, t["frame"]))
        R.append(fr(ix0, .1, ix1, top - .07, t["inner"]))
    else:
        # rack aberto: postes de tras e travessas laterais (veem-se pelas frestas / se vazio)
        for px in (x0 + .01, x1 - .045):
            R.append(fr(px, 0, px + .035, top, t["post"], z=ZF + .75))
        for yy in (.06, top - .05):
            R.append(poly([(x1 - .01, yy + .03, ZF), (x1 - .01, yy + .03, ZF + .75), (x1 - .01, yy, ZF + .75), (x1 - .01, yy, ZF)], t["post"]))
            R.append(poly([(x0 + .01, yy + .03, ZF), (x0 + .01, yy + .03, ZF + .75), (x0 + .01, yy, ZF + .75), (x0 + .01, yy, ZF)], t["post"]))
        # base e tampo
        R.append(hz(x0, x1, .1, ZF, ZF + .75, t["frame"]))
        if not skeleton:
            R.append(fr(ix0, .1, ix1, top - .07, t["inner"], ' opacity=".92"', z=ZF + .74))
    y = top - .09
    if not paused:
        # patch panel
        np_ = 24
        R.append(fr(ix0 + .015, y - UH, ix1 - .015, y, t["face1"]))
        pp = []
        for k in range(np_):
            px = ix0 + .045 + k * (ix1 - ix0 - .09) / np_
            R.append(fr(px, y - UH * .72, px + .011, y - UH * .3, t["inner"]))
            pp.append(px + .0055)
        ypp = y - UH * .5
        y -= UH
        # switch
        R.append(fr(ix0 + .015, y - UH, ix1 - .015, y, t["face0"]))
        for k in range(np_):
            px = ix0 + .045 + k * (ix1 - ix0 - .09) / np_
            R.append(fr(px, y - UH * .74, px + .011, y - UH * .3, t["inner"]))
            if rnd.random() < .45 + .5 * min(1, tot / 250):
                G.append(dot(px + .0055, y - UH * .18, .0024, t["pwr"] if rnd.random() < .6 else t["act"][2],
                             f' class="{rnd.choice(["b1", "b2", "b3"])}" style="--d:{.35 + rnd.random():.2f}s;animation-delay:-{rnd.random() * 2:.2f}s"'))
        ysw = y - UH * .5
        y -= UH
        # patch cables: laco curto do patch panel ao switch
        cabs = []
        for k in range(np_):
            if rnd.random() < .55 + .4 * min(1, tot / 250):
                col = rnd.choice(t["cable"])
                xa = pp[k]
                xb = pp[min(np_ - 1, max(0, k + rnd.choice([-1, 0, 0, 1])))]
                sag = .02 + rnd.random() * .03
                ps = []
                for i in range(9):
                    u = i / 8
                    xx = xa + (xb - xa) * u
                    yy = ypp + (ysw - ypp) * u - sag * math.sin(math.pi * u) * 1.0 - .012 * math.sin(math.pi * u)
                    ps.append((xx, yy, ZF - .02 - .03 * math.sin(math.pi * u)))
                cabs.append(path3(ps, col, max(.5, .006 * scale(xa, ZF)), ' opacity=".95"'))
        R.append("".join(cabs))
        y -= .01
    # dispositivos por dia
    ubot = .1 + 2 * UH + .02
    day, ri = 1, 0
    while day <= nd:
        tok = "1" if paused else recipe[ri % len(recipe)]
        ri += 1
        n, hU = {"1": (1, 1), "2": (2, 2), "4": (4, 2)}[tok]
        n = min(n, nd - day + 1)
        y0 = y - hU * UH
        cs = [by.get(k, 0) for k in range(day, day + n)]
        if paused and cs[0] == 0:
            y = y0
            day += n
            continue
        if tok in "12":
            # lateral do chassis (ve-se na fresta)
            R.append(sx(ix1 - .02, ix1 - .02, y0 + .002, y - .002, ZF, ZF + .68, t["side"]))
            R.append(fr(ix0 + .015, y0 + .0015, ix1 - .015, y - .0015, "url(#face)"))
            R.append(fr(ix0 + .015, y - .005, ix1 - .015, y - .0015, t["bay_hi"], ' opacity=".45"'))
            # orelhas
            for ex in (ix0 + .015, ix1 - .035):
                R.append(fr(ex, y0 + .003, ex + .02, y - .003, t["face1"]))
            for j, c in enumerate(cs):
                ry1 = y - j * UH
                ry0 = ry1 - UH
                nb = 4 if tok == "1" else 6
                bw = (ix1 - ix0 - .17) / nb
                for k in range(nb):
                    bx = ix0 + .1 + k * bw
                    R.append(fr(bx, ry0 + .008, bx + bw - .006, ry1 - .008, t["bay"]))
                    R.append(fr(bx + bw - .016, ry0 + .012, bx + bw - .010, ry1 - .012, t["bay_hi"], ' opacity=".6"'))
                day_bar(G, Hs, t, rnd, ix0 + .1, ix1 - .075, (ry0 + ry1) / 2, c, UH)
                G.append(dot(ix0 + .06, (ry0 + ry1) / 2, .0028, t["pwr"], ' opacity=".85"'))
        else:
            # prateleira de 4 mini PCs
            R.append(fr(ix0 + .015, y0, ix1 - .015, y0 + .007, t["frame_hi"], ' opacity=".8"'))
            mw = (ix1 - ix0 - .05) / 4
            for j, c in enumerate(cs):
                mx = ix0 + .025 + j * mw
                R.append(fr(mx + .007, y0 + .007, mx + mw - .007, y0 + .007 + UH * 1.35, "url(#face)"))
                R.append(fr(mx + .007, y0 + .007 + UH * 1.3, mx + mw - .007, y0 + .007 + UH * 1.35, t["bay_hi"], ' opacity=".6"'))
                mini_light(G, Hs, t, rnd, mx + mw / 2, y0 + .007 + UH * .65, c, mw)
        y = y0
        day += n
    # espaco livre: tampas cegas alternadas
    k = 0
    while y - UH > ubot and not paused:
        if k % 3 != 1:
            R.append(fr(ix0 + .015, y - UH + .002, ix1 - .015, y - .002, t["blank"]))
        y -= UH
        k += 1
    if not paused:
        # UPS
        R.append(fr(ix0 + .015, .1, ix1 - .015, ubot - .01, "url(#face)"))
        for k in range(10):
            vx = ix0 + .04 + k * .022
            R.append(fr(vx, .1 + UH * .35, vx + .012, .1 + UH * 1.6, t["bay"]))
        R.append(fr(ix1 - .16, .1 + UH * .75, ix1 - .07, .1 + UH * 1.3, t["ups_lcd"], ' opacity=".3"'))
        G.append(fr(ix1 - .16, .1 + UH * .75, ix1 - .07, .1 + UH * 1.3, t["ups_lcd"], ' opacity=".22"'))
        G.append(dot(ix1 - .045, .1 + UH, .003, t["pwr"]))
    # frente: postes / moldura
    if style == "glass":
        R.append(fr(x0, 0, x1, .1, t["frame"]))
        for k in range(7):
            vx = x0 + .07 + k * (wdt - .14) / 7
            R.append(fr(vx, .03, vx + .045, .07, t["inner"]))
        # porta de vidro
        R.append(fr(x0 + .02, .1, x1 - .02, top - .02, t["glass"], f' opacity="{t["glass_op"]}"'))
        R.append(poly([(x0 + .04, top - .08, ZF), (x0 + .2, top - .08, ZF), (x0 + .04, top - .62, ZF)], "#fff", ' opacity=".045"'))
        R.append(poly([(x0 + .28, top - .08, ZF), (x0 + .33, top - .08, ZF), (x0 + .04, top - .95, ZF), (x0 + .04, top - .78, ZF)], "#fff", ' opacity=".03"'))
        for (a0, a1, b0, b1) in ((x0, x0 + .025, .1, top), (x1 - .025, x1, .1, top), (x0, x1, top - .07, top), (x0, x1, .1, .12)):
            R.append(fr(a0, b0, a1, b1, t["frame"]))
        R.append(fr(x1 - .05, .95, x1 - .036, 1.25, t["frame_hi"]))
        # topo perfurado
        for k in range(12):
            vx = x0 + .06 + k * (wdt - .12) / 12
            R.append(fr(vx, top - .05, vx + .02, top - .035, t["inner"]))
    else:
        for (a0, a1) in ((x0, x0 + .045), (x1 - .045, x1)):
            R.append(fr(a0, 0, a1, top, t["post"]))
            R.append(fr(a0 + .03, .1, a0 + .036, top - .06, t["frame"]))
            for k in range(int((top - .2) / (UH * 1.0))):
                R.append(fr(a0 + .031, .12 + k * UH, a0 + .035, .12 + k * UH + .006, t["frame_hi"], ' opacity=".6"'))
        R.append(fr(x0, top - .05, x1, top, t["post"]))
        R.append(fr(x0, 0, x1, .1, t["post"]))
        R.append(fr(x0 + .045, .03, x1 - .045, .06, t["frame"]))
        if not paused:
            # cabos presos no poste esquerdo (organizador)
            ncab = 4
            for k in range(ncab):
                col = t["cable"][(k + int(x0 * 3)) % len(t["cable"])]
                cx_ = x0 + .008 + k * .008
                R.append(fr(cx_, .5 + k * .08, cx_ + .005, top - .12, col, ' opacity=".9"'))
            for yy in [.7 + k * .28 for k in range(5)]:
                if yy < top - .15:
                    R.append(fr(x0 + .004, yy, x0 + .044, yy + .016, t["velcro"]))
    # etiqueta em branco no topo (sem texto)
    if not paused:
        R.append(fr(x0 + .06, top - .045, x0 + .16, top - .02, t["label"], ' opacity=".85"'))


def wire_shelf(t, rnd, x0, wdt, top, recipe, md, paused, R, G, Hs):
    x1 = x0 + wdt
    Dp = .5
    by = {d.day: c for d, c in md}
    nd = len(md)
    for px in (x0 + .015, x1 - .015):
        R.append(poly([(px - .011, top, ZF + Dp), (px + .011, top, ZF + Dp), (px + .011, 0, ZF + Dp), (px - .011, 0, ZF + Dp)], t["wire"], ' opacity=".75"'))
    shelves = [0.1, 0.4, 0.7, 1.0, 1.28, top - .02]
    items, day, ri = [], 1, 0
    while day <= nd:
        tok = "m" if paused else recipe[ri % len(recipe)]
        ri += 1
        n = min(4 if tok == "t" else 1, nd - day + 1)
        items.append((tok, list(range(day, day + n))))
        day += n
    wt = {"t": .19, "m": .125}
    rows, cur, cw = [], [], 0
    for it in items:
        w_ = wt[it[0]] + .014
        if cw + w_ > wdt - .05 and cur:
            rows.append(cur)
            cur, cw = [], 0
        cur.append(it)
        cw += w_
    if cur:
        rows.append(cur)
    for sy in shelves:
        R.append(hz(x0, x1, sy, ZF, ZF + Dp, t["wire"], ' opacity=".3"'))
        for k in range(1, 9):
            zz = ZF + k * Dp / 9
            R.append(line3((x0, sy, zz), (x1, sy, zz), t["wire"], .5, ' opacity=".55"'))
        R.append(fr(x0, sy - .014, x1, sy + .008, t["wire"]))
        R.append(fr(x0, sy + .004, x1, sy + .008, t["wire_hi"], ' opacity=".7"'))
    placed = 0
    for si, row in enumerate(rows):
        sy = shelves[len(shelves) - 2 - si] + .008
        cx_ = x0 + .03
        for tok, dd in row:
            cs = [by.get(k, 0) for k in dd]
            if paused and cs[0] == 0:
                cx_ += wt[tok] + .014
                continue
            placed += 1
            if tok == "m":
                R.append(box(cx_, cx_ + .125, sy, sy + .048, ZF + .03, ZF + .16, t["bay_hi"], "url(#face)", t["side"]))
                R.append(fr(cx_, sy + .043, cx_ + .125, sy + .048, t["bay_hi"], ' opacity=".6"', z=ZF + .03))
                mini_light(G, Hs, t, rnd, cx_ + .0625, sy + .024, cs[0], .125)
            else:
                th = .25
                R.append(box(cx_, cx_ + .19, sy, sy + th, ZF + .02, ZF + .26, t["bay_hi"], "url(#face)", t["side"]))
                bw = .034
                for j, c in enumerate(cs):
                    bx = cx_ + .018 + j * (bw + .009)
                    R.append(fr(bx, sy + .035, bx + bw, sy + th - .045, t["bay"], z=ZF + .02))
                    bay_light(G, Hs, t, rnd, bx + bw / 2, sy + .035, sy + th - .045, c)
                G.append(dot(cx_ + .095, sy + th - .022, .004, t["pwr"]))
            cx_ += wt[tok] + .014
    if paused:
        # estante vazia: caixas de cartao e um rolo de cabo
        for (bx, bw_, bh, sy) in ((x0 + .06, .3, .2, shelves[0]), (x0 + .45, .22, .14, shelves[0]), (x0 + .5, .28, .16, shelves[2])):
            R.append(box(bx, bx + bw_, sy + .008, sy + .008 + bh, ZF + .05, ZF + .4, t["box_top"], t["box"], t["box_side"]))
            R.append(fr(bx + bw_ * .45, sy + .008 + bh - .03, bx + bw_ * .55, sy + .008 + bh, t["tape"], ' opacity=".8"', z=ZF + .05))
        cxx, cyy = x0 + .25, shelves[3] + .07
        for r_ in (.06, .05, .04):
            R.append(ell(cxx, cyy, r_, r_ * .9, "none", f' stroke="{t["cable"][5]}" stroke-width="1.2" opacity=".9"', z=ZF + .1))
    for px in (x0 + .015, x1 - .015):
        R.append(fr(px - .012, 0, px + .012, top, t["wire"]))
        R.append(fr(px - .004, 0, px + .003, top, t["wire_hi"], ' opacity=".65"'))



WIN_AZ = 180.0          # a janela olha para sul
STREET = (0.8, -0.9, -1.0)   # candeeiro da rua (direcao fixa, a do r6 escuro)


NIGHT = dict(T["dark"], grade="#1d2230", grade_op=0.0, grain=0.02,
             wall0="#0f1622", wall1="#090d15", joint="#05080d", endw="#0b111b", ceil="#05080c",
             beam_side="#080c13", beam_bot="#0b1019", fl0="#0a0e15", fl1="#030508", fjoint="#10151f",
             vig=0.55, ceilglow=0.5)
GOLD = dict(T["light"], grade_op=0.28, grain=0.035, grade="#2a1c30",
            wall0="#8a7c70", wall1="#6c615a", endw="#6e635c", fl0="#8e8078", fl1="#4e4642",
            rim="#ffc070", rim_op=0.7)
# sol baixo da manha: rosado e fresco (sombras frias)
ROSE = dict(GOLD, grade="#26304a", grade_op=0.22,
            wall0="#8a7f86", wall1="#6a6270", joint="#58515c", endw="#6d6573", ceil="#534d58",
            fl0="#8c8490", fl1="#4c4854", fjoint="#686270", beam_side="#443f4a", beam_bot="#5c5662",
            reveal="#b09aa0", sill="#e0c4c4", rim="#ffb4a8", rim_op=0.55, wire_hi="#ecd8dc",
            box="#9c7c62", box_top="#b8967a", box_side="#806350")
DAY = dict(GOLD,
           wall0="#7c7874", wall1="#63605c", joint="#56524f", endw="#6a6662", ceil="#504d4b",
           beam_side="#403d3b", beam_bot="#5a5653", fl0="#86817c", fl1="#4c4845", fjoint="#645f5a",
           frame_hi="#555a64", glass="#eef3ff", glass_op=0.08, wire="#83868e", wire_hi="#dfe2e7",
           reveal="#b8b2aa", sill="#dcd6ce", grass="#5f7040",
           amb_led=0.3, bloom=0.28, halo=0.3, refl=0.36, screen_glow=0.35,
           tray="#4c4744", tray_hi="#6c6661", pipe="#5b5551", pipe2="#68615c", pipe_hi="#b8b0a8",
           door_in="#fff0dc", door_leaf="#877a6e", door_edge="#a39486", door_step="#b39472", door_op=0.06,
           rim="#fff1dc", rim_op=0.25, grade="#1d2230", grade_op=0.12, vig=0.2, shelf_sh=0.24, ao=0.38, grain=0.03)
# hora azul da manha: fria, a clarear
BLUE = dict(NIGHT,
            wall0="#2a3650", wall1="#1b2436", joint="#131a28", endw="#202b42", ceil="#121824",
            beam_side="#172030", beam_bot="#1e2738", fl0="#233049", fl1="#0c1119", fjoint="#2b364b",
            frame_hi="#2c3647", post="#222b39", reveal="#2d364a", sill="#343f56", grass="#0e141f",
            glass="#b8c8ee", glass_op=0.07, wire="#3d4553", wire_hi="#617090",
            amb_led=0.9, bloom=0.85, halo=0.85, refl=0.55, ceilglow=0.3, pipe_warm=0.35,
            tray="#1b2331", tray_hi="#2a3446", pipe="#1d2532", pipe2="#19202b", pipe_hi="#37445e",
            box="#3c3530", box_top="#4c443a", box_side="#2f2924", cart="#232b37", cart_top="#2f3847",
            steel="#4c5667", device_w="#3c4454", door_op=0.3, screen_glow=0.85, ap_glow=0.2,
            outglow_op=0.1, rim="#9fb3e0", rim_op=0.3, vig=0.45, grade="#1d2230", grade_op=0.08, grain=0.025)
# anoitecer: violeta, a janela ainda quente, os LEDs a ganhar forca
DUSK = dict(BLUE,
            wall0="#2c2842", wall1="#1c1a2e", joint="#141222", endw="#231f36", ceil="#12101c",
            beam_side="#18152a", beam_bot="#1f1b32", fl0="#262238", fl1="#0c0b14", fjoint="#2c2840",
            frame_hi="#2e2a44", reveal="#3a3048", sill="#4a3a50", post="#241f33",
            wire="#3e3a52", wire_hi="#6e6090", tray="#1c1a2c", tray_hi="#2c2840", pipe="#1d1a2c", pipe2="#1a1728", pipe_hi="#3a3452",
            amb_led=1.05, bloom=1.05, refl=0.6, ceilglow=0.55, pipe_warm=0.55,
            outglow="#ff9a5c", outglow_op=0.3, rim="#e0a0c0", rim_op=0.3, vig=0.45, grade="#2a1830", grade_op=0.1)

PALS = {"N": NIGHT, "B": BLUE, "V": DUSK, "D": DAY, "G": GOLD, "R": ROSE}
# paleta de base (sem sol direto): noite -> crepusculo (T = azul de manha / violeta a tarde) -> dia
BASE_KF = [(-90, {"N": 1}), (-18, {"N": 1}), (-13, {"N": .6, "T": .4}), (-8, {"N": .3, "T": .7}),
           (-4, {"N": .1, "T": .9}), (0, {"T": .85, "D": .15}), (4, {"T": .6, "D": .4}), (10, {"T": .28, "D": .72}),
           (20, {"D": 1}), (90, {"D": 1})]

# ceu visto pela janela (baixo = junto a rua, cima)
SKY_AM = [(-90, ("#132646", "#1a3060")), (-16, ("#132646", "#1a3060")), (-12, ("#1c2c58", "#172a56")),
          (-8.5, ("#3c4478", "#1d2e5e")), (-5, ("#7a74a8", "#2d4278")), (-2, ("#d7a0b4", "#5a70aa")),
          (1, ("#ffc2b0", "#86a2d4")), (5, ("#ffe0c8", "#a6c2e8")), (12, ("#f3f1ea", "#a4c6ec")),
          (40, ("#e6eef8", "#8fbbe8")), (90, ("#e6eef8", "#8fbbe8"))]
SKY_PM = [(-90, ("#132646", "#1a3060")), (-18, ("#132646", "#1a3060")), (-14.5, ("#2a2a5e", "#162450")), (-11.5, ("#4a3070", "#1a2654")),
          (-8.5, ("#6a3c72", "#22285a")), (-5, ("#d0647a", "#3a3a78")), (-2, ("#ff8e5a", "#6a64a0")),
          (1, ("#ffae6a", "#8e9ccc")), (6, ("#ffd29a", "#abc0e0")), (15, ("#f4ecdc", "#a4c6ec")),
          (40, ("#e6eef8", "#8fbbe8")), (90, ("#e6eef8", "#8fbbe8"))]
# cor do sol direto (feixe, mancha) em funcao da elevacao: manha rosada, tarde dourada
SUN_AM = [(-2, ("#ff94a0", "#ffa8b0")), (2, ("#ffa4a4", "#ffb8ae")), (6, ("#ffc0a8", "#ffd0b8")),
          (12, ("#ffdcc0", "#ffe6cc")), (24, ("#fff0dc", "#fff4e4")), (45, ("#fffaf2", "#fffcf6"))]
SUN_PM = [(-2, ("#ff7440", "#ff8a58")), (2, ("#ff8e46", "#ffa060")), (6, ("#ffab58", "#ffbe70")),
          (14, ("#ffc676", "#ffd08c")), (26, ("#ffe0b0", "#ffe6bc")), (45, ("#fffaf2", "#fffcf6"))]


def bump(x, a, b, c, d):
    return ss(a, b, x) * (1 - ss(c, d, x))


def state(el, az):
    """tudo o que depende da hora (so da posicao do sol; continuo em elevacao e azimute)."""
    diff = (az - WIN_AZ + 540) % 360 - 180            # -180..180: - = sol a leste (manha), + = oeste (tarde)
    s = math.sin(math.radians(diff))                  # continuo tambem a meia-noite
    pmw = ss(-.3, .3, s)                              # 0 = manha, 1 = tarde
    w = dict(keyed(BASE_KF, el))
    tw = w.pop("T", 0)
    if tw:
        w["B"] = w.get("B", 0) + tw * (1 - pmw)
        w["V"] = w.get("V", 0) + tw * pmw
    # sol direto pela janela (exagerado de proposito: ao nascer e ao por do sol tambem entra, rasante)
    k_az = ss(135, 95, abs(diff))
    k_el = ss(-0.6, 2.2, el)
    sun_str = k_az * k_el
    # direcao "de cena" (estilizada): de manha o feixe corre rasante para a direita ao longo da fila,
    # a tarde desce para a esquerda e deita-se no chao a frente dos primeiros moveis
    d_geo = max(-42.0, -diff * .45) if diff > 0 else min(76.0, -diff * .88)
    nk = ss(28, 44, el)                               # sol alto: feixe curto e ingreme, a mancha fica colada as estantes
    e_geo = max(14.0, min(46.0 + 12.0 * nk, (15 + 9 * pmw) + .8 * max(el, 0) + 12.0 * nk))
    d_geo *= 1 - .6 * nk
    hh = math.cos(math.radians(e_geo))
    sun_dir = (math.sin(math.radians(d_geo)) * hh, -math.sin(math.radians(e_geo)), -math.cos(math.radians(d_geo)) * hh)
    low = ss(16, 2, el) * (1 - pmw) + ss(30, 5, el) * pmw
    gw = sun_str * low * .92
    wts = {k: v * (1 - gw) for k, v in w.items() if v > 0}
    wts["R"] = gw * (1 - pmw)
    wts["G"] = gw * pmw
    pals = [(PALS[k], v) for k, v in wts.items() if v > 1e-4]
    tot = sum(v for _, v in pals)
    t = blend([(p_, v / tot) for p_, v in pals])
    ska, skp = keyed(SKY_AM, el), keyed(SKY_PM, el)
    sky = tuple(lerpc(a_, b_, pmw) for a_, b_ in zip(ska, skp))
    sa, sp = keyed(SUN_AM, el), keyed(SUN_PM, el)
    beam_c, patch_c = lerpc(sa[0], sp[0], pmw), lerpc(sa[1], sp[1], pmw)
    return dict(
        t=t, el=el, az=az, pm=pmw > .5, pmw=pmw, sky=sky, skyb=ss(-10, 12, el), w=wts,
        stars=ss(-8, -15, el),
        street=ss(-3.5, -9, el),
        dawn=bump(el, -15, -9, -1, 4) * (1 - pmw),       # primeira luz fria a subir na parede
        rise=ss(-13, 0, el),
        dusk=bump(el, -18, -11, -1.5, 3) * pmw,             # anoitecer: janela laranja-violeta
        noon=ss(26, 44, el) * sun_str,                     # luz de ceu difusa e poeira
        day=ss(-2, 12, el),
        sun=dict(dir=sun_dir, str=sun_str, col=beam_c, pcol=patch_c, low=low),
    )


def sun_light(defs, st, segs, idp, shelf_sh):
    """sol direto: feixe riscado pelos pinazios, mancha no chao e poeira; assinatura por fase."""
    sun = st["sun"]
    k = sun["str"]
    low = sun.get("low", 0)
    noon = st.get("noon", 0)
    # meio-dia: feixe palido e difuso, mancha mais fraca, muita poeira em suspensao
    return light_through_window(defs, sun["dir"], sun["col"], sun["pcol"], (.5 + .06 * low + .28 * noon) * k, (.9 + .2 * low - .1 * noon) * k,
                                int(10 + 18 * k + 40 * noon), (.55 + .1 * noon) * k, "#fff6e6", shelf_sh, segs, idp + "sn", 12,
                                soft=noon, dust_r=.8 + .35 * noon)


def window_glow(st, WX0, WX1, WY0, WY1):
    """luz da janela na parede do fundo: ceu de dia, primeira luz fria (a subir), anoitecer quente-violeta.
    Elipses com gradiente radial (queda suave e curta, cerca de 1.2x a largura da janela para cada lado),
    recortadas no topo da parede."""
    cx, cy = (WX0 + WX1) / 2, (WY0 + WY1) / 2
    ww = WX1 - WX0
    o, gd = [], []
    day, dawn, dusk, rise = st.get("day", 0), st.get("dawn", 0), st.get("dusk", 0), st.get("rise", 0)
    sun = st["sun"]

    def glow(k, x, y, rx, ry, col, op):
        gd.append(f'<radialGradient id="wg{k}"><stop offset="0" stop-color="{col}" stop-opacity="{op:.3f}"/>'
                  f'<stop offset=".45" stop-color="{col}" stop-opacity="{op * .45:.3f}"/><stop offset="1" stop-color="{col}" stop-opacity="0"/></radialGradient>')
        o.append(ell(x, y, rx, ry, f"url(#wg{k})", "", z=ZB))
    if day > .01:
        c = lerpc(lerpc(st["sky"][0], "#ffffff", .3), sun["col"], min(1, sun["str"]) * .6)
        glow(0, cx, cy - .05, 1.2 * ww, .95, c, .42 * day + .12 * sun["str"])
    if dawn > .01:
        yc = WY1 - .25 + .3 * rise                     # clarao frio que sobe pela parede
        glow(1, cx, yc, 1.2 * ww, .55 + .2 * rise, "#8ea8ec", .55 * dawn)
        glow(2, cx, WY1 + .05, .75 * ww, .2, "#c4d2ff", .35 * dawn * rise)
    if dusk > .01:
        glow(3, cx, cy, 1.25 * ww, .95, "#8a5cc8", .5 * dusk)
        glow(4, cx, cy - .08, .8 * ww, .55, "#ff9a66", .42 * dusk)
    if not o:
        return ""
    top = CEIL - .01
    clip = pts([P(cx - 3 * ww, top, ZB), P(cx + 3 * ww, top, ZB), P(cx + 3 * ww, 0, ZB), P(cx - 3 * ww, 0, ZB)])
    return (f'<defs>{"".join(gd)}<clipPath id="wgc"><polygon points="{clip}"/></clipPath></defs>'
            f'<g clip-path="url(#wgc)">' + "".join(o) + '</g>')


# ---------------- geometria da luz ----------------
def clip_poly(poly_, inside, inter):
    out = []
    for i in range(len(poly_)):
        a, b = poly_[i - 1], poly_[i]
        ia, ib = inside(a), inside(b)
        if ib:
            if not ia:
                out.append(inter(a, b))
            out.append(b)
        elif ia:
            out.append(inter(a, b))
    return out


def clip_axis(poly_, idx, lim, keep_le):
    def inside(p):
        return p[idx] <= lim if keep_le else p[idx] >= lim

    def inter(a, b):
        u = (lim - a[idx]) / (b[idx] - a[idx])
        return tuple(a[i] + (b[i] - a[i]) * u for i in range(3))
    return clip_poly(poly_, inside, inter)


def hull2d(ps):
    ps = sorted(set((round(x, 1), round(y, 1)) for x, y in ps))
    if len(ps) < 3:
        return ps

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in ps:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(ps):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def light_through_window(defs, d, col, pcol, beam_op, patch_op, dust_n, dust_op, dust_col, shadow_op, segs, idp, seed, soft=0.0, dust_r=1.0):
    """feixe volumetrico + mancha no chao para uma luz de direcao d a entrar pela janela.
    Devolve (camada_chao, camada_feixe) como strings SVG."""
    dx, dy, dz = d
    WX0, WX1, WY0, WY1 = WIN
    s = 0.15 / -dz                                   # vao da parede (espessura efetiva)
    ax0, ax1 = max(WX0, WX0 + dx * s), min(WX1, WX1 + dx * s)
    ay0, ay1 = max(WY0, WY0 + dy * s), min(WY1, WY1 + dy * s)
    if ax1 - ax0 < .02 or ay1 - ay0 < .02 or beam_op <= 0.004:
        return "", ""
    frac = (ax1 - ax0) * (ay1 - ay0) / ((WX1 - WX0) * (WY1 - WY0))
    beam_op *= frac ** .5
    patch_op *= frac ** .5
    ap = [(ax0, ay0, ZB), (ax1, ay0, ZB), (ax1, ay1, ZB), (ax0, ay1, ZB)]

    def to_floor(p):
        k = p[1] / -dy
        return (p[0] + dx * k, 0.0, p[2] + dz * k)

    def end(p):
        f = to_floor(p)
        if f[2] > ZF - .02:               # bate atras da fila: para no plano das frentes
            k = (p[2] - (ZF - .02)) / -dz
            return (p[0] + dx * k, max(0.0, p[1] + dy * k), ZF - .02)
        if f[0] < XEND:                   # bate na parede do topo
            k = (p[0] - XEND) / -dx
            return (XEND, max(0.0, p[1] + dy * k), p[2] + dz * k)
        return f

    patch = [to_floor(p) for p in ap]
    patch = clip_axis(patch, 2, ZF - .02, True)
    patch = clip_axis(patch, 2, -6.0, False)
    patch = clip_axis(patch, 0, XEND, False)
    ends = [end(p) for p in ap]
    floor_l, beam_l = [], []
    if len(patch) >= 3:
        pp = pts([P(*p) for p in patch])
        defs.append(f'<clipPath id="{idp}pc"><polygon points="{pp}"/></clipPath>')
        floor_l.append(f'<polygon points="{pp}" fill="{col}" opacity="{patch_op * .5:.3f}" filter="url(#bl3)"/>')
        floor_l.append(f'<polygon points="{pp}" fill="{pcol}" opacity="{patch_op:.3f}" filter="url(#bl1)" style="mix-blend-mode:screen"/>')
        # sombra dos pinazios
        for k in range(1, NP):
            xm = WX0 + k * (WX1 - WX0) / NP
            if ax0 < xm < ax1:
                floor_l.append(line3(to_floor((xm, ay0, ZB)), to_floor((xm, ay1, ZB)), "#000", 3.5, f' opacity="{.35 * min(1, patch_op * 1.5):.2f}" filter="url(#bl1)"'))
        # sombras dos moveis dentro da mancha
        shp = []
        for q0, q1, wd in segs:
            f0, f1 = to_floor(q0), to_floor(q1)
            shp.append(line3(f0, f1, "#000", max(1.2, wd * scale(f0[0], min(f0[2], -.2)))))
        floor_l.append(f'<g clip-path="url(#{idp}pc)" opacity="{shadow_op * min(1, patch_op * 1.4):.2f}" filter="url(#bl1)">' + "".join(shp) + '</g>')
    # feixe: um veu largo (volume) + um raio por vidro (os pinazios riscam a luz)
    top_c = P((ax0 + ax1) / 2, ay1, ZB)
    ec = [sum(e[i] for e in ends) / 4 for i in range(3)]
    bot_c = P(*ec)
    defs.append(f'<linearGradient id="{idp}bg" gradientUnits="userSpaceOnUse" x1="{top_c[0]:.0f}" y1="{top_c[1]:.0f}" x2="{bot_c[0]:.0f}" y2="{bot_c[1]:.0f}">'
                f'<stop offset="0" stop-color="{col}" stop-opacity="{beam_op:.3f}"/><stop offset=".35" stop-color="{col}" stop-opacity="{beam_op * .66:.3f}"/>'
                f'<stop offset=".75" stop-color="{col}" stop-opacity="{beam_op * .2:.3f}"/><stop offset="1" stop-color="{col}" stop-opacity="0"/></linearGradient>')
    hull = hull2d([P(*p) for p in ap + ends])
    shafts = []
    pw = (WX1 - WX0) / NP
    for k in range(NP):
        q0, q1 = max(ax0, WX0 + k * pw + .02), min(ax1, WX0 + (k + 1) * pw - .02)
        if q1 - q0 < .02:
            continue
        a4 = [(q0, ay0 + .02, ZB), (q1, ay0 + .02, ZB), (q1, ay1 - .03, ZB), (q0, ay1 - .03, ZB)]
        shafts.append(f'<polygon points="{pts(hull2d([P(*p) for p in a4 + [end(p) for p in a4]]))}"/>')
    haze = .3 + .5 * soft
    beam_l.append(f'<g style="mix-blend-mode:screen"><polygon points="{pts(hull)}" fill="url(#{idp}bg)" opacity="{haze:.2f}" filter="url(#bl3)"/>'
                  f'<g fill="url(#{idp}bg)" opacity="{.85 * (1 - .55 * soft):.2f}" filter="url(#{"bl2" if soft > .5 else "bl1"})">{"".join(shafts)}</g></g>')
    rd = random.Random(seed)
    dust = []
    for k in range(dust_n):
        u, v, w_ = rd.random(), rd.random(), rd.random() * .9 + .05
        p0 = (ax0 + u * (ax1 - ax0), ay0 + v * (ay1 - ay0), ZB)
        p1 = end(p0)
        p = P(*[p0[i] + (p1[i] - p0[i]) * w_ for i in range(3)])
        r_ = (.5 + rd.random() * .9) * dust_r
        dust.append(f'<circle class="dust" style="--d:{6 + rd.random() * 8:.1f}s;--dx:{rd.uniform(-6, 6):.1f}px;--dy:{rd.uniform(-5, 7):.1f}px;animation-delay:-{rd.random() * 8:.1f}s" '
                    f'cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{r_:.2f}" fill="{dust_col}" opacity="{dust_op * (.4 + .6 * rd.random()):.2f}"/>')
    beam_l.append('<g>' + "".join(dust) + '</g>')
    return "".join(floor_l), "".join(beam_l)


def shadow_segs(xs):
    segs = []
    for mi, (style, wdt, top, _) in enumerate(KIND):
        x0 = xs[mi]
        x1 = x0 + wdt
        if style == "wire":
            for px in (x0 + .015, x1 - .015):
                for pz in (ZF + .02, ZF + .5):
                    segs.append(((px, 0, pz), (px, top, pz), .025))
            for sy in (0.4, 0.7, 1.0, 1.28, top - .02):
                for pz in (ZF, ZF + .5):
                    segs.append(((x0, sy, pz), (x1, sy, pz), .02))
        else:
            for px in (x0 + .02, x1 - .02):
                for pz in (ZF, ZF + .75):
                    segs.append(((px, 0, pz), (px, top, pz), .045))
            segs.append(((x0, top - .03, ZF), (x1, top - .03, ZF), .05))
    return segs


# ---------------- easter eggs ----------------
# eventos raros no loop: (periodo s, primeira vez aos s, fator de velocidade)
RARE = dict(robot=(97.0, 11.0, 1.0), snake=(71.0, 26.0, 1.0), reboot=(113.0, 47.0, 1.0))
# no timelapse (loop de 40 s = 24 h): cada evento uma vez por volta, a horas diferentes
RARE_TL = dict(robot=(48.0, 2.6, .7), snake=(48.0, 25.8, .9), reboot=(48.0, 39.0, .9))
RB = 8                 # movel que "reinicia" (rack aberto; em build passa para o rack aberto ativo mais perto deste)
CAT = 11               # o gato dorme em cima do armario do mes corrente (o mais perto)
GH_DARK = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
GH_LIGHT = ["#dfe5ee", "#9be9a8", "#40c463", "#30a14e", "#216e39"]


def egg_cfg(days, local_dt, tl=False):
    """o que acontece nesta imagem: etiquetas de data, fase da lua, 'commitou hoje', tempos dos raros."""
    last_d, last_c = days[-1]
    return dict(
        ev=set() if tl else events(local_dt, days),
        moon=moon_phase(to_utc(local_dt)),
        today=(last_d == local_dt.date() and last_c > 0),
        last7=[c for _, c in days[-7:]],
        weeks40=[sum(c for _, c in days[max(0, len(days) - 7 * (i + 1)):len(days) - 7 * i]) for i in range(39, -1, -1)],
        rare=RARE_TL if tl else RARE,
        tl=tl,
        show=None,          # depuracao: nome de um evento raro a mostrar parado a meio
        dt=local_dt,
    )


def _pc(t, period):
    return f"{max(0.0, min(100.0, 100.0 * t / period)):.3f}%"


def _anim(name, period, start):
    return f"animation:{name} {period:.1f}s linear {start:.2f}s infinite"


def moon_svg(eg, st):
    """lua com a fase real, no canto direito da janela (so quando ha estrelas)."""
    ph = eg["moon"]
    vis = st["stars"]
    lit = (1 - math.cos(2 * math.pi * ph)) / 2
    if vis < .05 or lit < .03:
        return ""
    z = ZB + WD
    mx, my = WIN[1] - .32, WIN[3] - .17
    cx, cy = P(mx, my, z)
    r = .052 * scale(mx, z)
    k = abs(math.cos(2 * math.pi * ph)) * r
    waxing = ph < .5
    s_out = 1 if waxing else 0            # meia circunferencia do lado iluminado
    gib = lit > .5
    s_in = (1 if gib else 0) if waxing else (0 if gib else 1)
    d = (f"M{cx:.2f} {cy - r:.2f} A{r:.2f} {r:.2f} 0 0 {s_out} {cx:.2f} {cy + r:.2f} "
         f"A{k:.2f} {r:.2f} 0 0 {s_in} {cx:.2f} {cy - r:.2f}Z")
    return (f'<g opacity="{vis:.2f}"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r * 3.2:.1f}" fill="#dfe6ff" opacity=".10" filter="url(#bl2)"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.2f}" fill="#2a3656" opacity=".55"/>'
            f'<path d="{d}" fill="#eef1f8"/></g>')


def fireworks_svg(t):
    """ano novo: fogo de artificio pela janela alta (recortado pelo vidro)."""
    z = ZB + WD
    WX0, WX1, WY0, WY1 = WIN
    clip = pts([P(WX0, WY1, z), P(WX1, WY1, z), P(WX1, WY0 + .06, z), P(WX0, WY0 + .06, z)])
    o = [f'<clipPath id="fwc"><polygon points="{clip}"/></clipPath><g clip-path="url(#fwc)">']
    rb = random.Random(31)
    bursts = [(WX0 + .45, WY1 - .15, "#ffd08a", -.5), (WX0 + 1.15, WY1 - .1, "#f4f1ea", -1.6), (WX1 - .45, WY1 - .2, "#ff9a86", -2.5),
              (WX0 + .8, WY1 - .26, "#bfe3ff", -3.1), (WX1 - .95, WY1 - .12, "#ffe6b0", -2.0)]
    for bx, by, col, dl in bursts:
        cx, cy = P(bx, by, z)
        rr = .22 * scale(bx, z)
        dots = []
        for j in range(18):
            a_ = 2 * math.pi * j / 18 + rb.random() * .2
            q = rr * (.8 + .25 * rb.random())
            dots.append(f'<circle cx="{cx + q * math.cos(a_):.1f}" cy="{cy + q * math.sin(a_) * .9:.1f}" r="{1.1 + rb.random() * .6:.2f}"/>')
            dots.append(f'<circle cx="{cx + q * .55 * math.cos(a_ + .2):.1f}" cy="{cy + q * .55 * math.sin(a_ + .2) * .9:.1f}" r=".6"/>')
        hide = "" if dl > -2 else ' opacity="0"'      # sem CSS so ficam 2 rebentamentos
        o.append(f'<g class="fw" style="animation-delay:{dl:.1f}s" fill="{col}"{hide}>'
                 f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rr * 1.1:.1f}" opacity=".18" filter="url(#bl2)"/>' + "".join(dots) + '</g>')
    o.append('</g>')
    # clarao na parede a volta da janela
    o.append(ell((WX0 + WX1) / 2, (WY0 + WY1) / 2, 1.3, .55, "#ffcf9a", ' class="fwg" opacity=".12" filter="url(#bl3)"', z=ZB))
    return "".join(o)


def natal_svg(t, xs, TX0, XLAST, TY):
    """natal: um fio de luzes quentes discretas pendurado na calha de cabos."""
    hang = [TX0] + [x + .02 for x in xs[5::2]] + [XLAST]
    hang = sorted(set(round(h, 3) for h in hang if TX0 <= h <= XLAST))
    wire, bulbs = [], []
    rb = random.Random(12)
    for a_, b_ in zip(hang, hang[1:]):
        seg = []
        n = max(3, int((b_ - a_) / .09))
        for i in range(n + 1):
            u = i / n
            x = a_ + (b_ - a_) * u
            y = TY - .015 - .09 * math.sin(math.pi * u)
            seg.append((x, y, .045))
            if 0 < i < n or (i == 0 and a_ == hang[0]):
                c = rb.choice(["#ffd9a0", "#ffe6c0", "#ffc98a"])
                bulbs.append(dot(x, y - .012, .011, c, f' class="tw" style="--d:{1.6 + rb.random() * 2.4:.1f}s;animation-delay:-{rb.random() * 3:.1f}s"', z=.045))
        wire.append(path3(seg, t["frame"], .8, ' opacity=".9"'))
    b = "".join(bulbs)
    return "".join(wire) + f'<g filter="url(#bl2)" opacity=".9">{b}</g><g>{b}</g>'


def pumpkin_svg(t, ax, night):
    """halloween: abobora esculpida em cima das caixas, com vela la dentro."""
    x, y, z = ax + .22, .46, -.26
    cx, cy = P(x, y, z)
    s = scale(x, z)
    rx, ry = .1 * s, .075 * s
    body = lerpc("#b8561a", t["box"], .35)
    dark = lerpc("#6e2c0c", t["box_side"], .3)
    o = [f'<ellipse cx="{cx:.1f}" cy="{cy - ry * .95:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{dark}"/>']
    for dx, w_ in ((-.55, .5), (.55, .5), (0, .62)):
        o.append(f'<ellipse cx="{cx + dx * rx:.1f}" cy="{cy - ry * .95:.1f}" rx="{rx * w_:.1f}" ry="{ry * .97:.1f}" fill="{body}" stroke="{dark}" stroke-width=".5" stroke-opacity=".6"/>')
    o.append(f'<path d="M{cx:.1f} {cy - ry * 1.85:.1f} q{rx * .05:.1f} {-ry * .35:.1f} {rx * .22:.1f} {-ry * .42:.1f}" stroke="#4a4a26" stroke-width="{max(1.2, .1 * rx):.1f}" fill="none" stroke-linecap="round"/>')
    fc = "#ffb04a" if night else "#3a1a08"
    ey = cy - ry * 1.15
    face = (f'<path d="M{cx - rx * .42:.1f} {ey:.1f} l{rx * .16:.1f} {-ry * .3:.1f} l{rx * .16:.1f} {ry * .3:.1f}Z'
            f'M{cx + rx * .1:.1f} {ey:.1f} l{rx * .16:.1f} {-ry * .3:.1f} l{rx * .16:.1f} {ry * .3:.1f}Z'
            f'M{cx - rx * .38:.1f} {cy - ry * .72:.1f} h{rx * .76:.1f} l{-rx * .1:.1f} {ry * .14:.1f} h{-rx * .56:.1f}Z" fill="{fc}"/>')
    o.append(face)
    if night:
        o.append(f'<ellipse class="flk" cx="{cx:.1f}" cy="{cy - ry:.1f}" rx="{rx * 2.4:.1f}" ry="{ry * 2.2:.1f}" fill="#ff9a3c" opacity=".22" filter="url(#bl3)"/>')
    return "".join(o)


def cupcake_svg(t, x, y, z):
    """aniversario da conta (24/10): um queque com uma vela (1 ano) no carrinho."""
    cx, cy = P(x, y, z)
    s = scale(x, z)
    w_, h_ = .03 * s, .03 * s
    o = [f'<path d="M{cx - w_:.1f} {cy - h_:.1f} L{cx + w_:.1f} {cy - h_:.1f} L{cx + w_ * .75:.1f} {cy:.1f} L{cx - w_ * .75:.1f} {cy:.1f}Z" fill="#c9a24e"/>']
    for k in range(-2, 3):
        o.append(f'<line x1="{cx + k * w_ * .35:.1f}" y1="{cy - h_:.1f}" x2="{cx + k * w_ * .27:.1f}" y2="{cy:.1f}" stroke="#9a7a34" stroke-width=".5"/>')
    o.append(f'<ellipse cx="{cx:.1f}" cy="{cy - h_:.1f}" rx="{w_ * 1.1:.1f}" ry="{h_ * .55:.1f}" fill="#f0e6dc"/>')
    o.append(f'<ellipse cx="{cx - w_ * .2:.1f}" cy="{cy - h_ * 1.35:.1f}" rx="{w_ * .7:.1f}" ry="{h_ * .35:.1f}" fill="#f7efe7"/>')
    o.append(f'<rect x="{cx - .7:.1f}" y="{cy - h_ * 2.6:.1f}" width="1.4" height="{h_ * 1.1:.1f}" fill="#8fb6e8"/>')
    fy = cy - h_ * 2.75
    o.append(f'<ellipse cx="{cx:.1f}" cy="{fy:.1f}" rx="{w_ * 1.8:.1f}" ry="{w_ * 1.8:.1f}" fill="#ffb760" opacity=".35" filter="url(#bl2)" class="flk"/>')
    o.append(f'<path class="flm" d="M{cx:.1f} {fy - 3.2:.1f} q1.4 2.2 0 3.4 q-1.4 -1.2 0 -3.4Z" fill="#ffd27a"/>')
    return "".join(o)


def postit_svg(x0):
    """sexta a partir das 17h: post-it vermelho colado no vidro do armario mais perto (sem texto)."""
    cx, cy, z = x0 + .15, 1.36, ZF - .004
    a_ = math.radians(-6)
    q = []
    for dx, dy in ((-.04, .04), (.04, .04), (.04, -.04), (-.04, -.04)):
        q.append((cx + dx * math.cos(a_) - dy * math.sin(a_), cy + dx * math.sin(a_) + dy * math.cos(a_), z))
    sh = [(p[0] + .006, p[1] - .008, z + .001) for p in q]
    curl = [q[2], (q[2][0] - .018, q[2][1], z), (q[2][0], q[2][1] + .018, z)]
    return (poly(sh, "#000", ' opacity=".35"') + poly(q, "#e0483e")
            + poly([q[0], q[1], (q[1][0], q[1][1] - .012, z), (q[0][0], q[0][1] - .012, z)], "#b8342c", ' opacity=".6"')
            + poly(curl, "#f07a70"))


def cat_svg(t, x0, top, night):
    """madrugada: um gato a dormir enrolado em cima do armario quente (silhueta, respira)."""
    x, y, z = x0 + .1, top, ZF + .12
    m = affine(x, y, z)
    fur = mixc([(t["frame"], .75), (t["box_side"], .25)])
    rim = t["act"][2] if night else t["wire_hi"]
    body = ("M0 0 C0 -.07 .05 -.135 .15 -.145 C.25 -.15 .31 -.115 .33 -.08 "
            "C.35 -.1 .37 -.12 .372 -.15 L.388 -.118 C.405 -.12 .418 -.118 .43 -.114 L.447 -.148 "
            "C.458 -.115 .462 -.08 .45 -.05 C.44 -.02 .41 -.005 .38 0 Z")
    back = "M0 0 C0 -.07 .05 -.135 .15 -.145 C.25 -.15 .31 -.115 .33 -.08 C.35 -.1 .37 -.12 .372 -.15"
    tail = "M.02 -.012 C.08 .004 .2 .006 .3 -.004 C.34 -.008 .37 -.004 .385 .002"
    return (f'<g transform="{m}">'
            f'<ellipse cx=".22" cy="0" rx=".24" ry=".02" fill="#000" opacity=".4"/>'
            f'<clipPath id="catc"><path d="{body}"/></clipPath>'
            f'<g class="brth"><path d="{body}" fill="{fur}"/>'
            f'<path d="{back}" clip-path="url(#catc)" fill="none" stroke="{rim}" stroke-width=".012" opacity="{.5 if night else .3}"/></g>'
            f'<path d="{tail}" fill="none" stroke="{fur}" stroke-width=".03" stroke-linecap="round"/>'
            f'<path d="M.395 -.07 q.012 .006 .024 0" stroke="{rim}" stroke-width=".004" fill="none" opacity=".5"/>'
            '</g>')


def robot_svg(t, cps, eg):
    """evento raro: um aspirador robot atravessa a sala, prende-se no cabo do portatil, desiste e vai-se embora."""
    period, start, k = eg["rare"]["robot"]
    zr = -.6
    xc = None
    for (xa, _, za), (xb, _, zb) in zip(cps, cps[1:]):
        if (za - zr) * (zb - zr) <= 0 and za != zb:
            xc = xa + (xb - xa) * (zr - za) / (zb - za)
    xc = (xc or 8.9) - .2
    # saida: volta para tras pelo mesmo corredor (entre as caixas e a cadeira) e some-se a esquerda
    zo = zr
    xo = -.45
    keys = []          # (t, x, z, dir)
    T = 0.0
    n = 16
    for i in range(n + 1):
        u = i / n
        keys.append((T + 7.0 * k * u, -.45 + (xc + .45) * u, zr, 1))
    T += 7.0 * k
    keys += [(T + .45 * k, xc, zr, 1), (T + .75 * k, xc + .02, zr, 1), (T + 1.1 * k, xc - .22, zr, 1),
             (T + 1.7 * k, xc - .22, zr, 1), (T + 2.3 * k, xc - .22, zr, -1)]
    T += 2.3 * k
    xs0 = xc - .22
    for i in range(1, n + 1):
        u = i / n
        keys.append((T + 7.0 * k * u, xs0 + (xo - xs0) * u, zr + (zo - zr) * u, -1))
    T += 7.0 * k
    tr = []
    for tt, x, z, dr in keys:
        sx_, sy_ = P(x, 0, z)
        s = scale(x, z)
        tr.append(f"{_pc(tt, period)}{{transform:translate({sx_:.1f}px,{sy_:.1f}px) scale({dr * s:.1f},{s:.1f})}}")
    tr.append(f"100%{{transform:translate({P(xo, 0, zo)[0]:.1f}px,{P(xo, 0, zo)[1]:.1f}px) scale({-scale(xo, zo):.1f},{scale(xo, zo):.1f})}}")
    op = f"0%{{opacity:0}}{_pc(.4 * k, period)}{{opacity:1}}{_pc(T - .1, period)}{{opacity:1}}{_pc(T, period)}{{opacity:0}}100%{{opacity:0}}"
    css = f"@keyframes robm{{{''.join(tr)}}}@keyframes robo{{{op}}}.robm{{{_anim('robm', period, start)}}}.robo{{{_anim('robo', period, start)}}}"
    r, h, ry = .17, .085, .17 * .3
    top, side = t["cart_top"], t["cart_side"]
    body = (f'<ellipse cx="0" cy="0" rx=".2" ry=".065" fill="#000" opacity=".4"/>'
            f'<path d="M{-r} 0 A{r} {ry} 0 0 0 {r} 0 L{r} {-h} A{r} {ry} 0 0 1 {-r} {-h}Z" fill="{side}"/>'
            f'<path d="M{-r} {-h * .45} A{r} {ry} 0 0 0 {r} {-h * .45}" fill="none" stroke="{t["frame_hi"]}" stroke-width=".008" opacity=".8"/>'
            f'<ellipse cx="0" cy="{-h}" rx="{r}" ry="{ry}" fill="{top}"/>'
            f'<ellipse cx="-.02" cy="{-h - .004}" rx="{r * .8}" ry="{ry * .72}" fill="none" stroke="{t["steel"]}" stroke-width=".005" opacity=".5"/>'
            f'<path d="M-.03 {-h} v-.022 a.04 .012 0 0 1 .08 0 v.022 a.04 .012 0 0 1 -.08 0Z" fill="{t["frame"]}"/>'
            f'<ellipse cx=".01" cy="{-h - .022}" rx=".04" ry=".012" fill="{t["frame_hi"]}"/>'
            f'<circle cx=".11" cy="{-h - .003}" r=".045" fill="#6fe3c4" opacity=".45" filter="url(#bl1)"/>'
            f'<circle cx=".11" cy="{-h - .003}" r=".013" fill="#b4fbe8"/>')
    if eg["show"] == "robot":
        _, x, z, dr = keys[len(keys) // 3]
        sx_, sy_ = P(x, 0, z)
        return f'<g transform="translate({sx_:.1f},{sy_:.1f}) scale({dr * scale(x, z):.1f},{scale(x, z):.1f})">{body}</g>', ""
    return f'<g class="robo" opacity="0"><g class="robm">{body}</g></g>', css


def screen_matrix(lx0, lx1, cy, lz1):
    o = P(lx0 + .012, cy + .258, lz1 + .066)
    ex = P(lx1 - .012, cy + .258, lz1 + .066)
    ey = P(lx0 + .012, cy + .062, lz1 + .004)
    return f"matrix({ex[0] - o[0]:.3f} {ex[1] - o[1]:.3f} {ey[0] - o[0]:.3f} {ey[1] - o[1]:.3f} {o[0]:.2f} {o[1]:.2f})"


def snake_svg(eg, M):
    """evento raro: o portatil mostra por instantes a grelha das ultimas 40 semanas e uma cobra a come-la."""
    period, start, k = eg["rare"]["snake"]
    cols, rows = 10, 4
    x0, y0, px, py = .07, .12, .086, .2
    cw, ch = px * .74, py * .7
    cells = []
    for i, c in enumerate(eg["weeks40"][-cols * rows:]):
        r_, c_ = divmod(i, cols)
        cells.append(f'<rect x="{x0 + c_ * px:.3f}" y="{y0 + r_ * py:.3f}" width="{cw:.3f}" height="{ch:.3f}" fill="{GH_DARK[lv(c, peak=max(250, max(eg["weeks40"])))]}"/>')
    step = .24 * k
    t0 = .5 * k
    # cabeca: linha 1 da esquerda para a direita, desce, linha 2 da direita para a esquerda
    path = [(c_, 1) for c_ in range(-1, cols)] + [(c_, 2) for c_ in range(cols - 1, -2, -1)]
    tend = t0 + step * (len(path) + 3)
    css = [f"@keyframes snko{{0%{{opacity:0}}{_pc(t0 - .15, period)}{{opacity:0}}{_pc(t0, period)}{{opacity:1}}"
           f"{_pc(tend, period)}{{opacity:1}}{_pc(tend + .2, period)}{{opacity:0}}100%{{opacity:0}}}}"
           f".snko{{{_anim('snko', period, start)}}}"]
    segs = []
    for j in range(4):
        kf = []
        for i, (c_, r_) in enumerate(path):
            kf.append(f"{_pc(t0 + step * (i + j), period)}{{transform:translate({x0 + c_ * px:.3f}px,{y0 + r_ * py:.3f}px)}}")
        c_, r_ = path[0]
        kf.insert(0, f"0%{{transform:translate({x0 + c_ * px:.3f}px,{y0 + r_ * py:.3f}px)}}")
        css.append(f"@keyframes snk{j}{{{''.join(kf)}}}.snk{j}{{animation:snk{j} {period:.1f}s steps(1,end) {start:.2f}s infinite}}")
        col = "#e6edf3" if j == 0 else "#aab4c0"
        segs.append(f'<rect class="snk{j}" x="0" y="0" width="{cw:.3f}" height="{ch:.3f}" fill="{col}" opacity="{1 - .18 * j:.2f}"/>')
    # o que ja foi comido fica apagado
    covers = []
    for ri, (rr, org, i0) in enumerate(((1, "0 0", 1), (2, "100% 0", cols + 1))):
        kf = (f"0%{{transform:scaleX(0)}}{_pc(t0 + step * i0, period)}{{transform:scaleX(0)}}{_pc(t0 + step * (i0 + cols), period)}{{transform:scaleX(1)}}"
              f"{_pc(tend + .2, period)}{{transform:scaleX(1)}}{_pc(tend + .3, period)}{{transform:scaleX(0)}}100%{{transform:scaleX(0)}}")
        css.append(f"@keyframes snc{ri}{{{kf}}}.snc{ri}{{animation:snc{ri} {period:.1f}s steps({cols},end) {start:.2f}s infinite;transform-box:fill-box;transform-origin:{org}}}")
        covers.append(f'<rect class="snc{ri}" x="{x0 - .01:.3f}" y="{y0 + rr * py - .01:.3f}" width="{cols * px:.3f}" height="{ch + .02:.3f}" fill="#0d1117" transform="scale(0 1)"/>')
    body = '<rect x="0" y="0" width="1" height="1" fill="#0d1117"/>' + "".join(cells) + "".join(covers) + "".join(segs)
    if eg["show"] == "snake":
        return f'<g transform="{M}">{body}</g>', ""
    return f'<g transform="{M}"><g class="snko" opacity="0">{body}</g></g>', "".join(css)


def today_svg(eg, M):
    """dados: se ha commits hoje, o portatil mostra a semana em verde no canto."""
    o = []
    for i, c in enumerate(eg["last7"]):
        o.append(f'<rect x="{.56 + i * .055:.3f}" y=".8" width=".044" height=".11" fill="{GH_LIGHT[lv(c, peak=PEAK)]}"/>')
    return f'<g transform="{M}">' + "".join(o) + '</g>'


def reboot_parts(eg, x0, wdt, top):
    """evento raro: um LED vermelho, o movel apaga-se e volta a acender em cascata (alguem reiniciou)."""
    period, start, k = eg["rare"]["reboot"]
    a_ = P(x0 - .08, top + .1, ZF)
    b_ = P(x0 + wdt + .08, -.02, ZF)
    t_red, t_off, t_on, t_end = .2, 1.9 * k, 3.6 * k, 5.2 * k
    css = (f"@keyframes rbr{{0%{{transform:scaleY(1)}}{_pc(t_off, period)}{{transform:scaleY(1)}}{_pc(t_off + .02, period)}{{transform:scaleY(0)}}"
           f"{_pc(t_on, period)}{{transform:scaleY(0);animation-timing-function:steps(8,end)}}{_pc(t_end, period)}{{transform:scaleY(1)}}100%{{transform:scaleY(1)}}}}"
           f".rbr{{{_anim('rbr', period, start)};transform-box:fill-box;transform-origin:50% 0}}"
           f"@keyframes rbl{{0%{{opacity:0}}{_pc(t_red, period)}{{opacity:1}}{_pc(t_on, period)}{{opacity:1}}{_pc(t_on + .05, period)}{{opacity:0}}100%{{opacity:0}}}}"
           f".rbl{{{_anim('rbl', period, start)}}}")
    hgt = b_[1] - a_[1]
    if eg["show"] == "reboot":
        hgt *= .45
    mask = (f'<mask id="rbm" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
            f'<rect class="rbr" x="{a_[0]:.1f}" y="{a_[1]:.1f}" width="{b_[0] - a_[0]:.1f}" height="{hgt:.1f}" fill="#fff"/></mask>')
    glow_ex = ' opacity=".75" filter="url(#bl1)"'
    led_ex = ' class="b1" style="--d:.5s"'
    red = (f'<g class="rbl" opacity="{1 if eg["show"] == "reboot" else 0}">'
           f'{dot(x0 + .22, top - .033, .035, "#ff3b30", glow_ex)}'
           f'{dot(x0 + .22, top - .033, .009, "#ff6a5a", led_ex)}</g>')
    return mask, red, css


EGG_CSS = ("@keyframes fw{0%{transform:scale(.15);opacity:0}6%{opacity:1}60%{transform:scale(1);opacity:.85}100%{transform:scale(1.08) translateY(2px);opacity:0}}"
           ".fw{animation:fw 3.3s cubic-bezier(.2,.7,.3,1) infinite both;transform-box:fill-box;transform-origin:50% 50%}"
           "@keyframes fwg{0%,100%{opacity:.04}10%{opacity:.2}40%{opacity:.08}55%{opacity:.18}}.fwg{animation:fwg 3.3s ease-in-out infinite}"
           "@keyframes flk{0%,100%{opacity:.22}30%{opacity:.3}55%{opacity:.17}80%{opacity:.27}}.flk{animation:flk 1.7s ease-in-out infinite}"
           "@keyframes flm{0%,100%{transform:scaleY(1)}50%{transform:scaleY(1.18) skewX(3deg)}}.flm{animation:flm .9s ease-in-out infinite;transform-box:fill-box;transform-origin:50% 100%}"
           "@keyframes brth{0%,100%{transform:scaleY(1)}50%{transform:scaleY(1.045)}}.brth{animation:brth 4.2s ease-in-out infinite;transform-box:fill-box;transform-origin:50% 100%}")


# ---------------- adereços (r9): homelab credivel, sem texto ----------------
TL_SECS = 48.0          # duracao do timelapse (24 h)


def disc_h(x, y, z, r, fill, extra="", n=28):
    """disco horizontal (plano y = const) em perspetiva."""
    ps = [(x + r * math.cos(2 * math.pi * i / n), y, z + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return poly(ps, fill, extra)


def ceiling_ap(t, x, z):
    """access point no teto: disco branco com anel de LED."""
    y = CEIL - .2
    o = [disc_h(x, y - .012, z, .11, t["device_w"]),
         poly([(x - .11, y - .012, z), (x + .11, y - .012, z), (x + .11, y, z), (x - .11, y, z)], t["device_w"], ' opacity=".9"'),
         disc_h(x, y - .0125, z, .045, "none", f' stroke="{t["ap_led"]}" stroke-width="1" opacity=".8" class="tw" style="--d:5s"')]
    if t["ap_glow"] > 0.02:
        o.append(ell(x, y - .03, .12, .05, t["ap_led"], f' opacity="{t["ap_glow"]:.2f}" filter="url(#bl2)"', z=z))
    return "".join(o)


def ups_tower(t, x0, z0):
    """UPS de torre no chao ao lado do ultimo armario: LCD com a carga e LED de estado a respirar."""
    x1, h, d = x0 + .2, .44, .46
    o = [f'<polygon points="{pts([P(x0 - .03, 0, z0 - .03), P(x1 + .05, 0, z0 - .03), P(x1 + .05, 0, z0 + d), P(x0 - .03, 0, z0 + d)])}" fill="#000" opacity="{t["ao"]:.2f}" filter="url(#bl1)"/>',
         box(x0, x1, 0, h, z0, z0 + d, t["bay_hi"], "url(#face)", t["side"])]
    o.append(fr(x0 + .02, h - .03, x1 - .02, h - .022, t["bay_hi"], ' opacity=".5"', z=z0 - .001))
    for k in range(9):                                     # grelha de ventilacao
        o.append(fr(x0 + .03, .05 + k * .022, x1 - .03, .058 + k * .022, t["bay"], ' opacity=".9"', z=z0 - .001))
    o.append(fr(x0 + .04, h - .12, x1 - .04, h - .07, t["bay"], z=z0 - .001))        # LCD
    for k in range(4):                                     # barra de carga (abstrata)
        o.append(fr(x0 + .05 + k * .026, h - .11, x0 + .07 + k * .026, h - .08, t["ups_lcd"], f' opacity="{.75 if k < 3 else .25}"', z=z0 - .002))
    o.append(dot(x1 - .045, h - .16, .014, "#3fd67a", ' opacity=".5" filter="url(#bl1)" class="ubr"', z=z0 - .002))
    o.append(dot(x1 - .045, h - .16, .0055, "#7cf0a8", ' class="ubr"', z=z0 - .002))
    o.append(dot(x0 + .045, h - .16, .0045, t["frame_hi"], "", z=z0 - .002))
    return "".join(o)


def cable_drop(t, x, y0, y1, z, n=5, seed=0):
    """feixe de cabos a descer da calha para o topo de um armario, preso com velcro."""
    rd = random.Random(seed)
    o = []
    for i in range(n):
        xx = x + (i - (n - 1) / 2) * .009
        col = t["cable"][rd.randrange(len(t["cable"]))]
        o.append(line3((xx, y0, z), (xx, y1, z), col, max(.6, .0065 * scale(xx, z)), ' opacity=".95"'))
    for yv in (y0 - (y0 - y1) * .3, y0 - (y0 - y1) * .75):
        o.append(fr(x - n * .0055, yv - .012, x + n * .0055, yv + .012, t["velcro"], z=z - .004))
        o.append(fr(x - n * .0055, yv + .006, x + n * .0055, yv + .012, t["frame_hi"], ' opacity=".35"', z=z - .005))
    return "".join(o)


def sill_plant(t, st, x, z):
    """planta (espada-de-sao-jorge) no parapeito da janela, em contraluz."""
    y = WIN[2]
    m = affine(x, y, z)
    pot = lerpc("#9a5a3a", t["box_side"], .35)
    pot_hi = lerpc("#c47e56", t["box"], .3)
    leaf = lerpc("#2d4a30", t["frame"], .45 - .25 * st.get("day", 0))
    edge = lerpc("#9fbf6a", st["sky"][0], .5)
    o = [f'<g transform="{m}">',
         f'<path d="M-.055 -.085 L.055 -.085 L.042 0 L-.042 0Z" fill="{pot}"/>',
         f'<path d="M-.06 -.1 L.06 -.1 L.06 -.082 L-.06 -.082Z" fill="{pot_hi}"/>']
    for (bx, h, lean, w) in ((-.03, .2, -.035, .022), (.0, .28, .01, .026), (.028, .22, .04, .022), (-.012, .16, -.06, .018), (.018, .15, .065, .016)):
        tip = (bx + lean, -.1 - h)
        o.append(f'<path d="M{bx - w / 2:.3f} -.1 Q{bx - w * .7 + lean * .4:.3f} {-.1 - h * .55:.3f} {tip[0]:.3f} {tip[1]:.3f} '
                 f'Q{bx + w * .7 + lean * .4:.3f} {-.1 - h * .55:.3f} {bx + w / 2:.3f} -.1Z" fill="{leaf}"/>')
        o.append(f'<path d="M{bx + w / 2:.3f} -.1 Q{bx + w * .7 + lean * .4:.3f} {-.1 - h * .55:.3f} {tip[0]:.3f} {tip[1]:.3f}" '
                 f'fill="none" stroke="{edge}" stroke-width=".004" opacity="{.35 + .4 * st.get("day", 0):.2f}"/>')
    o.append('</g>')
    return "".join(o)


def chair(t, st, cx, cz, yaw_deg=0):
    """cadeira de escritorio: base em estrela, coluna, assento almofadado, encosto preso ao assento por um
    suporte, bracos apoiados no assento. Tudo no mesmo referencial local; as pecas desenham-se da mais
    longe para a mais perto da camara."""
    ya = math.radians(yaw_deg)
    fwd = (math.cos(ya), math.sin(ya))            # para onde a cadeira olha (plano xz)
    side = (-fwd[1], fwd[0])

    def L(u, v, y):                                # coordenadas locais -> mundo
        return (cx + fwd[0] * u + side[0] * v, y, cz + fwd[1] * u + side[1] * v)

    def dist(p):
        return math.dist(p, CAM)
    body = t["frame"]
    hi = t["frame_hi"]
    seat = mixc([(t["cart_top"], .6), (t["post"], .4)])
    seat_hi = lerpc(seat, t["wire_hi"], .22)
    mesh = lerpc(seat, t["wall1"], .3)
    sc = scale(cx, cz)
    o = [ell(cx, 0, .34, .14, "#000", f' opacity="{t["ao"] * .9:.2f}" filter="url(#bl2)"', z=cz)]
    legs = []
    for k in range(5):
        a_ = 2 * math.pi * k / 5 + .35
        p1 = (cx + .27 * math.cos(a_), .045, cz + .27 * math.sin(a_))
        legs.append(p1)
    for p1 in sorted(legs, key=lambda q: -dist(q)):
        o.append(line3((cx, .075, cz), p1, body, max(1.2, .032 * sc)))
        o.append(ell(p1[0], .022, .022, .022, body, "", z=p1[2]))
    o.append(line3((cx, .07, cz), (cx, .44, cz), hi, max(1.2, .028 * sc)))
    o.append(line3((cx, .07, cz), (cx, .3, cz), body, max(1.6, .042 * sc)))
    h0, h1 = .45, .51

    def seat_part():
        r = [poly([L(-.1, -.1, .44), L(.1, -.1, .44), L(.1, .1, .44), L(-.1, .1, .44)], body)]
        faces = [((.22, -.22), (.22, .22)), ((.22, .22), (-.22, .22)), ((-.22, .22), (-.22, -.22)), ((-.22, -.22), (.22, -.22))]
        cen = L(0, 0, h0)
        for (u0, v0), (u1, v1) in faces:          # so as faces laterais viradas para a camara
            mid = L((u0 + u1) / 2, (v0 + v1) / 2, h0)
            if dist(mid) < dist(cen):
                r.append(poly([L(u0, v0, h1), L(u1, v1, h1), L(u1, v1, h0), L(u0, v0, h0)], lerpc(body, seat, .3)))
        r.append(poly([L(.22, -.22, h1), L(.22, .22, h1), L(-.22, .22, h1), L(-.22, -.22, h1)], seat))
        r.append(poly([L(.2, -.2, h1 + .001), L(.2, .2, h1 + .001), L(.08, .2, h1 + .001), L(.08, -.2, h1 + .001)], seat_hi, ' opacity=".4"'))
        return "".join(r)

    def bk(u0, v, y):                             # encosto ligeiramente inclinado para tras
        return L(u0 - .07 * (y - .55) / .36, v, y)

    def back_part():
        r = [path3([L(-.06, 0, .45), L(-.22, 0, .455), L(-.25, 0, .5), bk(-.25, 0, .6)], body, max(1.6, .045 * sc))]
        frame_ = [bk(-.26, -.19, .55), bk(-.26, .19, .55), bk(-.26, .18, .91), bk(-.26, -.18, .91)]
        r.append(poly(frame_, body))
        front_vis = dist(L(0, 0, .7)) < dist(L(-.5, 0, .7))
        if front_vis:
            r.append(poly([bk(-.258, -.165, .57), bk(-.258, .165, .57), bk(-.258, .155, .89), bk(-.258, -.155, .89)], mesh, ' opacity=".95"'))
            for k in range(1, 7):
                yy = .57 + .32 * k / 7
                r.append(line3(bk(-.256, -.16, yy), bk(-.256, .16, yy), body, .5, ' opacity=".45"'))
        else:
            # visto por tras: casca com um friso e o suporte lombar
            r.append(poly([bk(-.262, -.17, .57), bk(-.262, .17, .57), bk(-.262, .16, .89), bk(-.262, -.16, .89)], lerpc(body, seat, .25)))
            r.append(poly([bk(-.264, -.12, .62), bk(-.264, .12, .62), bk(-.264, .12, .68), bk(-.264, -.12, .68)], body, ' opacity=".8"'))
        r.append(line3(bk(-.262, -.18, .905), bk(-.262, .18, .905), hi, max(.8, .012 * sc), ' opacity=".6"'))
        return "".join(r)

    def arm(v):
        r = [line3(L(-.1, v, h1), L(-.08, v, .66), body, max(1.1, .026 * sc)),
             line3(L(.06, v, h1), L(-.01, v, .66), body, max(1.0, .02 * sc)),
             line3(L(-.17, v, .67), L(.1, v, .67), body, max(1.6, .042 * sc)),
             line3(L(-.16, v, .684), L(.09, v, .684), hi, max(.6, .012 * sc), ' opacity=".5"')]
        return "".join(r)
    far_v, near_v = sorted((-.205, .205), key=lambda v: -dist(L(0, v, .6)))
    parts = [(dist(L(0, 0, .5)) + .05, seat_part()), (dist(L(-.03, far_v, .6)), arm(far_v)),
             (dist(L(-.03, near_v, .6)) - .3, arm(near_v)), (dist(bk(-.26, 0, .73)), back_part())]
    for _, pp in sorted(parts, key=lambda q: -q[0]):
        o.append(pp)
    return "".join(o)


def sun_times(day):
    """(nascer, por) do sol em horas locais decimais para o dia (elevacao 0 com refracao)."""
    base = datetime(day.year, day.month, day.day)
    prev = None
    rise = sett = None
    for m in range(0, 24 * 60 + 1, 10):
        el = solar(to_utc(base + timedelta(minutes=m)))[0]
        if prev is not None:
            if prev < 0 <= el and rise is None:
                rise = (m - 10 + 10 * (-prev) / (el - prev)) / 60
            if prev >= 0 > el:
                sett = (m - 10 + 10 * prev / (prev - el)) / 60
        prev = el
    return rise or 7.0, sett or 19.0


def clock_ang(h):
    """angulo (graus, sentido horario a partir do topo) do ponteiro das horas num mostrador normal de 12 h."""
    return (h % 12) / 12 * 360


def _lum(c):
    c = c.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return .2126 * r + .7152 * g + .0722 * b


def wall_clock(t, st, eg, x, y, z, r=.16):
    """relogio de parede analogico normal de 12 h (12 marcas, 3/6/9/12 mais fortes, sem numeros).
    Ao vivo (live): ponteiros das horas, dos minutos e dos segundos (fino, cor de acento), na hora exata de
    geracao e a andar a velocidade real (CSS: 43200 s / 3600 s / 60 s em steps). O transform estatico de cada
    ponteiro ja e a hora de geracao (a animacao e relativa), por isso sem animacao le-se a hora certa.
    Fallback (imagem da Action, vista com atraso): so o ponteiro das horas, adiantado (eg["clock_dt"]).
    Timelapse: so o ponteiro das horas, duas voltas por ciclo, em fase com a luz."""
    m = affine(x, y, z)
    dt = (eg.get("clock_dt") or eg["dt"]) if eg else datetime(2026, 9, 30, 12, 0)
    tl = eg["tl"] if eg else False
    full = bool(eg) and not tl and not eg.get("clock_fb")         # live: minutos e segundos
    day = st.get("day", 0)
    face = lerpc(t["label"], t["wall1"], .12 + .38 * (1 - day))   # creme de dia, apagado de noite
    ink = "#1b1d22" if _lum(face) > .42 else "#d9deea"
    ink = lerpc(ink, face, .08)
    rim = t["frame"]
    rim_hi = lerpc(rim, "#ffffff", .18 + .12 * day)
    acc = "#b04a32"                                                # vermelho-tijolo discreto

    def pt(a, rr):
        a = math.radians(a)
        return rr * math.sin(a), -rr * math.cos(a)
    o = [f'<g transform="{m}">',
         f'<circle cx="{r * .1:.4f}" cy="{r * .16:.4f}" r="{r * 1.12:.3f}" fill="#000" opacity="{.16 + .1 * day:.2f}"/>',
         f'<circle cx="{r * .05:.4f}" cy="{r * .08:.4f}" r="{r * 1.1:.3f}" fill="#000" opacity="{.12 + .08 * day:.2f}"/>',
         f'<circle r="{r * 1.1:.3f}" fill="{rim}"/>',
         f'<circle r="{r * 1.06:.3f}" fill="none" stroke="{rim_hi}" stroke-width="{r * .035:.4f}" opacity=".7"/>',
         f'<circle r="{r:.3f}" fill="{face}"/>',
         # sombra do aro no mostrador (vidro fundo): mais escuro em cima a esquerda
         f'<circle cx="{r * .03:.4f}" cy="{r * .05:.4f}" r="{r * .97:.3f}" fill="none" stroke="#000" '
         f'stroke-width="{r * .06:.4f}" opacity=".12"/>']
    # 12 marcas: 12/3/6/9 mais fortes
    for k in range(12):
        a_ = k * 30
        strong = k % 3 == 0
        r0, r1 = r * (.7 if strong else .78), r * .9
        q0, q1 = pt(a_, r0), pt(a_, r1)
        o.append(f'<line x1="{q0[0]:.4f}" y1="{q0[1]:.4f}" x2="{q1[0]:.4f}" y2="{q1[1]:.4f}" stroke="{ink}" '
                 f'stroke-width="{r * (.085 if strong else .04):.4f}" stroke-linecap="butt"/>')
    hours = dt.hour + dt.minute / 60 + dt.second / 3600
    ah = clock_ang(hours)
    am = (dt.minute + dt.second / 60) * 6
    asec = dt.second * 6
    box = f'<circle r="{r:.3f}" fill="none"/>'            # caixa simetrica: o centro de rotacao (fill-box) e o do mostrador
    hh = (box + f'<path d="M{-r * .065:.4f} {r * .16:.4f} L{-r * .045:.4f} {-r * .4:.4f} L0 {-r * .54:.4f} '
          f'L{r * .045:.4f} {-r * .4:.4f} L{r * .065:.4f} {r * .16:.4f}Z" fill="{ink}"/>')
    mh = (box + f'<path d="M{-r * .045:.4f} {r * .18:.4f} L{-r * .03:.4f} {-r * .66:.4f} L0 {-r * .84:.4f} '
          f'L{r * .03:.4f} {-r * .66:.4f} L{r * .045:.4f} {r * .18:.4f}Z" fill="{ink}"/>')
    sh = (box + f'<path d="M0 {r * .24:.4f} L0 {-r * .88:.4f}" stroke="{acc}" stroke-width="{r * .028:.4f}" stroke-linecap="round"/>'
          f'<circle cy="{r * .2:.4f}" r="{r * .055:.4f}" fill="{acc}"/>')
    if tl:
        o.append(f'<g class="chh" transform="rotate({ah:.2f})">{hh}</g>')
        css = (f"@keyframes chh{{from{{transform:rotate(0deg)}}to{{transform:rotate(720deg)}}}}"
               f".chh{{animation:chh {TL_SECS:.0f}s linear infinite;transform-box:fill-box;transform-origin:50% 50%}}")
    else:
        o.append(f'<g transform="rotate({ah:.2f})"><g class="ckh">{hh}</g></g>')
        css = ("@keyframes ckr{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}"
               ".ckh,.ckm,.cks{transform-box:fill-box;transform-origin:50% 50%}"
               ".ckh{animation:ckr 43200s linear infinite}")
        if full:
            o.append(f'<g transform="rotate({am:.2f})"><g class="ckm">{mh}</g></g>')
            o.append(f'<g transform="rotate({asec:.2f})"><g class="cks">{sh}</g></g>')
            css += ".ckm{animation:ckr 3600s linear infinite}.cks{animation:ckr 60s steps(60) infinite}"
    o.append(f'<circle r="{r * .075:.4f}" fill="{ink}"/>')
    if full:
        o.append(f'<circle r="{r * .035:.4f}" fill="{acc}"/>')
    # vidro: reflexo subtil (mais vivo de dia)
    o.append(f'<path d="M{-r * .8:.4f} {-r * .22:.4f} A{r * .84:.4f} {r * .84:.4f} 0 0 1 {-r * .2:.4f} {-r * .82:.4f}" fill="none" '
             f'stroke="#fff" stroke-width="{r * .07:.4f}" opacity="{.1 + .14 * day:.2f}" stroke-linecap="round"/>')
    o.append(f'<path d="M{-r * .62:.4f} {-r * .62:.4f} A{r * .9:.4f} {r * .9:.4f} 0 0 1 {r * .55:.4f} {-r * .7:.4f} '
             f'A{r * 1.3:.4f} {r * 1.3:.4f} 0 0 0 {-r * .62:.4f} {-r * .62:.4f}Z" fill="#fff" opacity="{.04 + .05 * day:.2f}"/>')
    o.append('</g>')
    return "".join(o), css


CLOCK_CSS = ("@keyframes rot{from{transform:rotate(0)}to{transform:rotate(360deg)}}"
                          "@keyframes ubr{0%,100%{opacity:1}50%{opacity:.45}}.ubr{animation:ubr 5s ease-in-out infinite}")


def day_load(day):
    """carga abstrata do dia (96 quartos de hora), deterministica por data: igual em todas as imagens do dia."""
    rd = random.Random(day.toordinal() * 7 + 3)
    ph = [rd.uniform(0, 2 * math.pi) for _ in range(3)]
    out = []
    for i in range(96):
        h = i / 4
        v = .3 + .18 * math.sin(2 * math.pi * (h - 9) / 24) + .06 * math.sin(ph[0] + h * 1.3) + .05 * math.sin(ph[1] + h * 2.9)
        v += .1 * math.exp(-((h - 3.2) / .5) ** 2)       # backups de madrugada
        out.append(max(.05, min(.95, v + rd.uniform(-.035, .035))))
    return out


def dashboard(t, eg, M):
    """o portatil mostra um painel abstrato: 24 barras de uptime (horas do dia) e a carga do dia ate agora."""
    dt = eg["dt"] if eg else datetime(2026, 9, 30, 12, 0)
    tl = eg["tl"] if eg else False
    ok, ink = "#2ea44f", t["kb"]
    acc = "#3b7ddd"
    now_i = dt.hour * 4 + dt.minute // 15
    vals = day_load(dt.date())
    x0, x1, yb0, yb1, cy0, cy1 = .07, .93, .08, .24, .34, .74
    bw = (x1 - x0) / 24
    o = [f'<g transform="{M}">']
    past, fut = [], []
    for h in range(24):
        r_ = f'<rect x="{x0 + h * bw + bw * .12:.4f}" y="{yb0:.3f}" width="{bw * .76:.4f}" height="{yb1 - yb0:.3f}"/>'
        (past if (tl or h < dt.hour) else fut).append(r_)
    n = 96 if tl else now_i + 1
    pts_ = [(x0 + (x1 - x0) * i / 95, cy1 - (cy1 - cy0) * vals[i]) for i in range(n)]
    line = "M" + " L".join(f"{a_:.4f} {b_:.4f}" for a_, b_ in pts_)
    area = line + f" L{pts_[-1][0]:.4f} {cy1:.3f} L{x0:.4f} {cy1:.3f}Z"
    grid = "".join(f'<line x1="{x0}" y1="{cy0 + (cy1 - cy0) * k / 3:.3f}" x2="{x1}" y2="{cy0 + (cy1 - cy0) * k / 3:.3f}" stroke="{ink}" stroke-width=".006" opacity=".12"/>' for k in range(4))
    body = (f'<g fill="{ok}" opacity=".78">{"".join(past)}</g>'
            f'<path d="{area}" fill="{acc}" opacity=".18"/><path d="{line}" fill="none" stroke="{acc}" stroke-width=".018" stroke-linejoin="round"/>')
    o.append(grid)
    o.append(f'<g fill="{ink}" opacity=".06">{"".join(fut) if not tl else "".join(past)}</g>')
    if tl:
        # no timelapse o dia vai-se desenhando: um recorte que cresce com o loop
        kx = (dt.hour + dt.minute / 60) / 24
        o.append(f'<clipPath id="dbc"><rect class="tlw" x="{x0:.3f}" y="0" width="{x1 - x0:.3f}" height="1" transform="translate({x0:.3f} 0) scale({kx:.3f} 1) translate({-x0:.3f} 0)"/></clipPath>'
                 f'<g clip-path="url(#dbc)">{body}</g>')
    else:
        o.append(body)
        ex, ey = pts_[-1]
        cur_x = x0 + dt.hour * bw + bw * .12
        o.append(f'<rect x="{cur_x - bw * .3:.4f}" y="{yb0 - .05:.3f}" width="{bw * 1.36:.4f}" height="{yb1 - yb0 + .1:.3f}" fill="#3fdc6a" opacity=".3"/>')
        o.append(f'<rect class="cur" x="{cur_x - bw * .06:.4f}" y="{yb0 - .02:.3f}" width="{bw * .88:.4f}" height="{yb1 - yb0 + .04:.3f}" fill="#2bd05a"/>')
        o.append(f'<circle cx="{ex:.4f}" cy="{ey:.4f}" r=".018" fill="{acc}"/>')
    o.append('</g>')
    return "".join(o)


# ---------------- cena ----------------
def build(days, st, idp="", draw_sun=True, eg=None):
    t = st["t"]
    ev = eg["ev"] if eg else set()
    ecss = []
    night = st["stars"] > .3 or st.get("el", 0) < -4
    global PEAK
    PEAK = max(1, max(c for _, c in days))
    if "dia_do_pico" in ev:          # dia/mes do dia com mais contribuicoes: tudo um pouco mais aceso
        t = dict(t, bloom=t["bloom"] * 1.6, amb_led=t["amb_led"] * 1.5, ceilglow=t["ceilglow"] * 1.5 + .15, pipe_warm=t["pipe_warm"] * 1.4 + .1,
                 refl=min(.8, t["refl"] * 1.2), screen_glow=t["screen_glow"] * 1.2)
    # os ultimos 12 meses ate ao mes corrente (data da imagem, hora de Lisboa); sem eg, o mes do ultimo dia dos dados
    months = list(last12(days, eg["dt"].date() if eg else None).items())
    rnd = random.Random(601)
    tots = [sum(c for _, c in v) for _, v in months]
    mmax = max(max(tots), 1)
    paused_m = [tt < 5 for tt in tots]
    # reboot: o rack aberto ativo mais perto da posicao RB
    rb_i = min((i for i, k in enumerate(KIND) if k[0] == "open" and not paused_m[i]), key=lambda i: abs(i - RB), default=RB)
    # caixas no chao: em frente ao mes mais parado (fora das estantes da janela e do canto do carrinho)
    box_i = min((0, 1, 2, 3, 4, 5, 8, 9, 10), key=lambda i: (tots[i], abs(i - 2)))
    xs = layout()
    XLAST = xs[-1] + KIND[-1][1]
    far, near, FRONTZ = XEND, XLAST + 4.0, -7.0
    sun = st["sun"]
    skyb = st["skyb"]

    o = []
    a = o.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
      f'aria-label="noxied">')
    a("<defs>")
    a(f'<linearGradient id="wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["wall0"]}"/><stop offset="1" stop-color="{t["wall1"]}"/></linearGradient>')
    a(f'<linearGradient id="fl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["fl0"]}"/><stop offset="1" stop-color="{t["fl1"]}"/></linearGradient>')
    a(f'<linearGradient id="face" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["face0"]}"/><stop offset="1" stop-color="{t["face1"]}"/></linearGradient>')
    a(f'<linearGradient id="win" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{st["sky"][0]}"/><stop offset="1" stop-color="{st["sky"][1]}"/></linearGradient>')
    a(f'<linearGradient id="scr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["screen0"]}"/><stop offset="1" stop-color="{t["screen1"]}"/></linearGradient>')
    for i, col in enumerate(t["act"] + [t["hot"]]):
        a(f'<radialGradient id="h{i}"><stop offset="0" stop-color="{col}" stop-opacity=".8"/>'
          f'<stop offset=".4" stop-color="{col}" stop-opacity=".2"/><stop offset="1" stop-color="{col}" stop-opacity="0"/></radialGradient>')
    a(f'<radialGradient id="warm"><stop offset="0" stop-color="{t["act"][2]}" stop-opacity=".7"/><stop offset="1" stop-color="{t["act"][2]}" stop-opacity="0"/></radialGradient>')
    a(f'<radialGradient id="cool"><stop offset="0" stop-color="{t["screen0"]}" stop-opacity=".6"/><stop offset="1" stop-color="{t["screen0"]}" stop-opacity="0"/></radialGradient>')
    pool_c = lerpc(st["sky"][0], sun["col"], min(1, sun["str"]))
    a(f'<radialGradient id="sunpool"><stop offset="0" stop-color="{pool_c}" stop-opacity=".55"/><stop offset="1" stop-color="{pool_c}" stop-opacity="0"/></radialGradient>')
    a(f'<radialGradient id="outg" cx=".85" cy="1" r=".9"><stop offset="0" stop-color="{t["outglow"]}" stop-opacity="{t["outglow_op"]:.3f}"/><stop offset="1" stop-color="{t["outglow"]}" stop-opacity="0"/></radialGradient>')
    a('<linearGradient id="doorg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></linearGradient>')
    a('<filter id="bl1" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="1.5"/></filter>')
    a('<filter id="bl2" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="5"/></filter>')
    a('<filter id="bl3" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="14"/></filter>')
    a('<filter id="bl4" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="28"/></filter>')
    a('<filter id="soft" x="-5%" y="-20%" width="110%" height="140%"><feGaussianBlur stdDeviation=".7 2.2"/></filter>')
    a(grain(amount=t["grain"]))
    a(f'<clipPath id="clip"><rect width="{W}" height="{H}" rx="12"/></clipPath>')
    a("</defs>")
    a("<style>"
      ".b1{animation:b1 var(--d) steps(1) infinite}"
      ".b2{animation:b2 var(--d) steps(1) infinite}"
      ".b3{animation:b3 var(--d) steps(1) infinite}"
      "@keyframes b1{0%{opacity:1}14%{opacity:.15}20%{opacity:1}52%{opacity:.2}58%{opacity:1}71%{opacity:.1}}"
      "@keyframes b2{0%{opacity:1}31%{opacity:.1}36%{opacity:1}44%{opacity:.25}49%{opacity:1}83%{opacity:.15}91%{opacity:1}}"
      "@keyframes b3{0%{opacity:.2}9%{opacity:1}62%{opacity:.15}66%{opacity:1}78%{opacity:.3}83%{opacity:1}}"
      ".steam{animation:steam 4.6s ease-out infinite}"
      "@keyframes steam{0%{transform:translateY(2px);opacity:0}25%{opacity:.55}100%{transform:translateY(-12px);opacity:0}}"
      ".dust{animation:dust var(--d) ease-in-out infinite alternate}"
      "@keyframes dust{0%{transform:translate(0,0)}100%{transform:translate(var(--dx),var(--dy))}}"
      ".tw{animation:tw var(--d) ease-in-out infinite alternate}"
      "@keyframes tw{0%{opacity:.15}100%{opacity:1}}"
      ".scr{animation:scr 8s ease-in-out infinite}"
      "@keyframes scr{0%,100%{opacity:1}46%{opacity:1}50%{opacity:.82}56%{opacity:1}}"
      ".cur{animation:cur 1.1s steps(1) infinite}"
      "@keyframes cur{0%{opacity:1}50%{opacity:0}}"
      + (EGG_CSS if eg else "") + "/*EGGS*/" + CLOCK_CSS +
      "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
      "</style>")
    # cartao opaco
    a(f'<rect width="{W}" height="{H}" rx="12" fill="{t["wall1"]}"/>')
    a('<g clip-path="url(#clip)">')
    ldefs = []

    # ---------- sala ----------
    a(poly([(far, CEIL, ZB), (near, CEIL, ZB), (near, 0, ZB), (far, 0, ZB)], "url(#wall)"))
    WX0, WX1, WY0, WY1 = WIN
    for k in range(1, 14):
        yb = k * 0.2
        a(line3((far, yb, ZB), (near, yb, ZB), t["joint"], .7, ' opacity=".8"'))
        xb = far + (0.2 if k % 2 else 0.0)
        while xb < near:
            a(line3((xb, yb - .2, ZB), (xb, yb, ZB), t["joint"], .55, ' opacity=".6"'))
            xb += 0.4
    # claridade do ceu na parede a volta da janela
    a(window_glow(st, WX0, WX1, WY0, WY1))
    a(poly([(far, CEIL, ZB), (far, 0, ZB), (far, 0, FRONTZ), (far, CEIL, FRONTZ)], t["endw"]))
    a(poly([(far, CEIL, ZB), (near, CEIL, ZB), (near, CEIL, FRONTZ), (far, CEIL, FRONTZ)], t["ceil"]))
    a(poly([(far, 0, ZB), (near, 0, ZB), (near, 0, FRONTZ), (far, 0, FRONTZ)], "url(#fl)"))
    a(hz(far, near, .0005, ZB - .02, ZB, t["joint"]))
    a(fr(far, 0, near, .09, t["joint"], ' opacity=".7"', z=ZB - .002))
    for i in range(0, 12):
        xj = far + .3 + i * 1.5
        a(line3((xj, 0, ZB), (xj, 0, FRONTZ), t["fjoint"], .9, ' opacity=".9"'))
    for zj in (-1.2, -2.7):
        a(line3((far, 0, zj), (near, 0, zj), t["fjoint"], .9, ' opacity=".9"'))

    # janela alta: ceu, estrelas, relva ao nivel da rua
    a(fr(WX0 - .05, WY0 - .06, WX1 + .05, WY1 + .05, t["frame_hi"], z=ZB - .001))
    a(sx(WX1, WX1, WY0, WY1, ZB, ZB + WD, t["reveal"]))
    a(hz(WX0, WX1, WY0, ZB, ZB + WD, t["sill"]))
    SILL = (WX0 - .09, WX1 + .09, WY0 - .055, WY0, ZB - .07)
    a(fr(WX0, WY0, WX1, WY1, "url(#win)", z=ZB + WD))
    if st["stars"] > 0.01:
        rs = random.Random(21)
        stars = []
        for k in range(26):
            sx_ = WX0 + .05 + rs.random() * (WX1 - WX0 - .1)
            sy_ = WY0 + .12 + rs.random() * (WY1 - WY0 - .15)
            r_ = .003 + rs.random() * .004
            stars.append(dot(sx_, sy_, r_, "#e8eeff", f' class="tw" style="--d:{2 + rs.random() * 4:.1f}s;animation-delay:-{rs.random() * 4:.1f}s"', z=ZB + WD))
        a(f'<g opacity="{st["stars"] * .85:.2f}">' + "".join(stars) + '</g>')
    if eg:
        a(moon_svg(eg, st))
        if "ano_novo" in ev:
            a(fireworks_svg(t))
    a(fr(WX0, WY0, WX1, WY1, "url(#outg)", z=ZB + WD))
    grass = []
    rg = random.Random(7)
    gx = WX0
    while gx < WX1:
        gh = .05 + rg.random() * .12
        grass.append(((gx, WY0 + .04, ZB + WD), (gx + .018, WY0 + .04 + gh, ZB + WD), (gx + .04, WY0 + .04, ZB + WD)))
        gx += .025 + rg.random() * .02
    a(fr(WX0, WY0, WX1, WY0 + .06, t["grass"], z=ZB + WD))
    for g in grass:
        a(poly(list(g), t["grass"]))
    for k in range(1, NP):
        xm = WX0 + k * (WX1 - WX0) / NP
        a(fr(xm - .016, WY0, xm + .016, WY1, t["frame_hi"], z=ZB + WD - .01))
    a(fr(WX0, WY1 - .03, WX1, WY1, t["frame_hi"], z=ZB + WD - .01))
    # parapeito saliente (ve-se de baixo: a frente e a face inferior) e a planta pousada nele
    sx0, sx1, sy0, sy1, sz = SILL
    a(hz(sx0, sx1, sy0, sz, ZB, lerpc(t["sill"], "#000000", .45)))
    a(sx(sx1, sx1, sy0, sy1, sz, ZB, lerpc(t["sill"], "#000000", .3)))
    a(sill_plant(t, st, WX0 + .3, ZB - .035))
    a(fr(sx0, sy0, sx1, sy1, lerpc(t["sill"], t["wall0"], .35), z=sz))
    a(fr(sx0, sy1 - .008, sx1, sy1, lerpc(t["sill"], "#ffffff", .15), f' opacity="{.3 + .4 * st.get("day", 0):.2f}"', z=sz - .001))
    ck, ckcss = wall_clock(t, st, eg, CLOCK[0], CLOCK[1], ZB - .006, r=CLOCK[2])
    a(ck)
    ecss.append(ckcss)

    # porta entreaberta (luz da escada)
    DX0, DX1, DH = DOOR
    phi = math.radians(24)
    Lw = DX1 - DX0
    fx_, fz_ = DX1 - Lw * math.cos(phi), ZB - Lw * math.sin(phi)
    a(fr(DX0 - .07, 0, DX1 + .07, DH + .07, t["frame_hi"], z=ZB - .002))
    a(fr(DX0, 0, DX1, DH, t["door_in"], z=ZB))
    a(fr(DX0, 0, DX1, DH, "url(#doorg)", z=ZB))
    for k in range(4):
        a(fr(DX0, .18 * k, DX1, .18 * k + .02, t["door_step"], f' opacity="{.5 - .1 * k:.2f}"', z=ZB + .35 + .25 * k))
    leaf = [(DX1, DH, ZB), (fx_, DH, fz_), (fx_, 0, fz_), (DX1, 0, ZB)]
    a(poly(leaf, t["door_leaf"]))
    a(poly([(fx_ + .02, DH, fz_ + .02 * math.tan(phi)), (fx_, DH, fz_), (fx_, 0, fz_), (fx_ + .02, 0, fz_ + .02 * math.tan(phi))], t["door_edge"]))
    hx_, hz_ = fx_ + .07 * math.cos(phi), fz_ + .07 * math.sin(phi)
    a(poly([(hx_, 1.02, hz_), (hx_ + .1 * math.cos(phi), 1.02, hz_ + .1 * math.sin(phi)), (hx_ + .1 * math.cos(phi), 1.0, hz_ + .1 * math.sin(phi)), (hx_, 1.0, hz_)], t["steel"]))
    a(fr(DX0 - .2, 1.18, DX0 - .13, 1.28, t["label"], ' opacity=".7"', z=ZB - .003))
    wedge = [(DX0, 0, ZB), (fx_, 0, fz_), (fx_ - .5, 0, fz_ - 1.9), (DX0 - 1.2, 0, ZB - 1.6)]
    door_light = [f'<polygon points="{pts([P(*p) for p in wedge])}" fill="{t["door_in"]}" opacity="{t["door_op"]:.3f}" filter="url(#bl2)"/>',
                  poly([(DX0, DH, ZB), (DX0 + .02, DH, ZB), (DX0 + .02, 0, ZB), (DX0, 0, ZB)], t["door_in"], ' opacity=".9"'),
                  fr(DX0 - .05, 0, DX0 + .12, DH, t["door_in"], f' opacity="{t["door_op"] * .8:.3f}" filter="url(#bl2)"', z=ZB - .01)]

    # vigas, tubos
    for i in range(0, 24):
        xj = far + .35 + i * .6
        if xj > near:
            break
        if xj + .06 < CAM[0]:
            a(sx(xj + .06, xj + .06, CEIL - .2, CEIL, ZB, FRONTZ, t["beam_side"]))
        a(hz(xj, xj + .06, CEIL - .2, ZB, FRONTZ, t["beam_bot"]))
    for (py, pz, pr, col) in ((2.61, 0.78, 0.05, t["pipe"]), (2.52, 0.86, 0.026, t["pipe2"])):
        a(fr(far, py - pr, near, py + pr, col, z=pz))
        a(fr(far, py + pr * .15, near, py + pr * .55, t["pipe_hi"], ' opacity=".5"', z=pz - .01))
        for xb in range(0, 12):
            a(fr(xb * 1.0 + .3, py - pr - .01, xb * 1.0 + .34, py + pr + .01, t["pipe_hi"], ' opacity=".35"', z=pz - .012))
    for mi_, x_ in enumerate(xs):
        k_ = (tots[mi_] / mmax) ** .6 if tots[mi_] else 0
        if k_ > .05 and t["pipe_warm"] > 0.02:
            for (py, pz, pr) in ((2.61, 0.78, 0.05), (2.52, 0.86, 0.026)):
                a(fr(x_ - .1, py - pr * .7, x_ + KIND[mi_][1] + .1, py - pr * .2, t["act"][2], f' opacity="{t["pipe_warm"] * k_:.2f}" filter="url(#bl1)"', z=pz - .015))
    sdx, sdz = 6.5, -0.25
    a(ell(sdx, CEIL - .2, .07, .02, t["device_w"], "", z=sdz))
    a(fr(sdx - .07, CEIL - .235, sdx + .07, CEIL - .2, t["device_w"], z=sdz))
    a(dot(sdx + .03, CEIL - .228, .006, "#ff4a3a", ' class="tw" style="--d:2.2s" opacity=".9"', z=sdz - .001))
    a(ceiling_ap(t, 8.3, -.7))
    TY = 2.3
    TX0 = xs[8] - .1
    for (ta, tb) in ((xs[0] - .05, xs[5] + .2), (TX0, XLAST)):      # calha de cabos em dois troços (a janela fica livre)
        a(hz(ta, tb, TY, .05, .5, t["tray"]))
        a(fr(ta, TY, tb, TY + .06, t["tray_hi"], z=.05))
        k = 0
        while ta + k * .3 < tb:
            xr = ta + k * .3
            a(hz(xr, min(tb, xr + .025), TY, .05, .5, t["tray_hi"], ' opacity=".6"'))
            k += 1
        for xh in (ta + .15, (ta + tb) / 2, tb - .15):
            a(line3((xh, CEIL - .2, .1), (xh, TY + .06, .1), t["tray_hi"], 1))
    drops = [i for i in (0, 1, 2, 3, 4, 8, 9, 10, 11) if not paused_m[i]]       # cabos da calha so para moveis ativos
    for sd_, mi_ in enumerate(drops, 1):
        a(cable_drop(t, xs[mi_] + .22, TY, KIND[mi_][2], .3, n=4 + sd_ % 3, seed=sd_))
    if "natal" in ev:
        a(natal_svg(t, xs, TX0, XLAST, TY))

    # ---------- luz pela janela: candeeiro da rua (noite) + sol ----------
    segs = shadow_segs(xs)
    floor_layers, beam_layers = [], []
    if st["street"] > 0.01:
        f_, b_ = light_through_window(ldefs, STREET, "#8fb0e8", "#9db8e6", .07 * st["street"], .13 * st["street"],
                                      16, .25 * st["street"], "#8fb0e8", .25, segs, idp + "st", 11)
        floor_layers.append(f_)
        beam_layers.append(b_)
    if draw_sun and sun["str"] > 0.01:
        f_, b_ = sun_light(ldefs, st, segs, idp, t["shelf_sh"])
        floor_layers.append(f_)
        beam_layers.append(b_)

    # ---------- moveis ----------
    racks, glow, halos, floorglow, ceilglow = [], [], [], [], []
    rim_op = t["rim_op"] * (.35 + .65 * max(sun["str"], 1 - skyb))
    for mi, ((yy, mm), md) in enumerate(months):
        style, wdt, top, recipe = KIND[mi]
        x0 = xs[mi]
        tot = tots[mi]
        paused = paused_m[mi]
        R, G, Hs = [], [], []
        if style == "wire":
            wire_shelf(t, rnd, x0, wdt, top, recipe, md, paused, R, G, Hs)
        else:
            rack(t, rnd, style, x0, wdt, top, recipe, md, paused, tot, R, G, Hs)
        if rim_op > 0.01:
            fall = max(0, 1 - abs(x0 - (WIN[0] + WIN[1]) / 2) / 6.5)
            R.append(fr(x0, .1, x0 + .012, top - .02, t["rim"], f' opacity="{rim_op * fall:.2f}"'))
        racks.append("".join(R))
        if eg and mi == rb_i:
            rb_mask, rb_red, rb_css = reboot_parts(eg, x0, wdt, top)
            ecss.append(rb_css)
            glow.append(rb_mask + '<g mask="url(#rbm)">' + "".join(G) + '</g>')
            halos.append('<g mask="url(#rbm)">' + "".join(Hs) + '</g>')
        else:
            glow.append("".join(G))
            halos.append("".join(Hs))
        if tot > 0:
            k = (tot / mmax) ** .55
            cxm = x0 + wdt / 2
            floorglow.append(ell(cxm, 0, wdt * .8, .3, t["act"][2], f' opacity="{.18 * k * t["amb_led"]:.2f}"', z=-0.3))
            if t["ceilglow"] > 0.02:
                ceilglow.append(ell(cxm, top + .12, wdt * .8, .16, "url(#warm)", f' opacity="{t["ceilglow"] * k:.2f}"', z=ZB))

    if ceilglow:
        a('<g filter="url(#bl2)">' + "".join(ceilglow) + '</g>')
    a("".join(door_light))
    a(f'<polygon points="{pts([P(-.05, 0, ZF - .005), P(XLAST + .05, 0, ZF - .005), P(XLAST + .05, 0, ZF - .16), P(-.05, 0, ZF - .16)])}" fill="#000" opacity="{t["ao"]:.2f}" filter="url(#bl1)"/>')
    a('<g id="body">' + "".join(racks) + '</g>')
    a(f'<g id="halos" opacity="{min(1, t.get("halo", 1)):.2f}">' + "".join(halos) + '</g>')
    a('<g id="em">' + "".join(glow) + '</g>')
    a(f'<use href="#em" filter="url(#bl1)" opacity="{t["bloom"]:.2f}"/>')
    a(f'<use href="#em" filter="url(#bl2)" opacity="{.75 * t["bloom"]:.2f}"/>')
    a(ups_tower(t, XLAST + .09, -.04))
    if eg:
        a(rb_red)
        if "sexta_tarde" in ev:
            a(postit_svg(xs[CAT]))
        cat = cat_svg(t, xs[CAT], KIND[CAT][2], night)
        if "madrugada" in ev and not eg["tl"]:
            a(cat)
        elif eg["tl"]:             # no timelapse o gato aparece das 02h as 05h
            a(f'<g class="catl" opacity="0">{cat}</g>')
            ecss.append("@keyframes catl{0%,8.1%{opacity:0}8.8%,20.1%{opacity:1}20.8%,100%{opacity:0}}.catl{animation:catl 48s linear infinite}")

    # reflexo no chao
    p0, p1 = P(0, 0, ZF), P(XLAST, 0, ZF)
    sl = (p1[1] - p0[1]) / (p1[0] - p0[0])
    b = p0[1] - sl * p0[0]
    m = f"matrix(1 {2 * sl:.5f} 0 -1 0 {2 * b:.2f})"
    fl_pts = [P(far, 0, ZF), P(near, 0, ZF), P(near, 0, -2.6), P(far, 0, -2.6)]
    a(f'<mask id="rmask" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
      f'<polygon points="{pts(fl_pts)}" fill="#fff"/></mask>')
    a(f'<linearGradient id="rgrad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="-95" gradientTransform="matrix(1 {sl:.5f} 0 1 0 {b:.2f})">'
      '<stop offset="0" stop-color="#fff"/><stop offset=".45" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    a(f'<mask id="rfade" maskUnits="userSpaceOnUse" x="-100" y="-400" width="{W + 200}" height="{H + 800}"><rect x="-100" y="-400" width="{W + 200}" height="{H + 800}" fill="url(#rgrad)"/></mask>')
    a(f'<g mask="url(#rmask)"><g opacity="{t["refl"]:.2f}"><g transform="{m}"><g mask="url(#rfade)"><g filter="url(#soft)"><use href="#body"/><use href="#em"/></g>'
      f'<use href="#em" filter="url(#bl2)" opacity=".5"/></g></g></g></g>')
    a('<g filter="url(#bl3)">' + "".join(floorglow) + '</g>')
    a("".join(floor_layers))

    # caixas no chao em frente ao mes mais parado
    ax = xs[box_i] + .06
    a(f'<polygon points="{pts([P(ax - .03, 0, -.03), P(ax + .5, 0, -.03), P(ax + .5, 0, -.47), P(ax - .03, 0, -.47)])}" fill="#000" opacity="{t["ao"]:.2f}" filter="url(#bl1)"/>')
    a(box(ax, ax + .46, 0, .3, -0.42, -0.06, t["box_top"], t["box"], t["box_side"]))
    a(fr(ax + .19, .27, ax + .26, .3, t["tape"], ' opacity=".8"', z=-.42))
    a(box(ax + .07, ax + .38, .3, .46, -0.36, -0.1, t["box_top"], t["box"], t["box_side"]))
    a(hz(ax + .19, ax + .25, .46, -.36, -.1, t["tape"], ' opacity=".8"'))
    a(fr(ax + .05, .1, ax + .17, .17, t["label"], ' opacity=".85"', z=-.421))
    a(fr(ax + .24, .36, ax + .33, .41, t["label"], ' opacity=".85"', z=-.361))
    if "halloween" in ev:
        a(pumpkin_svg(t, ax, night))

    # carrinho com portatil
    c0, c1, cz0, cz1, cy = 7.50, 8.06, -1.25, -0.9, .8
    a(ell((c0 + c1) / 2, 0, .34, .24, "#000", f' opacity="{t["ao"] * .8:.2f}" filter="url(#bl2)"', z=(cz0 + cz1) / 2))
    cart = []
    for (lx, lz) in ((c0 + .02, cz1 - .02), (c1 - .02, cz1 - .02)):
        cart.append(fr(lx - .012, .06, lx + .012, cy, t["steel"], z=lz))
    cart.append(box(c0, c1, .22, .25, cz0, cz1, t["cart_top"], t["cart"], t["cart_side"]))
    for r_ in (.07, .058, .046):
        cart.append(ell(c0 + .15, .25 + r_, r_ * 1.0, r_ * .95, "none", f' stroke="{t["cable"][5]}" stroke-width="1.4" opacity=".95"', z=cz0 + .15))
    cart.append(box(c0 + .27, c0 + .43, .25, .29, cz0 + .06, cz0 + .26, t["bay_hi"], "url(#face)", t["side"]))
    cart.append(dot(c0 + .40, .27, .003, t["pwr"], "", z=cz0 + .06))
    for (lx, lz) in ((c0 + .02, cz0 + .02), (c1 - .02, cz0 + .02)):
        cart.append(fr(lx - .014, .06, lx + .014, cy, t["steel"], z=lz))
        cart.append(ell(lx, .035, .035, .035, t["frame"], "", z=lz))
    cart.append(box(c0, c1, cy, cy + .035, cz0, cz1, t["cart_top"], t["cart"], t["cart_side"]))
    lx0, lx1, lz0, lz1 = c0 + .05, c0 + .35, cz0 + .06, cz0 + .27
    cart.append(box(lx0, lx1, cy + .035, cy + .05, lz0, lz1, t["steel"], t["cart_side"], t["cart_side"]))
    cart.append(hz(lx0 + .02, lx1 - .02, cy + .0505, lz0 + .07, lz1 - .02, t["kb"]))
    scr = [(lx0, cy + .05, lz1), (lx1, cy + .05, lz1), (lx1, cy + .27, lz1 + .07), (lx0, cy + .27, lz1 + .07)]
    cart.append(poly(scr, t["frame"]))
    inset = [(lx0 + .012, cy + .062, lz1 + .004), (lx1 - .012, cy + .062, lz1 + .004), (lx1 - .012, cy + .258, lz1 + .066), (lx0 + .012, cy + .258, lz1 + .066)]
    cart.append(f'<g class="scr">{poly(inset, "url(#scr)")}')
    Msc = screen_matrix(lx0, lx1, cy, lz1)
    if "1_abril" in ev:                 # 1 de abril: o ecra esta de pernas para o ar
        cq = [P(*p) for p in inset]
        ccx, ccy = sum(q[0] for q in cq) / 4, sum(q[1] for q in cq) / 4
        cart.append(f'<g transform="rotate(180 {ccx:.1f} {ccy:.1f})">')
    cart.append(dashboard(t, eg, Msc))
    if eg and eg["today"]:
        cart.append(today_svg(eg, Msc))
    if "1_abril" in ev:
        cart.append('</g>')
    if eg:
        snk, scss = snake_svg(eg, Msc)
        cart.append(snk)
        ecss.append(scss)
    cart.append('</g>')
    mx_, mz_ = c1 - .075, cz0 + .25
    cart.append(fr(mx_ - .04, cy + .035, mx_ + .04, cy + .14, t["mug"], z=mz_))
    cart.append(fr(mx_ + .02, cy + .035, mx_ + .04, cy + .14, t["mug_dark"], ' opacity=".6"', z=mz_))
    cart.append(ell(mx_, cy + .14, .04, .012, t["mug_dark"], "", z=mz_))
    empty = "madrugada" in ev
    cart.append(ell(mx_, cy + .14, .032, .008, lerpc(t["mug_dark"], "#000000", .55) if empty else "#2a1c14", "", z=mz_))
    hs = P(mx_ + .04, cy + .11, mz_)
    sc = scale(mx_, mz_)
    cart.append(f'<path d="M{hs[0]:.1f} {hs[1]:.1f} a{.028 * sc:.1f} {.03 * sc:.1f} 0 0 1 0 {.05 * sc:.1f}" fill="none" stroke="{t["mug"]}" stroke-width="{.012 * sc:.1f}"/>')
    st_ = P(mx_, cy + .16, mz_)
    for j in range(0 if empty else 3):
        xo = (j - 1) * .012 * sc
        cart.append(f'<path class="steam" style="animation-delay:-{j * 1.5:.1f}s" d="M{st_[0] + xo:.1f} {st_[1]:.1f} q-3 -5 0 -10 q3 -5 0 -10" '
                    f'fill="none" stroke="{t["steam"]}" stroke-width="1" opacity=".4" stroke-linecap="round"/>')
    lab_x, lab_y = c0 + .04, cy + .03
    wlab = text_path("nOxieD", 0, 0, 24, wght=620, tracking=0.06)[1]
    lw = wlab * .001 + .012
    # fita de etiquetadora (preta, letra clara e discreta): le-se de perto, a 830 px nao grita
    tape = lerpc("#15171b", t["cart"], .25)
    cart.append(fr(lab_x, cy + .007, lab_x + lw, cy + .029, tape, z=cz0 - .001))
    cart.append(fr(lab_x, cy + .026, lab_x + lw, cy + .029, "#ffffff", ' opacity=".06"', z=cz0 - .0015))
    cart.append(f'<path d="{text_path("nOxieD", 6, 20, 24, wght=620, tracking=0.06)[0]}" fill="{lerpc("#d9d5cb", tape, .3)}" transform="{affine(lab_x, lab_y, cz0 - .002)} scale(.001)"/>')
    cps = []
    for i in range(21):
        u = i / 20
        xx = (c1 - .05) * (1 - u) ** 2 + 2 * u * (1 - u) * (c1 + .45) + u * u * (xs[11] + .25)
        zz = (cz1 - .02) * (1 - u) ** 2 + 2 * u * (1 - u) * (-.85) + u * u * (-.02)
        cps.append((xx, .006, zz))
    a(path3(cps, t["frame"], 2.2))
    if eg:
        rob, rcss = robot_svg(t, cps, eg)
        a(rob)
        ecss.append(rcss)
    a(ell((lx0 + lx1) / 2, cy + .05, .5, .22, "url(#cool)", f' opacity="{.55 * t["screen_glow"]:.2f}" filter="url(#bl2)"', z=lz0))
    a("".join(cart))
    a(chair(t, st, c0 - .5, cz0 + .2, yaw_deg=58))
    if eg and eg["today"]:            # LED verde no carrinho: hoje houve commits
        a(dot(c1 - .035, cy + .018, .006, "#3fd67a", ' opacity=".95"', z=cz0 - .002))
        a(dot(c1 - .035, cy + .018, .02, "#3fd67a", ' opacity=".35" filter="url(#bl1)"', z=cz0 - .002))
    if "aniversario_conta" in ev:
        a(cupcake_svg(t, c1 - .12, cy + .035, cz0 + .025))
    a(ell((lx0 + lx1) / 2, cy + .15, .28, .2, "url(#cool)", f' opacity="{.5 * t["screen_glow"]:.2f}"', z=lz1 - .05))
    a(ell((c0 + c1) / 2, 0, .8, .5, "url(#cool)", f' opacity="{.35 * t["screen_glow"]:.2f}" filter="url(#bl2)"', z=cz0 - .3))

    # feixes volumetricos e poeira
    a("".join(beam_layers))

    # acabamento
    if t["grade_op"] > 0.01:
        a(f'<linearGradient id="gr" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["grade"]}" stop-opacity="0"/>'
          f'<stop offset=".55" stop-color="{t["grade"]}" stop-opacity="{t["grade_op"] * .18:.3f}"/><stop offset="1" stop-color="{t["grade"]}" stop-opacity="{t["grade_op"]:.3f}"/></linearGradient>')
        a(f'<rect width="{W}" height="{H}" fill="url(#gr)"/>')
    a(f'<radialGradient id="vig" cx=".42" cy=".5" r=".75"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="{t["vig"]:.3f}"/></radialGradient>')
    a(f'<rect width="{W}" height="{H}" fill="url(#vig)"/>')
    a(f'<rect width="{W}" height="{H}" filter="url(#grain)"/>')
    a(f'<rect width="{W}" height="{H}" filter="url(#graind)"/>')
    a('</g>')
    # aro subtil: le-se em fundo claro e escuro
    a(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="11.5" fill="none" stroke="#8b949e" stroke-opacity=".4"/>')
    a('<defs>' + "".join(ldefs) + '</defs>')
    a('</svg>')
    return "".join(o).replace("/*EGGS*/", "".join(ecss), 1)


FALLBACK_LEAD = 10     # minutos: a imagem de fallback tem entre 0 e ~25 min quando e vista


def render_full(days, local_dt, idp="", show=None, mode="live", lead_min=FALLBACK_LEAD):
    """mode="live": relogio exatamente na hora dada. mode="fallback": imagem que vai ser vista com atraso
    (Action + caches): so o ponteiro das horas (12 h, sem minutos nem segundos), adiantado lead_min minutos."""
    el, az = solar(to_utc(local_dt))
    st = state(el, az)
    eg = egg_cfg(days, local_dt)
    eg["show"] = show
    if mode == "fallback":
        eg["clock_dt"] = local_dt + timedelta(minutes=lead_min)
        eg["clock_fb"] = True
    return build(days, st, idp, eg=eg), st


def render(days, local_dt, mode="live"):
    """svg (string) da sala a hora local dada, com easter eggs."""
    return render_full(days, local_dt, mode=mode)[0]


# ---------------- timelapse (24 h em loop) ----------------
def _prefix(svg, p):
    import re
    body = re.sub(r"^<svg[^>]*>", "", svg)[:-len("</svg>")]
    body = re.sub(r"<style>.*?</style>", "", body, flags=re.S)
    body = re.sub(r'<rect x="\.5" y="\.5"[^>]*/>', "", body)          # aro: so um, no fim
    body = re.sub(r'id="([^"]+)"', lambda m: f'id="{p}{m.group(1)}"', body)
    body = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#{p}{m.group(1)})", body)
    return re.sub(r'href="#([^"]+)"', lambda m: f'href="#{p}{m.group(1)}"', body)


def _style(svg):
    import re
    return re.search(r"<style>.*?</style>", svg, flags=re.S).group(0)


def timelapse(days, day, secs=TL_SECS, n=48, static_at=(17, 30)):
    """Loop de 24 h: 6 camadas de paleta completas (noite, azul da manha, violeta do anoitecer, dia,
    dourado, rosado), cada uma com a sua luz de janela, empilhadas com opacidade animada; por cima,
    um feixe de sol por meia hora em crossfade. O ponteiro das horas do relogio e o painel do portatil andam com o loop
    (uma volta / um dia por ciclo). Estatico (sem CSS) = static_at."""
    import re
    samples = [day + timedelta(minutes=30 * i) for i in range(n + 1)]
    sts = [state(*solar(to_utc(t))) for t in samples]
    nosun = dict(dir=(0, -1, -1), str=0.0, col="#ffcf85", pcol="#ffd494", low=0)
    base = dict(dawn=0, dusk=0, rise=1, noon=0, day=0)
    lay = {
        "N": dict(base, t=NIGHT, sky=keyed(SKY_AM, -30), skyb=0, stars=1, street=1, sun=nosun),
        "B": dict(base, t=BLUE, sky=keyed(SKY_AM, -6), skyb=.3, stars=.2, street=.4, sun=nosun, dawn=1, rise=.6),
        "V": dict(base, t=DUSK, sky=keyed(SKY_PM, -6), skyb=.3, stars=.2, street=.5, sun=nosun, dusk=1),
        "D": dict(base, t=DAY, sky=keyed(SKY_AM, 35), skyb=1, stars=0, street=0, sun=nosun, day=1),
        "G": dict(base, t=GOLD, sky=keyed(SKY_PM, 6), skyb=.8, stars=0, street=0, sun=dict(nosun, str=.8, col=keyed(SUN_PM, 6)[0]), day=.6),
        "R": dict(base, t=ROSE, sky=keyed(SKY_AM, 3), skyb=.6, stars=0, street=0, sun=dict(nosun, str=.8, col=keyed(SUN_AM, 3)[0]), day=.4),
    }
    order = ["N", "B", "V", "D", "G", "R"]
    si = [i for i, t in enumerate(samples) if (t.hour, t.minute) == static_at][0]
    eg = egg_cfg(days, day, tl=True)
    eg["dt"] = samples[si]

    def ops(w):
        out, rem = {}, 1.0
        for k in reversed(order[1:]):
            v = w.get(k, 0)
            out[k] = v / rem if rem > 1e-6 else 0.0
            rem -= v
        return out
    opl = [ops(s_["w"]) for s_ in sts]
    css, parts = [], []
    first = None
    for k in order:
        svg = build(days, lay[k], draw_sun=False, eg=eg)
        first = first or svg
        if k == "N":
            parts.append(f'<g>{_prefix(svg, "N")}</g>')
            continue
        kf = "".join(f"{100 * i / n:.3f}%{{opacity:{opl[i][k]:.3f}}}" for i in range(n + 1))
        css.append(f"@keyframes L{k}{{{kf}}}.L{k}{{animation:L{k} {secs}s linear infinite}}")
        parts.append(f'<g class="L{k}" opacity="{opl[si][k]:.3f}">{_prefix(svg, k)}</g>')
    xs = layout()
    segs = shadow_segs(xs)
    for i, s_ in enumerate(sts[:-1]):
        if s_["sun"]["str"] <= 0.15:
            continue
        defs = []
        f_, b_ = sun_light(defs, s_, segs, f"s{i}", .25)
        kf = [f"{max(0, min(100, 100 * j / n)):.3f}%{{opacity:{1 if j == i else 0}}}" for j in (i - 1, i, i + 1)]
        pre = "0%{opacity:0}" if i > 1 else ""
        post = "100%{opacity:0}" if i < n - 1 else ""
        css.append(f"@keyframes s{i}{{{pre}{''.join(kf)}{post}}}.s{i}{{animation:s{i} {secs}s linear infinite}}")
        parts.append(f'<g class="s{i}" opacity="{1 if i == si else 0}" clip-path="url(#clip)"><defs>{"".join(defs)}</defs>{f_}{b_}</g>')
    css.append(f"@keyframes tlw{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}.tlw{{animation:tlw {secs}s linear infinite;transform-box:fill-box;transform-origin:0 0}}")
    head = re.match(r"^<svg[^>]*>", first).group(0)
    st0 = _style(first).replace("</style>", "".join(css) + "</style>")
    st0 = st0.replace("@media (prefers-reduced-motion:reduce){*{animation:none!important}}", "")              .replace("</style>", "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>")
    filt = "".join(re.findall(r'<filter id="bl[1234]".*?</filter>', first))
    return (head + st0 + f'<defs><clipPath id="clip"><rect width="{W}" height="{H}" rx="12"/></clipPath>{filt}</defs>'
            + "".join(parts)
            + f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="11.5" fill="none" stroke="#8b949e" stroke-opacity=".4"/></svg>')


# ---------------- galeria r9 ----------------
SLUG = "01-sala"
LIVE_AT = "2026-09-30T21:30"
MOMENTS = [("0030", "2026-09-30T00:30"), ("0650", "2026-09-30T06:50"), ("0740", "2026-09-30T07:40"), ("0930", "2026-09-30T09:30"),
           ("1330", "2026-09-30T13:30"), ("1745", "2026-09-30T17:45"), ("1920", "2026-09-30T19:20"), ("2015", "2026-09-30T20:15")]
SPECIAL = [("natal", "2026-12-24T22:00"), ("anonovo", "2026-12-31T23:58"), ("aniversario", "2026-10-24T18:00"),
           ("1abril", "2027-04-01T15:00"), ("madrugada", "2026-09-30T03:30")]
TITLE = "Sala de servidores (final)"
DESC = ("Versao para o perfil. Relogio de 24 h por cima da porta: meio-dia em cima, arco claro do nascer ao por do sol desse dia, "
        "um so ponteiro que da 1 volta por dia (ao vivo a velocidade real; no timelapse sincronizado com a luz, tambem sem animacao). "
        "Janela com folga dos dois lados e parapeito com a planta. LEDs nitidos de dia e com halo so de noite. Luz da janela so a volta dela. "
        "Meio-dia com sol alto: feixe curto e ingreme sobre as estantes, com poeira. Cadeira refeita, caneca fora do ecra, painel a ler-se "
        "como 'estamos a X/24 do dia'. Etiqueta nOxieD em fita preta discreta. Easter eggs mantidos (robot, cobra, reboot, gato, natal, "
        "fogo de artificio, abobora, queque, 1 de abril, post-it de sexta, dia do pico, lua real)")


def gallery(days, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    jobs = [("agora", LIVE_AT)] + MOMENTS + SPECIAL
    for tag, at in jobs:
        t0 = time.time()
        svg, st = render_full(days, datetime.fromisoformat(at))
        (folder / f"{SLUG}-{tag}.svg").write_text(svg, encoding="utf-8")
        print(f"{tag}: elev {st['el']:.1f} | {len(svg) / 1024:.0f} KB | {time.time() - t0:.2f}s")
    t0 = time.time()
    svg = timelapse(days, datetime(2026, 9, 30))
    (folder / f"{SLUG}-timelapse.svg").write_text(svg, encoding="utf-8")
    print(f"timelapse: {len(svg) / 1024:.0f} KB | {time.time() - t0:.2f}s")
    cell = lambda t: f'<td><img alt="" src="assets/{SLUG}-{t}.svg" width="200"></td>'
    md = "\n".join([f"<!-- {TITLE} | {DESC} -->",
                    f'<img alt="" src="assets/{SLUG}-agora.svg" width="100%">', "",
                    f'<img alt="" src="assets/{SLUG}-timelapse.svg" width="100%">', "",
                    "<table><tr>" + "".join(cell(m[0]) for m in MOMENTS[:4]) + "</tr><tr>" + "".join(cell(m[0]) for m in MOMENTS[4:]) + "</tr></table>", "",
                    "<table><tr>" + "".join(cell(m[0]) for m in SPECIAL) + "</tr></table>", ""])
    (folder / f"{SLUG}.md").write_text(md, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("contrib")
    ap.add_argument("out", help="ficheiro .svg (ou pasta, com --gallery)")
    ap.add_argument("--at", help="hora local Europe/Lisbon, ex. 2026-09-30T19:10")
    ap.add_argument("--gallery", action="store_true", help="gera a galeria r9 (ao vivo, timelapse, momentos, datas especiais) na pasta out")
    ap.add_argument("--show", help="depuracao: mostra parado um evento raro (robot, snake, reboot)")
    a = ap.parse_args()
    if a.gallery:
        gallery(load(a.contrib), a.out)
        return
    local = datetime.fromisoformat(a.at) if a.at else now_local()
    t0 = time.time()
    svg, st = render_full(load(a.contrib), local, show=a.show)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(svg, encoding="utf-8")
    print(f"{local:%Y-%m-%d %H:%M} Lisboa | sol elev {st['el']:.1f} az {st['az']:.0f} | feixe {st['sun']['str']:.2f} "
          f"| {len(svg) / 1024:.0f} KB | {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
