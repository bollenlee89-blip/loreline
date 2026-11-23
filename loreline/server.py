"""Tiny local web UI: browse files, click any line, see why it exists."""
from __future__ import annotations

import json
import os
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from . import __version__, gitutil
from .explain import Explainer

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
MAX_FILE = 1_500_000


def make_handler(repo):
    explainer = Explainer(repo)
    lock = threading.Lock()
    tracked = {"files": None}

    def files() -> list[str]:
        if tracked["files"] is None:
            tracked["files"] = gitutil.ls_files(repo.root)
        return tracked["files"]

    class Handler(BaseHTTPRequestHandler):
        server_version = f"loreline/{__version__}"

        def log_message(self, fmt, *args):  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode(), "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802
            # Only answer requests addressed to localhost (DNS-rebinding guard).
            host = (self.headers.get("Host") or "").split(":")[0]
            if host not in ("127.0.0.1", "localhost", "[::1]", "::1"):
                return self._json({"error": "forbidden host"}, 403)
            url = urllib.parse.urlparse(self.path)
            q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            try:
                with lock:
                    return self.route(url.path, q)
            except gitutil.GitError as exc:
                return self._json({"error": str(exc)}, 400)
            except Exception as exc:  # noqa: BLE001
                return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)

        def route(self, path: str, q: dict):
            if path in ("/", "/index.html"):
                with open(os.path.join(WEB_DIR, "index.html"), "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            if path == "/api/info":
                return self._json({"name": os.path.basename(repo.root), "version": __version__,
                                   "llm": f"{repo.llm.name}/{repo.llm.model}" if repo.llm.available() else None,
                                   "stats": repo.store.stats()})
            if path == "/api/files":
                return self._json(files())
            if path == "/api/file":
                p = q.get("path", "")
                if p not in set(files()):
                    return self._json({"error": "not a tracked file"}, 404)
                full = os.path.join(repo.root, p)
                if os.path.getsize(full) > MAX_FILE:
                    return self._json({"error": "file too large to display"}, 413)
                with open(full, "rb") as fh:
                    raw = fh.read()
                if b"\x00" in raw[:8000]:
                    return self._json({"error": "binary file"}, 415)
                return self._json({"path": p, "lines": raw.decode("utf-8", "replace").splitlines()})
            if path == "/api/why":
                p = q.get("path", "")
                if p not in set(files()):
                    return self._json({"error": "not a tracked file"}, 404)
                line = int(q["line"]) if q.get("line") else None
                ev = explainer.why(p, line)
                narrative = explainer.narrate(ev) if q.get("llm", "1") == "1" else None
                return self._json({"evidence": ev, "narrative": narrative})
            if path == "/api/ask":
                return self._json(explainer.ask(q.get("q", "")))
            if path == "/api/map":
                return self._json(explainer.build_map(use_llm=q.get("llm") == "1", limit=int(q.get("limit", 0)) or None))
            return self._json({"error": "not found"}, 404)

    return Handler


def serve(repo, host: str = "127.0.0.1", port: int = 7777, open_browser: bool = True) -> None:  # pragma: no cover
    httpd = HTTPServer((host, port), make_handler(repo))
    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{httpd.server_port}/"
    print(f"loreline UI → {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
