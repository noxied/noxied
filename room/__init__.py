"""Cena do perfil: sala de servidores / secretaria, com a luz e o relogio na hora de Lisboa.

API unica:
    render_room(now_local, days, mode="live" | "fallback", room=None) -> str (SVG)

- now_local: datetime "naive" na hora de Europe/Lisbon.
- days: lista [(date, contagem)] por ordem cronologica (ver parse_contrib / load_contrib).
- mode="live": relogio exato (o servidor serve por pedido).
- mode="fallback": imagem publicada pela Action, vista com atraso; o unico ponteiro (24 h, sem minutos nem
  segundos) leva um pequeno avanco para o erro medio ficar perto de zero.
- room: None = cena do dia (dia ordinal par -> sala, impar -> secretaria), ou "sala" / "secretaria".
"""
import json
from datetime import date, datetime
from pathlib import Path

from .clock_common import now_local as lisbon_now  # noqa: F401  (reexportado)

HERE = Path(__file__).parent
EMBEDDED = HERE / "contrib_embedded.json"
ROOMS = ("sala", "secretaria")


def parse_contrib(obj):
    """JSON da query GraphQL (contributionCalendar) -> [(date, contagem)] ordenado."""
    cal = obj["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(date.fromisoformat(d["date"]), int(d["contributionCount"]))
            for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda x: x[0])
    if len(days) < 300:
        raise ValueError(f"contrib.json com poucos dias ({len(days)})")
    return days


def load_contrib(path=EMBEDDED):
    return parse_contrib(json.loads(Path(path).read_text(encoding="utf-8")))


def room_for(day):
    """cena do dia: alterna por dia (ordinal par = sala, impar = secretaria)."""
    return ROOMS[day.toordinal() % 2]


def _weeks(days):
    """semanas como no GitHub (domingo a sabado), a partir da lista de dias."""
    weeks, cur = [], []
    for d, c in days:
        if d.weekday() == 6 and cur:
            weeks.append(cur)
            cur = []
        cur.append((d, c))
    if cur:
        weeks.append(cur)
    return weeks


def render_room(now_local, days, mode="live", room=None):
    if mode not in ("live", "fallback"):
        raise ValueError("mode tem de ser 'live' ou 'fallback'")
    if not isinstance(now_local, datetime):
        raise TypeError("now_local tem de ser datetime")
    now_local = now_local.replace(tzinfo=None, microsecond=0)
    room = room or room_for(now_local.date())
    if room == "sala":
        from . import sala
        return sala.render(days, now_local, mode=mode)
    if room == "secretaria":
        from . import secretaria
        data = ({d: c for d, c in days}, _weeks(days))
        return secretaria.render(data, now_local, mode=mode)[0]
    raise ValueError(f"cena desconhecida: {room}")
