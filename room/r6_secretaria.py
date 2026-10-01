"""R6 / 03: a secretaria (evolucao da r5/07), panorama 830x260.

Um quarto de programador visto por tras da cadeira: janela grande com a cidade, radiador,
secretaria com monitor, portatil, teclado mecanico, caderno sob o candeeiro, prateleira de
parede com um cluster de Raspberry Pi, estante com NAS / switch / router, servidor debaixo da
mesa, auscultadores pendurados, plantas em primeiro plano.

Dois MOMENTOS da mesma cena:
  escuro = noite de chuva: o candeeiro e o monitor iluminam de verdade (mascara de luz com
           queda suave, sombras projetadas, cone volumetrico com po a flutuar).
  claro  = fim de tarde: o sol baixo entra pela janela, raios com po, mancha dourada no chao,
           candeeiro apagado, cidade contra o por do sol.

Timelapse dos ultimos 12 meses (ate ao corrente), 2 s por mes, dados reais (data/contrib.json):
  - o ecra do monitor mostra o grafico de contribuicoes a encher-se mes a mes;
  - brilho do monitor / candeeiro / luz do quarto = atividade do mes (meses parados: apagado);
  - chavenas vazias acumulam-se na mesa (o mes mais ativo enche-a); a mais recente fumega;
  - o calendario de parede vira a folha, com os dias ativos marcados;
  - o portatil mostra a curva semanal do ano.
O estado sem animacao (as capturas tiram o <style>) e a noite / tarde do mes mais ativo.

Uso: python tools/r6_03_secretaria-noite.py [data/contrib.json] [rondas/r6]
"""
import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    from .r5_common_a import months_ending
except ImportError:                       # corrido como script solto
    from r5_common_a import months_ending

W, H = 830, 260
FL = 214            # linha do chao junto a parede
VPX, VPY = 462, 112  # ponto de fuga (altura dos olhos)
DUR = 24
# os 12 meses sao calculados em build() (os ultimos 12 ate ao mes de referencia, o corrente e o ultimo);
# MARCH (o frame estatico) e o mes com mais contribuicoes. BAND: cor do calendario por mes do ano, a comecar em outubro.
BAND = ["#b8683a", "#8f5b3e", "#56708f", "#6b7d9c", "#7b8ea6", "#5f9460",
        "#86b061", "#c0a948", "#d79a3a", "#d07c2c", "#bb612f", "#9f653b"]

# secretaria
DB, DF = 144, 152   # rebordo de tras / da frente do tampo
DX0, DX1 = 294, 640
# monitor
MX0, MX1, MY0, MY1 = 392, 532, 66, 130
# candeeiro
LB = (614, 149)
LE = (630, 100)
LJ = (590, 79)
LT = (566, 147)


def load(path):
    cal = json.load(open(path, encoding="utf-8"))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = {date.fromisoformat(d["date"]): d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]}
    weeks = [[(date.fromisoformat(d["date"]), d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]]
    return days, weeks


def keyframes(name, vals, prop="opacity", e=0.45):
    P = 100 / 12
    pts = [(0, vals[0])]
    for m, v in enumerate(vals):
        pts.append((m * P + e, v))
        pts.append(((m + 1) * P - e, v))
    pts.append((100, vals[0]))
    body = "".join(f"{p:.2f}%{{{prop}:{v:.3g}}}" for p, v in pts)
    return f"@keyframes {name}{{{body}}}"


def month_idx(d, months):
    for i, (y, m) in enumerate(months):
        if (d.year, d.month) == (y, m):
            return i
    return 0 if d < date(*months[0], 1) else 11


def catmull(pts, n=10):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    out.append(pts[-1])
    return out


def monstera_leaf(seed, splits=4):
    """Folha de monstera em coords locais: pe em (0,0), ponta em (0,-1). Devolve path d."""
    r = random.Random(seed)
    right = [(0, 0.02), (0.14, 0.13), (0.38, 0.1), (0.58, -0.1), (0.64, -0.4), (0.55, -0.7), (0.3, -0.93), (0.02, -1.02)]
    out = []
    for side in (1, -1):
        s = catmull([(x * side * r.uniform(0.93, 1.05), y) for x, y in right], 8)
        n = len(s)
        cuts = sorted(r.sample(range(12, n - 8, 3), splits))
        res = []
        skip = set()
        for i, p in enumerate(s):
            if i in skip:
                continue
            if i in cuts and i + 2 < n:
                q = s[i + 2]
                depth = r.uniform(0.5, 0.72)
                mx_, my_ = 0, (p[1] + q[1]) / 2 - 0.08
                ip = ((p[0] + q[0]) / 2 * (1 - depth) + mx_ * depth, ((p[1] + q[1]) / 2) * (1 - depth) + my_ * depth)
                res += [p, ip, q]
                skip.update({i + 1, i + 2})
            else:
                res.append(p)
        out.append(res if side == 1 else list(reversed(res)))
    pts = out[0] + out[1]
    return "M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in pts) + "Z"


def hull(pts):
    pts = sorted(set(pts))
    def cross(o, a_, b_):
        return (a_[0] - o[0]) * (b_[1] - o[1]) - (a_[1] - o[1]) * (b_[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def poly(pts):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"


GLASS = (78, 24, 242, 116)
PANES = [((0, 0.49), (0, 0.41)), ((0.51, 1), (0, 0.41)), ((0, 0.49), (0.45, 1)), ((0.51, 1), (0.45, 1))]


def floorpt(u, v):
    """Ponto do vidro (u,v) projetado no chao pelo sol baixo (v=1 = base do vidro)."""
    xt, xb = 330 + 250 * u, 104 + 140 * u
    return (xt + (xb - xt) * v, 290 + (224 - 290) * v)


def glasspt(u, v):
    return (GLASS[0] + (GLASS[2] - GLASS[0]) * u, GLASS[1] + (GLASS[3] - GLASS[1]) * v)


def build(days, weeks, mode, ref=None):
    dark = mode == "dark"
    MONTHS = months_ending(ref or max(days))
    mc = [sum(c for d, c in days.items() if (d.year, d.month) == ym) for ym in MONTHS]
    MARCH = max(range(12), key=lambda i: (mc[i], i))      # frame estatico: o mes mais ativo
    peak = max(max(mc), 1)
    f = [math.sqrt(c / peak) for c in mc]
    on = [c >= 5 for c in mc]
    cups = [0 if not on[m] else max(1, round(8 * f[m])) for m in range(12)]
    o = []
    a = o.append
    css = []

    C = dict(
        dark=dict(wall0="#4a4046", wall1="#3c3339", base="#2c2428", fl0="#4a3428", fl1="#5e4231", seam="#1c130f",
                  frame="#cfc6b8", frame_d="#9d9488", sill="#d8cfc2", rad="#c2bbb0", rad_d="#8f887e", cur0="#46575e", cur1="#5c6f76",
                  desk0="#9a6f4b", desk1="#7d5a3c", edge="#5a3f2a", metal="#2b2a2f", rug="#384152", rug2="#4b5568",
                  chair="#2a292f", chair2="#36353c", mesh="#1d1c21", book=["#6b3f3a", "#35506a", "#7a6a45", "#3f5d4c", "#5a4668", "#8a5a3a", "#2f3b4f"],
                  ov="#05070f", ovop=0.87),
        light=dict(wall0="#ecdcc6", wall1="#e2d0b8", base="#cdb99f", fl0="#b58962", fl1="#c9996c", seam="#8c6546",
                   frame="#f6f0e6", frame_d="#d6ccbe", sill="#f7f1e7", rad="#ebe5dc", rad_d="#c4bcb0", cur0="#cdbb9f", cur1="#e2d3bb",
                   desk0="#c08e60", desk1="#a3754c", edge="#7c5638", metal="#33323a", rug="#7c5a4e", rug2="#9b7564",
                   chair="#2f2e35", chair2="#46454d", mesh="#24232a", book=["#8b4d45", "#46678a", "#a58e5a", "#557a62", "#76608a", "#b0703f", "#3f4e66"],
                   ov="#2a1c34", ovop=0.5),
    )[mode]

    # ------------------------------------------------------------------ defs
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
    a("<defs>")
    a(f'<clipPath id="card"><rect width="{W}" height="{H}" rx="12"/></clipPath>')
    a('<clipPath id="glass"><rect x="78" y="24" width="164" height="92"/></clipPath>')
    a(f'<clipPath id="screen"><rect x="{MX0 + 3}" y="{MY0 + 3}" width="{MX1 - MX0 - 6}" height="{MY1 - MY0 - 6}"/></clipPath>')
    a(f'<clipPath id="wallc"><rect x="0" y="0" width="{W}" height="{FL}"/></clipPath>')
    a(f'<linearGradient id="wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C["wall0"]}"/><stop offset="1" stop-color="{C["wall1"]}"/></linearGradient>')
    a(f'<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C["fl0"]}"/><stop offset="1" stop-color="{C["fl1"]}"/></linearGradient>')
    if dark:
        a('<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0a1222"/><stop offset="0.55" stop-color="#16213a"/><stop offset="0.85" stop-color="#2e2f47"/><stop offset="1" stop-color="#4a3a48"/></linearGradient>')
    else:
        a('<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7f93c2"/><stop offset="0.35" stop-color="#b9a1b8"/><stop offset="0.62" stop-color="#eaa987"/><stop offset="0.85" stop-color="#fbc486"/><stop offset="1" stop-color="#ffdca2"/></linearGradient>')
    a(f'<linearGradient id="deskt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C["desk1"]}"/><stop offset="1" stop-color="{C["desk0"]}"/></linearGradient>')
    a(f'<linearGradient id="cur" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C["cur0"]}"/><stop offset="0.2" stop-color="{C["cur1"]}"/><stop offset="0.35" stop-color="{C["cur0"]}"/><stop offset="0.55" stop-color="{C["cur1"]}"/><stop offset="0.75" stop-color="{C["cur0"]}"/><stop offset="0.9" stop-color="{C["cur1"]}"/><stop offset="1" stop-color="{C["cur0"]}"/></linearGradient>')
    a('<linearGradient id="scrbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#141b2c"/><stop offset="1" stop-color="#0c111c"/></linearGradient>')
    a('<linearGradient id="gloss" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0.09"/><stop offset="0.45" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    a(f'<linearGradient id="chairg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C["chair"]}"/><stop offset="0.5" stop-color="{C["chair2"]}"/><stop offset="1" stop-color="{C["chair"]}"/></linearGradient>')
    a('<linearGradient id="metalg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#9aa0a8"/><stop offset="0.5" stop-color="#d7dbe0"/><stop offset="1" stop-color="#7d838c"/></linearGradient>')
    # buracos de luz para a mascara (preto = sem escuridao)
    def hole(id_, stops):
        a(f'<radialGradient id="{id_}">' + "".join(f'<stop offset="{s}" stop-color="#000" stop-opacity="{op}"/>' for s, op in stops) + "</radialGradient>")
    hole("hLamp", [(0, 1), (0.25, 0.9), (0.55, 0.55), (0.8, 0.2), (1, 0)])
    hole("hMon", [(0, 0.85), (0.45, 0.5), (0.8, 0.15), (1, 0)])
    hole("hWin", [(0, 0.7), (0.5, 0.35), (1, 0)])
    hole("hSoft", [(0, 1), (1, 0)])

    def glow(id_, col, stops):
        a(f'<radialGradient id="{id_}">' + "".join(f'<stop offset="{s}" stop-color="{col}" stop-opacity="{op}"/>' for s, op in stops) + "</radialGradient>")
    glow("gWarm", "#ff9a45", [(0, 0.5), (0.4, 0.24), (1, 0)])
    glow("gPool", "#ffd49a", [(0, 0.85), (0.5, 0.35), (1, 0)])
    glow("gCool", "#6f9bff", [(0, 0.3), (0.5, 0.12), (1, 0)])
    glow("gCoolPool", "#a9c3ff", [(0, 0.45), (1, 0)])
    glow("gSun", "#fff0c8", [(0, 1), (0.2, 0.8), (0.5, 0.25), (1, 0)])
    glow("gCity", "#ff9d5c", [(0, 0.35), (1, 0)])
    glow("gLed", "#ffffff", [(0, 0.9), (1, 0)])
    glow("gShadow", "#000", [(0, 0.55), (1, 0)])
    a('<linearGradient id="cone" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd9a0" stop-opacity="0.75"/><stop offset="0.6" stop-color="#ffc27a" stop-opacity="0.25"/><stop offset="1" stop-color="#ffb466" stop-opacity="0.04"/></linearGradient>')
    a('<linearGradient id="beam" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffd79a" stop-opacity="0.55"/><stop offset="1" stop-color="#ffb870" stop-opacity="0"/></linearGradient>')
    a('<radialGradient id="vig" cx="0.5" cy="0.45" r="0.8"><stop offset="0.5" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="%s"/></radialGradient>' % (0.55 if dark else 0.28))
    for s in (0.6, 1.2, 2, 3, 5, 9, 14):
        a(f'<filter id="b{str(s).replace(".", "_")}" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="{s}"/></filter>')
    a('<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7"/>'
      '<feColorMatrix values="0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 1.6 -0.55"/></filter>')
    B = lambda s: f'filter="url(#b{str(s).replace(".", "_")})"'

    # ------------------------------------------------------------------ mascaras de luz
    panes = [[floorpt(u, v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))] for (u0, u1), (v0, v1) in PANES]
    sunpatch = " ".join(poly(q) for q in panes)
    beams = [poly(hull(q + [glasspt(u, v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]))
             for q, ((u0, u1), (v0, v1)) in zip(panes, PANES)]
    a(f'<mask id="mLit" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">')
    a(f'<rect width="{W}" height="{H}" fill="#fff"/>')
    if dark:
        a('<ellipse cx="566" cy="140" rx="200" ry="140" fill="url(#hLamp)"/>')
        a('<ellipse cx="566" cy="150" rx="90" ry="40" fill="url(#hLamp)"/>')
        a('<ellipse cx="462" cy="112" rx="170" ry="120" fill="url(#hMon)"/>')
        a('<ellipse cx="160" cy="80" rx="150" ry="130" fill="url(#hWin)"/>')
        a('<ellipse cx="170" cy="238" rx="130" ry="30" fill="url(#hWin)"/>')
        a('<ellipse cx="600" cy="120" rx="130" ry="70" fill="url(#hLamp)" opacity="0.5"/>')
    else:
        a('<ellipse cx="170" cy="90" rx="300" ry="220" fill="url(#hWin)"/>')
        a('<ellipse cx="170" cy="100" rx="150" ry="120" fill="url(#hWin)"/>')
        a(f'<path d="{sunpatch}" fill="#000" {B(2)}/>')
        a("".join(f'<path d="{b_}" fill="#000" opacity="0.18" {B(6)}/>' for b_ in beams))
        a('<ellipse cx="462" cy="112" rx="120" ry="90" fill="url(#hMon)" opacity="0.6"/>')
    a('<rect x="78" y="24" width="164" height="92" fill="#000"/>')
    a("</mask>")
    a(f'<mask id="mDim" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#fff"/>'
      '<rect x="78" y="24" width="164" height="92" fill="#000"/><ellipse cx="160" cy="80" rx="120" ry="110" fill="url(#hWin)"/></mask>')
    a("</defs>")

    # ------------------------------------------------------------------ timelapse css
    anim = lambda cls, name: css.append(f".{cls}{{animation:{name} {DUR}s linear infinite}}")
    mon = [0.35 + 0.65 * f[m] if on[m] else 0 for m in range(12)]
    lamp = [0.55 + 0.45 * f[m] if on[m] else 0 for m in range(12)]
    dim = [0 if f[m] >= 0.99 else (0.8 if not on[m] else 0.5 * (1 - f[m])) for m in range(12)]
    if not dark:
        dim = [0 if on[m] else 0.35 for m in range(12)]
    css.append(keyframes("kmon", mon)); anim("mon", "kmon")
    css.append(keyframes("klamp", lamp)); anim("lamp", "klamp")
    css.append(keyframes("kscr", [1 if on[m] else 0 for m in range(12)])); anim("scr", "kscr")
    css.append(keyframes("koff", [0 if on[m] else 1 for m in range(12)])); anim("off", "koff")
    css.append(keyframes("kdim", dim)); anim("dim", "kdim")
    for k in range(8):
        css.append(keyframes(f"kc{k}", [1 if cups[m] > k else 0 for m in range(12)])); anim(f"c{k}", f"kc{k}")
        css.append(keyframes(f"ks{k}", [1 if cups[m] == k + 1 else 0 for m in range(12)])); anim(f"s{k}", f"ks{k}")
    for m in range(12):
        css.append(keyframes(f"kp{m}", [1 if i == m else 0 for i in range(12)])); anim(f"p{m}", f"kp{m}")
        css.append(keyframes(f"kh{m}", [1 if i >= m else 0 for i in range(12)])); anim(f"h{m}", f"kh{m}")
    css.append(".rn{animation:rn .6s linear infinite}.rn2{animation:rn .85s linear infinite}@keyframes rn{from{transform:translate(0,-46px)}to{transform:translate(-7px,0)}}")
    css.append(".dr{animation:dr 7s ease-in infinite}@keyframes dr{0%{transform:translateY(0);opacity:0}8%{opacity:1}70%{transform:translateY(0)}100%{transform:translateY(40px);opacity:0}}")
    css.append(".code{animation:code 12s steps(24) infinite}@keyframes code{to{transform:translateY(-72px)}}")
    css.append(".cur{animation:cur 1.1s steps(1) infinite}@keyframes cur{50%{opacity:0}}")
    css.append(".led{animation:led 1.7s steps(1) infinite}@keyframes led{0%{opacity:1}30%{opacity:.25}45%{opacity:1}60%{opacity:.35}}")
    css.append(".blink{animation:blink 3s steps(1) infinite}@keyframes blink{0%{opacity:1}6%{opacity:0}}")
    css.append(".tw{animation:tw 9s steps(1) infinite}@keyframes tw{0%{opacity:1}50%{opacity:0}}")
    css.append(".stm{animation:stm 3.4s linear infinite}@keyframes stm{from{stroke-dashoffset:36}to{stroke-dashoffset:0}}")
    css.append(".hh{animation:rot 24s linear infinite}.mh{animation:rot 2s linear infinite}@keyframes rot{to{transform:rotate(360deg)}}")
    css.append(".sway{transform-box:fill-box;transform-origin:50% 0;animation:sway 7s ease-in-out infinite alternate}@keyframes sway{from{transform:rotate(-1.5deg)}to{transform:rotate(2deg)}}")
    css.append(".swb{transform-box:fill-box;transform-origin:50% 100%;animation:swb 9s ease-in-out infinite alternate}@keyframes swb{from{transform:rotate(-1deg)}to{transform:rotate(1.2deg)}}")
    css.append(".mote{animation:mote 14s ease-in-out infinite alternate}@keyframes mote{0%{transform:translate(0,0);opacity:.2}50%{opacity:.9}100%{transform:translate(9px,-16px);opacity:.3}}")
    css.append(".plane{animation:plane 38s linear infinite}@keyframes plane{from{transform:translate(0,0)}to{transform:translate(200px,-14px)}}")
    css.append(".cloud{animation:cloud 60s linear infinite alternate}@keyframes cloud{to{transform:translate(26px,0)}}")
    css.append(".spark{animation:spark 6s linear infinite}@keyframes spark{to{transform:translate(-24px,0)}}")
    css.append(".fl{animation:fl 3.3s ease-in-out infinite alternate}@keyframes fl{from{opacity:.85}to{opacity:1}}")

    a("<style>" + "".join(css) + "</style>")
    a('<g clip-path="url(#card)">')

    # ================================================================== PAREDE
    a(f'<rect width="{W}" height="{H}" fill="url(#wall)"/>')
    # textura suave de reboco
    rr = random.Random(4)

    # ------------------------------------------------------------------ JANELA (exterior)
    a('<g clip-path="url(#glass)">')
    a('<rect x="78" y="24" width="164" height="92" fill="url(#sky)"/>')
    if dark:
        a('<ellipse cx="160" cy="118" rx="120" ry="34" fill="url(#gCity)"/>')
        # avião (luz a piscar a atravessar)
        a('<g class="plane"><g transform="translate(40 44)"><circle cx="0" cy="0" r="0.7" fill="#ff6a5a" class="blink"/><circle cx="3" cy="0.3" r="0.5" fill="#dfe8ff" class="blink" style="animation-delay:-1.4s"/></g></g>')
    else:
        # nuvens com a parte de baixo rosada
        a('<g class="cloud" opacity="0.8">')
        for cx_, cy_, rx_, ry_ in [(110, 40, 30, 3.2), (132, 37, 18, 2.4), (200, 50, 36, 3.4), (225, 46, 16, 2.2), (95, 60, 22, 2)]:
            a(f'<ellipse cx="{cx_}" cy="{cy_}" rx="{rx_}" ry="{ry_}" fill="#f6c3a8" {B(0.6)}/><ellipse cx="{cx_}" cy="{cy_ + 1}" rx="{rx_ * 0.8:.1f}" ry="{ry_ * 0.5:.1f}" fill="#ffd8b0"/>')
        a("</g>")
        # sol baixo
        a('<circle cx="196" cy="80" r="60" fill="url(#gSun)" opacity="0.8"/>')
        a('<circle cx="196" cy="80" r="7" fill="#fff6dc"/>')
    br = random.Random(3)
    layers = ([("#2a3553", 102, 8, 26, 0.08, "#c9a37a"), ("#1c2440", 108, 12, 44, 0.16, "#ffcf85"), ("#11172b", 114, 18, 70, 0.2, "#ffd796")] if dark else
              [("#b89aa8", 102, 8, 26, 0.0, "#ffe2a8"), ("#8d7390", 108, 12, 44, 0.03, "#ffe4a0"), ("#5d4a68", 114, 18, 70, 0.05, "#ffe9b0")])
    for li, (col, y0, hmin, hmax, lit, wcol) in enumerate(layers):
        x = 70
        bl, wl, tw = [], [], []
        while x < 250:
            bw = br.uniform(8, 22) * (1 + li * 0.25)
            bh = br.uniform(hmin, hmax)
            if li == 2 and br.random() < 0.55:
                x += bw * 1.4
                continue
            top = y0 + 4 - bh
            bl.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{bh + 30:.1f}"/>')
            if li == 2 and br.random() < 0.3:
                bl.append(f'<rect x="{x + bw * 0.3:.1f}" y="{top - 5:.1f}" width="{bw * 0.4:.1f}" height="6"/>')
            for yy in range(int(top + 3), 118, 3 + li):
                for xx in range(int(x + 2), int(x + bw - 2), 3 + li):
                    if br.random() < lit:
                        r_ = f'<rect x="{xx}" y="{yy}" width="{1 + li * 0.4:.1f}" height="{1.3 + li * 0.4:.1f}"/>'
                        (tw if br.random() < 0.06 else wl).append(r_)
            x += bw + br.uniform(0, 3)
        a(f'<g fill="{col}">{"".join(bl)}</g>')
        if wl:
            a(f'<g fill="{wcol}" opacity="{0.55 + 0.2 * li}">{"".join(wl)}</g>')
        if tw:
            a(f'<g fill="{wcol}" class="tw" style="animation-delay:-{li * 3}s">{"".join(tw)}</g>')
        if not dark:
            # contraluz: borda dourada nos predios
            a(f'<g fill="#ffcf8f" opacity="{0.25 - li * 0.06:.2f}">' + "".join(
                b.replace('height="', 'data-h="').replace("<rect", '<rect height="0.8"') for b in bl) + "</g>")
    if not dark:
        a('<circle cx="196" cy="80" r="34" fill="url(#gSun)" opacity="0.55" style="mix-blend-mode:screen"/>')
    # antena com luz vermelha
    a('<path d="M214,62 V48" stroke="%s" stroke-width="0.8"/><circle cx="214" cy="47.5" r="0.9" fill="#ff4a3a" class="blink"/>' % ("#0c1120" if dark else "#5d4a68"))
    if dark:
        a('<rect x="78" y="80" width="164" height="36" fill="#5a6a86" opacity="0.18"/>')  # nevoa da chuva
        bo = random.Random(77)
        a(f'<g {B(1.2)}>' + "".join(f'<circle cx="{bo.uniform(82, 238):.1f}" cy="{bo.uniform(84, 114):.1f}" r="{bo.uniform(1.5, 3.2):.1f}" fill="{bo.choice(["#ffc27a", "#ffd9a0", "#9fc0ff", "#ff9d6a"])}" opacity="{bo.uniform(0.25, 0.5):.2f}"/>' for _ in range(16)) + "</g>")
        for cls, n, op, ln, sd in (("rn", 90, 0.3, 9, 1), ("rn2", 70, 0.45, 14, 2)):
            r2 = random.Random(sd)
            ls = "".join(f'<path d="M{r2.uniform(78, 250):.1f},{r2.uniform(-20, 118):.1f} l-1.5,{ln}"/>' for _ in range(n))
            a(f'<g class="{cls}"><g stroke="#aac2e2" stroke-width="0.55" opacity="{op}">{ls}</g></g>')
        gr = random.Random(9)
        drops = []
        for _ in range(70):
            x, y, r = gr.uniform(79, 241), gr.uniform(25, 115), gr.choice([0.5, 0.7, 0.9, 1.1, 1.4])
            drops.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#1a2438" stroke="#a9bedb" stroke-width="0.3" opacity="0.8"/>'
                         f'<circle cx="{x - r * 0.3:.1f}" cy="{y - r * 0.35:.1f}" r="{r * 0.3:.2f}" fill="#e6eef9" opacity="0.75"/>')
        a("".join(drops))
        for k, (x, y) in enumerate([(96, 40), (132, 52), (186, 34), (228, 58)]):
            a(f'<g class="dr" style="animation-delay:-{k * 1.9:.1f}s"><path d="M{x},{y - 16} v16" stroke="#a9bedb" stroke-width="0.5" opacity="0.3"/>'
              f'<circle cx="{x}" cy="{y}" r="1.5" fill="#1a2438" stroke="#b7cae6" stroke-width="0.4"/><circle cx="{x - 0.5}" cy="{y - 0.6}" r="0.45" fill="#eef4fb"/></g>')
        # reflexo do candeeiro no vidro
    else:
        a('<rect x="78" y="86" width="164" height="30" fill="#ffc88a" opacity="0.25"/>')
        # algumas gotas a secar, com brilho do sol
        gr = random.Random(11)
        a("".join(f'<circle cx="{gr.uniform(80, 240):.1f}" cy="{gr.uniform(26, 114):.1f}" r="{gr.choice([0.4, 0.6, 0.8])}" fill="#fff4dc" opacity="{gr.uniform(0.3, 0.8):.2f}"/>' for _ in range(28)))
    a('<rect x="78" y="24" width="164" height="92" fill="url(#gloss)"/>')
    a("</g>")

    # caixilho (branco) + peitoril
    fr, frd = C["frame"], C["frame_d"]
    a(f'<path d="M70,16 h180 v108 h-180Z M78,24 v92 h164 v-92Z" fill="{fr}" fill-rule="evenodd"/>')
    a(f'<path d="M78,24 h164 v2 h-162 v90 h-2Z" fill="{frd}"/>')
    a(f'<rect x="158" y="24" width="4.5" height="92" fill="{fr}"/><rect x="158" y="24" width="1.2" height="92" fill="{frd}"/>')
    a(f'<rect x="78" y="62" width="164" height="3.5" fill="{fr}"/><rect x="78" y="65.5" width="164" height="0.8" fill="{frd}"/>')
    a(f'<rect x="150" y="66" width="1.5" height="6" rx="0.7" fill="{frd}"/>')  # puxador
    a(f'<path d="M62,124 h196 l4,5 h-204Z" fill="{C["sill"]}"/><rect x="58" y="129" width="204" height="2.5" fill="{frd}"/>')

    # radiador
    a(f'<rect x="104" y="152" width="120" height="46" rx="2" fill="{C["rad"]}"/>')
    a(f'<g fill="{C["rad_d"]}" opacity="0.8">' + "".join(f'<rect x="{106 + k * 6.5:.1f}" y="154" width="1.6" height="42" rx="0.8"/>' for k in range(18)) + "</g>")
    a('<g fill="#fff" opacity="0.25">' + "".join(f'<rect x="{109 + k * 6.5:.1f}" y="154" width="1" height="42"/>' for k in range(18)) + "</g>")
    a(f'<path d="M110,198 v16 M218,198 v16" stroke="{C["rad_d"]}" stroke-width="2.4"/><rect x="214" y="200" width="8" height="5" rx="1" fill="{C["rad_d"]}"/>')
    a(f'<rect x="104" y="196" width="120" height="3" fill="#000" opacity="0.15"/>')

    # cortinas (varao + duas abas)
    a(f'<rect x="36" y="8" width="244" height="2.4" rx="1.2" fill="{C["metal"]}"/><circle cx="36" cy="9.2" r="2.4" fill="{C["metal"]}"/><circle cx="280" cy="9.2" r="2.4" fill="{C["metal"]}"/>')
    a(f'<path d="M44,10 C46,70 42,150 40,212 L80,212 C76,150 74,60 72,10Z" fill="url(#cur)"/>')
    a(f'<path d="M252,10 C254,60 256,150 262,212 L282,212 C280,150 278,70 276,10Z" fill="url(#cur)"/>')
    a('<path d="M44,10 C46,70 42,150 40,212" stroke="#000" stroke-opacity="0.15" stroke-width="1" fill="none"/>')

    # ------------------------------------------------------------------ parede da secretaria
    # relogio
    ccx, ccy = 290, 34
    a(f'<circle cx="{ccx + 1}" cy="{ccy + 1.5}" r="12" fill="#000" opacity="0.25" {B(1.2)}/>')
    a(f'<circle cx="{ccx}" cy="{ccy}" r="12" fill="#2c262c"/><circle cx="{ccx}" cy="{ccy}" r="10.4" fill="#e9e2d6"/>')
    a("".join(f'<path d="M{ccx + 8.4 * math.cos(t * math.pi / 6):.2f},{ccy + 8.4 * math.sin(t * math.pi / 6):.2f} L{ccx + 9.6 * math.cos(t * math.pi / 6):.2f},{ccy + 9.6 * math.sin(t * math.pi / 6):.2f}" stroke="#3a3238" stroke-width="{1 if t % 3 == 0 else 0.45}"/>' for t in range(12)))
    a(f'<g class="hh" style="transform-origin:{ccx}px {ccy}px"><path d="M{ccx},{ccy} L{ccx - 3},{ccy - 4.6}" stroke="#221c22" stroke-width="1.4" stroke-linecap="round"/></g>')
    a(f'<g class="mh" style="transform-origin:{ccx}px {ccy}px"><path d="M{ccx},{ccy} L{ccx + 4.6},{ccy - 6.4}" stroke="#221c22" stroke-width="0.8" stroke-linecap="round"/></g>')
    a(f'<circle cx="{ccx}" cy="{ccy}" r="0.9" fill="#221c22"/>')

    # calendario de parede (folha do mes)
    cx0, cy0 = 316, 34
    a(f'<circle cx="{cx0 + 19}" cy="{cy0 - 5}" r="1" fill="#3a3035"/><path d="M{cx0 + 19},{cy0 - 5} L{cx0 + 6},{cy0} M{cx0 + 19},{cy0 - 5} L{cx0 + 32},{cy0}" stroke="#3a3035" stroke-width="0.5"/>')
    a(f'<rect x="{cx0 + 2}" y="{cy0 + 2}" width="38" height="46" fill="#000" opacity="0.3" {B(1.2)}/>')
    for m, (yy, mm) in enumerate(MONTHS):
        first = date(yy, mm, 1)
        nd = (date(yy + (mm == 12), mm % 12 + 1, 1) - first).days
        off = first.weekday()
        cells = []
        for d in range(nd):
            k = off + d
            cxx = cx0 + 3.5 + (k % 7) * 5
            cyy = cy0 + 17 + (k // 7) * 5
            c = days.get(date(yy, mm, d + 1), 0)
            if c:
                col = "#d9822f" if c < 40 else "#b8421f"
                cells.append(f'<rect x="{cxx}" y="{cyy}" width="3.8" height="3.8" rx="0.5" fill="{col}"/>')
            else:
                cells.append(f'<rect x="{cxx}" y="{cyy}" width="3.8" height="3.8" rx="0.5" fill="#9a8f82" opacity="0.35"/>')
        vis = "1" if m == MARCH else "0"
        # imagem do mes no topo (faixa de cor com uma "paisagem" abstrata)
        a(f'<g class="p{m}" opacity="{vis}"><rect x="{cx0}" y="{cy0}" width="38" height="47" fill="#f1ebe0"/>'
          f'<rect x="{cx0 + 2}" y="{cy0 + 2}" width="34" height="12" fill="{BAND[(mm - 10) % 12]}"/>'
          f'<path d="M{cx0 + 2},{cy0 + 14} L{cx0 + 12},{cy0 + 8} L{cx0 + 19},{cy0 + 11} L{cx0 + 28},{cy0 + 6} L{cx0 + 36},{cy0 + 12} V{cy0 + 14}Z" fill="#000" opacity="0.18"/>'
          f'{"".join(cells)}</g>')
    a(f'<rect x="{cx0}" y="{cy0}" width="38" height="1.2" fill="#fff" opacity="0.4"/>')

    # quadro emoldurado por cima do monitor (horizonte abstrato)
    qx, qy, qw, qh = 424, 14, 76, 44
    a(f'<rect x="{qx + 3}" y="{qy + 3}" width="{qw}" height="{qh}" fill="#000" opacity="0.3" {B(2)}/>')
    a(f'<rect x="{qx}" y="{qy}" width="{qw}" height="{qh}" fill="#241e1c"/><rect x="{qx + 2.5}" y="{qy + 2.5}" width="{qw - 5}" height="{qh - 5}" fill="#efe8dc"/>')
    ix, iy, iw, ih = qx + 10, qy + 9, qw - 20, qh - 18
    a(f'<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" fill="#d8c3a4"/>')
    a(f'<circle cx="{ix + iw * 0.66:.1f}" cy="{iy + ih * 0.48:.1f}" r="5" fill="#c9683e"/>')
    a(f'<path d="M{ix},{iy + ih * 0.62:.1f} C{ix + 12},{iy + ih * 0.5:.1f} {ix + 22},{iy + ih * 0.72:.1f} {ix + iw},{iy + ih * 0.58:.1f} V{iy + ih} H{ix}Z" fill="#6f7f86"/>')
    a(f'<path d="M{ix},{iy + ih * 0.8:.1f} C{ix + 16},{iy + ih * 0.68:.1f} {ix + 30},{iy + ih * 0.9:.1f} {ix + iw},{iy + ih * 0.76:.1f} V{iy + ih} H{ix}Z" fill="#3e4c56"/>')
    a(f'<path d="M{qx},{qy} h{qw}" stroke="#fff" stroke-opacity="0.18" stroke-width="0.8"/>')

    # prateleira de parede: cluster de Raspberry Pi, suculenta, livros deitados
    sy = 60
    a(f'<rect x="548" y="{sy + 3}" width="112" height="6" fill="#000" opacity="0.25" {B(2)}/>')
    a(f'<rect x="546" y="{sy}" width="114" height="4" fill="{C["desk1"]}"/><rect x="546" y="{sy}" width="114" height="0.8" fill="#fff" opacity="0.25"/>')
    a(f'<path d="M556,{sy + 4} v6 h5 M650,{sy + 4} v6 h-5" stroke="{C["metal"]}" stroke-width="1.4" fill="none"/>')
    # cluster Pi: 4 placas verdes com espacadores
    px0 = 626
    for k in range(4):
        yb = sy - 2 - k * 6.2
        a(f'<rect x="{px0}" y="{yb - 1.4:.1f}" width="26" height="1.6" fill="#1f6b43"/>'
          f'<rect x="{px0 + 2}" y="{yb - 3.4:.1f}" width="5" height="2" fill="#b8bcc2"/>'
          f'<rect x="{px0 + 9}" y="{yb - 2.8:.1f}" width="4" height="1.4" fill="#1c1c1f"/>'
          f'<rect x="{px0 + 16}" y="{yb - 3.8:.1f}" width="6" height="2.4" fill="#c8ccd2"/>')
    a(f'<path d="M{px0 + 1},{sy} V{sy - 25} M{px0 + 25},{sy} V{sy - 25}" stroke="#c7a44a" stroke-width="0.8"/>')
    a(f'<rect x="{px0 - 1}" y="{sy - 26.5}" width="28" height="1.3" fill="#2b2c30"/>')
    # cabos ethernet a descer
    a(f'<path d="M{px0 + 20},{sy + 4} C{px0 + 22},{sy + 50} {px0 + 26},{sy + 90} 647,186" stroke="#2f4f73" stroke-width="0.9" fill="none"/>'
      f'<path d="M{px0 + 23},{sy + 4} C{px0 + 25},{sy + 50} {px0 + 29},{sy + 90} 650,186" stroke="#77736e" stroke-width="0.9" fill="none"/>')
    # suculenta em vaso de barro
    a(f'<path d="M602,{sy} l-2,-9 h14 l-2,9Z" fill="#b5673f"/><rect x="599" y="{sy - 10.5}" width="16" height="2.2" rx="0.8" fill="#c77a4f"/>')
    for ang, ln in [(-60, 7), (-30, 9), (0, 10), (30, 9), (60, 7), (-12, 6), (14, 6)]:
        rad = math.radians(ang - 90)
        ex, ey = 607 + ln * math.cos(rad), sy - 10 + ln * math.sin(rad)
        a(f'<path d="M607,{sy - 10} Q{(607 + ex) / 2 + 1:.1f},{(sy - 10 + ey) / 2:.1f} {ex:.1f},{ey:.1f}" stroke="#5e8a5a" stroke-width="2.4" stroke-linecap="round" fill="none"/>')
    # livros deitados + um de pe
    bk = C["book"]
    for k, (h_, w_) in enumerate([(3.2, 32), (2.6, 30), (3.6, 33)]):
        yb = sy - sum(x[0] for x in [(3.2, 32), (2.6, 30), (3.6, 33)][:k])
        a(f'<rect x="{554 + k:.0f}" y="{yb - h_:.1f}" width="{w_}" height="{h_}" fill="{bk[k]}"/><rect x="{554 + k:.0f}" y="{yb - h_:.1f}" width="{w_}" height="0.6" fill="#fff" opacity="0.2"/>')
    a(f'<rect x="590" y="{sy - 20}" width="4" height="20" fill="{bk[4]}" transform="rotate(-10 594 {sy})"/><rect x="585" y="{sy - 18}" width="4" height="18" fill="{bk[6]}"/>')

    # tomada e cabos
    a(f'<rect x="644" y="186" width="10" height="12" rx="1.2" fill="{C["frame"]}"/><circle cx="649" cy="192" r="2.4" fill="{C["frame_d"]}"/>')

    # ------------------------------------------------------------------ ESTANTE (direita)
    ex0, ex1, etop = 676, 790, 30
    shelves = [etop, 72, 114, 156, FL - 4]
    a(f'<rect x="{ex0 - 4}" y="{etop}" width="{ex1 - ex0 + 8}" height="{FL - etop}" fill="#000" opacity="0.25" {B(3)}/>')
    a(f'<rect x="{ex0}" y="{etop}" width="{ex1 - ex0}" height="{FL - etop}" fill="{C["desk1"]}"/>')
    a(f'<rect x="{ex0 + 4}" y="{etop + 4}" width="{ex1 - ex0 - 8}" height="{FL - etop - 8}" fill="#000" opacity="0.35"/>')
    # sombra interior de cada prateleira (em cima)
    for y in shelves[:-1]:
        a(f'<rect x="{ex0 + 4}" y="{y + 4}" width="{ex1 - ex0 - 8}" height="7" fill="#000" opacity="0.25" {B(1.2)}/>')
    # conteudos
    # prateleira 1: livros
    r3 = random.Random(8)
    x = ex0 + 6
    while x < ex1 - 18:
        w_ = r3.uniform(3, 6)
        h_ = r3.uniform(26, 36)
        col = r3.choice(bk)
        a(f'<rect x="{x:.1f}" y="{72 - h_:.1f}" width="{w_:.1f}" height="{h_:.1f}" fill="{col}"/><rect x="{x:.1f}" y="{72 - h_ + 4:.1f}" width="{w_:.1f}" height="1" fill="#fff" opacity="0.18"/>')
        x += w_ + 0.6
    a(f'<rect x="{ex1 - 16}" y="{72 - 30}" width="5" height="30" fill="{bk[5]}" transform="rotate(-14 {ex1 - 11} 72)"/>')
    # prateleira 2: NAS 4 baias + switch com patch cables
    nx, ny = ex0 + 8, 114 - 32
    a(f'<rect x="{nx}" y="{ny}" width="34" height="32" rx="2" fill="#1b1b20"/><rect x="{nx}" y="{ny}" width="34" height="1" fill="#fff" opacity="0.15"/>')
    for k in range(4):
        a(f'<rect x="{nx + 3 + k * 7.3:.1f}" y="{ny + 5}" width="6" height="22" rx="0.8" fill="#26262c"/><rect x="{nx + 4 + k * 7.3:.1f}" y="{ny + 7}" width="4" height="0.7" fill="#3a3a42"/>')
    sw = (ex0 + 48, 114 - 11, 56, 11)
    a(f'<rect x="{sw[0]}" y="{sw[1]}" width="{sw[2]}" height="{sw[3]}" rx="1" fill="#2c3036"/>')
    for k in range(8):
        a(f'<rect x="{sw[0] + 4 + k * 5.8:.1f}" y="{sw[1] + 3}" width="4" height="3.4" fill="#0e0f12"/>')
    pc = ["#3d7fc4", "#d9a33a", "#3d7fc4", "#c9c9c9", "#58a563", "#3d7fc4"]
    for k, col in enumerate(pc):
        xk = sw[0] + 6 + k * 5.8
        a(f'<path d="M{xk:.1f},{sw[1] + 4} C{xk:.1f},{sw[1] - 8} {xk + 10 - k * 4:.1f},{sw[1] - 12} {sw[0] + 20 + k * 2:.1f},{sw[1] - 22}" stroke="{col}" stroke-width="1" fill="none" opacity="0.9"/>')
    # prateleira 3: dois mini PCs empilhados + caixa
    mx_, my_ = ex0 + 8, 156 - 8
    a(f'<rect x="{mx_}" y="{my_}" width="26" height="8" rx="1.5" fill="#2a2b31"/><rect x="{mx_}" y="{my_ - 8.5}" width="26" height="8" rx="1.5" fill="#34353c"/>')
    a(f'<rect x="{ex0 + 42}" y="{156 - 20}" width="30" height="20" fill="#b99c76"/><rect x="{ex0 + 42}" y="{156 - 20}" width="30" height="3" fill="#a4865f"/>')
    a(f'<rect x="{ex0 + 78}" y="{156 - 24}" width="4" height="24" fill="{bk[1]}"/><rect x="{ex0 + 82.5}" y="{156 - 22}" width="4" height="22" fill="{bk[3]}"/><rect x="{ex0 + 87}" y="{156 - 26}" width="5" height="26" fill="{bk[0]}"/>')
    # prateleira 4: caixas de tecido
    for k in range(2):
        bx = ex0 + 8 + k * 50
        a(f'<path d="M{bx},{FL - 4} v-38 h46 v38Z" fill="{"#4f5a63" if dark else "#8d9aa3"}"/><rect x="{bx + 17}" y="{FL - 36}" width="12" height="3" rx="1.5" fill="#000" opacity="0.35"/>')
    # prateleiras (frente das tabuas)
    for y in shelves:
        a(f'<rect x="{ex0}" y="{y}" width="{ex1 - ex0}" height="4" fill="{C["desk0"]}"/><rect x="{ex0}" y="{y}" width="{ex1 - ex0}" height="0.8" fill="#fff" opacity="0.22"/>')
    a(f'<rect x="{ex0}" y="{etop}" width="4" height="{FL - etop}" fill="{C["desk0"]}"/><rect x="{ex1 - 4}" y="{etop}" width="4" height="{FL - etop}" fill="{C["desk1"]}"/>')
    # topo: router + pothos a cair
    rx_, ry_ = ex0 + 10, etop
    a(f'<rect x="{rx_}" y="{ry_ - 7}" width="40" height="7" rx="1.5" fill="#1d1d22"/>')
    for k, dx in enumerate((4, 14, 26, 36)):
        a(f'<path d="M{rx_ + dx},{ry_ - 6} l{-3 + k * 2},-14" stroke="#1d1d22" stroke-width="1.6" stroke-linecap="round"/>')
    a(f'<path d="M{ex1 - 30},{etop} l-2,-12 h20 l-2,12Z" fill="#d7d1c6"/>')
    vines = []
    lr = random.Random(21)
    for (sx, ex_, ey) in [(ex1 - 26, ex1 - 34, 96), (ex1 - 18, ex1 - 12, 132), (ex1 - 12, ex1 + 2, 70), (ex1 - 22, ex1 - 26, 58)]:
        sy_ = etop - 10
        cx_ = (sx + ex_) / 2 + lr.uniform(-8, 8)
        vines.append(f'<path d="M{sx},{sy_} Q{cx_:.1f},{(sy_ + ey) / 2:.1f} {ex_},{ey}" stroke="#2f5234" stroke-width="0.8" fill="none"/>')
        for t in [i / 7 for i in range(1, 8)]:
            px = (1 - t) ** 2 * sx + 2 * (1 - t) * t * cx_ + t * t * ex_
            py = (1 - t) ** 2 * sy_ + 2 * (1 - t) * t * (sy_ + ey) / 2 + t * t * ey
            ang = lr.uniform(-70, 70)
            vines.append(f'<ellipse cx="{px:.1f}" cy="{py:.1f}" rx="3.6" ry="2.3" transform="rotate({ang:.0f} {px:.1f} {py:.1f})" fill="{lr.choice(["#4a7a47", "#3d6a3f", "#5b8a4f"])}"/>')
    for k in range(6):
        ang = -90 + (k - 2.5) * 22
        rad = math.radians(ang)
        a(f'<ellipse cx="{ex1 - 20 + 8 * math.cos(rad):.1f}" cy="{etop - 12 + 6 * math.sin(rad):.1f}" rx="4" ry="2.5" transform="rotate({ang + 90:.0f} {ex1 - 20 + 8 * math.cos(rad):.1f} {etop - 12 + 6 * math.sin(rad):.1f})" fill="#4d7d4a"/>')
    a('<g class="sway">' + "".join(vines) + "</g>")

    # ================================================================== CHAO
    a(f'<rect x="0" y="{FL}" width="{W}" height="{H - FL}" fill="url(#floor)"/>')
    seams = []
    for xb in range(-900, 1800, 30):
        x1 = VPX + (xb - VPX) * (FL - VPY) / (H - VPY)
        seams.append(f'<path d="M{x1:.1f},{FL} L{xb},{H}"/>')
    a(f'<g stroke="{C["seam"]}" stroke-width="0.6" opacity="0.45">{"".join(seams)}</g>')
    # juntas transversais das tabuas (desencontradas)
    r4 = random.Random(12)
    tj = []
    for row in range(6):
        y = FL + 3 + row * row * 1.3 + row * 4
        for _ in range(10):
            x = r4.uniform(0, W)
            tj.append(f'<path d="M{x:.0f},{y:.1f} h{4 + row:.0f}"/>')
    a(f'<g stroke="{C["seam"]}" stroke-width="0.5" opacity="0.4">{"".join(tj)}</g>')
    a(f'<rect x="0" y="{FL - 6}" width="{W}" height="6" fill="{C["base"]}"/><rect x="0" y="{FL - 6}" width="{W}" height="0.8" fill="#fff" opacity="0.2"/>')
    # sombra de contacto parede/chao
    a(f'<rect x="0" y="{FL}" width="{W}" height="5" fill="#000" opacity="0.2" {B(1.2)}/>')
    # tapete
    a(f'<path d="M352,222 L630,222 L700,262 L286,262Z" fill="{C["rug"]}"/>')
    a(f'<path d="M358,225 L624,225 L688,262 L298,262Z" fill="none" stroke="{C["rug2"]}" stroke-width="1.2"/>')
    a(f'<path d="M366,229 L616,229 L674,262 L312,262Z" fill="none" stroke="{C["rug2"]}" stroke-width="0.6" stroke-dasharray="2 2"/>')
    # reflexo da janela no soalho (noite: frio) / mancha de sol (tarde)
    if dark:
        a(f'<path d="M96,216 L230,216 L300,256 L130,256Z" fill="#7d9ccc" opacity="0.22" {B(5)}/>')

    # ================================================================== SECRETARIA
    # pernas traseiras + travessa
    a(f'<rect x="{DX0 + 16}" y="{DB}" width="4" height="{FL - DB}" fill="{C["metal"]}"/><rect x="{DX1 - 20}" y="{DB}" width="4" height="{FL - DB}" fill="{C["metal"]}"/>')
    a(f'<rect x="{DX0 + 16}" y="190" width="{DX1 - DX0 - 32}" height="3" fill="{C["metal"]}"/>')
    # servidor debaixo da mesa
    sx0, sy0 = 572, 176
    a(f'<ellipse cx="{sx0 + 16}" cy="{FL + 2}" rx="22" ry="3" fill="#000" opacity="0.4" {B(1.2)}/>')
    a(f'<rect x="{sx0}" y="{sy0}" width="32" height="{FL + 2 - sy0}" rx="2" fill="#1c1c22"/><rect x="{sx0}" y="{sy0}" width="32" height="1" fill="#fff" opacity="0.12"/>')
    a(f'<g fill="#2a2a31">' + "".join(f'<rect x="{sx0 + 4}" y="{sy0 + 6 + k * 3}" width="24" height="1.4"/>' for k in range(6)) + "</g>")
    # calha de cabos e cabos a pender
    a(f'<rect x="360" y="{DF + 5}" width="200" height="4" fill="{C["metal"]}"/>')
    a(f'<path d="M548,{DF + 9} C552,190 610,176 612,{sy0} M556,{DF + 9} C570,196 634,210 645,196" stroke="#15151a" stroke-width="1.3" fill="none"/>')
    a(f'<path d="M380,{DF + 9} C384,176 410,178 418,{DF + 9}" stroke="#15151a" stroke-width="1.1" fill="none"/>')
    # tampo
    a(f'<path d="M{DX0 + 4},{DB} L{DX1 - 4},{DB} L{DX1},{DF} L{DX0},{DF}Z" fill="url(#deskt)"/>')
    a(f'<rect x="{DX0}" y="{DF}" width="{DX1 - DX0}" height="5" fill="{C["edge"]}"/><rect x="{DX0}" y="{DF}" width="{DX1 - DX0}" height="0.8" fill="#fff" opacity="0.3"/>')
    # veios da madeira
    r5 = random.Random(2)
    a('<g stroke="#000" stroke-width="0.35" opacity="0.12" fill="none">' + "".join(
        f'<path d="M{DX0 + 6},{DB + 1 + k * 1.6:.1f} C{r5.uniform(360, 460):.0f},{DB + 1 + k * 1.6 + r5.uniform(-0.6, 0.6):.1f} {r5.uniform(480, 580):.0f},{DB + 1 + k * 1.6 + r5.uniform(-0.6, 0.6):.1f} {DX1 - 6},{DB + 1 + k * 1.6:.1f}"/>' for k in range(5)) + "</g>")
    # pernas da frente (mais perto: descem mais)
    for x in (DX0 + 6, DX1 - 12):
        a(f'<rect x="{x}" y="{DF + 5}" width="6" height="{222 - DF - 5}" fill="{C["metal"]}"/><rect x="{x}" y="{DF + 5}" width="1.2" height="{222 - DF - 5}" fill="#fff" opacity="0.12"/>')
        a(f'<ellipse cx="{x + 3}" cy="223" rx="8" ry="1.6" fill="#000" opacity="0.35" {B(0.6)}/>')
    # auscultadores pendurados num gancho no lado esquerdo do tampo
    hx, hy = DX0 + 22, DF + 5
    a(f'<path d="M{hx - 2},{hy} v4 h4" stroke="{C["metal"]}" stroke-width="1.4" fill="none"/>')
    a(f'<path d="M{hx - 11},{hy + 20} C{hx - 12},{hy + 2} {hx + 10},{hy + 2} {hx + 9},{hy + 20}" stroke="#1d1c22" stroke-width="2.6" fill="none" stroke-linecap="round"/>')
    a(f'<path d="M{hx - 11},{hy + 20} C{hx - 12},{hy + 4} {hx + 10},{hy + 4} {hx + 9},{hy + 20}" stroke="#4a4852" stroke-width="0.6" fill="none"/>')
    for sx_ in (hx - 12, hx + 8):
        a(f'<rect x="{sx_ - 4}" y="{hy + 17}" width="9" height="13" rx="4" fill="#26252b"/><rect x="{sx_ - 2.5}" y="{hy + 19}" width="6" height="9" rx="3" fill="#3b3943"/>')
    a(f'<path d="M{hx + 8},{hy + 30} C{hx + 10},{hy + 44} {hx - 6},{hy + 48} {hx - 4},{FL + 1}" stroke="#1d1c22" stroke-width="0.8" fill="none"/>')

    # ---------------------------------------------------------------- objetos sobre a mesa
    # sombras projetadas pelo candeeiro na parede (so de noite, luz vem da direita)
    if dark:
        a(f'<g class="lamp" opacity="1"><rect x="{MX0 - 12}" y="{MY0 + 4}" width="{MX1 - MX0}" height="{MY1 - MY0 + 8}" fill="#000" opacity="0.3" {B(9)}/></g>')
    else:
        a(f'<rect x="{MX0 + 6}" y="{MY0 + 6}" width="{MX1 - MX0}" height="{MY1 - MY0}" fill="#000" opacity="0.1" {B(9)}/>')

    # portatil num suporte (esquerda)
    lx0, lx1, ly0, ly1 = 322, 374, 100, 134
    a(f'<ellipse cx="{(lx0 + lx1) / 2}" cy="{DB + 3}" rx="30" ry="2.5" fill="#000" opacity="0.35" {B(1.2)}/>')
    a(f'<path d="M{lx0 + 8},{DB + 2} L{lx0 + 16},{ly1 + 2} M{lx1 - 8},{DB + 2} L{lx1 - 16},{ly1 + 2}" stroke="url(#metalg)" stroke-width="2"/>')
    a(f'<path d="M{lx0 - 2},{ly1} L{lx1 + 2},{ly1} L{lx1 + 4},{ly1 + 3} L{lx0 - 4},{ly1 + 3}Z" fill="#9aa0a8"/>')
    a(f'<rect x="{lx0}" y="{ly0}" width="{lx1 - lx0}" height="{ly1 - ly0}" rx="1.5" fill="#141417"/>')

    # monitor: pe + coluna + moldura
    a(f'<ellipse cx="462" cy="{DB + 2.5}" rx="24" ry="3" fill="#000" opacity="0.4" {B(1.2)}/>')
    a(f'<path d="M444,{DB + 2.5} Q462,{DB - 1} 480,{DB + 2.5}Z" fill="#26252b"/>')
    a(f'<rect x="457" y="{MY1 - 4}" width="10" height="{DB - MY1 + 5}" fill="url(#metalg)" opacity="0.6"/><rect x="457" y="{MY1 - 4}" width="10" height="{DB - MY1 + 5}" fill="#1f1e24" opacity="0.6"/>')
    a(f'<rect x="{MX0}" y="{MY0}" width="{MX1 - MX0}" height="{MY1 - MY0}" rx="2.5" fill="#141417"/>')
    a(f'<rect x="{MX0}" y="{MY1 - 3}" width="{MX1 - MX0}" height="3" rx="1" fill="#1d1c21"/>')

    # tapete de secretaria, teclado, rato
    a(f'<path d="M396,{DB + 1.5} L548,{DB + 1.5} L551,{DF - 0.5} L392,{DF - 0.5}Z" fill="#2b2d33"/>')
    kx0, kx1 = 412, 500
    a(f'<ellipse cx="{(kx0 + kx1) / 2}" cy="{DF - 1.3}" rx="47" ry="1.6" fill="#000" opacity="0.5" {B(0.6)}/>')
    a(f'<path d="M{kx0 + 1},{DB + 2.5} L{kx1 - 1},{DB + 2.5} L{kx1 + 1},{DF - 1.2} L{kx0 - 1},{DF - 1.2}Z" fill="#3a3a40"/>')
    kr = random.Random(6)
    keys = []
    for row in range(4):
        t = row / 3
        y = DB + 3 + row * 1.25
        x0_ = kx0 + 1.5 - t * 1.4
        x1_ = kx1 - 1.5 + t * 1.4
        n = 15
        kw = (x1_ - x0_) / n
        for k in range(n):
            col = "#e6e0d4"
            if (row, k) in ((0, 0), (3, 14), (2, 13)):
                col = "#d9824a"
            elif row == 3 and 4 <= k <= 9:
                if k != 4:
                    continue
                keys.append(f'<rect x="{x0_ + k * kw + 0.2:.2f}" y="{y:.2f}" width="{kw * 6 - 0.5:.2f}" height="1" rx="0.3" fill="#d6d0c4"/>')
                continue
            elif kr.random() < 0.18:
                col = "#9fa3ad"
            keys.append(f'<rect x="{x0_ + k * kw + 0.2:.2f}" y="{y:.2f}" width="{kw - 0.5:.2f}" height="1" rx="0.3" fill="{col}"/>')
    a("".join(keys))
    a(f'<ellipse cx="524" cy="{DF - 2.4}" rx="4.2" ry="1.9" fill="#d7d2c8"/><ellipse cx="524" cy="{DF - 3}" rx="3" ry="0.9" fill="#fff" opacity="0.4"/>')
    a(f'<path d="M524,{DB + 2.6} C524,{DB} 528,{DB} 530,{DB - 1}" stroke="#222" stroke-width="0.5" fill="none"/>')

    # caderno aberto + caneta (debaixo do candeeiro)
    nb = f'M552,{DB + 2} L597,{DB + 2} L600,{DF - 1} L549,{DF - 1}Z'
    a(f'<ellipse cx="574" cy="{DF - 0.8}" rx="27" ry="1.4" fill="#000" opacity="0.45" {B(0.6)}/>')
    a(f'<path d="{nb}" fill="#f2ecdf"/><path d="M574.5,{DB + 2} L574.5,{DF - 1}" stroke="#b9b0a0" stroke-width="0.6"/>')
    a('<g stroke="#8a95a8" stroke-width="0.25" opacity="0.7">' + "".join(f'<path d="M{553 - k * 0.6:.1f},{DB + 3.3 + k * 1.2:.1f} h{20 + k * 0.3:.1f} M{576:.1f},{DB + 3.3 + k * 1.2:.1f} h{21 + k * 0.6:.1f}"/>' for k in range(5)) + "</g>")
    a(f'<path d="M580,{DB + 5.5} l3,-0.2" stroke="#3c4b66" stroke-width="0.35"/><path d="M556,{DB + 4.5} l8,0 M556,{DB + 5.7} l12,0 M556,{DB + 6.9} l6,0" stroke="#3c4b66" stroke-width="0.35" opacity="0.8"/>')
    a(f'<path d="M583,{DF - 2} L597,{DB + 3.2}" stroke="#23262e" stroke-width="1" stroke-linecap="round"/><path d="M596,{DB + 3.3} l1.2,-0.3" stroke="#c9a44a" stroke-width="1"/>')

    # chavenas: 8 lugares
    slots = [(300, DB + 5.5, "#e3d9c6"), (386, DB + 5.2, "#8c4b3a"), (312, DB + 7.4, "#3e5570"),
             (505, DB + 4.5, "#d6cdbd"), (398, DB + 7.4, "#6f7f5a"), (536, DB + 5.8, "#e3d9c6"),
             (352, DB + 8, "#b56a45"), (377, DB + 7.6, "#2f3b52")]
    for k, (x, yb, col) in enumerate(slots):
        a(f'<g class="c{k}" opacity="{1 if cups[MARCH] > k else 0}">'
          f'<ellipse cx="{x + 3.6}" cy="{yb + 0.3}" rx="5" ry="0.9" fill="#000" opacity="0.45" {B(0.6)}/>'
          f'<path d="M{x + 7},{yb - 6} q3.6,0 3.6,2.6 t-3.6,2.6" stroke="{col}" stroke-width="1.2" fill="none"/>'
          f'<path d="M{x},{yb - 8.5} h7.4 v7.2 q0,1.3 -1.3,1.3 h-4.8 q-1.3,0 -1.3,-1.3Z" fill="{col}"/>'
          f'<path d="M{x},{yb - 8.5} h2.2 v8.5 h-0.9 q-1.3,0 -1.3,-1.3Z" fill="#000" opacity="0.18"/>'
          f'<path d="M{x + 5.2},{yb - 8.5} h2.2 v7.2 q0,1.3 -1.3,1.3 h-0.9Z" fill="#fff" opacity="0.18"/>'
          f'<ellipse cx="{x + 3.7}" cy="{yb - 8.5}" rx="3.7" ry="0.9" fill="#1a1216"/></g>')

    # candeeiro articulado (corpo; a luz vem depois)
    bx, by = LB
    a(f'<ellipse cx="{bx}" cy="{by + 0.5}" rx="13" ry="2" fill="#000" opacity="0.45" {B(0.6)}/>')
    a(f'<path d="M{bx - 10},{by} Q{bx},{by - 5} {bx + 10},{by}Z" fill="#2a282e"/>')
    a(f'<path d="M{bx},{by - 2} L{LE[0]},{LE[1]} L{LJ[0]},{LJ[1]}" stroke="#2f2c33" stroke-width="2.2" fill="none" stroke-linejoin="round"/>')
    a(f'<path d="M{bx + 3},{by - 6} L{LE[0] + 2.5},{LE[1] + 6}" stroke="#4a4550" stroke-width="0.6"/><path d="M{LE[0] - 3},{LE[1] - 1} L{LJ[0] + 4},{LJ[1] + 3.5}" stroke="#4a4550" stroke-width="0.6"/>')
    a(f'<circle cx="{LE[0]}" cy="{LE[1]}" r="2.2" fill="#3a3640"/>')
    dx, dy = LT[0] - LJ[0], LT[1] - LJ[1]
    ln = math.hypot(dx, dy)
    d = (dx / ln, dy / ln)
    n = (-d[1], d[0])
    J = LJ
    L0 = 5
    L1 = 19
    Mo = (J[0] + d[0] * L1, J[1] + d[1] * L1)
    shade = [(J[0] - d[0] * L0 + n[0] * 3, J[1] - d[1] * L0 + n[1] * 3), (J[0] - d[0] * L0 - n[0] * 3, J[1] - d[1] * L0 - n[1] * 3),
             (Mo[0] - n[0] * 11.5, Mo[1] - n[1] * 11.5), (Mo[0] + n[0] * 11.5, Mo[1] + n[1] * 11.5)]
    ang_n = math.degrees(math.atan2(n[1], n[0]))
    bk0 = (J[0] - d[0] * L0, J[1] - d[1] * L0)
    c1 = (J[0] + d[0] * 5 + n[0] * 10, J[1] + d[1] * 5 + n[1] * 10)
    c2 = (J[0] + d[0] * 5 - n[0] * 10, J[1] + d[1] * 5 - n[1] * 10)
    dome = (f'M{bk0[0] + n[0] * 3:.1f},{bk0[1] + n[1] * 3:.1f} Q{c1[0]:.1f},{c1[1]:.1f} {shade[3][0]:.1f},{shade[3][1]:.1f} '
            f'L{shade[2][0]:.1f},{shade[2][1]:.1f} Q{c2[0]:.1f},{c2[1]:.1f} {bk0[0] - n[0] * 3:.1f},{bk0[1] - n[1] * 3:.1f}Z')
    a(f'<linearGradient id="shadeg" gradientUnits="userSpaceOnUse" x1="{Mo[0] - n[0] * 12:.1f}" y1="{Mo[1] - n[1] * 12:.1f}" x2="{Mo[0] + n[0] * 12:.1f}" y2="{Mo[1] + n[1] * 12:.1f}">'
      f'<stop offset="0" stop-color="{"#57505e" if dark else "#6a6270"}"/><stop offset="0.45" stop-color="#34303a"/><stop offset="1" stop-color="#211e25"/></linearGradient>')
    a(f'<path d="{dome}" fill="url(#shadeg)"/>')
    a(f'<ellipse cx="{bk0[0]:.1f}" cy="{bk0[1]:.1f}" rx="3" ry="1.4" transform="rotate({ang_n:.0f} {bk0[0]:.1f} {bk0[1]:.1f})" fill="#48424e"/>')
    a(f'<circle cx="{J[0]}" cy="{J[1]}" r="2" fill="#3a3640"/>')
    mouth_el = f'cx="{Mo[0]:.1f}" cy="{Mo[1]:.1f}" rx="11.5" ry="3.2" transform="rotate({ang_n:.0f} {Mo[0]:.1f} {Mo[1]:.1f})"'
    a(f'<ellipse {mouth_el} fill="#1b191e"/>')
    mouth_in = mouth_el.replace('rx="11.5" ry="3.2"', 'rx="7" ry="1.8"')

    # ================================================================== CADEIRA (por tras, ligeiramente virada)
    ch = 470
    rim_w = "#ffb56a"
    rim_c = "#9fbcff"
    # sombra no chao
    if dark:
        a(f'<ellipse cx="{ch + 4}" cy="253" rx="46" ry="6" fill="#000" opacity="0.5" {B(3)}/>')
    else:
        a(f'<path d="M{ch - 30},250 L{ch + 30},248 L{ch + 130},262 L{ch + 20},262Z" fill="#000" opacity="0.28" {B(3)}/>')
    # base em estrela
    hub = (ch, 244)
    ends = [(-40, 8), (-22, 13), (24, 13), (42, 7), (4, 4)]
    for ex_, ey_ in ends:
        a(f'<path d="M{hub[0]},{hub[1]} L{hub[0] + ex_},{hub[1] + ey_}" stroke="#1b1a1f" stroke-width="{3.4 if ey_ > 8 else 2.6}" stroke-linecap="round"/>')
    for ex_, ey_ in ends:
        a(f'<ellipse cx="{hub[0] + ex_}" cy="{hub[1] + ey_ + 2.6}" rx="3" ry="2.4" fill="#111014"/>')
    # coluna de gas + capa
    a(f'<rect x="{ch - 2.5}" y="214" width="5" height="30" fill="url(#metalg)" opacity="0.85"/>')
    a(f'<path d="M{ch - 5},226 h10 l1.5,18 h-13Z" fill="#1d1c21"/>')
    # assento visto por tras
    a(f'<path d="M{ch - 38},206 C{ch - 40},212 {ch - 30},216 {ch},216 C{ch + 30},216 {ch + 40},212 {ch + 38},206 C{ch + 20},203 {ch - 20},203 {ch - 38},206Z" fill="#1f1e24"/>')
    a(f'<rect x="{ch - 10}" y="212" width="20" height="5" rx="1.5" fill="#15141a"/>')
    # bracos
    for s in (-1, 1):
        xa = ch + s * 36
        a(f'<path d="M{xa},{210} L{xa + s * 2},{190}" stroke="#1b1a1f" stroke-width="3.2" stroke-linecap="round"/>')
        a(f'<rect x="{xa + s * 2 - 6}" y="186" width="12" height="4.2" rx="2" fill="#24232a"/>')
    # espinha
    a(f'<path d="M{ch - 4},{214} L{ch - 4},{196} L{ch + 4},{196} L{ch + 4},{214}Z" fill="#17161b"/>')
    # encosto: moldura + malha
    back = (f'M{ch - 30},150 C{ch - 20},143 {ch + 20},143 {ch + 30},150 C{ch + 33},166 {ch + 30},182 {ch + 22},198 '
            f'C{ch + 10},202 {ch - 10},202 {ch - 22},198 C{ch - 30},182 {ch - 33},166 {ch - 30},150Z')
    a(f'<clipPath id="bk"><path d="{back}"/></clipPath>')
    a(f'<path d="{back}" fill="url(#chairg)"/>')
    a(f'<g clip-path="url(#bk)"><g stroke="{C["mesh"]}" stroke-width="0.5" opacity="0.8">' +
      "".join(f'<path d="M{ch - 40 + k * 2.2:.1f},140 l30,70"/><path d="M{ch + 40 - k * 2.2:.1f},140 l-30,70"/>' for k in range(36)) + "</g>"
      f'<path d="M{ch - 34},176 C{ch - 10},184 {ch + 10},184 {ch + 34},176 L{ch + 34},186 C{ch + 10},194 {ch - 10},194 {ch - 34},186Z" fill="#000" opacity="0.28"/>'
      f'<ellipse cx="{ch + 8}" cy="160" rx="22" ry="12" fill="#fff" opacity="0.05"/></g>')
    a(f'<path d="{back}" fill="none" stroke="#141318" stroke-width="2.2"/>')
    # luzes de recorte
    if dark:
        a(f'<g class="mon" opacity="1"><path d="M{ch - 26},148 C{ch - 16},142.8 {ch + 16},142.8 {ch + 26},148" stroke="{rim_c}" stroke-width="1" fill="none" opacity="0.7" stroke-linecap="round"/></g>')
        a(f'<g class="lamp" opacity="1"><path d="M{ch + 31},152 C{ch + 33},166 {ch + 31},180 {ch + 24},196" stroke="{rim_w}" stroke-width="1.2" fill="none" opacity="0.8" stroke-linecap="round"/>'
          f'<path d="M{ch + 38},187 h4" stroke="{rim_w}" stroke-width="1" opacity="0.6" stroke-linecap="round"/></g>')
    else:
        a(f'<path d="M{ch - 31},152 C{ch - 33},166 {ch - 31},180 {ch - 24},196" stroke="#ffc27a" stroke-width="1.3" fill="none" opacity="0.85" stroke-linecap="round"/>'
          f'<path d="M{ch - 42},187 h4" stroke="#ffc27a" stroke-width="1" opacity="0.7" stroke-linecap="round"/>')

    # ================================================================== ESCURIDAO (mascara de luz)
    a(f'<rect width="{W}" height="{H}" fill="{C["ov"]}" opacity="{C["ovop"]}" mask="url(#mLit)"/>')
    a(f'<rect class="dim" width="{W}" height="{H}" fill="{C["ov"]}" opacity="0" mask="url(#mDim)"/>')

    # ================================================================== EMISSIVOS E LUZ
    scr = lambda: None
    # ---- ecra do monitor
    sx, sy_, sw_, sh_ = MX0 + 3, MY0 + 3, MX1 - MX0 - 6, MY1 - MY0 - 6
    a('<g clip-path="url(#screen)">')
    a(f'<rect x="{sx}" y="{sy_}" width="{sw_}" height="{sh_}" fill="#07080b"/>')
    a(f'<g class="scr" opacity="1">')
    a(f'<rect x="{sx}" y="{sy_}" width="{sw_}" height="{sh_}" fill="url(#scrbg)"/>')
    # barra de topo, arvore de ficheiros
    a(f'<rect x="{sx}" y="{sy_}" width="{sw_}" height="4" fill="#1b2438"/>')
    for k, w_ in enumerate((16, 13, 18)):
        a(f'<rect x="{sx + 20 + k * 20}" y="{sy_ + 1.2}" width="{w_}" height="1.8" rx="0.9" fill="{"#3c4a6a" if k == 0 else "#27324a"}"/>')
    a(f'<rect x="{sx}" y="{sy_ + 4}" width="17" height="{sh_ - 4}" fill="#10151f"/>')
    tr = random.Random(14)
    a("".join(f'<rect x="{sx + 2 + tr.choice([0, 2, 4])}" y="{sy_ + 7 + k * 3.2:.1f}" width="{tr.uniform(5, 11):.1f}" height="1.3" rx="0.6" fill="#44506a"/>' for k in range(14)))
    # codigo (sem letras) a rolar
    cr = random.Random(5)
    rows = []
    pal = ["#7aa2d8", "#d8a45c", "#c9d1dc", "#83c08e", "#b58fd6", "#6b7688"]
    y = sy_ + 8
    ind = 0
    for r in range(40):
        ind = max(0, min(4, ind + cr.choice([-1, 0, 0, 1])))
        x = sx + 26 + ind * 5
        if cr.random() < 0.12:
            y += 3.4
            continue
        for _ in range(cr.randint(1, 4)):
            w_ = cr.uniform(4, 20)
            if x + w_ > sx + sw_ - 4:
                break
            rows.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w_:.1f}" height="1.5" rx="0.7" fill="{cr.choice(pal)}" opacity="0.85"/>')
            x += w_ + 2.4
        y += 3.4
    gutter = "".join(f'<rect x="{sx + 19}" y="{sy_ + 8 + k * 3.4:.1f}" width="4" height="1.1" fill="#34405a"/>' for k in range(40))
    a(f'<clipPath id="codec"><rect x="{sx + 17}" y="{sy_ + 5}" width="{sw_ - 17}" height="30"/></clipPath>')
    a(f'<g clip-path="url(#codec)"><g class="code">{gutter}{"".join(rows)}</g></g>')
    a(f'<rect class="cur" x="{sx + 62}" y="{sy_ + 25}" width="1" height="3" fill="#e8eef9"/>')
    # painel: grafico de contribuicoes real (53 x 7), a encher mes a mes
    hx0, hy0 = sx + 19, sy_ + 37.5
    a(f'<rect x="{sx + 17}" y="{sy_ + 35}" width="{sw_ - 17}" height="{sh_ - 35}" fill="#0d1117"/>')
    a(f'<rect x="{sx + 17}" y="{sy_ + 35}" width="{sw_ - 17}" height="0.6" fill="#2a3346"/>')
    pitch = (sw_ - 21) / 53
    cs = pitch * 0.78
    ramp = ["#0e4429", "#006d32", "#26a641", "#39d353"]
    empty = []
    bym = {m: [] for m in range(12)}
    for wi, wk in enumerate(weeks[-53:]):
        for d_, c in wk:
            di = (d_.weekday() + 1) % 7
            x = hx0 + wi * pitch
            y = hy0 + di * pitch
            empty.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cs:.2f}" height="{cs:.2f}" rx="0.3"/>')
            if c:
                lvl = 0 if c < 5 else 1 if c < 15 else 2 if c < 40 else 3
                bym[month_idx(d_, MONTHS)].append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cs:.2f}" height="{cs:.2f}" rx="0.3" fill="{ramp[lvl]}"/>')
    a(f'<g fill="#1a212c">{"".join(empty)}</g>')
    for m in range(12):
        if bym[m]:
            a(f'<g class="h{m}" opacity="{1 if m <= MARCH else 0}">{"".join(bym[m])}</g>')
    a("</g>")  # scr
    a(f'<rect x="{sx}" y="{sy_}" width="{sw_}" height="{sh_}" fill="url(#gloss)"/>')
    a("</g>")
    # LED de standby do monitor (acende quando o ecra esta desligado)
    a(f'<circle class="off" opacity="0" cx="{MX1 - 6}" cy="{MY1 - 1.5}" r="0.7" fill="#ffae42"/>')
    a(f'<circle cx="{MX1 - 6}" cy="{MY1 - 1.5}" r="0.6" fill="#8fb5ff" class="scr" opacity="1"/>')
    # bloom do ecra
    a(f'<g class="mon" opacity="1" style="mix-blend-mode:screen"><rect x="{MX0}" y="{MY0}" width="{MX1 - MX0}" height="{MY1 - MY0}" fill="#9ab8ff" opacity="{0.22 if dark else 0.12}" {B(5)}/></g>')

    # ---- ecra do portatil: curva semanal do ano (dashboard)
    a(f'<clipPath id="lap"><rect x="{lx0 + 2}" y="{ly0 + 2}" width="{lx1 - lx0 - 4}" height="{ly1 - ly0 - 4}"/></clipPath>')
    a(f'<g clip-path="url(#lap)"><g class="scr" opacity="1">')
    a(f'<rect x="{lx0 + 2}" y="{ly0 + 2}" width="{lx1 - lx0 - 4}" height="{ly1 - ly0 - 4}" fill="#0f141d"/>')
    wk = [sum(c for _, c in w_) for w_ in weeks[-53:]]
    wmax = max(wk)
    gx0, gx1, gy0, gy1 = lx0 + 4, lx1 - 4, ly0 + 12, ly1 - 4
    pts = [(gx0 + (gx1 - gx0) * i / (len(wk) - 1), gy1 - (gy1 - gy0) * math.sqrt(v / wmax)) for i, v in enumerate(wk)]
    area = f"M{gx0},{gy1} " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts) + f" L{gx1},{gy1}Z"
    a(f'<path d="{area}" fill="#39d353" opacity="0.18"/><path d="M' + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + '" stroke="#39d353" stroke-width="0.6" fill="none"/>')
    for k, col in enumerate(("#39d353", "#39d353", "#39d353", "#e3b341")):
        a(f'<rect x="{lx0 + 4 + k * 11}" y="{ly0 + 4}" width="9" height="5" rx="0.8" fill="#161d2a"/><circle cx="{lx0 + 6.5 + k * 11}" cy="{ly0 + 6.5}" r="0.9" fill="{col}" class="led" style="animation-delay:-{k * 0.7}s;animation-duration:{2 + k * 0.6:.1f}s"/>'
          f'<rect x="{lx0 + 8.5 + k * 11}" y="{ly0 + 6}" width="3.5" height="1" fill="#44506a"/>')
    a("</g></g>")
    a(f'<rect x="{lx0 + 2}" y="{ly0 + 2}" width="{lx1 - lx0 - 4}" height="{ly1 - ly0 - 4}" fill="url(#gloss)"/>')

    # ---- LEDs: NAS, switch, router, cluster Pi, servidor
    leds = []
    for k in range(4):
        leds.append((nx + 6 + k * 7.3, ny + 28.5, "#62e08a" if k != 2 else "#62b8ff", 0.9 + k * 0.35))
    leds.append((nx + 30, ny + 3, "#62b8ff", 0))
    for k in range(8):
        leds.append((sw[0] + 5 + k * 5.8, sw[1] + 8.5, "#62e08a" if k < 6 else "#e8b04a", 0.6 + (k % 3) * 0.4))
    for k in range(4):
        leds.append((rx_ + 22 + k * 4, ry_ - 3.5, "#62e08a", 1.1 + k * 0.3))
    for k in range(4):
        yb = sy - 2 - k * 6.2
        leds.append((px0 + 23.5, yb - 2.2, "#ff5a4a", 0))
        leds.append((px0 + 21.5, yb - 2.2, "#62e08a", 0.5 + k * 0.23))
    for k in range(3):
        leds.append((sx0 + 6 + k * 4, sy0 + 30, ["#62e08a", "#62e08a", "#62b8ff"][k], 0.9 + k * 0.5))
    leds.append((mx_ + 22, my_ + 4, "#62b8ff", 0))
    leds.append((mx_ + 22, my_ - 4.5, "#62e08a", 1.3))
    lr_ = random.Random(31)
    lh = []
    for x, y, col, dur in leds:
        if dur:
            lh.append(f'<circle class="led" style="animation-delay:-{lr_.uniform(0, 2):.2f}s;animation-duration:{dur:.2f}s" cx="{x:.1f}" cy="{y:.1f}" r="0.75" fill="{col}"/>')
        else:
            lh.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="0.75" fill="{col}"/>')
    a("".join(lh))
    if dark:
        halo = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{col}" opacity="0.28"/>' for x, y, col, _ in leds)
        a(f'<g {B(1.2)}>{halo}</g>')

    # ---- luz do candeeiro (noite)
    if dark:
        a('<g class="lamp" opacity="1" style="mix-blend-mode:screen">')
        a('<ellipse cx="560" cy="128" rx="170" ry="105" fill="url(#gWarm)"/>')
        a(f'<ellipse cx="566" cy="{DB + 4}" rx="62" ry="7" fill="url(#gPool)"/>')
        cone = f'M{shade[2][0]:.1f},{shade[2][1]:.1f} L{shade[3][0]:.1f},{shade[3][1]:.1f} L612,{DB + 5} L522,{DB + 5}Z'
        a(f'<clipPath id="conec"><rect x="0" y="0" width="{W}" height="{DB + 5}"/></clipPath>')
        a(f'<g clip-path="url(#conec)"><path d="{cone}" fill="url(#cone)" {B(3)}/></g>')
        a(f'<path d="M548,{DB + 2} L597,{DB + 2} L600,{DF - 1} L549,{DF - 1}Z" fill="#ffcf8f" opacity="0.35"/>')
        a(f'<path d="M{DX0 + 180},{DF + 0.4} H{DX1 - 10}" stroke="#ffc27a" stroke-width="0.8" opacity="0.5"/>')
        a("</g>")
        a(f'<g class="lamp" opacity="1"><ellipse {mouth_el} fill="#ffe9c4"/><ellipse {mouth_in} fill="#fffaf0"/>'
          f'<circle cx="{Mo[0]:.1f}" cy="{Mo[1]:.1f}" r="9" fill="#ffc47a" opacity="0.55" {B(5)}/>'
          f'<circle cx="{Mo[0]:.1f}" cy="{Mo[1]:.1f}" r="3.2" fill="#fff4dc" opacity="0.95" {B(1.2)}/></g>')
        # luz fria do monitor sobre a mesa e o teclado
        a('<g class="mon" opacity="1" style="mix-blend-mode:screen">')
        a('<ellipse cx="462" cy="100" rx="140" ry="80" fill="url(#gCool)"/>')
        a(f'<ellipse cx="462" cy="{DB + 4}" rx="80" ry="6" fill="url(#gCoolPool)"/>')
        a("</g>")
        # po a flutuar no cone
        mr = random.Random(40)
        motes = []
        for k in range(16):
            t = mr.random()
            y = shade[2][1] + 8 + t * (DB - shade[2][1] - 12)
            half = 6 + t * 36
            x = 567 + mr.uniform(-half, half) * 0.8
            motes.append(f'<circle class="mote" style="animation-delay:-{mr.uniform(0, 14):.1f}s;animation-duration:{mr.uniform(9, 17):.1f}s" cx="{x:.1f}" cy="{y:.1f}" r="{mr.choice([0.35, 0.45, 0.6])}" fill="#ffe6bf"/>')
        a('<g class="lamp" opacity="1">' + "".join(motes) + "</g>")
    else:
        # ---- sol de fim de tarde: raios + mancha no chao + brilho na janela
        a('<g style="mix-blend-mode:screen">')
        a(f'<path d="{sunpatch}" fill="#ffb45c" opacity="0.6" {B(1.2)}/>')
        a("".join(f'<path d="{b_}" fill="url(#beam)" opacity="0.33" {B(5)}/>' for b_ in beams))
        a('<ellipse cx="196" cy="80" rx="90" ry="70" fill="url(#gSun)" opacity="0.35"/>')
        a('<ellipse cx="160" cy="130" rx="110" ry="20" fill="#ffc47a" opacity="0.25" ' + B(9) + "/>")
        a('<ellipse cx="170" cy="110" rx="270" ry="170" fill="url(#gWarm)" opacity="0.55"/>')
        a("</g>")
        a('<linearGradient id="coolr" x1="0" y1="0" x2="1" y2="0"><stop offset="0.4" stop-color="#9c8cba" stop-opacity="0"/><stop offset="1" stop-color="#8a7aa8" stop-opacity="0.5"/></linearGradient>')
        a(f'<rect width="{W}" height="{H}" fill="url(#coolr)" style="mix-blend-mode:multiply"/>')
        a('<g style="mix-blend-mode:screen">')
        # radiador e peitoril apanham sol
        a('<path d="M62,124 h196 l4,5 h-204Z" fill="#ffd9a0" opacity="0.45"/>')
        a("</g>")
        # monitor: brilho frio suave
        a('<g class="mon" opacity="1" style="mix-blend-mode:screen"><ellipse cx="462" cy="104" rx="110" ry="60" fill="url(#gCool)" opacity="0.6"/></g>')
        mr = random.Random(41)
        motes = []
        for k in range(34):
            t = mr.random()
            x0_ = 90 + t * 250 + mr.uniform(-40, 40)
            y = 40 + t * 200 + mr.uniform(-20, 20)
            motes.append(f'<circle class="mote" style="animation-delay:-{mr.uniform(0, 14):.1f}s;animation-duration:{mr.uniform(9, 18):.1f}s" cx="{x0_:.1f}" cy="{y:.1f}" r="{mr.choice([0.35, 0.5, 0.7])}" fill="#fff0c8"/>')
        a("<g>" + "".join(motes) + "</g>")

    # vapor da chavena mais recente
    for k, (x, yb, col) in enumerate(slots):
        a(f'<g class="s{k}" opacity="{1 if cups[MARCH] == k + 1 else 0}"><path class="stm" stroke-dasharray="7 29" d="M{x + 2.5},{yb - 10} c-3,-4 3,-7 0,-11 s3,-7 0,-11" stroke="#efe6da" stroke-width="0.8" fill="none" opacity="0.5" stroke-linecap="round"/>'
          f'<path class="stm" stroke-dasharray="7 29" style="animation-delay:-1.7s" d="M{x + 5},{yb - 10} c-3,-4 3,-7 0,-11 s3,-7 0,-11" stroke="#efe6da" stroke-width="0.7" fill="none" opacity="0.4" stroke-linecap="round"/></g>')

    # ================================================================== PRIMEIRO PLANO: monstera (esq.) e planta suspensa (dir.)
    fg_leaf = "#0e150f" if dark else "#27401f"
    fg_rim = "#4f6d9c" if dark else "#ffd27a"
    a(f'<ellipse cx="34" cy="262" rx="40" ry="10" fill="#000" opacity="0.45" {B(5)}/>')
    a(f'<path d="M8,262 L14,232 H62 L68,262Z" fill="{"#15110f" if dark else "#5c3b2a"}"/><rect x="11" y="229" width="54" height="5" rx="1.5" fill="{"#1c1714" if dark else "#6e4834"}"/>')
    fg_vein = "#1b2a1c" if dark else "#a9c77a"
    if dark:
        a('<linearGradient id="leafg" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#0b110c"/><stop offset="1" stop-color="#15201a"/></linearGradient>')
    else:
        a('<linearGradient id="leafg" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#23391c"/><stop offset="0.6" stop-color="#3f6a2c"/><stop offset="1" stop-color="#6f9a3a"/></linearGradient>')
    leaves = [(34, 230, 70, -52, 40, 3), (38, 230, 92, -18, 46, 2), (40, 230, 60, 22, 40, 1), (30, 230, 44, -80, 34, 4),
              (44, 230, 40, 58, 34, 5), (36, 230, 30, 4, 30, 6)]
    for (bx_, by_, pl, ang, sz, seed) in leaves:
        rad = math.radians(ang - 90)
        tipx, tipy = bx_ + math.cos(rad) * pl, by_ + math.sin(rad) * pl
        ctrl = (bx_ + math.cos(rad) * pl * 0.3, by_ + math.sin(rad) * pl * 0.75)
        droop = 38 if ang > 5 else -38 if ang < -5 else 12
        a(f'<g class="swb" style="animation-delay:-{seed * 1.3:.1f}s">')
        a(f'<path d="M{bx_},{by_} Q{ctrl[0]:.1f},{ctrl[1]:.1f} {tipx:.1f},{tipy:.1f}" stroke="{fg_leaf}" stroke-width="1.5" fill="none"/>')
        d_ = monstera_leaf(seed)
        k = sz
        veins = "".join(f'<path d="M0,{-0.12 - j * 0.16:.2f} Q{s_ * 0.2:.2f},{-0.2 - j * 0.16:.2f} {s_ * 0.5:.2f},{-0.3 - j * 0.15:.2f}"/>' for j in range(5) for s_ in (-1, 1))
        tf = f'translate({tipx:.1f} {tipy:.1f}) rotate({ang + droop:.0f}) scale({k})'
        a(f'<g transform="translate(1.1 -0.9)" opacity="{0.55 if dark else 0.8}"><path transform="{tf}" d="{d_}" fill="{fg_rim}"/></g>')
        a(f'<g transform="{tf}"><path d="{d_}" fill="url(#leafg)"/>'
          f'<g stroke="{fg_vein}" stroke-width="{0.45 / k:.3f}" fill="none" opacity="0.3"><path d="M0,0.02 L0,-0.98"/>{veins}</g></g>')
        a("</g>")
    # planta suspensa a direita (vaso cortado em cima)
    pot_c = "#161210" if dark else "#c8b7a2"
    a(f'<path d="M812,-2 L822,24 M838,-2 L826,24 M824,-2 L824,24" stroke="{"#2a2320" if dark else "#a39581"}" stroke-width="0.7"/>')
    a(f'<path d="M810,24 H838 C838,40 810,40 810,24Z" fill="{pot_c}"/><rect x="809" y="22.5" width="30" height="3" rx="1.2" fill="{pot_c}"/>')
    hv = []
    hr = random.Random(55)
    for (sx_, ex_, ey_) in [(814, 806, 120), (820, 824, 160), (828, 814, 92), (816, 798, 74), (832, 836, 130)]:
        cx_ = (sx_ + ex_) / 2 + hr.uniform(-6, 6)
        hv.append(f'<path d="M{sx_},26 Q{cx_:.1f},{(26 + ey_) / 2:.1f} {ex_},{ey_}" stroke="{fg_leaf}" stroke-width="1" fill="none"/>')
        for t in [i / 8 for i in range(1, 9)]:
            px = (1 - t) ** 2 * sx_ + 2 * (1 - t) * t * cx_ + t * t * ex_
            py = (1 - t) ** 2 * 26 + 2 * (1 - t) * t * (26 + ey_) / 2 + t * t * ey_
            ang = hr.uniform(-60, 60)
            hv.append(f'<ellipse cx="{px:.1f}" cy="{py:.1f}" rx="5.2" ry="3.2" transform="rotate({ang:.0f} {px:.1f} {py:.1f})" fill="{fg_leaf}" stroke="{fg_rim}" stroke-width="0.4" stroke-opacity="0.4"/>')
    a('<g class="sway" style="animation-delay:-3s">' + "".join(hv) + "</g>")

    # ================================================================== acabamento
    a(f'<rect width="{W}" height="{H}" fill="url(#vig)"/>')
    a(f'<rect width="{W}" height="{H}" filter="url(#grain)" opacity="{0.08 if dark else 0.06}" style="mix-blend-mode:overlay"/>')
    a("</g></svg>")
    return "\n".join(o)


def main():
    days, weeks = load(sys.argv[1] if len(sys.argv) > 1 else "data/contrib.json")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "rondas/r6")
    out.mkdir(parents=True, exist_ok=True)
    for mode in ("dark", "light"):
        (out / f"03-secretaria-{mode}.svg").write_text(build(days, weeks, mode), encoding="utf-8")
    (out / "03-secretaria-noite.md").write_text(
        "<!-- Secretaria, noite e fim de tarde | Panorama largo do quarto por tras da cadeira. Escuro: noite de chuva, "
        "o candeeiro e o monitor iluminam a mesa de verdade. Claro: fim de tarde, sol baixo a entrar pela janela. "
        "Timelapse do ano (2 s por mes, dados reais): o ecra mostra o grafico de contribuicoes a encher-se, a luz segue a "
        "atividade do mes, as chavenas acumulam-se, o calendario vira a folha; os meses parados ficam as escuras. "
        "Captura estatica = o mes mais ativo. Sem texto. -->\n"
        '<picture>\n  <source media="(prefers-color-scheme: dark)" srcset="assets/03-secretaria-dark.svg">\n'
        '  <img alt="" src="assets/03-secretaria-light.svg" width="100%">\n</picture>\n', encoding="utf-8")


if __name__ == "__main__":
    main()
