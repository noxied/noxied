"""Servidor minimo da cena (so stdlib). Fica atras do Cloudflare Tunnel; quem o chama e o Worker.

GET /room.svg   SVG da cena na hora atual de Lisboa (exige X-Origin-Key == ORIGIN_KEY, se definida)
                 ?room=sala|secretaria forca a cena (para testes)
GET /health      200 "ok" (sem segredos nem dados)

Variaveis de ambiente:
  ORIGIN_KEY        segredo partilhado com o Worker (vazio = sem verificacao, so para testes locais)
  DATA_URL          contrib.json publicado pela Action (omissao: ramo output do repo do perfil)
  DATA_REFRESH_S    intervalo entre buscas dos dados (omissao 1800)
  DATA_CACHE        ficheiro onde guardar a ultima copia boa (omissao /tmp/contrib.json)
  HOST, PORT        omissao 0.0.0.0:8080
"""
import gzip
import hmac
import json
import logging
import os
import sys
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from room import ROOMS, lisbon_now, load_contrib, parse_contrib, render_room, room_for  # noqa: E402

ORIGIN_KEY = os.environ.get("ORIGIN_KEY", "")
DATA_URL = os.environ.get("DATA_URL", "https://raw.githubusercontent.com/noxied/noxied/output/contrib.json")
DATA_REFRESH_S = int(os.environ.get("DATA_REFRESH_S", "1800"))
DATA_CACHE = Path(os.environ.get("DATA_CACHE", "/tmp/contrib.json"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
NO_CACHE = "no-cache, no-store, max-age=0, must-revalidate"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
log = logging.getLogger("room")
logging.getLogger("fontTools").setLevel(logging.WARNING)


# ------------------------------------------------------------------ dados
class Data:
    """ultima copia boa das contribuicoes: remota -> ficheiro de cache -> embutida."""

    def __init__(self):
        self.lock = threading.Lock()
        self.days, self.source, self.version = None, "", 0
        try:
            self._set(load_contrib(DATA_CACHE), "cache")
        except Exception:
            self._set(load_contrib(), "embedded")

    def _set(self, days, source):
        with self.lock:
            self.days, self.source, self.version, self.loaded_at = days, source, self.version + 1, time.time()
        log.info("dados: %s (%d dias, ultimo %s)", source, len(days), days[-1][0])

    def get(self):
        with self.lock:
            return self.days, self.version

    def refresh(self):
        try:
            req = urllib.request.Request(DATA_URL, headers={"User-Agent": "room", "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read(5_000_000)
            days = parse_contrib(json.loads(raw))
        except Exception as e:  # rede, 404 antes do primeiro run da Action, JSON estragado...
            log.warning("dados: falhou a busca (%s); mantenho %s", e.__class__.__name__, self.source)
            return False
        if days != self.get()[0]:
            self._set(days, "remote")
            try:
                tmp = DATA_CACHE.with_suffix(".tmp")
                tmp.write_bytes(raw)
                tmp.replace(DATA_CACHE)
            except OSError as e:
                log.warning("dados: nao consegui guardar a cache (%s)", e)
        return True

    def loop(self):
        while True:
            self.refresh()
            time.sleep(DATA_REFRESH_S)


# ------------------------------------------------------------------ render com cache por minuto
class Renders:
    def __init__(self, data):
        self.data = data
        self.lock = threading.Lock()
        self.cache = {}          # (minuto, cena, versao dos dados) -> (svg, svg_gzip)

    def get(self, room=None):
        now = lisbon_now().replace(second=0, microsecond=0)
        days, ver = self.data.get()
        room = room or room_for(now.date())
        key = (now.isoformat(timespec="minutes"), room, ver)
        hit = self.cache.get(key)
        if hit:
            return hit, True, key
        with self.lock:                     # um render de cada vez (evita a manada no virar do minuto)
            hit = self.cache.get(key)
            if hit:
                return hit, True, key
            svg = render_room(now, days, mode="live", room=room).encode("utf-8")
            hit = (svg, gzip.compress(svg, 6))
            self.cache = {k: v for k, v in self.cache.items() if k[0] >= (now - timedelta(minutes=1)).isoformat(timespec="minutes")}
            self.cache[key] = hit
            return hit, False, key

    def warm_loop(self):
        """renderiza a cena logo no inicio de cada minuto, para os pedidos encontrarem sempre a cache quente."""
        while True:
            try:
                t0 = time.time()
                _, cached, key = self.get()
                if not cached:
                    log.info("render %s %s em %.0f ms", key[1], key[0], (time.time() - t0) * 1000)
            except Exception:
                log.exception("render falhou")
            time.sleep(60.5 - (time.time() % 60))


# ------------------------------------------------------------------ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "room"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):      # sem IPs nos logs; o pedido e registado em _send
        pass

    def _send(self, status, body, ctype, extra=None, note=""):
        t0 = getattr(self, "_t0", time.time())
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", NO_CACHE)
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        log.info("%s %s %d %dB %.0fms %s", self.command, urlsplit(self.path).path, status, len(body),
                 (time.time() - t0) * 1000, note)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        self._t0 = time.time()
        u = urlsplit(self.path)
        if u.path == "/health":
            return self._send(200, b"ok\n", "text/plain; charset=utf-8")
        if u.path != "/room.svg":
            return self._send(404, b"not found\n", "text/plain; charset=utf-8")
        if ORIGIN_KEY and not hmac.compare_digest(self.headers.get("X-Origin-Key", "").encode(), ORIGIN_KEY.encode()):
            return self._send(403, b"forbidden\n", "text/plain; charset=utf-8", note="chave invalida")
        room = (parse_qs(u.query).get("room") or [None])[0]
        if room is not None and room not in ROOMS:
            return self._send(400, b"bad room\n", "text/plain; charset=utf-8")
        try:
            (svg, svgz), cached, key = RENDERS.get(room)
        except Exception:
            log.exception("render falhou")
            return self._send(500, b"render error\n", "text/plain; charset=utf-8")
        extra = {"X-Room": f"{key[1]} {key[0]}", "Vary": "Accept-Encoding"}
        body = svg
        if "gzip" in self.headers.get("Accept-Encoding", ""):
            body, extra["Content-Encoding"] = svgz, "gzip"
        self._send(200, body, "image/svg+xml; charset=utf-8", extra, note=("cache" if cached else "render") + f" {key[1]}")


DATA = Data()
RENDERS = Renders(DATA)


def main():
    if not ORIGIN_KEY:
        log.warning("ORIGIN_KEY vazia: /room.svg aberto a qualquer pedido (so para testes locais)")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    srv.daemon_threads = True
    threading.Thread(target=DATA.loop, daemon=True, name="data").start()
    threading.Thread(target=RENDERS.warm_loop, daemon=True, name="warm").start()
    log.info("a ouvir em %s:%d (cena de hoje: %s)", HOST, PORT, room_for(lisbon_now().date()))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
