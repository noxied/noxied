"""CLI: gera um SVG da cena.

  python -m room --data contrib.json --out fallback.svg --mode fallback
  python -m room --out agora.svg                      (dados embutidos, hora atual de Lisboa, modo live)
  python -m room --at 2026-10-01T21:30 --room sala --out x.svg
"""
import argparse
import time
from datetime import datetime
from pathlib import Path

from . import EMBEDDED, ROOMS, lisbon_now, load_contrib, render_room, room_for


def main():
    ap = argparse.ArgumentParser(prog="python -m room")
    ap.add_argument("--data", default=str(EMBEDDED), help="contrib.json (resposta GraphQL)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=("live", "fallback"), default="live")
    ap.add_argument("--at", help="hora local de Lisboa, ex. 2026-10-01T21:30 (omissao: agora)")
    ap.add_argument("--room", choices=ROOMS, help="omissao: cena do dia")
    a = ap.parse_args()
    now = datetime.fromisoformat(a.at) if a.at else lisbon_now()
    t0 = time.time()
    days = load_contrib(a.data)
    svg = render_room(now, days, mode=a.mode, room=a.room)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"{now:%Y-%m-%d %H:%M} Lisboa | {a.room or room_for(now.date())} | {a.mode} | "
          f"{len(svg) / 1024:.0f} KB | {time.time() - t0:.2f}s")


if __name__ == "__main__":
    main()
