"""Partes comuns do 'relogio de luz' (hora real em Portugal) para todas as cenas.

- tempo: now_local(), to_utc(local_naive), lisbon_offset(utc)
- sol: solar(utc) -> (elevacao, azimute) para um ponto GENERICO de Portugal (lat 39.5, lon -8.0)
- cores: hx, hexc, mixc, lerpc, ss (smoothstep), keyed (keyframes por elevacao), blend (mistura de paletas)
- extras: moon_phase(utc) e events(local_dt, days) (datas especiais para easter eggs)

Extraido de tools/clock_sala.py (que por agora mantem a sua copia).
"""
import math
from datetime import datetime, timedelta, timezone

LAT, LON = 39.5, -8.0
# ---------------- tempo e sol ----------------
def lisbon_offset(utc):
    """UTC+1 entre o ultimo domingo de marco e o ultimo domingo de outubro (01:00 UTC)."""
    def last_sunday(y, m):
        d = datetime(y, m + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    y = utc.year
    a = last_sunday(y, 3).replace(hour=1)
    b = last_sunday(y, 10).replace(hour=1)
    return timedelta(hours=1) if a <= utc < b else timedelta(0)


def to_utc(local_naive):
    try:
        from zoneinfo import ZoneInfo
        return local_naive.replace(tzinfo=ZoneInfo("Europe/Lisbon")).astimezone(timezone.utc)
    except Exception:
        guess = local_naive.replace(tzinfo=timezone.utc)
        return guess - lisbon_offset(guess - timedelta(hours=1))


def now_local():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Lisbon")).replace(tzinfo=None)
    except Exception:
        u = datetime.now(timezone.utc)
        return (u + lisbon_offset(u)).replace(tzinfo=None)


def solar(utc, lat=LAT, lon=LON):
    """(elevacao, azimute a partir do norte) em graus. NOAA (Meeus simplificado), com refracao."""
    jd = utc.timestamp() / 86400.0 + 2440587.5
    T = (jd - 2451545.0) / 36525.0
    r = math.radians
    L0 = (280.46646 + T * (36000.76983 + T * 0.0003032)) % 360
    M = 357.52911 + T * (35999.05029 - 0.0001537 * T)
    ec = 0.016708634 - T * (0.000042037 + 0.0000001267 * T)
    C = (math.sin(r(M)) * (1.914602 - T * (0.004817 + 0.000014 * T))
         + math.sin(r(2 * M)) * (0.019993 - 0.000101 * T) + math.sin(r(3 * M)) * 0.000289)
    om = 125.04 - 1934.136 * T
    lam = L0 + C - 0.00569 - 0.00478 * math.sin(r(om))
    eps0 = 23 + (26 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(r(om))
    dec = math.asin(math.sin(r(eps)) * math.sin(r(lam)))
    y = math.tan(r(eps / 2)) ** 2
    eot = 4 * math.degrees(y * math.sin(2 * r(L0)) - 2 * ec * math.sin(r(M))
                           + 4 * ec * y * math.sin(r(M)) * math.cos(2 * r(L0))
                           - .5 * y * y * math.sin(4 * r(L0)) - 1.25 * ec * ec * math.sin(2 * r(M)))
    mins = utc.hour * 60 + utc.minute + utc.second / 60
    ha = ((mins + eot + 4 * lon) % 1440) / 4 - 180
    la = r(lat)
    cz = math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(r(ha))
    el = 90 - math.degrees(math.acos(max(-1, min(1, cz))))
    az = (math.degrees(math.atan2(math.sin(r(ha)), math.cos(r(ha)) * math.sin(la) - math.tan(dec) * math.cos(la))) + 180) % 360
    if el > -1:   # refracao aproximada perto do horizonte
        el += 1.02 / math.tan(r(el + 10.3 / (el + 5.11))) / 60
    return el, az


# ---------------- cores ----------------
def hx(c):
    c = c.lstrip("#")
    return [int(c[i:i + 2], 16) for i in (0, 2, 4)]


def hexc(v):
    return "#" + "".join(f"{max(0, min(255, round(x))):02x}" for x in v)


def mixc(cols_w):
    acc = [0.0, 0.0, 0.0]
    for c, w in cols_w:
        for i, x in enumerate(hx(c)):
            acc[i] += x * w
    return hexc(acc)


def lerpc(a, b, t):
    return mixc([(a, 1 - t), (b, t)])


def ss(a, b, x):
    """smoothstep de a para b (a pode ser > b)."""
    if a == b:
        return 1.0 if x >= b else 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def keyed(kf, x):
    """interpolacao linear por tramos de uma lista [(x, valor)] (valor = dict de pesos ou tuplo de cores)."""
    if x <= kf[0][0]:
        return kf[0][1]
    for (x0, v0), (x1, v1) in zip(kf, kf[1:]):
        if x <= x1:
            u = (x - x0) / (x1 - x0)
            if isinstance(v0, dict):
                ks = set(v0) | set(v1)
                return {k: v0.get(k, 0) * (1 - u) + v1.get(k, 0) * u for k in ks}
            return tuple(lerpc(a, b, u) for a, b in zip(v0, v1))
    return kf[-1][1]


def blend(pals):
    """pals = [(dict, peso)] com pesos a somar 1."""
    out = {}
    base = pals[0][0]
    for k, v in base.items():
        if isinstance(v, str) and v.startswith("#"):
            out[k] = mixc([(p[k], w) for p, w in pals])
        elif isinstance(v, list):
            out[k] = [mixc([(p[k][i], w) for p, w in pals]) for i in range(len(v))]
        elif isinstance(v, (int, float)):
            out[k] = sum(p[k] * w for p, w in pals)
        else:
            out[k] = v
    return out


# ---------------- extras para easter eggs ----------------
def moon_phase(utc):
    """0 = lua nova, 0.5 = cheia, em [0, 1)."""
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    return ((utc - ref).total_seconds() / 86400.0 / 29.530588853) % 1.0


def top_days(days, n=2):
    """os n dias com mais contribuicoes [(date, count)], do maior para o menor (empate: o mais recente).
    `days` pode ser lista [(date, n)] ou dict {date: n}."""
    items = days.items() if isinstance(days, dict) else days
    return sorted(((d, c) for d, c in items if c > 0), key=lambda x: (-x[1], -x[0].toordinal()))[:n]


def events(local_dt, days=None):
    """Conjunto de etiquetas de datas especiais (hora local). Cada cena decide o que fazer com elas.
    Com `days`, junta "dia_do_pico" no dia/mes do dia com mais contribuicoes dos dados (calculado, nao fixo)."""
    d, m, h, wd = local_dt.day, local_dt.month, local_dt.hour, local_dt.weekday()
    ev = set()
    if m == 12 and d >= 1 or (m == 1 and d <= 6):
        ev.add("natal")                      # luzes de natal, 1/12 a 6/1
    if (m == 12 and d == 31 and h >= 23) or (m == 1 and d == 1 and h < 1):
        ev.add("ano_novo")                   # fogo de artificio a volta da meia-noite
    if m == 10 and d == 31 or (m == 11 and d == 1 and h < 3):
        ev.add("halloween")
    if m == 10 and d == 24:
        ev.add("aniversario_conta")          # conta GitHub criada a 24/10/2025
    if m == 4 and d == 1:
        ev.add("1_abril")
    if wd == 4 and h >= 17:
        ev.add("sexta_tarde")                # "nao se faz deploy a sexta"
    if 2 <= h < 5:
        ev.add("madrugada")
    pk = top_days(days, 1) if days else []
    if pk and (pk[0][0].month, pk[0][0].day) == (m, d):
        ev.add("dia_do_pico")                # aniversario (dia/mes) do dia com mais contribuicoes
    return ev
