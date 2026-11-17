"""Local HTTP service for the central runbook.

Serves one page and a small JSON API on 127.0.0.1. It is the boundary between any web
page in the user's browser and a file agents act on, so every request is checked for
Host (DNS rebinding), and every write for Origin and the per-install token (CSRF).
Stdlib only.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

import rblib
import runbook

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DEFAULT_PORT = 8765
MAX_BODY = 1024 * 1024
DRAIN_LIMIT = 16 * 1024 * 1024
SWEEP_EVERY_S = 60.0
SWEEP_TAG = "found-by-sweep"
ITEM_PATH = re.compile(r"/api/items/([^/]+)")
DISMISS_PATH = re.compile(r"/api/items/([^/]+)/dismiss")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class HttpError(Exception):
    def __init__(self, status: int, error: str):
        super().__init__(error)
        self.status = status
        self.error = error


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _bump(state: dict) -> None:
    """Mark an owner write so the processor can tell it landed mid-run."""
    state["owner_rev"] = state.get("owner_rev", 0) + 1


def _find(state: dict, item_id: str) -> dict:
    for it in state["items"]:
        if it.get("id") == item_id:
            return it
    raise HttpError(404, "unknown item")


def _validate_fields(fields) -> dict:
    if not isinstance(fields, dict) or not fields:
        raise HttpError(400, "fields must be a non-empty object")
    bad = sorted(set(fields) - rblib.OWNER_ITEM_FIELDS)
    if bad:
        raise HttpError(400, "fields not editable: " + ", ".join(bad))
    if "state" in fields and fields["state"] not in rblib.ITEM_STATES:
        raise HttpError(400, "state must be one of " + ", ".join(rblib.ITEM_STATES))
    for k in ("output", "other"):
        if k in fields and not isinstance(fields[k], str):
            raise HttpError(400, f"{k} must be a string")
    if "chosen" in fields and fields["chosen"] is not None and not isinstance(fields["chosen"], str):
        raise HttpError(400, "chosen must be a string or null")
    return fields


def _version(body: dict) -> int:
    v = body.get("version")
    if isinstance(v, bool) or not isinstance(v, int):
        raise HttpError(400, "version must be an integer")
    return v


def _text(body: dict) -> str:
    t = body.get("text")
    if not isinstance(t, str):
        raise HttpError(400, "text must be a string")
    return t


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # one request per connection; no leftover body to desync on
    server_version = "runbook"

    # ---- plumbing
    def log_message(self, fmt, *args):  # request log off; errors go through log()
        pass

    def _send(self, status: int, payload, ctype: str = "application/json", extra: dict | None = None):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _check_host(self):
        if self.headers.get("Host", "") not in self.server.allowed_hosts:
            raise HttpError(403, "bad host")

    def _check_write(self):
        origin = self.headers.get("Origin")
        if origin is not None and origin not in self.server.allowed_origins:
            raise HttpError(403, "bad origin")
        sent = self.headers.get("X-Runbook-Token", "")
        if not hmac.compare_digest(sent.encode("utf-8"), self.server.token.encode("utf-8")):
            raise HttpError(403, "bad token")

    def _body(self) -> dict:
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise HttpError(400, "Content-Type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise HttpError(400, "bad Content-Length") from None
        if length < 0:
            raise HttpError(400, "bad Content-Length")
        if length > MAX_BODY:
            left = length if length <= DRAIN_LIMIT else 0  # let the client finish sending
            while left > 0:
                chunk = self.rfile.read(min(65536, left))
                if not chunk:
                    break
                left -= len(chunk)
            raise HttpError(413, "body too large")
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            raise HttpError(400, "invalid JSON") from None
        if not isinstance(body, dict):
            raise HttpError(400, "body must be an object")
        return body

    def _dispatch(self, method: str):
        try:
            self._check_host()
            path = self.path.split("?", 1)[0]
            if method == "GET":
                self._get(path)
            else:
                self._check_write()
                self._write(method, path)
        except HttpError as e:
            self._send(e.status, {"error": e.error})
        except rblib.StaleVersion:
            self._send(409, {"error": "stale"})
        except rblib.CorruptState:
            self._send(503, {"error": "corrupt"})
        except rblib.LockTimeout:
            self._send(503, {"error": "busy"})
        except Exception:  # never leak a trace to the client
            log(traceback.format_exc())
            self._send(500, {"error": "internal"})

    do_GET = lambda self: self._dispatch("GET")  # noqa: E731
    do_POST = lambda self: self._dispatch("POST")  # noqa: E731
    do_PUT = lambda self: self._dispatch("PUT")  # noqa: E731
    do_PATCH = lambda self: self._dispatch("PATCH")  # noqa: E731
    do_DELETE = lambda self: self._dispatch("DELETE")  # noqa: E731

    # ---- routes
    def _get(self, path: str):
        if path == "/":
            try:
                html = (STATIC / "index.html").read_text(encoding="utf-8")
            except OSError:
                raise HttpError(404, "page missing") from None
            self._send(200, html.replace("{{TOKEN}}", self.server.token).encode("utf-8"),
                       "text/html; charset=utf-8")
        elif path == "/api/state":
            self._send(200, rblib.load(self.server.state_path))
        else:
            raise HttpError(404, "not found")

    def _write(self, method: str, path: str):
        sp = self.server.state_path
        if method == "POST" and path == "/api/submit":
            self._body()
            self.server.spawn("submit")
            return self._send(202, {"ok": True})
        m = DISMISS_PATH.fullmatch(path)
        if method == "POST" and m:
            body = self._body()
            return self._dismiss(sp, m.group(1), _version(body))
        m = ITEM_PATH.fullmatch(path)
        if method == "PATCH" and m:
            body = self._body()
            return self._patch(sp, m.group(1), _version(body), _validate_fields(body.get("fields")))
        if method == "PUT" and path == "/api/notes_self":
            body = self._body()
            v, text = _version(body), _text(body)

            text, kinds = rblib.redact(text)

            def fn(state):
                state["notes_self"] = text
                _bump(state)
                return state
            return self._send(200, {"state": rblib.mutate(fn, sp, v), "redacted": kinds})
        if method == "POST" and path == "/api/notes_claude":
            body = self._body()
            v, text = _version(body), _text(body)

            text, kinds = rblib.redact(text)

            def fn(state):
                state["notes_claude"].append({
                    "id": rblib.next_note_id(state), "text": text,
                    "at": _now().isoformat(timespec="seconds"), "status": "new", "reply": "",
                })
                _bump(state)
                return state
            return self._send(200, {"state": rblib.mutate(fn, sp, v), "redacted": kinds})
        raise HttpError(404, "not found")

    def _patch(self, sp: Path, item_id: str, version: int, fields: dict):
        fields = dict(fields)
        kinds: list[str] = []
        for k in ("output", "other"):
            if k in fields:
                fields[k], found = rblib.redact(fields[k])
                kinds += [x for x in found if x not in kinds]

        def fn(state):
            it = _find(state, item_id)
            if it.get("state") == "done" and fields.get("state") not in ("open", "problem"):
                raise HttpError(423, "item is done; reopen it first")
            it.update(fields)
            _bump(state)
            return state

        self._send(200, {"state": rblib.mutate(fn, sp, version), "redacted": kinds})

    def _dismiss(self, sp: Path, item_id: str, version: int):
        def fn(state):
            it = _find(state, item_id)
            if SWEEP_TAG not in (it.get("tags") or []):
                raise HttpError(400, "only items found by a sweep can be dismissed")
            rblib.move_to_done_log(state, item_id, "dismissed by the owner", "owner", _now())
            _bump(state)
            return state

        self._send(200, {"state": rblib.mutate(fn, sp, version)})


# ---------------------------------------------------------------- inbox sweep

_TEXT_KEYS = ("why", "kind", "verify", "rollback", "source", "agent_note", "added_by", "added")
_STEP_KEYS = ("shell", "cmd", "expect", "prompts")


def _strings(value):
    """Every string anywhere inside value (dict values, list items, nested)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _str_list(item: dict, key: str) -> None:
    v = item.get(key, [])
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ValueError(f"{key} must be a list of strings")


def _check_inbox_item(item) -> dict:
    """Same bar as `runbook add`, because any local process can drop an inbox file."""
    if not isinstance(item, dict):
        raise ValueError("inbox item is not an object")
    # The owner's fields (state, output, chosen, other) and the id are never taken from a file.
    item = {k: v for k, v in item.items() if k not in rblib.OWNER_ITEM_FIELDS and k != "id"}
    for k in ("repo", "title"):
        if not isinstance(item.get(k), str) or not item[k].strip():
            raise ValueError(f"{k} must be a non-empty string")
    for k in _TEXT_KEYS:
        if k in item and not isinstance(item[k], str):
            raise ValueError(f"{k} must be a string")
    _str_list(item, "after")
    _str_list(item, "tags")
    if "priority" in item and item["priority"] not in runbook.PRIORITIES:
        raise ValueError("priority must be one of " + ", ".join(runbook.PRIORITIES))
    if item.get("due") is not None and not runbook.is_iso_date(item["due"]):
        raise ValueError("due must be YYYY-MM-DD or null")
    steps = item.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("steps must be a list of objects")
    for s in steps:
        if not isinstance(s, dict):
            raise ValueError("steps must be a list of objects")
        if not isinstance(s.get("shell"), str) or not isinstance(s.get("cmd"), str):
            raise ValueError("each step needs string shell and cmd")
        if any(k in s and not isinstance(s[k], str) for k in _STEP_KEYS):
            raise ValueError("step shell, cmd, expect and prompts must be strings")
    dec = item.get("decision")
    if dec is not None:
        if not isinstance(dec, dict) or not isinstance(dec.get("options", []), list):
            raise ValueError("decision must be an object with a list of options")
        # The answer lives only at item top level, and only the owner writes it.
        dec = {k: v for k, v in dec.items() if k not in ("chosen", "other")}
        item["decision"] = dec
        for o in dec.get("options", []):
            if not isinstance(o, dict) or not isinstance(o.get("label"), str):
                raise ValueError("decision options must be objects with a string label")
            if not isinstance(o.get("detail", ""), str):
                raise ValueError("decision option detail must be a string")
            if not isinstance(o.get("recommended", False), bool):
                raise ValueError("decision option recommended must be a boolean")
    problems = []
    for t in _strings(item):
        problems += [f"secret:{k}" for k in rblib.find_secrets(t)]
        problems += [f"placeholder:{p}" for p in rblib.find_placeholders(t)]
    if problems:
        raise ValueError("refused: " + ", ".join(dict.fromkeys(problems)))
    return item


def _quarantine(path: Path) -> None:
    try:
        os.replace(path, path.with_name(path.name + ".bad"))
    except OSError as e:
        log(f"sweep: cannot rename {path}: {e}")


def sweep_inboxes(state_path: Path, roots: list[Path]) -> int:
    files: list[Path] = []
    for root in roots:
        root = Path(root)
        files += sorted(root.glob("*/.runbook/inbox/*.json"))
        files += sorted(root.glob("*/*/.runbook/inbox/*.json"))
    merged = 0
    for path in files:
        try:
            try:
                item = _check_inbox_item(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, UnicodeDecodeError) as e:  # JSONDecodeError is a ValueError
                log(f"sweep: {path}: {e}")
                _quarantine(path)
                continue
            rblib.mutate(lambda st, it=item: runbook.merge_inbox(st, it), state_path)
            path.unlink()
            merged += 1
        except Exception as e:  # one bad file must not stop the rest
            log(f"sweep: {path}: {type(e).__name__}: {e}")
    return merged


# ---------------------------------------------------------------- server

class _Server(ThreadingHTTPServer):
    # HTTPServer defaults to SO_REUSEADDR, which on Windows lets a second socket bind the
    # same port and hijack the page's token and writes.
    allow_reuse_address = False

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_server(port: int, state_path: Path, token: str, inbox_roots: list[Path],
                spawn: Callable[[str], None]) -> ThreadingHTTPServer:
    srv = _Server(("127.0.0.1", port), Handler)
    bound = srv.server_address[1]
    srv.state_path = Path(state_path)
    srv.token = token
    srv.inbox_roots = list(inbox_roots)
    srv.spawn = spawn
    srv.allowed_hosts = {f"127.0.0.1:{bound}", f"localhost:{bound}"}
    srv.allowed_origins = {f"http://127.0.0.1:{bound}", f"http://localhost:{bound}"}
    return srv


def default_spawn(reason: str) -> None:
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe") if exe.name.lower() == "python.exe" else exe
    py = str(pyw if pyw.exists() else exe)
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [py, str(ROOT / "process.py"), "--reason", reason],
        creationflags=flags, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, close_fds=True,
    )


def _read_token(path: Path) -> str:
    try:
        tok = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        tok = ""
    if not tok:
        tok = secrets.token_urlsafe(32)
        path.write_text(tok + "\n", encoding="utf-8")
    return tok


def _sweep_loop(state_path: Path, roots: list[Path], stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            n = sweep_inboxes(state_path, roots)
            if n:
                log(f"sweep: merged {n} inbox item(s)")
        except Exception:
            log("sweep failed, traceback follows\n" + traceback.format_exc())
        stop.wait(SWEEP_EVERY_S)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="server")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--state", type=Path, default=rblib.STATE)
    args = ap.parse_args(argv)
    roots = [rblib.projects_root()]
    srv = make_server(args.port, args.state, _read_token(ROOT / ".token"), roots, default_spawn)
    stop = threading.Event()
    threading.Thread(target=_sweep_loop, args=(args.state, roots, stop), daemon=True).start()
    log(f"runbook listening on http://127.0.0.1:{srv.server_address[1]}/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
