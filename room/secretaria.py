"""Copia de tools/final_secretaria.py para o pacote room (imports relativos, mode="fallback" em render()).

FINAL (r9): a secretaria com relogio de luz, versao para o perfil. Evolui tools/clock_secretaria.py
(que fica intacto; a geometria base continua importada de tools/r6_03_secretaria-noite.py).

Mudancas r9b (revisao do diretor de arte):
- Relogio de 24 h com UM ponteiro (meia-noite em baixo, meio-dia em cima), aro dia/noite com o nascer e o por
  do sol reais, lume no ponteiro e nas marcas a noite. Ao vivo roda 1 volta/dia (86400 s): o atraso da Action
  + Camo (15-30 min) sao 4-8 graus, invisivel. Timelapse: 1 volta por loop, em fase com a luz.
- Lua com posicao real (alt/az) e fase: so aparece quando cai no cone da janela (de dia, palida); o luar na
  sala depende da fase, da altura e da orientacao; sem Lua a frente nao ha cunha de luz no chao.
- Monitor maior; o grafico de contribuicoes ocupa a metade de baixo do ecra (celulas de ~3 px a 1x, 40 semanas).
- Portatil tambem em tema claro de dia. Nascer: fachadas a ENE em pessego com lado de sombra azul, reflexos
  nos vidros e sala rosada; manha fria azulada; meio-dia mais branco.
- Timelapse: nuvens, janelas da cidade e avioes acelerados; sem chuva/aspirador/cobra/traca.
- Easter eggs maiores (gato redesenhado com contraluz, queque 2.3x no caderno, post-it, traca); quadro com
  casa/cipreste/passaro (1 de abril le-se logo); varao visivel no natal; planta suspensa longe do canto.
- mix-blend-mode sobe para o grupo com a opacidade (uma opacidade < 1 isolava a mistura).
- aria-label neutro ("desk").

Mudancas r9:
- Relogio de parede: ao vivo, ponteiros na hora de geracao (--at ou agora em Europe/Lisbon) e a andar a
  velocidade real (h 43200 s, min 3600 s, seg 60 s). No timelapse so roda o ponteiro das horas (2 voltas por
  loop, linear, em fase com as amostras de luz) e o dos minutos e um borrao esbatido: nunca 24 voltas nitidas.
- Janela a WSW (258 graus): mancha curta ao inicio da tarde, feixe dourado comprido ao fim do dia, jamba e
  parede a volta da janela ao sol; fachadas rosadas ao nascer; manha limpa; luar/cidade a entrar a noite.
- Monitor e candeeiro iluminam parede, mesa, teclado e rebordo; a cadeira fica em contraluz (mascara).
- Cadeira redesenhada (encosto de rede com aro, lombar, espinha, assento com espessura, bracos em L,
  base de 5 pes com rodas duplas). Extensao eletrica com LED e molho de cabos.
- Ceu: nuvens macias que passam (loop 420 s), 2 avioes a noite, grua com luz, janelas que acendem e apagam.
- Ecra: tema claro de dia e escuro a noite; logs/diff/codigo/testes conforme o bloco de 3 h.
- Calendario com o mes REAL (dias futuros so em contorno, hoje com aro); chavenas = atividade do mes real.
- Chuva rara (~5 min) e nunca ao vivo por cima de um feixe de sol. Novo: traca no candeeiro (noites quentes).
EASTER EGGS
 (a) eventos raros no loop (com atraso inicial, para quem fica a olhar):
     - robot aspirador atravessa o chao, bate na cadeira, recua e segue (ciclo 97 s, ~9 s);
     - o monitor mostra por instantes uma cobra a comer os quadrados do grafico de
       contribuicoes (piscadela a Platane/snk) (ciclo 71 s, ~5 s);
     - aguaceiro: chuva e gotas no vidro durante ~16 s (ciclo 311 s) (a chuva da r6 passou a
       easter egg ocasional).
 (b) por data/hora (clock_common.events, moon_phase):
     - natal: fio de luzes quentes no varao da cortina e no topo da estante;
     - ano_novo: fogo de artificio sobre a cidade;
     - halloween: abobora no peitoril com uma vela;
     - aniversario_conta (24/10): queque com uma vela acesa na secretaria;
     - 1_abril: o quadro esta de pernas para o ar e o relogio anda para tras;
     - sexta_tarde: post-it vermelho no canto do monitor (nao se faz deploy a sexta);
     - madrugada (02-05h): candeeiro apagado, monitor em descanso, chavenas sem vapor, cidade
       quase apagada e um gato a dormir no peitoril, em silhueta contra as luzes;
     - dia_do_pico (dia/mes do dia com mais contribuicoes, calculado dos dados): tudo mais aceso (LEDs, monitor, 8 chavenas);
     - Lua com a fase real sempre que ha ceu noturno.
 (c) pelos dados: se o ultimo dia de data/contrib.json e HOJE e tem contribuicoes, o portatil
     fica todo verde (os 4 indicadores), com um ponto a pulsar no fim da curva, e o dia de hoje
     no calendario ganha um aro.

Uso:
  python tools/final_secretaria.py data/contrib.json saida.svg [--at 2026-09-30T21:30] [--timelapse] [--show vac|snk|rain|moth]
  python tools/final_secretaria.py data/contrib.json rondas/r9-final --gallery
"""
import argparse
import importlib.util
import math
import random
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
from .clock_common import solar, to_utc, now_local, ss, keyed, moon_phase, events, lerpc  # noqa: E402
from . import r6_secretaria as R6  # noqa: E402
from .r5_common_a import months_ending  # noqa: E402
W, H, FL, VPX, VPY = R6.W, R6.H, R6.FL, R6.VPX, R6.VPY
DB, DF, DX0, DX1 = R6.DB, R6.DF, R6.DX0, R6.DX1
MX0, MX1, MY0, MY1 = 384, 540, 58, 130   # r9b: monitor maior (o grafico de contribuicoes e o protagonista)
LB, LE, LJ, LT = R6.LB, R6.LE, R6.LJ, R6.LT
GLASS, PANES = R6.GLASS, R6.PANES
monstera_leaf, hull, poly = R6.monstera_leaf, R6.hull, R6.poly

WIN_AZ = 258.0          # a janela olha para WSW (sol da tarde a entrar a direito ao fim do dia)
SECS = 48.0          # timelapse: 24 h em 48 s (1 h = 2 s)


# ================================================================== rig de luz
class Rig:
    """Cada camada de luz recebe a opacidade de um dict de pesos. Estatico: o valor do momento.
    Timelapse: uma animacao CSS com os pesos amostrados (mesma estrutura SVG)."""

    def __init__(self, samples, static_index=0, secs=SECS, timelapse=False):
        self.samples, self.si, self.secs, self.tl = samples, static_index, secs, timelapse
        self.css = {}

    def w(self, name):
        return float(self.samples[self.si].get(name, 0.0))

    def any(self, name, thr=0.004):
        if self.tl:
            return max(float(s.get(name, 0.0)) for s in self.samples) > thr
        return self.w(name) > thr

    def op(self, name):
        v = self.w(name)
        if not self.tl:
            return f'opacity="{v:.3f}"'
        key = "k" + "".join(ch if ch.isalnum() else "_" for ch in name)
        if key not in self.css:
            vals = [float(s.get(name, 0.0)) for s in self.samples]
            n = len(vals) - 1
            kf = "".join(f"{100 * i / n:.2f}%{{opacity:{v_:.3f}}}" for i, v_ in enumerate(vals))
            self.css[key] = f"@keyframes {key}{{{kf}}}.{key}{{animation:{key} {self.secs}s linear infinite}}"
        return f'class="{key}" opacity="{v:.3f}"'

    def g(self, name, body, extra=""):
        if not body or not self.any(name):
            return ""
        # a opacidade do grupo isola a mistura: um mix-blend-mode la dentro so mistura com o proprio grupo.
        # Se o corpo e um unico <g style="mix-blend-mode:X">, o modo sobe para o grupo com a opacidade.
        m = re.match(r'<g style="mix-blend-mode:(\w+)">', body)
        if m and not extra and body.endswith("</g>") and _single_group(body):
            extra = f' style="mix-blend-mode:{m.group(1)}"'
            body = body[m.end():-4]
        return f'<g {self.op(name)}{extra}>{body}</g>'

    def per_sample(self, i, body, extra=""):
        if not self.tl:
            return f'<g{extra}>{body}</g>' if i == self.si else ""
        n = len(self.samples) - 1
        key = f"ps{i}"
        kf = "".join(f"{max(0, min(100, 100 * j / n)):.3f}%{{opacity:{1 if j == i else 0}}}" for j in (i - 1, i, i + 1))
        pre = "0%{opacity:0}" if i > 1 else ""
        post = "100%{opacity:0}" if i < n - 1 else ""
        self.css[key] = f"@keyframes {key}{{{pre}{kf}{post}}}.{key}{{animation:{key} {self.secs}s linear infinite}}"
        return f'<g class="{key}" opacity="{1 if i == self.si else 0}"{extra}>{body}</g>'

    def style(self):
        return "".join(self.css.values())


def _single_group(body):
    """True se o primeiro <g ...> fecha exatamente no fim do corpo."""
    depth = 0
    for m in re.finditer(r"<g[\s>]|</g>", body):
        depth += -1 if m.group(0) == "</g>" else 1
        if depth == 0:
            return m.end() == len(body)
    return False


def stack_ops(order, w):
    """pesos que somam 1 -> opacidades de camadas empilhadas (de baixo para cima) = mistura linear."""
    out, rem = {}, 1.0
    for k in reversed(order[1:]):
        v = w.get(k, 0.0)
        out[k] = min(1.0, v / rem) if rem > 1e-6 else 0.0
        rem -= v
    out[order[0]] = 1.0
    return out


# ================================================================== dados
def load(path):
    return R6.load(path)          # (days {date: n}, weeks [[(date, n)]])


# ================================================================== estado da luz
SKY_ORDER = ["night", "bluea", "blue", "rise", "morn", "day", "gold", "ember"]
SKY_AM = [(-90, {"night": 1}), (-16, {"night": 1}), (-12, {"night": .35, "bluea": .65}), (-4.5, {"bluea": 1}),
          (-1, {"bluea": .35, "rise": .65}), (3, {"rise": 1}), (9, {"rise": .25, "morn": .75}),
          (20, {"morn": .35, "day": .65}), (32, {"day": 1}), (90, {"day": 1})]
SKY_PM = [(-90, {"night": 1}), (-16, {"night": 1}), (-12, {"night": .3, "blue": .7}), (-4.5, {"blue": 1}),
          (-1.5, {"blue": .4, "ember": .6}), (1.5, {"ember": 1}), (6, {"ember": .35, "gold": .65}),
          (14, {"gold": 1}), (24, {"gold": .4, "day": .6}), (34, {"day": 1}), (90, {"day": 1})]


def hour_curve(h, pts):
    """interpolacao ciclica numa lista [(hora, valor)]."""
    pts = sorted(pts)
    ext = [(pts[-1][0] - 24, pts[-1][1])] + pts + [(pts[0][0] + 24, pts[0][1])]
    for (x0, v0), (x1, v1) in zip(ext, ext[1:]):
        if x0 <= h <= x1:
            return v0 + (v1 - v0) * ((h - x0) / (x1 - x0) if x1 > x0 else 0)
    return pts[0][1]


def state(local_dt, days=None):
    utc = to_utc(local_dt)
    el, az = solar(utc)
    ev = events(local_dt, days)
    h = local_dt.hour + local_dt.minute / 60
    pm = az > 180
    sk = keyed(SKY_PM if pm else SKY_AM, el)
    tot = sum(sk.values()) or 1
    sk = {k: v / tot for k, v in sk.items()}
    N, B = sk.get("night", 0), sk.get("bluea", 0) + sk.get("blue", 0)
    R, M, D = sk.get("rise", 0), sk.get("morn", 0), sk.get("day", 0)
    G, E = sk.get("gold", 0), sk.get("ember", 0)
    mad = "madrugada" in ev
    sleep = 1.0 if 2 <= h < 7 else 0.0
    lamp = ss(0.5, -1.5, el) * (1 - sleep)
    diff = (az - WIN_AZ + 540) % 360 - 180
    sun = ss(95, 65, abs(diff)) * ss(-1.2, 2.5, el)
    dark = ss(3, -6, el)
    peak = "dia_do_pico" in ev
    malt, maz = moon_pos(utc)
    mph = moon_phase(utc)
    illum = (1 - math.cos(2 * math.pi * mph)) / 2
    mdiff = (maz - WIN_AZ + 540) % 360 - 180
    mup = ss(-1, 8, malt)
    mface = ss(100, 55, abs(mdiff))
    w = {}
    for k, v in stack_ops(SKY_ORDER, sk).items():
        w["sk_" + k] = v
    w.update({
        "ovN_L": N * lamp, "ovN_D": N * (1 - lamp), "ovB_L": B * lamp, "ovB_D": B * (1 - lamp),
        "ovR": R, "ovM": M, "ovG": G, "ovE": E, "vig2": N + .5 * B,
        "lamp": lamp, "dark": dark, "stars": ss(-6, -13, el), "sun": sun,
        "sunglow": sun * (G + E + .5 * R + .3 * M + .25 * D),
        "cityA": ss(1, -4, el) * hour_curve(h, [(0, .9), (3, .6), (6, .7), (8, .8), (12, 1), (18, 1)]),
        "cityB": ss(-1, -6, el) * hour_curve(h, [(0, .7), (1.5, .25), (5, .1), (6.5, .5), (8, .6), (18, 1), (23, 1)]),
        "cityC": ss(-3, -9, el) * hour_curve(h, [(0, .35), (1, .05), (6, 0), (6.8, .5), (8, .5), (18.5, .8), (21, 1), (23, .8)]),
        "haze": M + .6 * R + .3 * D,
        "rimW": min(1, (G + E) * (.4 + .6 * sun) + .3 * R),
        "rimC": min(1, N + B),
        "shL": lamp, "shD": 1 - lamp,
        "chN": 1 - sun * (G + E + D + M), "chD": sun * (G + E + D + M),
        "reflN": (N + B) * .6 * min(1, .3 + .7 * illum * mup * (.35 + .65 * mface)),
        "scr": .35 if mad else (1.25 if peak else 1.0),
        "scrsaver": 1.0 if mad else 0.0,
        "steam": 0.0 if mad else hour_curve(h, [(6.5, 0), (7.5, 1), (10.5, 1), (11.5, 0), (13, 0), (13.5, 1), (15, 1), (16, 0),
                                                 (20, 0), (20.5, 1), (23, 1), (23.9, 0)]),
        "cat": 1.0 if mad else 0.0,
        "skypool": min(1, M + D + .6 * R + .5 * G),
        "ledbright": .55 + .45 * dark,
        "ovD": D,
        "daywin": ss(-2, 5, el),
        "fall": min(1, .45 * M + .4 * D + .8 * R + .75 * G + .9 * E + .6 * B),
        "lampT": lamp * min(1, N + B),
        # r9: personalidade das horas
        "thL": ss(1.5, 4, el) * (0 if mad else 1),                   # tema claro no ecra de dia
        "thD": 1 - ss(1.5, 4, el) * (0 if mad else 1),
        "bfront": (0 if pm else 1) * ss(-2.5, 1.5, el) * ss(24, 7, el),  # fachadas rosadas ao nascer
        # luz fria da janela a noite: brilho da cidade (fixo, fraco) + luar (fase x altura x orientacao)
        "moonfill": min(1, N + .6 * B) * min(1, .3 + .7 * illum * mup * (.35 + .65 * mface)),
        "moonbeam": N * illum * mup * mface * ss(35, 5, malt),       # cunha de luar no chao: so com a Lua a frente
        "reveal": min(1, sun * (G + E + .6 * D + .4 * M)) * ss(-12, 12, diff),            # jamba da janela ao sol
        "leafsh": sun,                                                  # sombra da monstera no chao
        "morn": min(1, M + .5 * R),                                     # manha: luz fria e limpa
        "moth": lamp * (1.0 if local_dt.month in (5, 6, 7, 8, 9, 10) else 0.0),
        "monlit": dark,                                                 # o monitor ilumina a sala
        "amcool": (0 if pm else 1) * ss(4, 12, el) * ss(44, 30, el),    # manha: luz fria azulada rebatida
        "noon": ss(34, 46, el),                                         # meio-dia: sala mais branca
    })
    for k in range(8):
        w[f"cv{k}"] = 1.0 if int(h // 3) == k else 0.0
    st = dict(el=el, az=az, pm=pm, diff=diff, sun=sun, ev=ev, h=h, utc=utc, dt=local_dt,
              moon=mph, malt=malt, maz=maz, sky=sk, peak=peak, mad=mad)
    return w, st


# ================================================================== paleta base (dia neutro)
C = dict(wall0="#e8dfd1", wall1="#dccfbd", base="#cbbba4", fl0="#b08662", fl1="#c4976c", seam="#8c6546",
         frame="#f6f1e8", frame_d="#d4cabd", sill="#f6f0e7", rad="#ebe6de", rad_d="#c2baae", cur0="#c6b69f", cur1="#ddd0bc",
         desk0="#c08e60", desk1="#a3754c", edge="#7c5638", metal="#33323a", rug="#6e5652", rug2="#8f7169",
         chair="#2f2e35", chair2="#46454d", mesh="#24232a",
         book=["#8b4d45", "#46678a", "#a58e5a", "#557a62", "#76608a", "#b0703f", "#3f4e66"])

SKY = {  # (paragens de cima para baixo)
    "night": [("0", "#050a17"), (".6", "#0c152b"), (".9", "#1b2140"), ("1", "#2c2a44")],
    "bluea": [("0", "#152756"), (".55", "#2f4682"), (".85", "#6b6a9e"), ("1", "#a08aa6")],
    "blue": [("0", "#13244f"), (".55", "#2b3f7a"), (".85", "#5f5f96"), ("1", "#8d7598")],
    "rise": [("0", "#6d8cc4"), (".45", "#b7b1cc"), (".8", "#f4c6aa"), ("1", "#ffd9b0")],
    "morn": [("0", "#93b3dc"), (".45", "#cddbec"), (".8", "#f6e2cf"), ("1", "#ffdcbc")],
    "day": [("0", "#3b76c8"), (".5", "#6fa2e0"), (".85", "#aecdf0"), ("1", "#cfe0f0")],
    "gold": [("0", "#7f93c2"), (".35", "#b9a1b8"), (".62", "#eaa987"), (".85", "#fbc486"), ("1", "#ffdca2")],
    "ember": [("0", "#34467e"), (".35", "#8a5f86"), (".65", "#e27c5a"), (".88", "#ffa25e"), ("1", "#ffc27a")],
}
BLD = {  # 3 planos de predios (longe, meio, perto)
    "night": ("#1f2946", "#161d36", "#0d1224"), "bluea": ("#39436e", "#2a3260", "#1b2146"),
    "blue": ("#3a3f6a", "#2b2f5a", "#1c1f42"), "rise": ("#a192ad", "#80719a", "#5b4f73"),
    "morn": ("#e2d9d0", "#e9d3bd", "#dcbfa3"), "day": ("#9fb0c6", "#7b8ca6", "#566680"),
    "gold": ("#b89aa8", "#8d7390", "#5d4a68"), "ember": ("#8c6a8c", "#644b74", "#3f3052"),
}
CLOUD = {"night": ("#2a3452", .45), "bluea": ("#6b6c9c", .6), "blue": ("#5d5a8c", .6), "rise": ("#ffd2c0", .85),
         "morn": ("#fff1e4", .75), "day": ("#ffffff", .9), "gold": ("#f6c3a8", .85), "ember": ("#ff9f80", .85)}
OVC = {"ovN": "#18203a", "ovB": "#4a5684", "ovR": "#c9b0ba", "ovM": "#cfd9ea", "ovG": "#ffc990", "ovE": "#d48a68", "ovD": "#f7f3ee"}


def moon_path(cx, cy, r, p):
    """silhueta iluminada da Lua para a fase p (0 nova, .5 cheia); hemisferio norte."""
    k = math.cos(2 * math.pi * p)
    rx = abs(k) * r
    top, bot = (cx, cy - r), (cx, cy + r)
    if p < .5:   # crescente: lado direito
        return (f"M{top[0]:.2f},{top[1]:.2f} A{r},{r} 0 0 1 {bot[0]:.2f},{bot[1]:.2f} "
                f"A{rx:.2f},{r} 0 0 {0 if k > 0 else 1} {top[0]:.2f},{top[1]:.2f}Z")
    return (f"M{top[0]:.2f},{top[1]:.2f} A{r},{r} 0 0 0 {bot[0]:.2f},{bot[1]:.2f} "
            f"A{rx:.2f},{r} 0 0 {1 if k > 0 else 0} {top[0]:.2f},{top[1]:.2f}Z")


def moon_pos(utc, lat=39.5, lon=-8.0):
    """(altitude, azimute a partir do norte) da Lua, baixa precisao (~1 grau; sem paralaxe)."""
    r = math.radians
    d = utc.timestamp() / 86400.0 + 2440587.5 - 2451545.0
    L = 218.316 + 13.176396 * d
    M = 134.963 + 13.064993 * d
    F = 93.272 + 13.229350 * d
    lam = r(L + 6.289 * math.sin(r(M)))
    bet = r(5.128 * math.sin(r(F)))
    eps = r(23.439)
    ra = math.atan2(math.sin(lam) * math.cos(eps) - math.tan(bet) * math.sin(eps), math.cos(lam))
    dec = math.asin(math.sin(bet) * math.cos(eps) + math.cos(bet) * math.sin(eps) * math.sin(lam))
    lst = r((280.46061837 + 360.98564736629 * d + lon) % 360)
    ha = lst - ra
    ph = r(lat)
    alt = math.asin(math.sin(ph) * math.sin(dec) + math.cos(ph) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha), math.tan(dec) * math.cos(ph) - math.sin(ph) * math.cos(ha))
    return math.degrees(alt), math.degrees(az) % 360


def moon_disc(st):
    """disco da Lua so quando cai no cone da janela (mesma projecao do sol)."""
    alt, az = st["malt"], st["maz"]
    diff = (az - WIN_AZ + 540) % 360 - 180
    if alt < -1 or abs(diff) > 75:
        return ""
    x, y = 160 + diff * 1.1, 108 - alt * 4.2
    if not (80 < x < 240 and 20 < y < 112):
        return ""
    p, day = st["moon"], ss(-6, 4, st["el"])
    illum = (1 - math.cos(2 * math.pi * p)) / 2
    if illum < .04:
        return ""
    r_ = 5.5
    glow = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r_ * 4}" fill="url(#gSky)" opacity="{.4 * illum * (1 - day):.2f}"/>'
    dark = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r_}" fill="#1c2238" opacity="{.55 * (1 - day):.2f}"/>'
    lit = f'<path d="{moon_path(x, y, r_, p)}" fill="{"#f1ecdc" if day < .5 else "#ffffff"}" opacity="{1 - .5 * day:.2f}"/>'
    return glow + dark + lit


# ================================================================== geometria do sol
def sun_geom(st):
    el, diff = st["el"], st["diff"]
    e_s = max(10.0, min(64.0, el * 1.05 + 4))
    s = 0.35 / math.tan(math.radians(e_s))
    lat = max(-2.4, min(2.6, -0.05 * diff))

    def floorpt(u, v):
        gx, gy = R6.glasspt(u, v)
        yy = FL + 8 + (1 - v) * 92 * s
        dy = yy - FL
        return (gx + dy * lat) * (1 + dy * .004) - VPX * dy * .004, yy
    return floorpt


def sun_layers(st, idp):
    """feixes + mancha no chao para este instante (string SVG)."""
    k = st["sun"]
    if k < .02:
        return ""
    fp = sun_geom(st)
    el = st["el"]
    col = lerpc("#ffa040", "#ffecc4", ss(8, 42, el))
    bc = lerpc("#ffb866", "#fff4e0", ss(8, 42, el))
    o = []
    panes = [[fp(u, v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))] for (u0, u1), (v0, v1) in PANES]
    beams = [poly(hull(q + [R6.glasspt(u, v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]))
             for q, ((u0, u1), (v0, v1)) in zip(panes, PANES)]
    low = 1 + .5 * ss(25, 4, el)
    o.append(f'<linearGradient id="{idp}bm" x1="0" y1="0" x2="{.3 + .7 * ss(10, 50, -abs(st["diff"]) + 60):.2f}" y2="1">'
             f'<stop offset="0" stop-color="{bc}" stop-opacity=".6"/><stop offset="1" stop-color="{bc}" stop-opacity="0"/></linearGradient>')
    o.append('<g style="mix-blend-mode:screen">')
    o.append(f'<g clip-path="url(#floorc)"><path d="{" ".join(poly(q) for q in panes)}" fill="{col}" opacity="{(.62 + .15 * ss(20, 45, el)) * k:.3f}" filter="url(#b2)"/>'
             f'<path d="{" ".join(poly(q) for q in panes)}" fill="{col}" opacity="{.42 * k:.3f}" filter="url(#b0_6)"/></g>')
    o.append("".join(f'<path d="{b_}" fill="url(#{idp}bm)" opacity="{.4 * k * low:.3f}" filter="url(#b5)"/>' for b_ in beams))
    # peitoril e radiador apanham sol
    o.append(f'<path d="M62,124 h196 l4,5 h-204Z" fill="#ffd9a0" opacity="{.45 * k:.3f}"/>')
    o.append("</g>")
    # po no feixe
    mr = random.Random(41)
    motes = []
    for _ in range(int(10 + 22 * k)):
        u, v, t = mr.random(), mr.random(), mr.random() * .9 + .05
        g0 = R6.glasspt(u, v)
        f0 = fp(u, v)
        x, y = g0[0] + (f0[0] - g0[0]) * t, g0[1] + (f0[1] - g0[1]) * t
        if y > H or x > W:
            continue
        motes.append(f'<circle class="mote" style="animation-delay:-{mr.uniform(0, 14):.1f}s;animation-duration:{mr.uniform(9, 18):.1f}s" '
                     f'cx="{x:.1f}" cy="{y:.1f}" r="{mr.choice([.35, .5, .7])}" fill="#fff0c8" opacity="{.9 * k:.2f}"/>')
    o.append("<g>" + "".join(motes) + "</g>")
    return "".join(o)


def sun_disc(st):
    el, diff = st["el"], st["diff"]
    if el < -2 or abs(diff) > 75:
        return ""
    x = 160 + diff * 1.1
    y = 108 - el * 4.2
    if not (60 < x < 262 and -20 < y < 130):
        return ""
    col = lerpc("#ffb070", "#fff8e8", ss(0, 20, el))
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="60" fill="url(#gSun)" opacity=".75"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{6.5 + 1.5 * ss(8, 0, el):.1f}" fill="{col}"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="30" fill="url(#gSun)" opacity=".5" style="mix-blend-mode:screen"/>')


# ================================================================== cena
def build(data, rig, st, sts=None, idp=""):
    """data = (days, weeks); rig = Rig; st = estado do momento estatico; sts = estados de todas as
    amostras (timelapse)."""
    days, weeks = data
    sts = sts or [st]
    ev = st["ev"]
    ldt = st["dt"]
    o = []
    a = o.append
    css = []
    B = lambda s: f'filter="url(#b{str(s).replace(".", "_")})"'

    # ---------------------------------------------------------------- dados do momento
    # os ultimos 12 meses ate ao mes corrente (hora de Lisboa); o mes corrente (parcial) e o ultimo
    mc = [sum(c for d, c in days.items() if (d.year, d.month) == ym) for ym in months_ending(ldt)]
    peak = max(max(mc), 1)
    # mes REAL (o calendario e as chavenas seguem a data, nao a janela fixa de 12 meses)
    cur_m = sum(c for d, c in days.items() if (d.year, d.month) == (ldt.year, ldt.month))
    cups_n = 8 if st["peak"] else (0 if cur_m < 5 else max(1, min(8, round(8 * math.sqrt(cur_m / peak)))))
    last_day = max(days)
    today_ok = last_day == ldt.date() and days[last_day] > 0

    # ---------------------------------------------------------------- defs
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
      f'aria-label="desk">')
    a("<!--STYLE-->")
    a("<defs>")
    a(f'<clipPath id="card"><rect width="{W}" height="{H}" rx="12"/></clipPath>')
    a('<clipPath id="glass"><rect x="78" y="24" width="164" height="92"/></clipPath>')
    a(f'<clipPath id="floorc"><rect x="0" y="{FL}" width="{W}" height="{H - FL}"/></clipPath>')
    a(f'<clipPath id="screen"><rect x="{MX0 + 3}" y="{MY0 + 3}" width="{MX1 - MX0 - 6}" height="{MY1 - MY0 - 6}"/></clipPath>')
    a(f'<linearGradient id="wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C["wall0"]}"/><stop offset="1" stop-color="{C["wall1"]}"/></linearGradient>')
    a(f'<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C["fl0"]}"/><stop offset="1" stop-color="{C["fl1"]}"/></linearGradient>')
    for k, stops in SKY.items():
        a(f'<linearGradient id="sky_{k}" x1="0" y1="0" x2="0" y2="1">' + "".join(f'<stop offset="{o_}" stop-color="{c_}"/>' for o_, c_ in stops) + "</linearGradient>")
    a(f'<linearGradient id="deskt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C["desk1"]}"/><stop offset="1" stop-color="{C["desk0"]}"/></linearGradient>')
    a(f'<linearGradient id="cur" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C["cur0"]}"/><stop offset="0.2" stop-color="{C["cur1"]}"/><stop offset="0.35" stop-color="{C["cur0"]}"/><stop offset="0.55" stop-color="{C["cur1"]}"/><stop offset="0.75" stop-color="{C["cur0"]}"/><stop offset="0.9" stop-color="{C["cur1"]}"/><stop offset="1" stop-color="{C["cur0"]}"/></linearGradient>')
    a('<linearGradient id="scrbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#141b2c"/><stop offset="1" stop-color="#0c111c"/></linearGradient>')
    a('<linearGradient id="gloss" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0.09"/><stop offset="0.45" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    a(f'<linearGradient id="chairg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C["chair"]}"/><stop offset="0.5" stop-color="{C["chair2"]}"/><stop offset="1" stop-color="{C["chair"]}"/></linearGradient>')
    a('<radialGradient id="clockface" cx=".45" cy=".4" r=".7"><stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset=".8" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".18"/></radialGradient>')
    a('<linearGradient id="metalg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#9aa0a8"/><stop offset="0.5" stop-color="#d7dbe0"/><stop offset="1" stop-color="#7d838c"/></linearGradient>')

    def hole(id_, stops):
        a(f'<radialGradient id="{id_}">' + "".join(f'<stop offset="{s}" stop-color="#000" stop-opacity="{op}"/>' for s, op in stops) + "</radialGradient>")
    hole("hLamp", [(0, .8), (0.25, 0.66), (0.55, 0.36), (0.8, 0.12), (1, 0)])
    hole("hMon", [(0, 0.45), (0.45, 0.26), (0.8, 0.08), (1, 0)])
    hole("hWin", [(0, 0.7), (0.5, 0.35), (1, 0)])

    def glow(id_, col, stops):
        a(f'<radialGradient id="{id_}">' + "".join(f'<stop offset="{s}" stop-color="{col}" stop-opacity="{op}"/>' for s, op in stops) + "</radialGradient>")
    glow("gWarm", "#ff9a45", [(0, 0.5), (0.4, 0.24), (1, 0)])
    glow("gPool", "#ffd49a", [(0, 0.85), (0.5, 0.35), (1, 0)])
    glow("gCool", "#6f9bff", [(0, 0.3), (0.5, 0.12), (1, 0)])
    glow("gCoolPool", "#a9c3ff", [(0, 0.45), (1, 0)])
    glow("gSun", "#fff0c8", [(0, 1), (0.2, 0.8), (0.5, 0.25), (1, 0)])
    glow("gCity", "#ff9d5c", [(0, 0.35), (1, 0)])
    glow("gSky", "#dfe9ff", [(0, 0.5), (1, 0)])
    glow("gFlame", "#ffb45a", [(0, 0.9), (0.4, 0.35), (1, 0)])
    a('<linearGradient id="cone" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd9a0" stop-opacity="0.75"/><stop offset="0.6" stop-color="#ffc27a" stop-opacity="0.25"/><stop offset="1" stop-color="#ffb466" stop-opacity="0.04"/></linearGradient>')
    a('<radialGradient id="vig" cx="0.5" cy="0.45" r="0.8"><stop offset="0.5" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.26"/></radialGradient>')
    a('<radialGradient id="vig2" cx="0.5" cy="0.45" r="0.8"><stop offset="0.45" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.4"/></radialGradient>')
    a('<filter id="shad" x="-20%" y="-20%" width="140%" height="140%"><feColorMatrix values="0 0 0 0 .05  0 0 0 0 .03  0 0 0 0 .02  0 0 0 .55 0"/><feGaussianBlur stdDeviation="1.1"/></filter>')
    for s in (0.6, 1.2, 2, 3, 5, 9, 14):
        a(f'<filter id="b{str(s).replace(".", "_")}" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="{s}"/></filter>')
    a('<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7"/>'
      '<feColorMatrix values="0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 1.6 -0.55"/></filter>')

    # mascaras de luz: preto = sem escuridao (buracos)
    def mask(id_, lamp):
        s = [f'<mask id="{id_}" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#fff"/>']
        if lamp:
            s.append('<ellipse cx="566" cy="140" rx="200" ry="140" fill="url(#hLamp)"/>')
            s.append('<ellipse cx="566" cy="150" rx="90" ry="40" fill="url(#hLamp)"/>')
            s.append('<ellipse cx="600" cy="120" rx="130" ry="70" fill="url(#hLamp)" opacity="0.5"/>')
        s.append('<ellipse cx="462" cy="112" rx="170" ry="120" fill="url(#hMon)"/>')
        s.append('<ellipse cx="160" cy="80" rx="150" ry="130" fill="url(#hWin)" opacity=".7"/>')
        s.append('<rect x="78" y="24" width="164" height="92" fill="#000"/>')
        s.append(f'<path d="{CH_BACK}" fill="#fff" opacity=".8"/><path d="M{CHX - 38},196 H{CHX + 38} V216 H{CHX - 38}Z" fill="#fff" opacity=".6"/></mask>')
        a("".join(s))
    a(f'<mask id="mNoChair" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#fff"/>'
      f'<path d="{CH_BACK}" fill="#000" opacity=".85"/><path d="M{CHX - 38},197 H{CHX + 38} V216 H{CHX - 38}Z" fill="#000" opacity=".6"/></mask>')
    mask("mLamp", True)
    mask("mDark", False)
    a(f'<mask id="mGlass" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#fff"/>'
      '<rect x="78" y="24" width="164" height="92" fill="#000"/></mask>')
    a("</defs>")

    # ---------------------------------------------------------------- css fixo
    css.append(".rn{animation:rn .6s linear infinite}.rn2{animation:rn .85s linear infinite}@keyframes rn{from{transform:translate(0,-46px)}to{transform:translate(-7px,0)}}")
    css.append(".dr{animation:dr 7s ease-in infinite}@keyframes dr{0%{transform:translateY(0);opacity:0}8%{opacity:1}70%{transform:translateY(0)}100%{transform:translateY(40px);opacity:0}}")
    css.append(".code{animation:code 12s steps(18) infinite}@keyframes code{to{transform:translateY(-57.6px)}}")
    css.append(".cur{animation:cur 1.1s steps(1) infinite}@keyframes cur{50%{opacity:0}}")
    css.append(".led{animation:led 1.7s steps(1) infinite}@keyframes led{0%{opacity:1}30%{opacity:.25}45%{opacity:1}60%{opacity:.35}}")
    css.append(".blink{animation:blink 3s steps(1) infinite}@keyframes blink{0%{opacity:1}6%{opacity:0}}")
    css.append(".tw{animation:tw 9s steps(1) infinite}@keyframes tw{0%{opacity:1}50%{opacity:0}}")
    css.append(".stw{animation:stw var(--d) ease-in-out infinite alternate}@keyframes stw{0%{opacity:.2}100%{opacity:1}}")
    css.append(".stm{animation:stm 3.4s linear infinite}@keyframes stm{from{stroke-dashoffset:36}to{stroke-dashoffset:0}}")
    css.append(".sway{transform-box:fill-box;transform-origin:50% 0;animation:sway 7s ease-in-out infinite alternate}@keyframes sway{from{transform:rotate(-1.5deg)}to{transform:rotate(2deg)}}")
    css.append(".swb{transform-box:fill-box;transform-origin:50% 100%;animation:swb 9s ease-in-out infinite alternate}@keyframes swb{from{transform:rotate(-1deg)}to{transform:rotate(1.2deg)}}")
    css.append(".mote{animation:mote 14s ease-in-out infinite alternate}@keyframes mote{0%{transform:translate(0,0);opacity:.2}50%{opacity:.9}100%{transform:translate(9px,-16px);opacity:.3}}")
    css.append(f".cloud{{animation:cloud {24 if rig.tl else 420}s linear infinite}}@keyframes cloud{{from{{transform:translate(0,0)}}to{{transform:translate(-{CLOUD_P}px,0)}}}}")
    css.append(".wt{animation:wt 90s steps(1) infinite}@keyframes wt{0%{opacity:0}35%{opacity:1}80%{opacity:0}}")
    css.append(".breath{transform-box:fill-box;transform-origin:50% 100%;animation:breath 4.2s ease-in-out infinite}@keyframes breath{50%{transform:scaleY(1.06)}}")
    css.append(".flk{animation:flk 1.3s ease-in-out infinite alternate}@keyframes flk{0%{opacity:.75}40%{opacity:1}70%{opacity:.85}100%{opacity:.95}}")
    css.append(".pulse{animation:pulse 1.6s ease-in-out infinite}@keyframes pulse{50%{opacity:.25}}")

    a('<g clip-path="url(#card)">')

    # ================================================================== PAREDE
    a(f'<rect width="{W}" height="{H}" fill="url(#wall)"/>')

    # ------------------------------------------------------------------ JANELA (exterior)
    a('<g clip-path="url(#glass)">')
    for k in SKY_ORDER:
        if rig.any("sk_" + k) or k == "night":
            a(f'<g {rig.op("sk_" + k)}><rect x="78" y="24" width="164" height="92" fill="url(#sky_{k})"/></g>')
    # estrelas e Lua
    rs = random.Random(21)
    stars = []
    for _ in range(30):
        x, y = rs.uniform(80, 240), rs.uniform(26, 92)
        stars.append(f'<circle class="stw" style="--d:{2 + rs.random() * 4:.1f}s;animation-delay:-{rs.random() * 4:.1f}s" cx="{x:.1f}" cy="{y:.1f}" r="{rs.uniform(.35, .8):.2f}" fill="#e8eeff"/>')
    a(rig.g("stars", "".join(stars)))
    # Lua: posicao e fase reais; so aparece quando esta no cone da janela (tambem de dia, palida)
    for i, s_ in enumerate(sts):
        d_ = moon_disc(s_)
        if d_:
            a(rig.per_sample(i, d_))
    # fogo de artificio (ano novo)
    if "ano_novo" in ev:
        a(fireworks())
    # sol (disco por amostra)
    for i, s_ in enumerate(sts):
        d_ = sun_disc(s_)
        if d_:
            a(rig.per_sample(i, d_))
    # nuvens: cumulos e estratos numa faixa que se repete e passa devagar (geometria unica, cor por momento)
    a(f'<defs><g id="{idp}clouds">{cloud_band()}</g></defs>')
    a('<g class="cloud">')
    for k in SKY_ORDER:
        if rig.any("sk_" + k) or k == "night":
            col, op_ = CLOUD[k]
            a(f'<g {rig.op("sk_" + k)} {B(1.2)}><use href="#{idp}clouds" fill="{col}" opacity="{op_}"/>'
              f'<use href="#{idp}clouds" x="{CLOUD_P}" fill="{col}" opacity="{op_}"/></g>')
    a("</g>")
    # avioes a noite (luz de navegacao vermelha + estroboscopio branco), com intervalos
    a(rig.g("dark", planes_svg(rig.tl)))
    # predios (3 planos) com janelas acesas por grupos
    br = random.Random(3)
    planes = [(102, 8, 26), (108, 12, 44), (114, 18, 70)]
    bgeo = []
    wins = {"A": [], "B": [], "C": []}
    edges = []
    sides = []
    for li, (y0, hmin, hmax) in enumerate(planes):
        x = 70
        bl = []
        while x < 250:
            bw = br.uniform(8, 22) * (1 + li * 0.25)
            bh = br.uniform(hmin, hmax)
            if li == 2 and br.random() < 0.55:
                x += bw * 1.4
                continue
            top = y0 + 4 - bh
            bl.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{bh + 30:.1f}"/>')
            edges.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" height="0.8"/>')
            if li < 2:   # lado a sombra (NNW) quando o sol nasce a E, atras de nos
                sides.append(f'<rect x="{x + bw * .74:.1f}" y="{top:.1f}" width="{bw * .26:.1f}" height="{bh + 30:.1f}"/>')
            if li == 2 and br.random() < 0.3:
                bl.append(f'<rect x="{x + bw * 0.3:.1f}" y="{top - 5:.1f}" width="{bw * 0.4:.1f}" height="6"/>')
            for yy in range(int(top + 3), 118, 3 + li):
                for xx in range(int(x + 2), int(x + bw - 2), 3 + li):
                    r_ = br.random()
                    if r_ < .09 + .07 * li:
                        grp = "A" if r_ < .035 + .03 * li else ("B" if r_ < .065 + .05 * li else "C")
                        wins[grp].append(f'<rect x="{xx}" y="{yy}" width="{1 + li * 0.4:.1f}" height="{1.3 + li * 0.4:.1f}"/>')
            x += bw + br.uniform(0, 3)
        bgeo.append("".join(bl))
    a(f'<defs>' + "".join(f'<g id="{idp}bp{li}">{g}</g>' for li, g in enumerate(bgeo)) + '</defs>')
    a(rig.g("haze", '<rect x="78" y="70" width="164" height="46" fill="#f4efe8" opacity=".35" filter="url(#b5)"/>'))
    # grua de construcao ao longe (cor do plano mais distante)
    a(f'<defs><g id="{idp}crane" fill="none" stroke="currentColor" stroke-width=".6">'
      '<path d="M121,98 V64 M119.5,98 V64 M119.5,64 H147 M119.5,64 H111 M121,64 L127,60 L136,64 M127,60 V64"/>'
      '<path d="M140,64 v9" stroke-width=".3"/><rect x="110" y="64" width="3" height="2.2" fill="currentColor" stroke="none"/>'
      '<path d="M119.5,70 L121,74 L119.5,78 L121,82 L119.5,86 L121,90 L119.5,94" stroke-width=".25"/></g></defs>')
    for k in SKY_ORDER:
        if rig.any("sk_" + k) or k == "night":
            a(f'<g {rig.op("sk_" + k)}><use href="#{idp}crane" color="{BLD[k][0]}"/></g>')
    for li in range(3):
        for k in SKY_ORDER:
            if rig.any("sk_" + k) or k == "night":
                a(f'<g {rig.op("sk_" + k)}><use href="#{idp}bp{li}" fill="{BLD[k][li]}"/></g>')
        if li < 2:   # neblina entre planos (perspetiva aerea)
            a(rig.g("haze", f'<rect x="78" y="{60 + li * 10}" width="164" height="60" fill="#eef0f2" opacity=".18"/>'))
    a(rig.g("sunglow", f'<g fill="#ffcf8f" opacity=".3">{"".join(edges)}</g>'))
    # nascer do sol: as fachadas viradas para nos (NE) apanham o sol baixo de leste e ficam rosadas
    # (as fachadas que vemos olham para ENE: ao nascer apanham o sol de frente; o lado direito fica em sombra azul)
    a(rig.g("bfront", f'<use href="#{idp}bp0" fill="#f3b69c" opacity=".78"/><use href="#{idp}bp1" fill="#e89f86" opacity=".7"/>'
                      f'<g fill="#6d6aa0" opacity=".62">{"".join(sides)}</g>'
                      f'<g fill="#fff0dc" opacity=".9">{"".join(edges)}</g>'))
    a(rig.g("dark", '<ellipse cx="160" cy="118" rx="120" ry="30" fill="url(#gCity)"/>'))
    a(rig.g("daywin", f'<g fill="#44506a" opacity=".3">{"".join(wins["A"] + wins["B"] + wins["C"])}</g>'))
    # nascer: alguns vidros devolvem o sol (reflexos dourados nas fachadas)
    a(rig.g("bfront", f'<g fill="#ffe7b8">{"".join(wins["A"][::2])}</g>'))
    for grp, name, col in (("A", "cityA", "#ffd08a"), ("B", "cityB", "#ffc47a"), ("C", "cityC", "#ffe2b0")):
        a(rig.g(name, f'<g fill="{col}">{"".join(wins[grp])}</g>'))
    # janelas que acendem e apagam aos poucos (vida na cidade), so com a cidade acesa
    tw = random.Random(77)
    pool = wins["C"] + wins["B"]
    tws = []
    for k in range(18):
        rect = tw.choice(pool)
        per, on0, dur = tw.uniform(40, 150), tw.uniform(0, 70), tw.uniform(15, 45)
        if rig.tl:
            per /= 15
        col = tw.choice(["#ffe2b0", "#ffc47a", "#cfe0ff", "#ffd08a"])
        tws.append(rect.replace("<rect ", f'<rect class="wt" style="animation-duration:{per:.1f}s;animation-delay:-{tw.uniform(0, per):.1f}s" fill="{col}" '))
    a(rig.g("cityB", "".join(tws)))
    a(rig.g("dark", '<circle cx="127" cy="59.6" r=".7" fill="#ff4a3a" class="blink" style="animation-duration:2.3s"/>'))
    # antena com luz vermelha
    a('<path d="M214,62 V48" stroke="#2a2f45" stroke-width="0.8"/>')
    a(rig.g("dark", '<circle cx="214" cy="47.5" r="0.9" fill="#ff4a3a" class="blink"/>'))
    # easter egg (a): aguaceiro ocasional
    if not rig.tl and st["sun"] < .25:    # nunca chove por cima de um feixe de sol; fora do timelapse
        a(rain_egg())
    a('<rect x="78" y="24" width="164" height="92" fill="url(#gloss)"/>')
    a("</g>")

    # caixilho + peitoril
    fr, frd = C["frame"], C["frame_d"]
    a(f'<path d="M70,16 h180 v108 h-180Z M78,24 v92 h164 v-92Z" fill="{fr}" fill-rule="evenodd"/>')
    a(f'<path d="M78,24 h164 v2 h-162 v90 h-2Z" fill="{frd}"/>')
    a(f'<rect x="158" y="24" width="4.5" height="92" fill="{fr}"/><rect x="158" y="24" width="1.2" height="92" fill="{frd}"/>')
    a(f'<rect x="78" y="62" width="164" height="3.5" fill="{fr}"/><rect x="78" y="65.5" width="164" height="0.8" fill="{frd}"/>')
    a(f'<rect x="150" y="66" width="1.5" height="6" rx="0.7" fill="{frd}"/>')
    a(f'<path d="M62,124 h196 l4,5 h-204Z" fill="{C["sill"]}"/><rect x="58" y="129" width="204" height="2.5" fill="{frd}"/>')
    # madrugada: gato a dormir no peitoril (silhueta)
    a(rig.g("cat", cat_svg(206, 124)))
    if "halloween" in ev:
        a(pumpkin(96, 124))

    # radiador
    a(f'<rect x="104" y="152" width="120" height="46" rx="2" fill="{C["rad"]}"/>')
    a(f'<g fill="{C["rad_d"]}" opacity="0.8">' + "".join(f'<rect x="{106 + k * 6.5:.1f}" y="154" width="1.6" height="42" rx="0.8"/>' for k in range(18)) + "</g>")
    a('<g fill="#fff" opacity="0.25">' + "".join(f'<rect x="{109 + k * 6.5:.1f}" y="154" width="1" height="42"/>' for k in range(18)) + "</g>")
    a(f'<path d="M110,198 v16 M218,198 v16" stroke="{C["rad_d"]}" stroke-width="2.4"/><rect x="214" y="200" width="8" height="5" rx="1" fill="{C["rad_d"]}"/>')
    a('<rect x="104" y="196" width="120" height="3" fill="#000" opacity="0.15"/>')

    # cortinas
    a(f'<rect x="36" y="8" width="244" height="2.4" rx="1.2" fill="{C["metal"]}"/><circle cx="36" cy="9.2" r="2.4" fill="{C["metal"]}"/><circle cx="280" cy="9.2" r="2.4" fill="{C["metal"]}"/>')
    a('<path d="M44,10 C46,70 42,150 40,212 L80,212 C76,150 74,60 72,10Z" fill="url(#cur)"/>')
    a('<path d="M252,10 C254,60 256,150 262,212 L282,212 C280,150 278,70 276,10Z" fill="url(#cur)"/>')
    a('<path d="M44,10 C46,70 42,150 40,212" stroke="#000" stroke-opacity="0.15" stroke-width="1" fill="none"/>')

    # ------------------------------------------------------------------ parede da secretaria
    # relogio de parede: hora real
    a(clock_svg(rig, st.get("clock_dt") or ldt, ev, css, fb=st.get("clock_fb", False)))

    # calendario de parede: mes corrente, dias ativos, hoje com aro
    cx0, cy0 = 316, 34
    yy_, mm_ = ldt.year, ldt.month
    a('<g transform="translate(327 28) scale(1.2) translate(-316 -34)">')
    a(f'<circle cx="{cx0 + 19}" cy="{cy0 - 5}" r="1" fill="#3a3035"/><path d="M{cx0 + 19},{cy0 - 5} L{cx0 + 6},{cy0} M{cx0 + 19},{cy0 - 5} L{cx0 + 32},{cy0}" stroke="#3a3035" stroke-width="0.5"/>')
    a(f'<rect x="{cx0 + 2}" y="{cy0 + 2}" width="38" height="46" fill="#000" opacity="0.3" {B(1.2)}/>')
    first = date(yy_, mm_, 1)
    nd = (date(yy_ + (mm_ == 12), mm_ % 12 + 1, 1) - first).days
    off = first.weekday()
    cells = []
    ring = ""
    for d in range(nd):
        k = off + d
        cxx = cx0 + 3.5 + (k % 7) * 5
        cyy = cy0 + 17 + (k // 7) * 5
        dd = date(yy_, mm_, d + 1)
        c = days.get(dd, 0)
        if dd > ldt.date():       # dias que ainda nao vieram: so o contorno
            cells.append(f'<rect x="{cxx + .2}" y="{cyy + .2}" width="3.4" height="3.4" rx="0.5" fill="none" stroke="#9a8f82" stroke-width=".35" opacity="0.6"/>')
        elif c:
            cells.append(f'<rect x="{cxx}" y="{cyy}" width="3.8" height="3.8" rx="0.5" fill="{"#e0a052" if c < 15 else "#d9822f" if c < 40 else "#b8421f"}"/>')
        else:
            cells.append(f'<rect x="{cxx}" y="{cyy}" width="3.8" height="3.8" rx="0.5" fill="#9a8f82" opacity="0.35"/>')
        if dd == ldt.date():
            ring = (f'<rect x="{cxx - .7}" y="{cyy - .7}" width="5.2" height="5.2" rx=".9" fill="none" '
                    f'stroke="{"#2f7d44" if today_ok else "#3a3035"}" stroke-width=".7"/>')
    a(f'<rect x="{cx0}" y="{cy0}" width="38" height="47" fill="#f1ebe0"/><rect x="{cx0 + 2}" y="{cy0 + 2}" width="34" height="12" fill="{R6.BAND[(mm_ - 10) % 12]}"/>'
      f'<path d="M{cx0 + 2},{cy0 + 14} L{cx0 + 12},{cy0 + 8} L{cx0 + 19},{cy0 + 11} L{cx0 + 28},{cy0 + 6} L{cx0 + 36},{cy0 + 12} V{cy0 + 14}Z" fill="#000" opacity="0.18"/>'
      + "".join(cells) + ring)
    a(f'<rect x="{cx0}" y="{cy0}" width="38" height="1.2" fill="#fff" opacity="0.4"/>')
    a('</g>')

    # quadro (1 de abril: de pernas para o ar)
    qx, qy, qw, qh = 424, 7, 76, 42
    flip = f' transform="rotate(183 {qx + qw / 2} {qy + qh / 2})"' if "1_abril" in ev else ""
    a(f'<rect x="{qx + 3}" y="{qy + 3}" width="{qw}" height="{qh}" fill="#000" opacity="0.3" {B(2)}/>')
    a(f'<g{flip}><rect x="{qx}" y="{qy}" width="{qw}" height="{qh}" fill="#241e1c"/><rect x="{qx + 2.5}" y="{qy + 2.5}" width="{qw - 5}" height="{qh - 5}" fill="#efe8dc"/>')
    ix, iy, iw, ih = qx + 10, qy + 9, qw - 20, qh - 18
    a(f'<rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" fill="#d8c3a4"/>')
    a(f'<circle cx="{ix + iw * 0.66:.1f}" cy="{iy + ih * 0.48:.1f}" r="5" fill="#c9683e"/>')
    a(f'<path d="M{ix},{iy + ih * 0.62:.1f} C{ix + 12},{iy + ih * 0.5:.1f} {ix + 22},{iy + ih * 0.72:.1f} {ix + iw},{iy + ih * 0.58:.1f} V{iy + ih} H{ix}Z" fill="#6f7f86"/>')
    a(f'<path d="M{ix},{iy + ih * 0.8:.1f} C{ix + 16},{iy + ih * 0.68:.1f} {ix + 30},{iy + ih * 0.9:.1f} {ix + iw},{iy + ih * 0.76:.1f} V{iy + ih} H{ix}Z" fill="#3e4c56"/>')
    # casa, cipreste e um passaro: o quadro tem um "para cima" claro (1 de abril le-se logo)
    hx_, hy_ = ix + 9, iy + ih * 0.56
    a(f'<rect x="{hx_:.1f}" y="{hy_ - 3.2:.1f}" width="5" height="3.4" fill="#f3ece0"/><path d="M{hx_ - .6:.1f},{hy_ - 3:.1f} L{hx_ + 2.5:.1f},{hy_ - 5.6:.1f} L{hx_ + 5.6:.1f},{hy_ - 3:.1f}Z" fill="#b8421f"/>'
      f'<rect x="{hx_ + 1.9:.1f}" y="{hy_ - 1.7:.1f}" width="1.2" height="1.9" fill="#3e4c56"/>'
      f'<path d="M{hx_ + 9:.1f},{hy_ + .4:.1f} C{hx_ + 7.6:.1f},{hy_ - 3:.1f} {hx_ + 8.4:.1f},{hy_ - 8:.1f} {hx_ + 9.3:.1f},{hy_ - 9:.1f} C{hx_ + 10.2:.1f},{hy_ - 8:.1f} {hx_ + 11:.1f},{hy_ - 3:.1f} {hx_ + 9.6:.1f},{hy_ + .4:.1f}Z" fill="#2f3d33"/>'
      f'<path d="M{ix + 19:.1f},{iy + 5:.1f} q1.2,-1 2.2,0 q1,-1 2.2,0" stroke="#4e3f3a" stroke-width=".5" fill="none"/></g>')
    if "1_abril" not in ev:
        a(f'<path d="M{qx},{qy} h{qw}" stroke="#fff" stroke-opacity="0.18" stroke-width="0.8"/>')

    # prateleira de parede: cluster Pi, suculenta, livros
    sy = 60
    a(f'<rect x="548" y="{sy + 3}" width="112" height="6" fill="#000" opacity="0.25" {B(2)}/>')
    a(f'<rect x="546" y="{sy}" width="114" height="4" fill="{C["desk1"]}"/><rect x="546" y="{sy}" width="114" height="0.8" fill="#fff" opacity="0.25"/>')
    a(f'<path d="M556,{sy + 4} v6 h5 M650,{sy + 4} v6 h-5" stroke="{C["metal"]}" stroke-width="1.4" fill="none"/>')
    px0 = 626
    for k in range(4):
        yb = sy - 2 - k * 6.2
        a(f'<rect x="{px0}" y="{yb - 1.4:.1f}" width="26" height="1.6" fill="#1f6b43"/>'
          f'<rect x="{px0 + 2}" y="{yb - 3.4:.1f}" width="5" height="2" fill="#b8bcc2"/>'
          f'<rect x="{px0 + 9}" y="{yb - 2.8:.1f}" width="4" height="1.4" fill="#1c1c1f"/>'
          f'<rect x="{px0 + 16}" y="{yb - 3.8:.1f}" width="6" height="2.4" fill="#c8ccd2"/>')
    a(f'<path d="M{px0 + 1},{sy} V{sy - 25} M{px0 + 25},{sy} V{sy - 25}" stroke="#c7a44a" stroke-width="0.8"/>')
    a(f'<rect x="{px0 - 1}" y="{sy - 26.5}" width="28" height="1.3" fill="#2b2c30"/>')
    a(f'<path d="M{px0 + 20},{sy + 4} C{px0 + 22},{sy + 50} {px0 + 26},{sy + 90} 647,186" stroke="#2f4f73" stroke-width="0.9" fill="none"/>'
      f'<path d="M{px0 + 23},{sy + 4} C{px0 + 25},{sy + 50} {px0 + 29},{sy + 90} 650,186" stroke="#77736e" stroke-width="0.9" fill="none"/>')
    a(f'<path d="M602,{sy} l-2,-9 h14 l-2,9Z" fill="#b5673f"/><rect x="599" y="{sy - 10.5}" width="16" height="2.2" rx="0.8" fill="#c77a4f"/>')
    for ang, ln in [(-60, 7), (-30, 9), (0, 10), (30, 9), (60, 7), (-12, 6), (14, 6)]:
        rad = math.radians(ang - 90)
        ex, ey = 607 + ln * math.cos(rad), sy - 10 + ln * math.sin(rad)
        a(f'<path d="M607,{sy - 10} Q{(607 + ex) / 2 + 1:.1f},{(sy - 10 + ey) / 2:.1f} {ex:.1f},{ey:.1f}" stroke="#5e8a5a" stroke-width="2.4" stroke-linecap="round" fill="none"/>')
    bk = C["book"]
    sizes = [(3.2, 32), (2.6, 30), (3.6, 33)]
    for k, (h_, w_) in enumerate(sizes):
        yb = sy - sum(x[0] for x in sizes[:k])
        a(f'<rect x="{554 + k:.0f}" y="{yb - h_:.1f}" width="{w_}" height="{h_}" fill="{bk[k]}"/><rect x="{554 + k:.0f}" y="{yb - h_:.1f}" width="{w_}" height="0.6" fill="#fff" opacity="0.2"/>')
    a(f'<rect x="590" y="{sy - 20}" width="4" height="20" fill="{bk[4]}" transform="rotate(-10 594 {sy})"/><rect x="585" y="{sy - 18}" width="4" height="18" fill="{bk[6]}"/>')
    a(f'<rect x="644" y="186" width="10" height="12" rx="1.2" fill="{C["frame"]}"/><circle cx="649" cy="192" r="2.4" fill="{C["frame_d"]}"/>')

    # ------------------------------------------------------------------ ESTANTE
    ex0, ex1, etop = 676, 790, 30
    shelves = [etop, 72, 114, 156, FL - 4]
    a(f'<rect x="{ex0 - 4}" y="{etop}" width="{ex1 - ex0 + 8}" height="{FL - etop}" fill="#000" opacity="0.25" {B(3)}/>')
    a(f'<rect x="{ex0}" y="{etop}" width="{ex1 - ex0}" height="{FL - etop}" fill="{C["desk1"]}"/>')
    a(f'<rect x="{ex0 + 4}" y="{etop + 4}" width="{ex1 - ex0 - 8}" height="{FL - etop - 8}" fill="#000" opacity="0.35"/>')
    for y in shelves[:-1]:
        a(f'<rect x="{ex0 + 4}" y="{y + 4}" width="{ex1 - ex0 - 8}" height="7" fill="#000" opacity="0.25" {B(1.2)}/>')
    r3 = random.Random(8)
    x = ex0 + 6
    while x < ex1 - 18:
        w_ = r3.uniform(3, 6)
        h_ = r3.uniform(26, 36)
        col = r3.choice(bk)
        a(f'<rect x="{x:.1f}" y="{72 - h_:.1f}" width="{w_:.1f}" height="{h_:.1f}" fill="{col}"/><rect x="{x:.1f}" y="{72 - h_ + 4:.1f}" width="{w_:.1f}" height="1" fill="#fff" opacity="0.18"/>')
        x += w_ + 0.6
    a(f'<rect x="{ex1 - 16}" y="{72 - 30}" width="5" height="30" fill="{bk[5]}" transform="rotate(-14 {ex1 - 11} 72)"/>')
    nx, ny = ex0 + 8, 114 - 32
    a(f'<rect x="{nx}" y="{ny}" width="34" height="32" rx="2" fill="#1b1b20"/><rect x="{nx}" y="{ny}" width="34" height="1" fill="#fff" opacity="0.15"/>')
    for k in range(4):
        a(f'<rect x="{nx + 3 + k * 7.3:.1f}" y="{ny + 5}" width="6" height="22" rx="0.8" fill="#26262c"/><rect x="{nx + 4 + k * 7.3:.1f}" y="{ny + 7}" width="4" height="0.7" fill="#3a3a42"/>')
    sw = (ex0 + 48, 114 - 11, 56, 11)
    a(f'<rect x="{sw[0]}" y="{sw[1]}" width="{sw[2]}" height="{sw[3]}" rx="1" fill="#2c3036"/>')
    for k in range(8):
        a(f'<rect x="{sw[0] + 4 + k * 5.8:.1f}" y="{sw[1] + 3}" width="4" height="3.4" fill="#0e0f12"/>')
    for k, col in enumerate(["#3d7fc4", "#d9a33a", "#3d7fc4", "#c9c9c9", "#58a563", "#3d7fc4"]):
        xk = sw[0] + 6 + k * 5.8
        a(f'<path d="M{xk:.1f},{sw[1] + 4} C{xk:.1f},{sw[1] - 8} {xk + 10 - k * 4:.1f},{sw[1] - 12} {sw[0] + 20 + k * 2:.1f},{sw[1] - 22}" stroke="{col}" stroke-width="1" fill="none" opacity="0.9"/>')
    mx_, my_ = ex0 + 8, 156 - 8
    a(f'<rect x="{mx_}" y="{my_}" width="26" height="8" rx="1.5" fill="#2a2b31"/><rect x="{mx_}" y="{my_ - 8.5}" width="26" height="8" rx="1.5" fill="#34353c"/>')
    a(f'<rect x="{ex0 + 42}" y="{156 - 20}" width="30" height="20" fill="#b99c76"/><rect x="{ex0 + 42}" y="{156 - 20}" width="30" height="3" fill="#a4865f"/>')
    a(f'<rect x="{ex0 + 78}" y="{156 - 24}" width="4" height="24" fill="{bk[1]}"/><rect x="{ex0 + 82.5}" y="{156 - 22}" width="4" height="22" fill="{bk[3]}"/><rect x="{ex0 + 87}" y="{156 - 26}" width="5" height="26" fill="{bk[0]}"/>')
    for k in range(2):
        bx = ex0 + 8 + k * 50
        a(f'<path d="M{bx},{FL - 4} v-38 h46 v38Z" fill="#7d8a94"/><rect x="{bx + 17}" y="{FL - 36}" width="12" height="3" rx="1.5" fill="#000" opacity="0.35"/>')
    for y in shelves:
        a(f'<rect x="{ex0}" y="{y}" width="{ex1 - ex0}" height="4" fill="{C["desk0"]}"/><rect x="{ex0}" y="{y}" width="{ex1 - ex0}" height="0.8" fill="#fff" opacity="0.22"/>')
    a(f'<rect x="{ex0}" y="{etop}" width="4" height="{FL - etop}" fill="{C["desk0"]}"/><rect x="{ex1 - 4}" y="{etop}" width="4" height="{FL - etop}" fill="{C["desk1"]}"/>')
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
    a(f'<clipPath id="shelfc"><rect x="{ex0}" y="{etop}" width="{ex1 - ex0}" height="{FL - etop}"/></clipPath>')
    a(f'<g clip-path="url(#shelfc)"><g transform="translate(-2.5 3.5)" filter="url(#shad)"><g class="sway">' + "".join(vines) + "</g></g></g>")
    a('<g class="sway">' + "".join(vines) + "</g>")

    # ================================================================== CHAO
    a(f'<rect x="0" y="{FL}" width="{W}" height="{H - FL}" fill="url(#floor)"/>')
    seams = []
    for xb in range(-900, 1800, 30):
        x1 = VPX + (xb - VPX) * (FL - VPY) / (H - VPY)
        seams.append(f'<path d="M{x1:.1f},{FL} L{xb},{H}"/>')
    a(f'<g stroke="{C["seam"]}" stroke-width="0.6" opacity="0.45">{"".join(seams)}</g>')
    r4 = random.Random(12)
    tj = []
    for row in range(6):
        y = FL + 3 + row * row * 1.3 + row * 4
        for _ in range(10):
            tj.append(f'<path d="M{r4.uniform(0, W):.0f},{y:.1f} h{4 + row:.0f}"/>')
    a(f'<g stroke="{C["seam"]}" stroke-width="0.5" opacity="0.4">{"".join(tj)}</g>')
    a(f'<rect x="0" y="{FL - 6}" width="{W}" height="6" fill="{C["base"]}"/><rect x="0" y="{FL - 6}" width="{W}" height="0.8" fill="#fff" opacity="0.2"/>')
    a(f'<rect x="0" y="{FL}" width="{W}" height="5" fill="#000" opacity="0.2" {B(1.2)}/>')
    a(f'<path d="M352,222 L630,222 L700,262 L286,262Z" fill="{C["rug"]}"/>')
    a(f'<path d="M358,225 L624,225 L688,262 L298,262Z" fill="none" stroke="{C["rug2"]}" stroke-width="1.2"/>')
    a(f'<path d="M366,229 L616,229 L674,262 L312,262Z" fill="none" stroke="{C["rug2"]}" stroke-width="0.6" stroke-dasharray="2 2"/>')
    # luz difusa do ceu no chao (dia)
    a(rig.g("skypool", f'<path d="M96,216 L230,216 L300,256 L130,256Z" fill="#fff6e8" opacity="0.22" {B(5)}/>'))

    # ================================================================== SECRETARIA
    a(f'<rect x="{DX0 + 16}" y="{DB}" width="4" height="{FL - DB}" fill="{C["metal"]}"/><rect x="{DX1 - 20}" y="{DB}" width="4" height="{FL - DB}" fill="{C["metal"]}"/>')
    a(f'<rect x="{DX0 + 16}" y="190" width="{DX1 - DX0 - 32}" height="3" fill="{C["metal"]}"/>')
    sx0, sy0 = 572, 176
    a(f'<ellipse cx="{sx0 + 16}" cy="{FL + 2}" rx="22" ry="3" fill="#000" opacity="0.4" {B(1.2)}/>')
    a(f'<rect x="{sx0}" y="{sy0}" width="32" height="{FL + 2 - sy0}" rx="2" fill="#1c1c22"/><rect x="{sx0}" y="{sy0}" width="32" height="1" fill="#fff" opacity="0.12"/>')
    a('<g fill="#2a2a31">' + "".join(f'<rect x="{sx0 + 4}" y="{sy0 + 6 + k * 3}" width="24" height="1.4"/>' for k in range(6)) + "</g>")
    a(f'<rect x="360" y="{DF + 5}" width="200" height="4" fill="{C["metal"]}"/>')
    # calha de cabos: um molho desce da calha ate a extensao no chao (atras da perna direita)
    a(f'<path d="M552,{DF + 9} C553,190 556,206 560,{FL + 5}" stroke="#141418" stroke-width="2.2" fill="none"/>'
      f'<path d="M554,{DF + 9} C556,192 559,206 564,{FL + 5}" stroke="#23232a" stroke-width="1" fill="none"/>')
    a(f'<ellipse cx="{560}" cy="{FL + 7.5}" rx="16" ry="1.6" fill="#000" opacity=".4" {B(0.6)}/>'
      f'<path d="M546,{FL + 3} h28 l1.5,3.4 h-31Z" fill="#e7e3dc"/><path d="M544.5,{FL + 6.4} h31 v1.4 h-31Z" fill="#bdb8ae"/>'
      + "".join(f'<rect x="{550 + k * 5.4:.1f}" y="{FL + 4}" width="3" height="1.6" rx=".4" fill="#8f8a82"/>' for k in range(4)))
    a(f'<path d="M548,{DF + 9} C552,190 610,176 612,{sy0} M556,{DF + 9} C570,196 634,210 645,196" stroke="#15151a" stroke-width="1.3" fill="none"/>')
    a(f'<path d="M380,{DF + 9} C384,176 410,178 418,{DF + 9}" stroke="#15151a" stroke-width="1.1" fill="none"/>')
    a(f'<path d="M{DX0 + 4},{DB} L{DX1 - 4},{DB} L{DX1},{DF} L{DX0},{DF}Z" fill="url(#deskt)"/>')
    a(f'<rect x="{DX0}" y="{DF}" width="{DX1 - DX0}" height="5" fill="{C["edge"]}"/><rect x="{DX0}" y="{DF}" width="{DX1 - DX0}" height="0.8" fill="#fff" opacity="0.3"/>')
    r5 = random.Random(2)
    a('<g stroke="#000" stroke-width="0.35" opacity="0.12" fill="none">' + "".join(
        f'<path d="M{DX0 + 6},{DB + 1 + k * 1.6:.1f} C{r5.uniform(360, 460):.0f},{DB + 1 + k * 1.6 + r5.uniform(-0.6, 0.6):.1f} {r5.uniform(480, 580):.0f},{DB + 1 + k * 1.6 + r5.uniform(-0.6, 0.6):.1f} {DX1 - 6},{DB + 1 + k * 1.6:.1f}"/>' for k in range(5)) + "</g>")
    for x in (DX0 + 6, DX1 - 12):
        a(f'<rect x="{x}" y="{DF + 5}" width="6" height="{222 - DF - 5}" fill="{C["metal"]}"/><rect x="{x}" y="{DF + 5}" width="1.2" height="{222 - DF - 5}" fill="#fff" opacity="0.12"/>')
        a(f'<ellipse cx="{x + 3}" cy="223" rx="8" ry="1.6" fill="#000" opacity="0.35" {B(0.6)}/>')
    hx, hy = DX0 + 22, DF + 5
    a(f'<path d="M{hx - 2},{hy} v4 h4" stroke="{C["metal"]}" stroke-width="1.4" fill="none"/>')
    a(f'<path d="M{hx - 11},{hy + 20} C{hx - 12},{hy + 2} {hx + 10},{hy + 2} {hx + 9},{hy + 20}" stroke="#1d1c22" stroke-width="2.6" fill="none" stroke-linecap="round"/>')
    a(f'<path d="M{hx - 11},{hy + 20} C{hx - 12},{hy + 4} {hx + 10},{hy + 4} {hx + 9},{hy + 20}" stroke="#4a4852" stroke-width="0.6" fill="none"/>')
    for sx_ in (hx - 12, hx + 8):
        a(f'<rect x="{sx_ - 4}" y="{hy + 17}" width="9" height="13" rx="4" fill="#26252b"/><rect x="{sx_ - 2.5}" y="{hy + 19}" width="6" height="9" rx="3" fill="#3b3943"/>')
    a(f'<path d="M{hx + 8},{hy + 30} C{hx + 10},{hy + 44} {hx - 6},{hy + 48} {hx - 4},{FL + 1}" stroke="#1d1c22" stroke-width="0.8" fill="none"/>')

    # sombras do monitor na parede: candeeiro (da direita) / luz difusa
    a(rig.g("shL", f'<rect x="{MX0 - 12}" y="{MY0 + 4}" width="{MX1 - MX0}" height="{MY1 - MY0 + 8}" fill="#000" opacity="0.3" {B(9)}/>'))
    a(rig.g("shD", f'<rect x="{MX0 + 6}" y="{MY0 + 6}" width="{MX1 - MX0}" height="{MY1 - MY0}" fill="#000" opacity="0.1" {B(9)}/>'))

    # portatil
    lx0, lx1, ly0, ly1 = 322, 374, 100, 134
    a(f'<ellipse cx="{(lx0 + lx1) / 2}" cy="{DB + 3}" rx="30" ry="2.5" fill="#000" opacity="0.35" {B(1.2)}/>')
    a(f'<path d="M{lx0 + 8},{DB + 2} L{lx0 + 16},{ly1 + 2} M{lx1 - 8},{DB + 2} L{lx1 - 16},{ly1 + 2}" stroke="url(#metalg)" stroke-width="2"/>')
    a(f'<path d="M{lx0 - 2},{ly1} L{lx1 + 2},{ly1} L{lx1 + 4},{ly1 + 3} L{lx0 - 4},{ly1 + 3}Z" fill="#9aa0a8"/>')
    a(f'<rect x="{lx0}" y="{ly0}" width="{lx1 - lx0}" height="{ly1 - ly0}" rx="1.5" fill="#141417"/>')
    # monitor
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
        kw = (x1_ - x0_) / 15
        for k in range(15):
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
    # caderno + caneta
    a(f'<ellipse cx="574" cy="{DF - 0.8}" rx="27" ry="1.4" fill="#000" opacity="0.45" {B(0.6)}/>')
    a(f'<path d="M552,{DB + 2} L597,{DB + 2} L600,{DF - 1} L549,{DF - 1}Z" fill="#f2ecdf"/><path d="M574.5,{DB + 2} L574.5,{DF - 1}" stroke="#b9b0a0" stroke-width="0.6"/>')
    a('<g stroke="#8a95a8" stroke-width="0.25" opacity="0.7">' + "".join(f'<path d="M{553 - k * 0.6:.1f},{DB + 3.3 + k * 1.2:.1f} h{20 + k * 0.3:.1f} M{576:.1f},{DB + 3.3 + k * 1.2:.1f} h{21 + k * 0.6:.1f}"/>' for k in range(5)) + "</g>")
    a(f'<path d="M556,{DB + 4.5} l8,0 M556,{DB + 5.7} l12,0 M556,{DB + 6.9} l6,0" stroke="#3c4b66" stroke-width="0.35" opacity="0.8"/>')
    a(f'<path d="M583,{DF - 2} L597,{DB + 3.2}" stroke="#23262e" stroke-width="1" stroke-linecap="round"/><path d="M596,{DB + 3.3} l1.2,-0.3" stroke="#c9a44a" stroke-width="1"/>')
    # chavenas (atividade do mes)
    slots = [(300, DB + 5.5, "#e3d9c6"), (386, DB + 5.2, "#8c4b3a"), (312, DB + 7.4, "#3e5570"),
             (505, DB + 4.5, "#d6cdbd"), (398, DB + 7.4, "#6f7f5a"), (536, DB + 5.8, "#e3d9c6"),
             (352, DB + 8, "#b56a45"), (377, DB + 7.6, "#2f3b52")]
    for k, (x, yb, col) in enumerate(slots[:cups_n]):
        a(f'<ellipse cx="{x + 3.6}" cy="{yb + 0.3}" rx="5" ry="0.9" fill="#000" opacity="0.45" {B(0.6)}/>'
          f'<path d="M{x + 7},{yb - 6} q3.6,0 3.6,2.6 t-3.6,2.6" stroke="{col}" stroke-width="1.2" fill="none"/>'
          f'<path d="M{x},{yb - 8.5} h7.4 v7.2 q0,1.3 -1.3,1.3 h-4.8 q-1.3,0 -1.3,-1.3Z" fill="{col}"/>'
          f'<path d="M{x},{yb - 8.5} h2.2 v8.5 h-0.9 q-1.3,0 -1.3,-1.3Z" fill="#000" opacity="0.18"/>'
          f'<path d="M{x + 5.2},{yb - 8.5} h2.2 v7.2 q0,1.3 -1.3,1.3 h-0.9Z" fill="#fff" opacity="0.18"/>'
          f'<ellipse cx="{x + 3.7}" cy="{yb - 8.5}" rx="3.7" ry="0.9" fill="#1a1216"/>')
    # aniversario da conta: queque com vela
    if "aniversario_conta" in ev:
        a(cupcake(566, DB + 6))
    # candeeiro articulado
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
    Mo = (J[0] + d[0] * 19, J[1] + d[1] * 19)
    shade = [(J[0] - d[0] * 5 + n[0] * 3, J[1] - d[1] * 5 + n[1] * 3), (J[0] - d[0] * 5 - n[0] * 3, J[1] - d[1] * 5 - n[1] * 3),
             (Mo[0] - n[0] * 11.5, Mo[1] - n[1] * 11.5), (Mo[0] + n[0] * 11.5, Mo[1] + n[1] * 11.5)]
    ang_n = math.degrees(math.atan2(n[1], n[0]))
    bk0 = (J[0] - d[0] * 5, J[1] - d[1] * 5)
    c1 = (J[0] + d[0] * 5 + n[0] * 10, J[1] + d[1] * 5 + n[1] * 10)
    c2 = (J[0] + d[0] * 5 - n[0] * 10, J[1] + d[1] * 5 - n[1] * 10)
    dome = (f'M{bk0[0] + n[0] * 3:.1f},{bk0[1] + n[1] * 3:.1f} Q{c1[0]:.1f},{c1[1]:.1f} {shade[3][0]:.1f},{shade[3][1]:.1f} '
            f'L{shade[2][0]:.1f},{shade[2][1]:.1f} Q{c2[0]:.1f},{c2[1]:.1f} {bk0[0] - n[0] * 3:.1f},{bk0[1] - n[1] * 3:.1f}Z')
    a(f'<linearGradient id="shadeg" gradientUnits="userSpaceOnUse" x1="{Mo[0] - n[0] * 12:.1f}" y1="{Mo[1] - n[1] * 12:.1f}" x2="{Mo[0] + n[0] * 12:.1f}" y2="{Mo[1] + n[1] * 12:.1f}">'
      '<stop offset="0" stop-color="#6a6270"/><stop offset="0.45" stop-color="#34303a"/><stop offset="1" stop-color="#211e25"/></linearGradient>')
    a(f'<path d="{dome}" fill="url(#shadeg)"/>')
    a(f'<ellipse cx="{bk0[0]:.1f}" cy="{bk0[1]:.1f}" rx="3" ry="1.4" transform="rotate({ang_n:.0f} {bk0[0]:.1f} {bk0[1]:.1f})" fill="#48424e"/>')
    a(f'<circle cx="{J[0]}" cy="{J[1]}" r="2" fill="#3a3640"/>')
    mouth_el = f'cx="{Mo[0]:.1f}" cy="{Mo[1]:.1f}" rx="11.5" ry="3.2" transform="rotate({ang_n:.0f} {Mo[0]:.1f} {Mo[1]:.1f})"'
    a(f'<ellipse {mouth_el} fill="#1b191e"/>')
    mouth_in = mouth_el.replace('rx="11.5" ry="3.2"', 'rx="7" ry="1.8"')

    # easter egg (a): robot aspirador (corpo; o LED vai nos emissivos)
    if not rig.tl:
        a(vacuum_body())

    # ================================================================== CADEIRA (vista de tras, ligeiramente de cima)
    ch = CHX
    a(rig.g("chN", f'<ellipse cx="{ch + 2}" cy="254" rx="48" ry="7" fill="#000" opacity="0.5" {B(3)}/>'))
    a(rig.g("chD", f'<path d="M{ch - 34},251 L{ch + 34},249 L{ch + 120},262 L{ch + 6},262Z" fill="#000" opacity="0.25" {B(3)}/>'))
    a(chair_svg())

    # ================================================================== PRIMEIRO PLANO (antes das tintas: escurece com a noite)
    a(f'<ellipse cx="34" cy="262" rx="40" ry="10" fill="#000" opacity="0.45" {B(5)}/>')
    a('<path d="M8,262 L14,232 H62 L68,262Z" fill="#5c3b2a"/><rect x="11" y="229" width="54" height="5" rx="1.5" fill="#6e4834"/>')
    a('<linearGradient id="leafg" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#23391c"/><stop offset="0.6" stop-color="#3f6a2c"/><stop offset="1" stop-color="#6f9a3a"/></linearGradient>')
    leaves = [(34, 230, 70, -52, 40, 3), (38, 230, 92, -18, 46, 2), (40, 230, 60, 22, 40, 1), (30, 230, 44, -80, 34, 4),
              (44, 230, 40, 58, 34, 5), (36, 230, 30, 4, 30, 6)]
    rims_w, rims_c = [], []
    for (bx_, by_, pl, ang, sz, seed) in leaves:
        rad = math.radians(ang - 90)
        tipx, tipy = bx_ + math.cos(rad) * pl, by_ + math.sin(rad) * pl
        ctrl = (bx_ + math.cos(rad) * pl * 0.3, by_ + math.sin(rad) * pl * 0.75)
        droop = 38 if ang > 5 else -38 if ang < -5 else 12
        a(f'<g class="swb" style="animation-delay:-{seed * 1.3:.1f}s">')
        a(f'<path d="M{bx_},{by_} Q{ctrl[0]:.1f},{ctrl[1]:.1f} {tipx:.1f},{tipy:.1f}" stroke="#27401f" stroke-width="1.5" fill="none"/>')
        d_ = monstera_leaf(seed)
        veins = "".join(f'<path d="M0,{-0.12 - j * 0.16:.2f} Q{s_ * 0.2:.2f},{-0.2 - j * 0.16:.2f} {s_ * 0.5:.2f},{-0.3 - j * 0.15:.2f}"/>' for j in range(5) for s_ in (-1, 1))
        tf = f'translate({tipx:.1f} {tipy:.1f}) rotate({ang + droop:.0f}) scale({sz})'
        a(rig.g("rimW", f'<g transform="translate(1.1 -0.9)"><path transform="{tf}" d="{d_}" fill="#ffd27a"/></g>'))
        a(rig.g("rimC", f'<g transform="translate(1.1 -0.9)"><path transform="{tf}" d="{d_}" fill="#6f8fc4" opacity=".7"/></g>'))
        a(f'<g transform="{tf}"><path d="{d_}" fill="url(#leafg)"/>'
          f'<g stroke="#a9c77a" stroke-width="{0.45 / sz:.3f}" fill="none" opacity="0.3"><path d="M0,0.02 L0,-0.98"/>{veins}</g></g>')
        a("</g>")
    _ = (rims_w, rims_c)
    a('<g transform="translate(-10 0)">')
    a('<path d="M824,-2 V6 M824,6 L811,23 M824,6 L837,23 M824,6 L824,23" stroke="#a39581" stroke-width="0.6" fill="none"/><circle cx="824" cy="6" r=".9" fill="#8a7d6a"/>')
    a('<path d="M810,24 H838 C838,40 810,40 810,24Z" fill="#c8b7a2"/><path d="M812,26 C813,36 826,39 836,30 C835,37 824,40 812,33Z" fill="#000" opacity=".12"/>'
      '<rect x="809" y="22.5" width="30" height="3" rx="1.2" fill="#d4c4af"/>')
    hv = []
    hr = random.Random(55)
    for (sx_, ex_, ey_) in [(814, 806, 120), (820, 824, 160), (828, 814, 92), (816, 798, 74), (832, 836, 130)]:
        cx_ = (sx_ + ex_) / 2 + hr.uniform(-6, 6)
        hv.append(f'<path d="M{sx_},26 Q{cx_:.1f},{(26 + ey_) / 2:.1f} {ex_},{ey_}" stroke="#27401f" stroke-width="1" fill="none"/>')
        for t in [i / 8 for i in range(1, 9)]:
            px = (1 - t) ** 2 * sx_ + 2 * (1 - t) * t * cx_ + t * t * ex_
            py = (1 - t) ** 2 * 26 + 2 * (1 - t) * t * (26 + ey_) / 2 + t * t * ey_
            ang = hr.uniform(-60, 60)
            hv.append(f'<ellipse cx="{px:.1f}" cy="{py:.1f}" rx="5.2" ry="3.2" transform="rotate({ang:.0f} {px:.1f} {py:.1f})" fill="#2f4d26" stroke="#ffd27a" stroke-width="0.4" stroke-opacity="0.3"/>')
    a('<g class="sway" style="animation-delay:-3s">' + "".join(hv) + "</g>")
    a('</g>')

    # ================================================================== TINTAS (luz ambiente do momento)
    fall = ('<linearGradient id="fallg" x1="0" y1="0" x2="1" y2="0"><stop offset=".15" stop-color="#fff"/><stop offset=".6" stop-color="#d9d2cc"/>'
            '<stop offset="1" stop-color="#a9a1a4"/></linearGradient>'
            f'<rect width="{W}" height="{H}" fill="url(#fallg)" mask="url(#mGlass)"/>')
    a(rig.g("fall", fall, ' style="mix-blend-mode:multiply"'))
    for key, col in (("ovD", OVC["ovD"]), ("ovR", OVC["ovR"]), ("ovM", OVC["ovM"]), ("ovG", OVC["ovG"]), ("ovE", OVC["ovE"])):
        a(rig.g(key, f'<rect width="{W}" height="{H}" fill="{col}" mask="url(#mGlass)"/>', ' style="mix-blend-mode:multiply"'))
    for key, col, m_ in (("ovB_L", OVC["ovB"], "mLamp"), ("ovB_D", OVC["ovB"], "mDark"), ("ovN_L", OVC["ovN"], "mLamp"), ("ovN_D", OVC["ovN"], "mDark")):
        a(rig.g(key, f'<rect width="{W}" height="{H}" fill="{col}" mask="url(#{m_})"/>', ' style="mix-blend-mode:multiply"'))
    # a luz do candeeiro e quente, a do monitor fria (tinta nos buracos de luz)
    a(rig.g("lampT", '<radialGradient id="lampt"><stop offset="0" stop-color="#ffb877"/><stop offset=".6" stop-color="#ffd1a6"/><stop offset="1" stop-color="#fff"/></radialGradient>'
                     '<ellipse cx="566" cy="140" rx="210" ry="150" fill="url(#lampt)"/>', ' style="mix-blend-mode:multiply"'))
    a(rig.g("rimC", '<radialGradient id="mont"><stop offset="0" stop-color="#b9c8ea"/><stop offset="1" stop-color="#fff"/></radialGradient>'
                    '<ellipse cx="462" cy="112" rx="150" ry="100" fill="url(#mont)"/>', ' style="mix-blend-mode:multiply"'))
    # reflexo frio da janela no soalho (noite)
    a(rig.g("reflN", f'<path d="M96,216 L230,216 L300,256 L130,256Z" fill="#7d9ccc" opacity="0.22" {B(5)}/>'))
    # noite: luar e brilho da cidade entram pela janela (luz fria e suave na parede, cortinas e chao)
    a(rig.g("moonfill", '<radialGradient id="gMoon" cx=".5" cy=".45" r=".5"><stop offset="0" stop-color="#6d89c9" stop-opacity=".22"/>'
                        '<stop offset=".6" stop-color="#4a5f96" stop-opacity=".08"/><stop offset="1" stop-color="#34446e" stop-opacity="0"/></radialGradient>'
                        '<g style="mix-blend-mode:screen"><ellipse cx="160" cy="120" rx="185" ry="135" fill="url(#gMoon)"/>'
                        '<path d="M58,129 h204 v3 h-204Z" fill="#8fa8d8" opacity=".2"/></g>'))
    a(rig.g("moonbeam", f'<g style="mix-blend-mode:screen"><path d="M78,{FL + 1} L242,{FL + 1} L290,{H} L60,{H}Z" fill="#5e7ab4" opacity=".2" {B(9)}/></g>'))
    a(rig.g("bfront", '<linearGradient id="roseg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff9e8e" stop-opacity=".3"/>'
                      '<stop offset=".55" stop-color="#ffb49a" stop-opacity=".1"/><stop offset="1" stop-color="#ffb49a" stop-opacity="0"/></linearGradient>'
                      f'<g style="mix-blend-mode:screen"><rect width="{W}" height="{H}" fill="url(#roseg)" mask="url(#mGlass)"/>'
                      '<ellipse cx="165" cy="235" rx="150" ry="28" fill="#ffb3a0" opacity=".22" filter="url(#b9)"/></g>'))
    # manha: luz limpa e fria que abre as sombras (a sala fica luminosa, nao cinzenta)
    a(rig.g("morn", '<g style="mix-blend-mode:screen"><rect width="830" height="260" fill="#242a36" opacity=".55"/>'
                    '<ellipse cx="170" cy="120" rx="260" ry="170" fill="url(#gCool)" opacity=".5"/></g>'))
    # dourado: brilho quente a volta da janela + lado direito mais frio
    warm = ('<g style="mix-blend-mode:screen"><ellipse cx="160" cy="130" rx="110" ry="20" fill="#ffc47a" opacity="0.25" ' + B(9) + '/>'
            '<ellipse cx="170" cy="110" rx="270" ry="170" fill="url(#gWarm)" opacity="0.5"/></g>'
            '<linearGradient id="coolr" x1="0" y1="0" x2="1" y2="0"><stop offset="0.4" stop-color="#9c8cba" stop-opacity="0"/><stop offset="1" stop-color="#6f5f96" stop-opacity="0.38"/></linearGradient>'
            f'<rect width="{W}" height="{H}" fill="url(#coolr)" style="mix-blend-mode:multiply"/>')
    a(rig.g("sunglow", warm))
    # manha / dia: claridade fria da janela
    a(rig.g("haze", '<g style="mix-blend-mode:screen"><ellipse cx="170" cy="100" rx="240" ry="150" fill="url(#gCool)" opacity=".35"/></g>'))

    a(rig.g("amcool", f'<rect width="{W}" height="{H}" fill="#e6edf7" mask="url(#mGlass)"/>', ' style="mix-blend-mode:multiply"'))
    a(rig.g("amcool", '<g style="mix-blend-mode:screen"><ellipse cx="150" cy="110" rx="230" ry="160" fill="url(#gCool)" opacity=".7"/>'
                      '<path d="M40,10 L80,10 L80,212 L40,212Z M252,10 L282,10 L282,212 L252,212Z" fill="#b8ccf0" opacity=".12"/></g>'))
    a(rig.g("noon", f'<g style="mix-blend-mode:screen"><rect width="{W}" height="{H}" fill="#fff8ec" opacity=".13" mask="url(#mGlass)"/></g>'))
    # jamba esquerda da janela e parede a volta apanham o sol quando vem da direita (fim da tarde)
    a(rig.g("reveal", '<g style="mix-blend-mode:screen"><path d="M70,16 L78,24 V116 L70,124Z" fill="#ffc778" opacity=".75"/>'
                      '<path d="M62,124 h196 l4,5 h-204Z" fill="#ffcf8a" opacity=".45"/>'
                      f'<ellipse cx="150" cy="200" rx="150" ry="36" fill="url(#gWarm)" opacity=".9"/></g>'))
    # ================================================================== SOL DIRETO (feixes por amostra)
    for i, s_ in enumerate(sts):
        body = sun_layers(s_, f"{idp}s{i}")
        if body:
            a(rig.per_sample(i, body))

    # ================================================================== EMISSIVOS
    # ecra do monitor: tema claro de dia, escuro a noite; o que esta no ecra muda com a hora
    sx, sy_, sw_, sh_ = MX0 + 3, MY0 + 3, MX1 - MX0 - 6, MY1 - MY0 - 6
    a('<g clip-path="url(#screen)">')
    a(f'<rect x="{sx}" y="{sy_}" width="{sw_}" height="{sh_}" fill="#07080b"/>')
    scr_svg, empty, full = screen_svg(rig, weeks, sx, sy_, sw_, sh_, idp)
    a(rig.g("scr", scr_svg))
    # descanso de ecra (madrugada): so o grafico, a derivar devagar
    if rig.any("scrsaver"):
        a(rig.g("scrsaver", f'<rect x="{sx}" y="{sy_}" width="{sw_}" height="{sh_}" fill="#05070b"/>'
                            f'<g transform="translate(0 -11)" opacity=".55"><g fill="#11161f">{"".join(empty)}</g>{"".join(full)}</g>'))
    # easter egg (a): cobra no grafico
    if not rig.tl:
        a(snake_egg(weeks, sx, sy_, sw_, sh_))
    a("</g>")
    a(f'<rect x="{sx}" y="{sy_}" width="{sw_}" height="{sh_}" fill="url(#gloss)"/>')
    a(f'<circle cx="{MX1 - 6}" cy="{MY1 - 1.5}" r="0.6" fill="#8fb5ff"/>')
    a(rig.g("dark", f'<g style="mix-blend-mode:screen"><rect x="{MX0}" y="{MY0}" width="{MX1 - MX0}" height="{MY1 - MY0}" fill="#9ab8ff" opacity=".1" {B(5)}/></g>'))
    if "sexta_tarde" in ev:
        a(f'<g transform="rotate(7 {MX1 - 10} {MY0 + 4})"><rect x="{MX1 - 18}" y="{MY0 - 1}" width="16" height="15" fill="#000" opacity=".3" {B(0.6)}/>'
          f'<rect x="{MX1 - 20}" y="{MY0 - 3}" width="16" height="15" fill="#ef5b5f"/><rect x="{MX1 - 20}" y="{MY0 - 3}" width="16" height="3" fill="#d4454a"/>'
          f'<path d="M{MX1 - 17},{MY0 + 3.5} h9 M{MX1 - 17},{MY0 + 6.5} h6 M{MX1 - 17},{MY0 + 9.5} h8" stroke="#8a1f24" stroke-width=".7" opacity=".6"/>'
          f'<path d="M{MX1 - 18},{MY0 + 7} l10,-4" stroke="#8a1f24" stroke-width=".9" opacity=".7"/></g>')

    # ecra do portatil: curva semanal; hoje com contribuicoes -> tudo verde
    a(f'<clipPath id="lap"><rect x="{lx0 + 2}" y="{ly0 + 2}" width="{lx1 - lx0 - 4}" height="{ly1 - ly0 - 4}"/></clipPath>')
    wk53 = weeks[-53:]
    wk = [sum(c for _, c in w_) for w_ in wk53]
    wmax = max(wk)
    gx0, gx1, gy0, gy1 = lx0 + 4, lx1 - 4, ly0 + 12, ly1 - 4
    pts_ = [(gx0 + (gx1 - gx0) * i / (len(wk) - 1), gy1 - (gy1 - gy0) * math.sqrt(v / wmax)) for i, v in enumerate(wk)]
    area = f"M{gx0},{gy1} " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts_) + f" L{gx1},{gy1}Z"
    stc = ("#39d353",) * 4 if today_ok else ("#39d353", "#39d353", "#39d353", "#e3b341")
    for th, bg, ln, ar, pill, bar in (("thD", "#0f141d", "#39d353", .18, "#161d2a", "#44506a"),
                                      ("thL", "#f6f8fa", "#1f883d", .16, "#e3e8ee", "#a3adba")):
        if not rig.any(th):
            continue
        lap = [f'<rect x="{lx0 + 2}" y="{ly0 + 2}" width="{lx1 - lx0 - 4}" height="{ly1 - ly0 - 4}" fill="{bg}"/>']
        lap.append(f'<path d="{area}" fill="{ln}" opacity="{ar}"/><path d="M' + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts_) + f'" stroke="{ln}" stroke-width="0.6" fill="none"/>')
        for k, col in enumerate(stc):
            lap.append(f'<rect x="{lx0 + 4 + k * 11}" y="{ly0 + 4}" width="9" height="5" rx="0.8" fill="{pill}"/><circle cx="{lx0 + 6.5 + k * 11}" cy="{ly0 + 6.5}" r="0.9" fill="{col}" class="led" style="animation-delay:-{k * 0.7}s;animation-duration:{2 + k * 0.6:.1f}s"/>'
                       f'<rect x="{lx0 + 8.5 + k * 11}" y="{ly0 + 6}" width="3.5" height="1" fill="{bar}"/>')
        if today_ok:
            ex_, ey_ = pts_[-1]
            lap.append(f'<circle cx="{ex_ - .6:.1f}" cy="{ey_:.1f}" r="2.4" fill="{ln}" opacity=".35" class="pulse"/><circle cx="{ex_ - .6:.1f}" cy="{ey_:.1f}" r=".9" fill="{"#aff5b4" if th == "thD" else "#1f883d"}"/>')
        a(f'<g clip-path="url(#lap)">{rig.g("scr", rig.g(th, "".join(lap)))}</g>')
    a(f'<rect x="{lx0 + 2}" y="{ly0 + 2}" width="{lx1 - lx0 - 4}" height="{ly1 - ly0 - 4}" fill="url(#gloss)"/>')

    # LEDs
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
    halo = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{col}" opacity="0.28"/>' for x, y, col, _ in leds)
    a(rig.g("dark", f'<g {B(1.2)} opacity="{1.6 if st["peak"] else 1}">{halo}</g>'))
    if not rig.tl:
        a(vacuum_led())
    a(f'<rect x="570.6" y="{FL + 4}" width="2.4" height="1.7" rx=".4" fill="#ff6a3d"/>')
    a(rig.g("dark", f'<circle cx="571.8" cy="{FL + 4.8}" r="3" fill="#ff6a3d" opacity=".35" {B(1.2)}/>'))
    # easter egg: uma traca as voltas do candeeiro, nas noites dos meses quentes
    if not rig.tl:
        a(rig.g("moth", moth_svg(Mo)))

    a(rig.g("cat", cat_rim(206, 124)))
    # relogio: lume e luz do monitor
    a(clock_night(rig, st.get("clock_dt") or ldt, fb=st.get("clock_fb", False)))
    # luz de recorte na cadeira: monitor (topo, frio), candeeiro (direita, quente), janela (esquerda, quente/frio)
    a(rig.g("rimC", f'<path d="{CH_TOP}" stroke="#a9c2ff" stroke-width="1.1" fill="none" opacity="0.75" stroke-linecap="round"/>'))
    a(rig.g("lamp", f'<path d="{CH_RIGHT}" stroke="#ffb56a" stroke-width="1.3" fill="none" opacity="0.85" stroke-linecap="round"/>'
                    f'<path d="M{CHX + 34},187.4 h7" stroke="#ffb56a" stroke-width=".9" opacity="0.7" stroke-linecap="round"/>'
                    f'<path d="M{CHX + 37},199 C{CHX + 36},204 {CHX + 34},207 {CHX + 36},209" stroke="#ffb56a" stroke-width=".8" fill="none" opacity="0.5"/>'))
    a(rig.g("rimW", f'<path d="{CH_LEFT}" stroke="#ffc27a" stroke-width="1.3" fill="none" opacity="0.85" stroke-linecap="round"/>'
                    f'<path d="M{CHX - 41},187.4 h7" stroke="#ffc27a" stroke-width=".9" opacity="0.7" stroke-linecap="round"/>'))

    # candeeiro aceso
    cone = f'M{shade[2][0]:.1f},{shade[2][1]:.1f} L{shade[3][0]:.1f},{shade[3][1]:.1f} L612,{DB + 5} L522,{DB + 5}Z'
    mr = random.Random(40)
    motes = []
    for k in range(16):
        t = mr.random()
        y = shade[2][1] + 8 + t * (DB - shade[2][1] - 12)
        half = 6 + t * 36
        x = 567 + mr.uniform(-half, half) * 0.8
        motes.append(f'<circle class="mote" style="animation-delay:-{mr.uniform(0, 14):.1f}s;animation-duration:{mr.uniform(9, 17):.1f}s" cx="{x:.1f}" cy="{y:.1f}" r="{mr.choice([0.35, 0.45, 0.6])}" fill="#ffe6bf"/>')
    lamp = ('<g style="mix-blend-mode:screen">'
            '<ellipse cx="560" cy="128" rx="170" ry="105" fill="url(#gWarm)" mask="url(#mNoChair)"/>'
            f'<ellipse cx="566" cy="{DB + 4}" rx="62" ry="7" fill="url(#gPool)"/>'
            f'<clipPath id="conec"><rect x="0" y="0" width="{W}" height="{DB + 5}"/></clipPath>'
            f'<g clip-path="url(#conec)"><path d="{cone}" fill="url(#cone)" {B(3)}/></g>'
            f'<path d="M548,{DB + 2} L597,{DB + 2} L600,{DF - 1} L549,{DF - 1}Z" fill="#ffcf8f" opacity="0.35"/>'
            f'<path d="M{CHX + 31},{DF + 0.4} H{DX1 - 10}" stroke="#ffc27a" stroke-width="0.8" opacity="0.5"/></g>'
            f'<ellipse {mouth_el} fill="#ffe9c4"/><ellipse {mouth_in} fill="#fffaf0"/>'
            f'<circle cx="{Mo[0]:.1f}" cy="{Mo[1]:.1f}" r="9" fill="#ffc47a" opacity="0.55" {B(5)}/>'
            f'<circle cx="{Mo[0]:.1f}" cy="{Mo[1]:.1f}" r="3.2" fill="#fff4dc" opacity="0.95" {B(1.2)}/>'
            + "".join(motes))
    a(rig.g("lamp", lamp))
    # luz fria do monitor
    a(rig.g("monlit", '<g style="mix-blend-mode:screen"><g mask="url(#mNoChair)"><ellipse cx="462" cy="100" rx="150" ry="86" fill="url(#gCool)"/>'
                      '<ellipse cx="462" cy="98" rx="92" ry="52" fill="url(#gCool)" opacity=".85"/></g>'
                      f'<ellipse cx="462" cy="{DB + 4}" rx="86" ry="7" fill="url(#gCoolPool)"/>'
                      f'<ellipse cx="462" cy="{DB + 3}" rx="40" ry="3" fill="url(#gCoolPool)"/>'
                      f'<path d="M413,{DB + 2.8} H{CHX - 29} M{CHX + 29},{DB + 2.8} H499" stroke="#b9ccff" stroke-width=".5" opacity=".55"/>'
                      f'<path d="M{DX0 + 60},{DF + .4} H{CHX - 31} M{CHX + 31},{DF + .4} H{DX1 - 150}" stroke="#9fb8ff" stroke-width=".7" opacity=".45"/></g>'))
    # vapor da chavena mais recente
    if cups_n:
        x, yb, _c = slots[cups_n - 1]
        a(rig.g("steam", f'<path class="stm" stroke-dasharray="7 29" d="M{x + 2.5},{yb - 10} c-3,-4 3,-7 0,-11 s3,-7 0,-11" stroke="#efe6da" stroke-width="0.8" fill="none" opacity="0.5" stroke-linecap="round"/>'
                         f'<path class="stm" stroke-dasharray="7 29" style="animation-delay:-1.7s" d="M{x + 5},{yb - 10} c-3,-4 3,-7 0,-11 s3,-7 0,-11" stroke="#efe6da" stroke-width="0.7" fill="none" opacity="0.4" stroke-linecap="round"/>'))
    if "aniversario_conta" in ev:
        a(cupcake_flame(566, DB + 6))
    if "natal" in ev:
        a(xmas_lights())
    if "halloween" in ev:
        a(pumpkin_glow(96, 124))

    # ================================================================== acabamento
    a(f'<rect width="{W}" height="{H}" fill="url(#vig)"/>')
    a(rig.g("vig2", f'<rect width="{W}" height="{H}" fill="url(#vig2)"/>'))
    a(f'<rect width="{W}" height="{H}" filter="url(#grain)" opacity="0.07" style="mix-blend-mode:overlay"/>')
    a("</g>")
    a(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="11.5" fill="none" stroke="#8b949e" stroke-opacity=".4"/>')
    a("</svg>")
    style = ("<style>" + "".join(css) + EGG_CSS + rig.style() +
             "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>")
    return "".join(o).replace("<!--STYLE-->", style, 1)


# ================================================================== ecra
THEMES = {
    "D": dict(bg="#0d1117", bar="#161b22", side="#10151c", tree="#3a4556", treeA="#6e7f99", gut="#2d3645", panel="#0b0f14",
              line="#21262d", cur="#e6edf3", sel="#1f6feb", add="#12361f", dele="#3d1518",
              k=["#ff7b72", "#d2a8ff", "#a5d6ff", "#6e7681", "#c9d1d9", "#79c0ff", "#ffa657"],
              gh=["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]),
    "L": dict(bg="#ffffff", bar="#eef1f4", side="#f6f8fa", tree="#b7c0cc", treeA="#57606a", gut="#c9d1d9", panel="#f6f8fa",
              line="#d8dee4", cur="#1f2328", sel="#0969da", add="#dafbe1", dele="#ffebe9",
              k=["#cf222e", "#8250df", "#0a3069", "#8c959f", "#24292f", "#0550ae", "#953800"],
              gh=["#e3e7eb", "#8fdca3", "#3fb95f", "#238a3e", "#0f5a28"]),
}
# o que esta no ecra em cada bloco de 3 h: 00-03 logs, 03-06 logs, 06-09 revisao (diff), 09-12 codigo,
# 12-15 codigo, 15-18 testes, 18-21 codigo, 21-24 revisao
SCREEN_KIND = ["logs", "logs", "diff", "code", "code", "tests", "code", "diff"]


def code_rows(kind, seed, x0, y0, wmax):
    """linhas abstratas de 'codigo' (retangulos com cor por categoria via var(--kN))."""
    r = random.Random(seed)
    o, y, ind = [], y0, 0
    for row in range(26):
        if kind == "logs":
            x = x0
            o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="9" height="1.4" rx=".6" style="fill:var(--k3)"/>')
            x += 11
            lv = r.random()
            o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="4" height="1.4" rx=".6" style="fill:var(--k{5 if lv < .8 else 6 if lv < .95 else 0})"/>')
            x += 6
            for _ in range(r.randint(1, 4)):
                w_ = r.uniform(4, 22)
                if x + w_ > x0 + wmax:
                    break
                o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w_:.1f}" height="1.4" rx=".6" style="fill:var(--k4)" opacity=".8"/>')
                x += w_ + 2
            y += 2.9
            continue
        if r.random() < .13:
            y += 3.2
            ind = max(0, ind - 1)
            continue
        ind = max(0, min(4, ind + r.choice([-1, 0, 0, 0, 1])))
        x = x0 + ind * 5
        if kind == "diff" and r.random() < .35:
            add = r.random() < .6
            o.append(f'<rect x="{x0 - 5}" y="{y - .7:.1f}" width="{wmax + 6}" height="2.9" style="fill:var(--{"add" if add else "dele"})"/>')
        if kind == "tests" and r.random() < .45:
            o.append(f'<circle cx="{x0 + 1:.1f}" cy="{y + .7:.1f}" r="1" fill="#2da44e"/>')
            x = x0 + 4
        if r.random() < .15:
            o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{r.uniform(18, 50):.1f}" height="1.4" rx=".6" style="fill:var(--k3)"/>')
        else:
            for j in range(r.randint(1, 4)):
                w_ = r.uniform(4, 18)
                if x + w_ > x0 + wmax:
                    break
                cat = 0 if j == 0 and r.random() < .5 else r.choice([1, 2, 4, 4, 5, 6])
                o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w_:.1f}" height="1.4" rx=".6" style="fill:var(--k{cat})"/>')
                x += w_ + 2.2
        y += 3.2
    return "".join(o)


def screen_svg(rig, weeks, sx, sy, sw, sh, idp):
    ed_x, ed_w, ed_y, ed_h = sx + 17, sw - 17, sy + 4.5, 23.5
    GY = 29.5              # o painel do grafico ocupa a metade de baixo do ecra
    defs = [f'<clipPath id="{idp}codec"><rect x="{ed_x}" y="{ed_y}" width="{ed_w}" height="{ed_h}"/></clipPath>']
    for v in range(8):
        if rig.any(f"cv{v}"):
            rows = code_rows(SCREEN_KIND[v], 100 + v * 7, ed_x + 9, ed_y + 3, ed_w - 14)
            defs.append(f'<g id="{idp}cv{v}">{rows}</g>')
    # grafico de contribuicoes (painel de baixo)
    pitch = 3.6
    nwk = int((sw - 5) // pitch)
    cs = pitch * 0.84
    hx0 = sx + (sw - nwk * pitch + (pitch - cs)) / 2
    hy0 = sy + GY + (sh - GY - 7 * pitch) / 2 + .6
    empty, full, lv = [], [], []
    for wi, wk_ in enumerate(weeks[-nwk:]):
        for d_, c in wk_:
            di = (d_.weekday() + 1) % 7
            x, y = hx0 + wi * pitch, hy0 + di * pitch
            empty.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cs:.2f}" height="{cs:.2f}" rx="0.5"/>')
            if c:
                l_ = 1 if c < 5 else 2 if c < 15 else 3 if c < 40 else 4
                lv.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cs:.2f}" height="{cs:.2f}" rx="0.5" style="fill:var(--g{l_})"/>')
                full.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cs:.2f}" height="{cs:.2f}" rx="0.5" fill="{THEMES["D"]["gh"][l_]}"/>')
    defs.append(f'<g id="{idp}gh"><g style="fill:var(--g0)">{"".join(empty)}</g>{"".join(lv)}</g>')
    tr = random.Random(14)
    tree = "".join(f'<rect x="{sx + 2 + tr.choice([0, 2, 4])}" y="{sy + 6 + k * 3.2:.1f}" width="{tr.uniform(5, 11):.1f}" height="1.3" rx="0.6" '
                   f'style="fill:var(--{"treeA" if k == 3 else "tree"})"/>' for k in range(7))
    gut = "".join(f'<rect x="{sx + 19}" y="{ed_y + 3 + k * 3.2:.1f}" width="4" height="1.1" style="fill:var(--gut)"/>' for k in range(7))
    out = ["<defs>" + "".join(defs) + "</defs>"]
    for th in ("D", "L"):
        T = THEMES[th]
        if not rig.any("th" + th):
            continue
        var = ";".join(f"--k{i}:{c}" for i, c in enumerate(T["k"])) + ";" + ";".join(f"--g{i}:{c}" for i, c in enumerate(T["gh"]))
        var += f";--add:{T['add']};--dele:{T['dele']};--tree:{T['tree']};--treeA:{T['treeA']};--gut:{T['gut']}"
        g = [f'<g style="{var}">',
             f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="{T["bg"]}"/>',
             f'<rect x="{sx}" y="{sy}" width="{sw}" height="4" fill="{T["bar"]}"/>',
             "".join(f'<rect x="{sx + 20 + k * 20}" y="{sy + 1.2}" width="{w_}" height="1.8" rx="0.9" fill="{T["sel"] if k == 0 else T["line"]}"/>'
                     for k, w_ in enumerate((16, 13, 18))),
             f'<rect x="{sx}" y="{sy + 4}" width="17" height="{GY - 4}" fill="{T["side"]}"/>',
             f'<rect x="{sx}" y="{sy + 13.8}" width="17" height="3" fill="{T["sel"]}" opacity=".18"/>', tree,
             gut, f'<g clip-path="url(#{idp}codec)"><g class="code">']
        for v in range(8):
            if rig.any(f"cv{v}"):
                g.append(rig.g(f"cv{v}", f'<use href="#{idp}cv{v}"/>'))
        g.append("</g></g>")
        g.append(f'<rect class="cur" x="{sx + 62}" y="{sy + 18.6}" width="1" height="3" fill="{T["cur"]}"/>')
        g.append(f'<rect x="{sx}" y="{sy + GY}" width="{sw}" height="{sh - GY}" fill="{T["panel"]}"/>'
                 f'<rect x="{sx}" y="{sy + GY}" width="{sw}" height="0.6" fill="{T["line"]}"/>')
        g.append(f'<use href="#{idp}gh"/></g>')
        out.append(rig.g("th" + th, "".join(g)))
    return "".join(out), empty, full


# ================================================================== ceu
CLOUD_P = 190


def cloud_band():
    """estratocumulos macios (elipses achatadas em cacho, base plana) e estratos finos; periodo CLOUD_P."""
    r = random.Random(4)
    o = []
    for cx, cy, wdt in [(98, 42, 38), (152, 33, 20), (206, 52, 46), (252, 38, 22)]:
        n = max(3, int(wdt / 6))
        for j in range(n):
            t = j / (n - 1)
            x = cx - wdt / 2 + wdt * t + r.uniform(-2, 2)
            hh = (1.4 + 2.6 * math.sin(math.pi * t)) * r.uniform(.8, 1.2)
            o.append(f'<ellipse cx="{x:.1f}" cy="{cy - hh * .5:.1f}" rx="{r.uniform(5, 9) * (wdt / 36) ** .3:.1f}" ry="{hh:.1f}"/>')
        o.append(f'<ellipse cx="{cx}" cy="{cy + .2}" rx="{wdt / 2 + 4:.1f}" ry="1.3"/>')
    for cx, cy, wdt in [(120, 29, 52), (232, 27, 40), (172, 64, 56)]:
        o.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{wdt / 2}" ry=".8" opacity=".6"/>')
    return "".join(o)


def planes_svg(tl=False):
    d1, d2 = (4.5, 7) if tl else (53, 89)
    o = [f'<style>.pl1{{animation:pl1 {d1}s linear infinite}}.pl2{{animation:pl2 {d2}s linear -{d2 / 3:.1f}s infinite}}'
         '@keyframes pl1{0%{transform:translate(0,0);opacity:1}55%{transform:translate(185px,-12px);opacity:1}55.1%,100%{opacity:0;transform:translate(185px,-12px)}}'
         '@keyframes pl2{0%{transform:translate(0,0);opacity:1}40%{transform:translate(-175px,6px);opacity:1}40.1%,100%{opacity:0;transform:translate(-175px,6px)}}</style>']
    o.append('<g class="pl1"><g transform="translate(66 46)"><circle r=".75" fill="#ff5a4a" class="blink"/>'
             '<circle cx="2.6" cy=".2" r=".5" fill="#eef3ff" class="blink" style="animation-duration:1.3s;animation-delay:-.6s"/></g></g>')
    o.append('<g class="pl2"><g transform="translate(256 34)"><circle r=".55" fill="#7dff9a" class="blink" style="animation-duration:1.9s"/>'
             '<circle cx="-2" cy=".1" r=".45" fill="#eef3ff" class="blink" style="animation-duration:1.1s"/></g></g>')
    return "".join(o)


# ================================================================== cadeira
CHX = 470
_c = CHX
CH_BACK = (f"M{_c - 29},148 C{_c - 18},141.5 {_c + 18},141.5 {_c + 29},148 C{_c + 32},160 {_c + 30},172 {_c + 26},184 "
           f"C{_c + 24},192 {_c + 23},197 {_c + 19},201 C{_c + 8},204.5 {_c - 8},204.5 {_c - 19},201 "
           f"C{_c - 23},197 {_c - 24},192 {_c - 26},184 C{_c - 30},172 {_c - 32},160 {_c - 29},148Z")
CH_TOP = f"M{_c - 27},147.2 C{_c - 17},141.8 {_c + 17},141.8 {_c + 27},147.2"
CH_RIGHT = f"M{_c + 29.5},150 C{_c + 32},161 {_c + 30},172 {_c + 26},184 C{_c + 24},192 {_c + 23},197 {_c + 19},201"
CH_LEFT = f"M{_c - 29.5},150 C{_c - 32},161 {_c - 30},172 {_c - 26},184 C{_c - 24},192 {_c - 23},197 {_c - 19},201"


def chair_svg():
    c = CHX
    o = []
    hub = (c, 243.5)
    tips = []
    for k in range(5):
        ang = math.radians(90 + 72 * k)
        tips.append((c + 41 * math.cos(ang), 250.5 + 8.5 * math.sin(ang), math.sin(ang)))
    back = [t for t in tips if t[2] < 0]
    front = [t for t in tips if t[2] >= 0]

    def spoke(t):
        x, y, sn = t
        wd = 3.6 + 1.2 * sn
        return (f'<path d="M{hub[0]},{hub[1] - 1.2} L{x:.1f},{y - 1.6:.1f}" stroke="#1a191e" stroke-width="{wd:.1f}" stroke-linecap="round"/>'
                f'<path d="M{hub[0]},{hub[1] - 2.2} L{x:.1f},{y - 2.6:.1f}" stroke="#4a4852" stroke-width=".5" opacity=".6"/>')

    def caster(t):
        x, y, sn = t
        return (f'<path d="M{x:.1f},{y - 1.4:.1f} v2.2" stroke="#2a2930" stroke-width="1.4"/>'
                f'<rect x="{x - 3.2:.1f}" y="{y + .4:.1f}" width="6.4" height="3.8" rx="1.9" fill="#0f0e12"/>'
                f'<rect x="{x - 2.4:.1f}" y="{y + .9:.1f}" width="1.6" height="2.6" rx=".8" fill="#2c2b33"/>'
                f'<rect x="{x + .8:.1f}" y="{y + .9:.1f}" width="1.6" height="2.6" rx=".8" fill="#2c2b33"/>')
    for t in back:
        o.append(caster(t))
        o.append(spoke(t))
    # coluna de gas: fole preto + haste cromada
    o.append(f'<rect x="{c - 1.9}" y="226" width="3.8" height="18" fill="url(#metalg)"/>')
    o.append(f'<path d="M{c - 3.6},212 h7.2 v16 q0,1.2 -1.2,1.2 h-4.8 q-1.2,0 -1.2,-1.2Z" fill="#17161b"/>')
    o.append(f'<path d="M{c - 1.8},213 v15" stroke="#3a3942" stroke-width=".6"/>')
    o.append(f'<ellipse cx="{c}" cy="{hub[1]}" rx="5.5" ry="2.2" fill="#141318"/>')
    for t in front:
        o.append(spoke(t))
        o.append(caster(t))
    # assento: tampo (vemo-lo um pouco de cima) + espessura
    o.append(f'<path d="M{c - 37},203 C{c - 38},199 {c - 30},196.5 {c},196.5 C{c + 30},196.5 {c + 38},199 {c + 37},203 '
             f'L{c + 36},209 C{c + 30},212.5 {c - 30},212.5 {c - 36},209Z" fill="#26252c"/>')
    o.append(f'<path d="M{c - 36},209 C{c - 30},212.5 {c + 30},212.5 {c + 36},209 L{c + 35.5},211.5 C{c + 28},215.5 {c - 28},215.5 {c - 35.5},211.5Z" fill="#141318"/>')
    o.append(f'<path d="M{c - 35},202 C{c - 34},199 {c - 26},197.6 {c},197.6 C{c + 26},197.6 {c + 34},199 {c + 35},202" stroke="#fff" stroke-opacity=".10" stroke-width=".8" fill="none"/>')
    # mecanismo e alavanca
    o.append(f'<rect x="{c - 13}" y="211" width="26" height="4.5" rx="1.2" fill="#1b1a20"/>')
    o.append(f'<path d="M{c + 12},213 L{c + 22},215.5" stroke="#1b1a20" stroke-width="1.3" stroke-linecap="round"/><circle cx="{c + 22.5}" cy="215.7" r="1.3" fill="#26252c"/>')
    # bracos: suporte em L desde debaixo do assento + almofada
    for sg in (-1, 1):
        xa = c + sg * 34
        o.append(f'<path d="M{c + sg * 14},212.5 H{xa + sg * 1.5} Q{xa + sg * 3.5},212.5 {xa + sg * 3.5},210 V191" stroke="#1a191e" stroke-width="3.2" fill="none" stroke-linejoin="round"/>')
        o.append(f'<path d="M{xa + sg * 3.5 - .9},209 V192" stroke="#46444e" stroke-width=".5"/>')
        o.append(f'<rect x="{xa + sg * 3.5 - 5.5:.1f}" y="187" width="11" height="4.6" rx="2.1" fill="#1f1e24"/>'
                 f'<rect x="{xa + sg * 3.5 - 4.8:.1f}" y="187.3" width="9.6" height="1.5" rx=".75" fill="#3b3a42"/>')
    # espinha: liga o encosto ao mecanismo
    o.append(f'<path d="M{c - 4},200 C{c - 4.5},206 {c - 5},209 {c - 6},212 H{c + 6} C{c + 5},209 {c + 4.5},206 {c + 4},200Z" fill="#16151a"/>')
    o.append(f'<path d="M{c - 2.4},201 C{c - 2.8},206 {c - 3.2},209 {c - 3.8},211.5" stroke="#3d3c45" stroke-width=".5" fill="none"/>')
    # encosto: rede com aro rigido, apoio lombar
    o.append(f'<clipPath id="bk"><path d="{CH_BACK}"/></clipPath>')
    o.append(f'<path d="{CH_BACK}" fill="url(#chairg)"/>')
    mesh = "".join(f'<path d="M{c - 44 + k * 1.9:.1f},138 l34,72"/><path d="M{c + 44 - k * 1.9:.1f},138 l-34,72"/>' for k in range(46))
    o.append(f'<g clip-path="url(#bk)"><g stroke="{C["mesh"]}" stroke-width="0.4" opacity="0.55">{mesh}</g>'
             f'<radialGradient id="bkhl" cx=".62" cy=".25" r=".7"><stop offset="0" stop-color="#fff" stop-opacity=".09"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
             f'<rect x="{c - 34}" y="140" width="68" height="66" fill="url(#bkhl)"/>'
             f'<path d="M{c - 34},179 C{c - 10},185 {c + 10},185 {c + 34},179 L{c + 34},188 C{c + 10},194 {c - 10},194 {c - 34},188Z" fill="#0f0e12" opacity="0.55"/>'
             f'<path d="M{c - 34},179 C{c - 10},185 {c + 10},185 {c + 34},179" stroke="#4a4852" stroke-width=".5" fill="none" opacity=".7"/>'
             f'<path d="M{c - 34},196 C{c - 10},203 {c + 10},203 {c + 34},196 V210 H{c - 34}Z" fill="#000" opacity="0.25"/></g>')
    o.append(f'<path d="{CH_BACK}" fill="none" stroke="#121116" stroke-width="2.6"/>')
    o.append(f'<path d="{CH_TOP}" fill="none" stroke="#56545e" stroke-width=".6" opacity=".8"/>')
    return "".join(o)


# ================================================================== relogio de parede
# relogio analogico normal de 12 h (12 marcas, 3/6/9/12 mais fortes, sem numeros).
# Ao vivo (o servidor gera a imagem no momento): ponteiros das horas, minutos e segundos (fino, vermelho-tijolo)
# na hora exata de geracao, a andar a velocidade real (CSS 43200 s / 3600 s / 60 s em steps). Cada ponteiro tem a
# hora de geracao no transform estatico e a animacao e relativa, por isso sem animacao le-se a hora certa.
# Fallback (imagem da Action, vista com atraso): so o ponteiro das horas, adiantado FALLBACK_LEAD minutos.
# Timelapse: so o ponteiro das horas, duas voltas por loop, em fase com a luz.
CCX, CCY, CR = 296, 39, 20.8
ACC = "#b04a32"          # ponteiro dos segundos: vermelho-tijolo discreto


def _pt(cx, cy, r, ang):
    a_ = math.radians(ang)
    return cx + r * math.sin(a_), cy - r * math.cos(a_)


def _arc(cx, cy, r, a0, a1):
    span = (a1 - a0) % 360
    x0, y0 = _pt(cx, cy, r, a0)
    x1, y1 = _pt(cx, cy, r, a0 + span)
    return f"M{x0:.2f},{y0:.2f} A{r},{r} 0 {1 if span > 180 else 0} 1 {x1:.2f},{y1:.2f}"


def clock_angles(ldt):
    """(horas, minutos, segundos) em graus, sentido horario a partir do topo, mostrador de 12 h."""
    h = (ldt.hour % 12) + ldt.minute / 60 + ldt.second / 3600
    return h * 30, (ldt.minute + ldt.second / 60) * 6, ldt.second * 6


def hand_hour(cx, cy, lume=False):
    if lume:
        return (f'<path d="M{cx},{cy - 4.5} L{cx},{cy - 9.2}" stroke="#c6ffd6" stroke-width=".9" stroke-linecap="round"/>'
                f'<path d="M{cx},{cy - 4.5} L{cx},{cy - 9.2}" stroke="#7dffa6" stroke-width="2.4" stroke-linecap="round" opacity=".35" filter="url(#b0_6)"/>')
    return (f'<path d="M{cx - 1.3},{cy + 2.6} L{cx - .9},{cy - 8.6} L{cx},{cy - 11.2} L{cx + .9},{cy - 8.6} L{cx + 1.3},{cy + 2.6}Z" fill="#1d181d"/>')


def hand_min(cx, cy, lume=False):
    if lume:
        return (f'<path d="M{cx},{cy - 7} L{cx},{cy - 14.6}" stroke="#c6ffd6" stroke-width=".7" stroke-linecap="round"/>'
                f'<path d="M{cx},{cy - 7} L{cx},{cy - 14.6}" stroke="#7dffa6" stroke-width="2" stroke-linecap="round" opacity=".3" filter="url(#b0_6)"/>')
    return (f'<path d="M{cx - .9},{cy + 3.2} L{cx - .6},{cy - 13.4} L{cx},{cy - 16.2} L{cx + .6},{cy - 13.4} L{cx + .9},{cy + 3.2}Z" fill="#1d181d"/>')


def hand_sec(cx, cy):
    return (f'<path d="M{cx},{cy + 4.6} L{cx},{cy - 16.4}" stroke="{ACC}" stroke-width=".55" stroke-linecap="round"/>'
            f'<circle cx="{cx}" cy="{cy + 3.8}" r=".95" fill="{ACC}"/>')


def clock_rot(rig, ldt, ev, css, cx, cy, full):
    """CSS de rotacao dos ponteiros (partilhado pelos ponteiros e pelo seu lume)."""
    org = f"transform-origin:{cx}px {cy}px;"
    if rig.tl:
        A = clock_angles(ldt)[0]       # angulo estatico (fallback sem animacao)
        css.append(f".hh{{{org}animation:hh {rig.secs}s linear infinite}}"
                   f"@keyframes hh{{from{{transform:rotate({-A:.2f}deg)}}to{{transform:rotate({720 - A:.2f}deg)}}}}")
        return
    rev = " reverse" if "1_abril" in ev else ""
    css.append("@keyframes ckr{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}"
               f".hh{{{org}animation:ckr 43200s linear infinite{rev}}}")
    if full:
        css.append(f".mh{{{org}animation:ckr 3600s linear infinite{rev}}}"
                   f".sh{{{org}animation:ckr 60s steps(60) infinite{rev}}}")


def _hands(cx, cy, ldt, full, lume=False):
    A, M, Sx = clock_angles(ldt)
    o = [f'<g transform="rotate({A:.2f} {cx} {cy})"><g class="hh">{hand_hour(cx, cy, lume)}</g></g>']
    if full:
        o.append(f'<g transform="rotate({M:.2f} {cx} {cy})"><g class="mh">{hand_min(cx, cy, lume)}</g></g>')
        if not lume:
            o.append(f'<g transform="rotate({Sx:.2f} {cx} {cy})"><g class="sh">{hand_sec(cx, cy)}</g></g>')
    return "".join(o)


def clock_svg(rig, ldt, ev, css, fb=False):
    cx, cy, r = CCX, CCY, CR
    full = not rig.tl and not fb
    o = []
    o.append(f'<circle cx="{cx + 1.8}" cy="{cy + 2.8}" r="{r}" fill="#000" opacity="0.3" filter="url(#b1_2)"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#29242a"/>'
             f'<circle cx="{cx}" cy="{cy}" r="{r - .7:.1f}" fill="none" stroke="#4a434b" stroke-width=".6"/>'
             f'<circle cx="{cx}" cy="{cy}" r="{r - 2.2:.1f}" fill="#f1ebdf"/>'
             f'<circle cx="{cx}" cy="{cy}" r="{r - 2.2:.1f}" fill="url(#clockface)"/>'
             f'<circle cx="{cx + .4}" cy="{cy + .7}" r="{r - 2.9:.1f}" fill="none" stroke="#000" stroke-width="1.1" opacity=".08"/>')
    # 12 marcas (12/3/6/9 maiores)
    ra = r - 3.3
    ticks = []
    for k in range(12):
        big = k % 3 == 0
        x0, y0 = _pt(cx, cy, ra - (3.4 if big else 2.1), k * 30)
        x1, y1 = _pt(cx, cy, ra, k * 30)
        ticks.append(f'<path d="M{x0:.2f},{y0:.2f} L{x1:.2f},{y1:.2f}" stroke-width="{1.5 if big else .7}"/>')
    o.append(f'<g stroke="#2e282e" stroke-linecap="butt">{"".join(ticks)}</g>')
    clock_rot(rig, ldt, ev, css, cx, cy, full)
    o.append(_hands(cx, cy, ldt, full))
    o.append(f'<circle cx="{cx}" cy="{cy}" r="1.6" fill="#1d181d"/>')
    if full:
        o.append(f'<circle cx="{cx}" cy="{cy}" r=".7" fill="{ACC}"/>')
    # vidro: reflexo
    o.append(f'<path d="M{cx - 13.6},{cy - 6.5} A{r - 4.2},{r - 4.2} 0 0 1 {cx + 4.5},{cy - 16}" stroke="#fff" stroke-opacity=".45" stroke-width="1.4" fill="none" stroke-linecap="round"/>')
    o.append(f'<path d="M{cx - 11},{cy - 11} A{r - 2.5},{r - 2.5} 0 0 1 {cx + 11},{cy - 11} A{r + 6},{r + 6} 0 0 0 {cx - 11},{cy - 11}Z" fill="#fff" opacity=".1"/>')
    return "".join(o)


def clock_night(rig, ldt, fb=False):
    """emissivos do relogio (depois das tintas): lume nos ponteiros e nas marcas 12/3/6/9, e o monitor a
    apanhar o aro e o mostrador (sem isto, de noite, o relogio desaparece)."""
    cx, cy, r = CCX, CCY, CR
    full = not rig.tl and not fb
    ra = r - 3.3
    dots = "".join(f'<circle cx="{_pt(cx, cy, ra - 1.7, k * 30)[0]:.2f}" cy="{_pt(cx, cy, ra - 1.7, k * 30)[1]:.2f}" r=".65" fill="#bfffd0"/>'
                   for k in (0, 3, 6, 9))
    face = (f'<g style="mix-blend-mode:screen"><circle cx="{cx}" cy="{cy}" r="{r - 2.2:.1f}" fill="#8da3cf" opacity=".22"/>'
            f'<path d="{_arc(cx, cy, r - .7, 70, 190)}" stroke="#a9c2ff" stroke-width=".8" fill="none" opacity=".5" stroke-linecap="round"/></g>')
    lume = f'<g opacity=".9">{dots}{_hands(cx, cy, ldt, full, lume=True)}</g>'
    return rig.g("monlit", face) + rig.g("dark", lume)


# ================================================================== easter eggs
EGG_CSS = (
    # robot aspirador: 97 s, primeira passagem aos 14 s
    ".vac{animation:vac 97s linear 14s infinite}"
    "@keyframes vac{0%{transform:translateX(0);opacity:1}3.2%{transform:translateX(-318px)}3.5%{transform:translateX(-318px)}"
    "4.1%{transform:translateX(-300px)}4.8%{transform:translateX(-300px)}9.5%{transform:translateX(-930px);opacity:1}9.6%,100%{transform:translateX(-930px);opacity:0}}"
    # cobra no monitor: 71 s, primeira aos 27 s
    ".snk{animation:snk 71s linear 27s infinite}@keyframes snk{0%{opacity:0}.6%{opacity:1}7.4%{opacity:1}8%,100%{opacity:0}}"
    # aguaceiro: 131 s, primeiro aos 5 s
    ".rain{animation:rain 311s ease-in-out 40s infinite}@keyframes rain{0%{opacity:0}1.1%{opacity:1}5%{opacity:1}6.1%,100%{opacity:0}}"
)


def vacuum_body():
    x, y = 860, 231
    return (f'<g class="vac" opacity="0"><g transform="translate({x} {y})">'
            '<ellipse cx="0" cy="3.4" rx="15" ry="3.2" fill="#000" opacity=".35" filter="url(#b1_2)"/>'
            '<path d="M-13,0 v2.6 a13,4.4 0 0 0 26,0 v-2.6Z" fill="#8f9096"/>'
            '<ellipse cx="0" cy="0" rx="13" ry="4.4" fill="#e4e4e6"/>'
            '<ellipse cx="0" cy="-.3" rx="10.5" ry="3.3" fill="#d2d3d7"/>'
            '<ellipse cx="-3" cy="-.9" rx="3.2" ry="1.3" fill="#1f1f25"/>'
            '<path d="M-12.6,.6 a13,4.4 0 0 0 5,3" stroke="#56565f" stroke-width=".6" fill="none"/>'
            '<path d="M-9,-2.4 a10,3 0 0 1 12,-1" stroke="#fff" stroke-opacity=".18" stroke-width=".5" fill="none"/>'
            '</g></g>')


def vacuum_led():
    x, y = 860, 231
    return (f'<g class="vac" opacity="0"><g transform="translate({x} {y})">'
            '<circle cx="4.2" cy="-.8" r=".6" fill="#6fe3ff" class="pulse"/><circle cx="4.2" cy="-.8" r="2.2" fill="#6fe3ff" opacity=".3" filter="url(#b1_2)"/>'
            '</g></g>')


def snake_egg(weeks, sx, sy, sw, sh):
    """o ecra passa a um 'jogo': as ultimas 24 semanas em grande, e uma cobra que as come."""
    cols, rows, p = 24, 7, 5.6
    gx0 = sx + (sw - cols * p) / 2
    gy0 = sy + (sh - rows * p) / 2 + 2
    wk = weeks[-cols:]
    ramp = ["#0e4429", "#006d32", "#26a641", "#39d353"]
    cells, cmap = [], {}
    for ci, w_ in enumerate(wk):
        for d_, c in w_:
            ri = (d_.weekday() + 1) % 7
            x, y = gx0 + ci * p, gy0 + ri * p
            if c:
                lvl = 0 if c < 5 else 1 if c < 15 else 2 if c < 40 else 3
                cells.append(f'<rect x="{x + .6:.1f}" y="{y + .6:.1f}" width="{p - 1.2}" height="{p - 1.2}" rx=".6" fill="{ramp[lvl]}"/>')
                cmap[(ci, ri)] = (x, y)
            else:
                cells.append(f'<rect x="{x + .6:.1f}" y="{y + .6:.1f}" width="{p - 1.2}" height="{p - 1.2}" rx=".6" fill="#161b22"/>')
    # percurso da cobra em celulas
    route = [(0, 3)]

    def go(c, r):
        c0, r0 = route[-1]
        while (c0, r0) != (c, r):
            c0 += (c > c0) - (c < c0) if c0 != c else 0
            if c0 == c:
                r0 += (r > r0) - (r < r0)
            route.append((c0, r0))
    for tgt in [(6, 3), (6, 5), (13, 5), (13, 1), (19, 1), (19, 4), (23, 4)]:
        go(*tgt)
    L = len(route)
    body = 5
    pts_ = [(gx0 + c * p + p / 2, gy0 + r * p + p / 2) for c, r in route]
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts_)
    total = (L - 1) * p
    # a cobra entra aos 0.8% e sai aos 7.2% do ciclo (71 s)
    t0, t1 = .8, 7.2
    css = []
    eats = []
    for i, (c, r) in enumerate(route):
        if (c, r) in cmap:
            x, y = cmap[(c, r)]
            t = t0 + (t1 - t0) * (i + body * .0) / (L - 1 + body)
            key = f"se{i}"
            css.append(f"@keyframes {key}{{0%,{t:.2f}%{{opacity:0}}{t + .05:.2f}%,100%{{opacity:1}}}}.{key}{{animation:{key} 71s linear 27s infinite}}")
            eats.append(f'<rect class="{key}" opacity="0" x="{x + .6:.1f}" y="{y + .6:.1f}" width="{p - 1.2}" height="{p - 1.2}" rx=".6" fill="#161b22"/>')
    dash = body * p
    css.append(f"@keyframes sb{{0%,{t0:.2f}%{{stroke-dashoffset:{dash:.1f}}}{t1:.2f}%,100%{{stroke-dashoffset:{-total:.1f}}}}}"
               f".sb{{animation:sb 71s linear 27s infinite}}")
    return (f'<style>{"".join(css)}</style><g class="snk" opacity="0">'
            f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="#0d1117"/>' + "".join(cells) + "".join(eats) +
            f'<path class="sb" d="{path}" fill="none" stroke="#b0c4ff" stroke-width="{p - 1.4}" stroke-linejoin="round" stroke-linecap="round" '
            f'stroke-dasharray="{dash:.1f} {total + dash + 10:.1f}" stroke-dashoffset="{dash:.1f}"/></g>')


def rain_egg():
    o = ['<g class="rain" opacity="0">', '<linearGradient id="raing" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5d6776" stop-opacity=".88"/>'
         '<stop offset=".6" stop-color="#6a7482" stop-opacity=".62"/><stop offset="1" stop-color="#5a6474" stop-opacity=".4"/></linearGradient>'
         '<rect x="78" y="24" width="164" height="92" fill="url(#raing)"/>']
    for cls, n, op, ln, sd in (("rn", 90, 0.35, 9, 1), ("rn2", 70, 0.5, 14, 2)):
        r2 = random.Random(sd)
        ls = "".join(f'<path d="M{r2.uniform(78, 250):.1f},{r2.uniform(-20, 118):.1f} l-1.5,{ln}"/>' for _ in range(n))
        o.append(f'<g class="{cls}"><g stroke="#c4d4ea" stroke-width="0.55" opacity="{op}">{ls}</g></g>')
    gr = random.Random(9)
    for _ in range(60):
        x, y, r = gr.uniform(79, 241), gr.uniform(25, 115), gr.choice([0.5, 0.7, 0.9, 1.1, 1.4])
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#2a3448" stroke="#b9cbe4" stroke-width="0.3" opacity="0.75"/>'
                 f'<circle cx="{x - r * 0.3:.1f}" cy="{y - r * 0.35:.1f}" r="{r * 0.3:.2f}" fill="#eef3fa" opacity="0.75"/>')
    for k, (x, y) in enumerate([(96, 40), (132, 52), (186, 34), (228, 58)]):
        o.append(f'<g class="dr" style="animation-delay:-{k * 1.9:.1f}s"><path d="M{x},{y - 16} v16" stroke="#a9bedb" stroke-width="0.5" opacity="0.3"/>'
                 f'<circle cx="{x}" cy="{y}" r="1.5" fill="#2a3448" stroke="#b7cae6" stroke-width="0.4"/><circle cx="{x - 0.5}" cy="{y - 0.6}" r="0.45" fill="#eef4fb"/></g>')
    o.append("</g>")
    return "".join(o)


CAT_BODY = "M-8.5,0 C-10,-5.5 -5,-10.6 2,-10.6 C8.6,-10.6 13.4,-6.8 13.4,-2 C13.4,-.6 12.6,0 11.4,0Z"
CAT_HEAD = ("M-16.2,0 C-17.2,-3.2 -16.4,-6 -14.6,-7.2 L-15.1,-10.6 L-12.4,-8.2 C-11.6,-8.4 -10.8,-8.4 -10,-8.2 "
            "L-8,-10.4 L-7.9,-6.9 C-6.7,-5.6 -6.4,-3.2 -7.2,0Z")


def cat_svg(x, y):
    """gato enrolado a dormir no peitoril: corpo em bola, cabeca pousada com as orelhas de pe, cauda a volta."""
    return (f'<g transform="translate({x} {y}) scale(1.5)">'
            '<ellipse cx="-1" cy=".2" rx="17" ry="1.6" fill="#000" opacity=".35" filter="url(#b1_2)"/>'
            f'<g class="breath"><path d="{CAT_BODY}" fill="#18171c"/></g>'
            f'<path d="{CAT_HEAD}" fill="#1c1b21"/>'
            '<path d="M-8.2,-3.2 C-7.4,-2 -7.2,-1 -7.4,0" stroke="#0e0d11" stroke-width=".6" fill="none"/>'
            '<path d="M-14.6,-3.4 q1,.5 2,0 M-11.4,-3.4 q1,.5 2,0" stroke="#34323b" stroke-width=".35" fill="none"/>'
            '<path d="M12.4,-.8 C14.6,.4 12.4,1.7 6,1.8 C0,1.9 -6,1.6 -10.6,.9" stroke="#18171c" stroke-width="2.1" fill="none" stroke-linecap="round"/>'
            '</g>')


def cat_rim(x, y):
    """contraluz: as luzes da cidade desenham o contorno do gato (emissivo, depois das tintas)."""
    return (f'<g transform="translate({x} {y}) scale(1.5)" fill="none" stroke-linecap="round" stroke-linejoin="round" style="mix-blend-mode:screen">'
            '<g class="breath"><path d="M-6.4,-8.4 C-3.6,-10.2 0,-10.6 2,-10.6 C8.6,-10.6 13.4,-6.8 13.4,-2.4" stroke="#a9bde8" stroke-width=".5" opacity=".9"/></g>'
            '<path d="M-16.4,-4.4 C-16.2,-5.8 -15.6,-6.7 -14.6,-7.2 L-15.1,-10.6 L-12.4,-8.2 M-10,-8.2 L-8,-10.4 L-7.9,-6.9" stroke="#a9bde8" stroke-width=".45" opacity=".85"/>'
            '</g>')


def pumpkin(x, y):
    return (f'<g transform="translate({x} {y})"><ellipse cx="0" cy="0" rx="8" ry="1.4" fill="#000" opacity=".3"/>'
            '<ellipse cx="-3" cy="-4" rx="4" ry="4.2" fill="#b95a1e"/><ellipse cx="3" cy="-4" rx="4" ry="4.2" fill="#b95a1e"/>'
            '<ellipse cx="0" cy="-4.2" rx="3.6" ry="4.4" fill="#cf6a24"/><path d="M0,-8.2 q.6,-2 1.8,-2.4" stroke="#4a5a2a" stroke-width="1.1" fill="none"/>'
            '<rect x="7" y="-2.4" width="2.6" height="2.4" rx=".4" fill="#e8e0d0"/></g>')


def pumpkin_glow(x, y):
    return (f'<g transform="translate({x} {y})"><circle cx="8.3" cy="-3.2" r=".6" fill="#ffd27a" class="flk"/>'
            '<circle cx="8.3" cy="-3" r="7" fill="url(#gFlame)" opacity=".5" class="flk"/></g>')


def cupcake(x, y):
    return (f'<g transform="translate({x} {y}) scale(2.3)"><ellipse cx="0" cy=".2" rx="4.6" ry=".8" fill="#000" opacity=".45"/>'
            '<path d="M-3.4,-4 L3.4,-4 L2.6,0 L-2.6,0Z" fill="#c9a47a"/><path d="M-2.6,-4 v4 M-1.2,-4 v4 M.2,-4 v4 M1.6,-4 v4" stroke="#a88659" stroke-width=".3"/>'
            '<path d="M-4,-4 C-4.4,-6 -2,-7.6 0,-7.4 C2,-7.6 4.4,-6 4,-4Z" fill="#f1e6de"/>'
            '<rect x="-.35" y="-11.4" width=".7" height="4" fill="#e8d3b0"/></g>')


def cupcake_flame(x, y):
    return (f'<g transform="translate({x} {y}) scale(2.3)" class="flk"><circle cx="0" cy="-12.4" r="10" fill="url(#gFlame)" opacity=".7"/>'
            '<path d="M0,-14.4 C.9,-13.2 .9,-12 0,-11.6 C-.9,-12 -.9,-13.2 0,-14.4Z" fill="#ffe2a0"/></g>')


def xmas_lights():
    o = []
    rr = random.Random(12)
    cols = ["#ffcf8a", "#ffe0b0", "#ffb86a"]
    # varao da cortina
    for k in range(26):
        t = k / 25
        x = 40 + 236 * t
        y = 11 + 5 * math.sin(math.pi * ((t * 4) % 1))
        c = rr.choice(cols)
        o.append(f'<circle class="stw" style="--d:{1.8 + rr.random() * 2.4:.1f}s;animation-delay:-{rr.random() * 3:.1f}s" cx="{x:.1f}" cy="{y:.1f}" r=".9" fill="{c}"/>')
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{c}" opacity=".35" filter="url(#b1_2)"/>')
    wire = "M40,11 " + " ".join(f"Q{40 + 59 * (i + .5):.1f},{19} {40 + 59 * (i + 1):.1f},11" for i in range(4))
    # topo da estante
    for k in range(16):
        x = 680 + k * 7
        y = 30 + 2.5 * math.sin(k * 1.3)
        c = rr.choice(cols)
        o.append(f'<circle class="stw" style="--d:{1.8 + rr.random() * 2.4:.1f}s;animation-delay:-{rr.random() * 3:.1f}s" cx="{x:.1f}" cy="{y:.1f}" r=".85" fill="{c}"/>')
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{c}" opacity=".35" filter="url(#b1_2)"/>')
    # o varao apanha a luz das lampadas (sem isto, de noite, as luzes parecem a flutuar)
    rod = ('<rect x="36" y="8" width="244" height="2.4" rx="1.2" fill="#6a5a4c" opacity=".55"/>'
           '<path d="M37,8.5 H279" stroke="#ffd9a0" stroke-width=".7" opacity=".7"/>'
           '<circle cx="36" cy="9.2" r="2.4" fill="#6a5a4c" opacity=".6"/><circle cx="280" cy="9.2" r="2.4" fill="#6a5a4c" opacity=".6"/>'
           '<path d="M34.6,7.9 a2,2 0 0 1 2.8,0 M278.6,7.9 a2,2 0 0 1 2.8,0" stroke="#ffd9a0" stroke-width=".6" fill="none" opacity=".8"/>'
           '<rect x="36" y="10.4" width="244" height="6" fill="#ffcf8a" opacity=".12" filter="url(#b2)"/>')
    return rod + f'<path d="{wire}" stroke="#4a3a2c" stroke-width=".45" fill="none"/>' + "".join(o)


def fireworks():
    o = ['<style>.fw{transform-box:fill-box;transform-origin:center;animation:fw 2.6s ease-out infinite}'
         '@keyframes fw{0%{transform:scale(.15);opacity:0}8%{opacity:1}70%{opacity:.8}100%{transform:scale(1.08);opacity:0}}</style>']
    rr = random.Random(5)
    for k, (cx, cy, r, col) in enumerate([(118, 46, 20, "#ffd08a"), (200, 38, 24, "#ff9f8a"), (158, 62, 15, "#b8d4ff"), (224, 72, 13, "#ffe6b0")]):
        dots = []
        for j in range(22):
            ang = 2 * math.pi * j / 22 + rr.uniform(-.08, .08)
            for f_ in (.55, .82, 1):
                dots.append(f'<circle cx="{cx + r * f_ * math.cos(ang):.1f}" cy="{cy + r * f_ * math.sin(ang) + f_ * 2:.1f}" r="{.45 + .2 * f_:.2f}"/>')
        o.append(f'<g class="fw" style="animation-delay:-{k * .7:.1f}s;animation-duration:{2.4 + k * .35:.2f}s" fill="{col}">{"".join(dots)}'
                 f'<circle cx="{cx}" cy="{cy}" r="{r * .9:.1f}" fill="{col}" opacity=".12"/></g>')
    return "".join(o)


def moth_svg(Mo):
    """traca: voa num oval irregular a volta da boca do candeeiro (SMIL), aparece de vez em quando (CSS)."""
    x, y = Mo
    path = (f"M{x + 10:.1f},{y + 4:.1f} C{x + 14:.1f},{y - 6:.1f} {x - 2:.1f},{y - 12:.1f} {x - 9:.1f},{y - 3:.1f} "
            f"C{x - 15:.1f},{y + 5:.1f} {x - 3:.1f},{y + 12:.1f} {x + 4:.1f},{y + 7:.1f} C{x + 8:.1f},{y + 4:.1f} {x + 7:.1f},{y + 8:.1f} {x + 10:.1f},{y + 4:.1f}Z")
    return ('<style>.moth{animation:moth 67s linear 21s infinite}@keyframes moth{0%{opacity:0}1.5%{opacity:1}14%{opacity:1}15.5%,100%{opacity:0}}'
            '.wing{transform-box:fill-box;transform-origin:50% 100%;animation:wing .09s linear infinite alternate}@keyframes wing{to{transform:scaleY(.25)}}</style>'
            f'<g class="moth" opacity="0"><g><animateMotion dur="2.3s" repeatCount="indefinite" path="{path}"/>'
            '<g transform="scale(1.7)"><ellipse class="wing" cx="-1.2" cy="-.6" rx="1.3" ry="1" fill="#e6d4ad" stroke="#5a4a38" stroke-width=".2"/><ellipse class="wing" cx="1.2" cy="-.6" rx="1.3" ry="1" fill="#e6d4ad" stroke="#5a4a38" stroke-width=".2"/>'
            '<ellipse cx="0" cy="0" rx=".35" ry=".7" fill="#8a7a64"/></g><circle r="3.5" fill="#ffe2b0" opacity=".25" filter="url(#b1_2)"/></g></g>')


# ================================================================== render / timelapse
FALLBACK_LEAD = 10     # minutos: a imagem de fallback tem entre 0 e ~25 min quando e vista


def render(data, local_dt, mode="live", lead_min=FALLBACK_LEAD):
    """mode="live": relogio exatamente na hora dada. mode="fallback": so o ponteiro das horas (12 h, sem minutos nem
    segundos), adiantado lead_min minutos, para compensar a idade media da imagem publicada pela Action."""
    w, st = state(local_dt, data[0])
    if mode == "fallback":
        st = dict(st, clock_dt=local_dt + timedelta(minutes=lead_min), clock_fb=True)
    rig = Rig([w], 0, timelapse=False)
    return build(data, rig, st), st


def timelapse(data, day, secs=SECS, n=48, static_at=(19, 0)):
    samples = [day + timedelta(minutes=30 * i) for i in range(n + 1)]
    res = [state(t) for t in samples]
    ws = [r[0] for r in res]
    sts = [r[1] for r in res]
    si = [i for i, t in enumerate(samples) if (t.hour, t.minute) == static_at][0]
    rig = Rig(ws, si, secs=secs, timelapse=True)
    return build(data, rig, sts[si], sts=sts, idp="t")


# ================================================================== galeria r9
NN, SLUG = "03", "secretaria"
LIVE_AT = "2026-09-30T21:30"
MOMENTS = [("2026-09-30T00:30", "0030"), ("2026-09-30T06:50", "0650"), ("2026-09-30T07:40", "0740"), ("2026-09-30T09:30", "0930"),
           ("2026-09-30T13:30", "1330"), ("2026-09-30T17:45", "1745"), ("2026-09-30T19:20", "1920"), ("2026-09-30T20:15", "2015")]
SPECIAL = [("2026-12-24T22:00", "natal"), ("2026-12-31T23:58", "anonovo"), ("2026-10-24T18:00", "aniversario"),
           ("2027-04-01T15:00", "1abril"), ("2026-09-30T03:30", "madrugada")]


def gallery(data, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    pre = f"{NN}-{SLUG}"
    for at, tag in [(LIVE_AT, "agora")] + MOMENTS + SPECIAL:
        lt = datetime.fromisoformat(at)
        t0 = time.time()
        svg, st = render(data, lt)
        name = f"{pre}-{tag}.svg"
        (folder / name).write_text(svg, encoding="utf-8")
        print(f"{name}: elev {st['el']:.1f} az {st['az']:.0f} sol {st['sun']:.2f} ev {sorted(st['ev'])} | {len(svg) / 1024:.0f} KB | {time.time() - t0:.2f}s")
    t0 = time.time()
    svg = timelapse(data, datetime(2026, 9, 30))
    (folder / f"{pre}-timelapse.svg").write_text(svg, encoding="utf-8")
    print(f"{pre}-timelapse.svg: {len(svg) / 1024:.0f} KB | {time.time() - t0:.2f}s")
    desc = ("Secretaria (final) | Ao vivo (21:30): a sala segue o sol real; relogio de 24 h com um so ponteiro (uma volta por dia, "
            "aro dia/noite com o nascer e o por do sol do dia, lume a noite), por isso o atraso da Action/Camo nao se nota. "
            "Lua com posicao e fase reais (so aparece quando esta a frente da janela). Grafico de contribuicoes grande no monitor. "
            "Nascer com fachadas em pessego, manha fria, meio-dia branco, feixe dourado ao fim da tarde, cidade a acender, noite com candeeiro. "
            "Timelapse = 24 h de 30/09 em 48 s, o ponteiro da uma volta em fase com a luz. "
            "Easter eggs: aspirador, cobra no grafico, aguaceiro, traca, gato de madrugada, natal, ano novo, 24/10, 1 de abril, sexta a tarde.")
    moments = [f'<td><img alt="" src="assets/{pre}-{t}.svg" width="200"></td>' for _, t in MOMENTS]
    md = [f"<!-- {desc} -->",
          f'<img alt="" src="assets/{pre}-agora.svg" width="100%">', "",
          f'<img alt="" src="assets/{pre}-timelapse.svg" width="100%">', "",
          "<table><tr>" + "".join(moments[:4]) + "</tr><tr>" + "".join(moments[4:]) + "</tr></table>", "",
          "<p>" + " ".join(f'<img alt="" src="assets/{pre}-{t}.svg" width="160">' for _, t in SPECIAL) + "</p>", ""]
    (folder / f"{pre}.md").write_text("\n".join(md), encoding="utf-8")


SHOW = {  # --show: congela um easter egg a meio (para rever): (seletor, tempo dentro do ciclo em s)
    "vac": ("[class~=vac]", 97 * .038),
    "snk": ("[class~=snk],[class~=sb],[class^=se]", 71 * .045),
    "rain": ("[class~=rain]", 311 * .03),
    "moth": ("[class~=moth]", 67 * .06),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("contrib")
    ap.add_argument("out", help="ficheiro .svg (ou pasta, com --gallery)")
    ap.add_argument("--at", help="hora local Europe/Lisbon, ex. 2026-09-30T19:10")
    ap.add_argument("--gallery", action="store_true")
    ap.add_argument("--timelapse", action="store_true", help="gera o timelapse de 24 h do dia de --at")
    ap.add_argument("--show", choices=sorted(SHOW), help="congela um easter egg a meio (revisao)")
    a = ap.parse_args()
    data = load(a.contrib)
    if a.gallery:
        gallery(data, a.out)
        return
    local = datetime.fromisoformat(a.at) if a.at else now_local()
    t0 = time.time()
    if a.timelapse:
        svg = timelapse(data, local.replace(hour=0, minute=0, second=0, microsecond=0))
        st = state(local)[1]
    else:
        svg, st = render(data, local)
    if a.show:
        sel, tt = SHOW[a.show]
        svg = svg.replace("</svg>", f"<style>{sel}{{animation-delay:-{tt:.2f}s!important;animation-play-state:paused!important}}</style></svg>")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(svg, encoding="utf-8")
    print(f"{local:%Y-%m-%d %H:%M} Lisboa | sol elev {st['el']:.1f} az {st['az']:.0f} | {len(svg) / 1024:.0f} KB | {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
