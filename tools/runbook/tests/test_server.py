import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rblib  # noqa: E402
import runbook  # noqa: E402
import server  # noqa: E402
from tests.fakes import FAKE_AWS  # noqa: E402

TOKEN = "t0ken-for-tests"


def item(**kw):
    base = {"repo": "r", "title": "t", "why": "w", "steps": [
        {"shell": "wsl", "cmd": "echo hi", "expect": "hi", "prompts": ""}], "verify": "v"}
    base.update(kw)
    return base


class ServerCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.state = self.dir / "runbook.json"
        self.spawned = []
        self.logged = []
        p = mock.patch.object(server, "log", self.logged.append)
        p.start()
        self.addCleanup(p.stop)
        self.srv = server.make_server(0, self.state, TOKEN, [self.dir], self.spawned.append)
        self.port = self.srv.server_address[1]
        t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        t.start()
        self.addCleanup(t.join, 5)
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def seed(self, *items):
        def fn(st):
            return [runbook.merge_inbox(st, it) for it in items]
        return rblib.mutate(fn, self.state)

    def req(self, method, path, body=None, host=None, token=TOKEN, headers=None, raw=None,
            ctype="application/json"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if token:
            h["X-Runbook-Token"] = token
        if body is not None or raw is not None:
            h["Content-Type"] = ctype
        h.update(headers or {})
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        payload = r.read()
        c.close()
        try:
            return r.status, json.loads(payload), r
        except ValueError:
            return r.status, payload, r

    def version(self):
        return rblib.load(self.state)["version"]


class TestServer(ServerCase):
    def test_get_page_injects_token(self):
        s, body, _ = self.req("GET", "/", token=None)
        self.assertEqual(s, 200)
        self.assertIn(TOKEN.encode(), body)
        self.assertNotIn(b"{{TOKEN}}", body)

    def test_bad_host_403(self):
        self.assertEqual(self.req("GET", "/", host="evil.example:8765", token=None)[0], 403)
        self.assertEqual(self.req("GET", "/api/state", host="evil.example:8765")[0], 403)
        self.seed(item())
        s, _, _ = self.req("PATCH", "/api/items/rb-0001",
                           {"version": self.version(), "fields": {"output": "x"}}, host="evil.example:8765")
        self.assertEqual(s, 403)

    def test_localhost_host_allowed(self):
        self.assertEqual(self.req("GET", "/api/state", host=f"localhost:{self.port}")[0], 200)

    def test_foreign_origin_403(self):
        self.seed(item())
        v = self.version()
        body = {"version": v, "fields": {"output": "x"}}
        s, _, _ = self.req("PATCH", "/api/items/rb-0001", body, headers={"Origin": "http://evil.example"})
        self.assertEqual(s, 403)
        self.assertEqual(self.version(), v)
        s, _, _ = self.req("PATCH", "/api/items/rb-0001", body,
                           headers={"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(s, 200)

    def test_write_without_token_403(self):
        self.seed(item())
        v = self.version()
        for tok in (None, "wrong"):
            s, _, _ = self.req("PATCH", "/api/items/rb-0001",
                               {"version": v, "fields": {"output": "x"}}, token=tok)
            self.assertEqual(s, 403)
        self.assertEqual(self.version(), v)

    def test_patch_owner_field_ok(self):
        self.seed(item())
        v = self.version()
        s, body, _ = self.req("PATCH", "/api/items/rb-0001", {"version": v, "fields": {"state": "done"}})
        self.assertEqual(s, 200)
        self.assertEqual(body["state"]["items"][0]["state"], "done")
        self.assertEqual(self.version(), v + 1)

    def test_patch_agent_field_400(self):
        self.seed(item())
        v = self.version()
        s, _, _ = self.req("PATCH", "/api/items/rb-0001", {"version": v, "fields": {"agent_note": "x"}})
        self.assertEqual(s, 400)
        self.assertEqual(self.version(), v)

    def test_patch_stale_version_409(self):
        self.seed(item())
        s, _, _ = self.req("PATCH", "/api/items/rb-0001",
                           {"version": self.version() - 1, "fields": {"output": "x"}})
        self.assertEqual(s, 409)

    def test_patch_unknown_id_404(self):
        self.seed(item())
        s, _, _ = self.req("PATCH", "/api/items/rb-9999",
                           {"version": self.version(), "fields": {"output": "x"}})
        self.assertEqual(s, 404)

    def test_patch_field_validation_400(self):
        self.seed(item())
        for fields in ({"state": "bogus"}, {"output": 5}, {"other": None}, {"chosen": 3}):
            s, _, _ = self.req("PATCH", "/api/items/rb-0001", {"version": self.version(), "fields": fields})
            self.assertEqual(s, 400, fields)
        s, _, _ = self.req("PATCH", "/api/items/rb-0001",
                           {"version": self.version(), "fields": {"chosen": None}})
        self.assertEqual(s, 200)

    def test_done_item_locked_423(self):
        self.seed(item())
        self.req("PATCH", "/api/items/rb-0001", {"version": self.version(), "fields": {"state": "done"}})
        s, _, _ = self.req("PATCH", "/api/items/rb-0001",
                           {"version": self.version(), "fields": {"output": "x"}})
        self.assertEqual(s, 423)
        s, _, _ = self.req("PATCH", "/api/items/rb-0001",
                           {"version": self.version(), "fields": {"state": "open", "output": "x"}})
        self.assertEqual(s, 200)

    def test_patch_output_redacts_secrets(self):
        self.seed(item())
        s, body, _ = self.req("PATCH", "/api/items/rb-0001",
                              {"version": self.version(), "fields": {"output": f"key {FAKE_AWS}"}})
        self.assertEqual(s, 200)
        self.assertEqual(body["redacted"], ["aws-access-key"])
        stored = rblib.load(self.state)["items"][0]["output"]
        self.assertEqual(stored, "key [REDACTED:aws-access-key]")

    def test_dismiss_only_sweep_items(self):
        self.seed(item(title="a"), item(title="b", tags=["found-by-sweep"]))
        s, _, _ = self.req("POST", "/api/items/rb-0001/dismiss", {"version": self.version()})
        self.assertEqual(s, 400)
        s, _, _ = self.req("POST", "/api/items/rb-0002/dismiss", {"version": self.version()})
        self.assertEqual(s, 200)
        st = rblib.load(self.state)
        self.assertEqual([i["id"] for i in st["done_log"]], ["rb-0002"])
        self.assertEqual(st["done_log"][0]["reason"], "dismissed by the owner")

    def test_notes_endpoints(self):
        s, _, _ = self.req("PUT", "/api/notes_self", {"version": self.version(), "text": "mine"})
        self.assertEqual(s, 200)
        s, _, _ = self.req("POST", "/api/notes_claude", {"version": self.version(), "text": "hello"})
        self.assertEqual(s, 200)
        st = rblib.load(self.state)
        self.assertEqual(st["notes_self"], "mine")
        n = st["notes_claude"][0]
        self.assertEqual((n["id"], n["text"], n["status"], n["reply"]), ("n-1", "hello", "new", ""))
        self.assertTrue(n["at"])

    def test_every_write_bumps_owner_rev(self):
        self.seed(item(title="a"), item(title="b", tags=["found-by-sweep"]))
        rev = lambda: rblib.load(self.state).get("owner_rev", 0)  # noqa: E731
        self.assertEqual(rev(), 0)
        calls = [
            ("PATCH", "/api/items/rb-0001", {"fields": {"output": "x"}}),
            ("POST", "/api/items/rb-0002/dismiss", {}),
            ("PUT", "/api/notes_self", {"text": "n"}),
            ("POST", "/api/notes_claude", {"text": "hi"}),
        ]
        for i, (m, p, b) in enumerate(calls, 1):
            s, _, _ = self.req(m, p, dict(b, version=self.version()))
            self.assertEqual(s, 200, p)
            self.assertEqual(rev(), i, p)

    def test_submit_spawns(self):
        s, _, _ = self.req("POST", "/api/submit", {})
        self.assertEqual(s, 202)
        self.assertEqual(self.spawned, ["submit"])

    def test_corrupt_state_503(self):
        self.state.write_text("{", encoding="utf-8")
        s, body, _ = self.req("GET", "/api/state")
        self.assertEqual(s, 503)
        self.assertEqual(body, {"error": "corrupt"})
        self.assertEqual(self.state.read_text(encoding="utf-8"), "{")

    def test_state_no_store(self):
        s, _, r = self.req("GET", "/api/state")
        self.assertEqual(s, 200)
        self.assertEqual(r.getheader("Cache-Control"), "no-store")

    def test_body_rules(self):
        self.seed(item())
        v = self.version()
        path = "/api/items/rb-0001"
        self.assertEqual(self.req("PATCH", path, raw=b"{nope")[0], 400)
        self.assertEqual(self.req("PATCH", path, {"version": v, "fields": {"output": "x"}},
                                  ctype="text/plain")[0], 400)
        self.assertEqual(self.req("PUT", "/api/notes_self", raw=b"x" * (1024 * 1024 + 1))[0], 413)
        self.assertEqual(self.version(), v)

    def test_second_bind_on_same_port_refused(self):
        with self.assertRaises(OSError):
            other = server.make_server(self.port, self.dir / "o.json", TOKEN, [], lambda r: None)
            other.server_close()

    def test_notes_redact_secrets(self):
        s, body, _ = self.req("PUT", "/api/notes_self", {"version": self.version(), "text": f"k {FAKE_AWS}"})
        self.assertEqual(s, 200)
        self.assertEqual(body["redacted"], ["aws-access-key"])
        s, body, _ = self.req("POST", "/api/notes_claude", {"version": self.version(), "text": f"k {FAKE_AWS}"})
        self.assertEqual(s, 200)
        self.assertEqual(body["redacted"], ["aws-access-key"])
        st = rblib.load(self.state)
        self.assertEqual(st["notes_self"], "k [REDACTED:aws-access-key]")
        self.assertEqual(st["notes_claude"][0]["text"], "k [REDACTED:aws-access-key]")
        self.assertNotIn("AKIA", self.state.read_text(encoding="utf-8"))

    def test_unknown_route_404(self):
        self.assertEqual(self.req("GET", "/nope")[0], 404)


class TestSweep(ServerCase):
    def drop(self, repo, name, content):
        d = self.dir / repo / ".runbook" / "inbox"
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return p

    def test_sweep_inboxes(self):
        a = self.drop("repoA", "1.json", item(title="one"))
        b = self.drop("repoA", "2.json", item(title="two"))
        bad = self.drop("repoA", "3.json", "{")
        self.assertEqual(server.sweep_inboxes(self.state, [self.dir]), 2)
        self.assertEqual(len(rblib.load(self.state)["items"]), 2)
        self.assertFalse(a.exists() or b.exists() or bad.exists())
        self.assertTrue(bad.with_name("3.json.bad").exists())

    def test_sweep_nested_glob(self):
        self.drop("group/repoB", "1.json", item(title="deep"))
        self.assertEqual(server.sweep_inboxes(self.state, [self.dir]), 1)

    def test_sweep_strips_owner_fields(self):
        self.drop("repoA", "1.json", item(title="x", state="done", output="o", chosen="c", other="z"))
        server.sweep_inboxes(self.state, [self.dir])
        it = rblib.load(self.state)["items"][0]
        self.assertEqual((it["state"], it["output"], it["chosen"], it["other"]), ("open", "", None, ""))

    def test_sweep_rejects_secret(self):
        bad = self.drop("repoA", "1.json", item(verify=f"echo {FAKE_AWS}"))
        self.assertEqual(server.sweep_inboxes(self.state, [self.dir]), 0)
        self.assertEqual(rblib.load(self.state)["items"], [])
        self.assertTrue(bad.with_name("1.json.bad").exists())

    def test_sweep_rejects_placeholder(self):
        bad = self.drop("repoA", "1.json", item(steps=[
            {"shell": "wsl", "cmd": "deploy <target>", "expect": "", "prompts": ""}]))
        self.assertEqual(server.sweep_inboxes(self.state, [self.dir]), 0)
        self.assertEqual(rblib.load(self.state)["items"], [])
        self.assertTrue(bad.with_name("1.json.bad").exists())

    def assert_bad(self, content):
        bad = self.drop("repoA", "1.json", content)
        self.assertEqual(server.sweep_inboxes(self.state, [self.dir]), 0)
        self.assertEqual(rblib.load(self.state)["items"], [])
        self.assertTrue(bad.with_name("1.json.bad").exists())

    def test_sweep_rejects_secret_in_any_string(self):
        cases = {
            "title": item(title=f"t {FAKE_AWS}"),
            "why": item(why=FAKE_AWS),
            "source": item(source=FAKE_AWS),
            "repo": item(repo=FAKE_AWS),
            "tag": item(tags=[FAKE_AWS]),
            "agent_note": item(agent_note=FAKE_AWS),
            "unknown key": item(extra={"deep": [FAKE_AWS]}),
            "step shell": item(steps=[{"shell": FAKE_AWS, "cmd": "c", "expect": "", "prompts": ""}]),
        }
        for name, content in cases.items():
            with self.subTest(name):
                self.assert_bad(content)
                self.clear_inbox()

    def clear_inbox(self):
        for p in (self.dir / "repoA" / ".runbook" / "inbox").glob("*"):
            p.unlink()
        if self.state.exists():
            self.state.unlink()

    def test_sweep_rejects_placeholder_in_title(self):
        self.assert_bad(item(title="fix YOUR_THING"))

    def test_sweep_decision_answer_not_plantable(self):
        self.drop("repoA", "1.json", item(
            title="d", kind="decision", steps=[], verify="",
            decision={"options": [{"label": "A", "detail": "", "recommended": False},
                                  {"label": "B", "detail": "", "recommended": True}],
                      "chosen": "A", "other": "planted"},
            chosen="A", other="planted"))
        self.assertEqual(server.sweep_inboxes(self.state, [self.dir]), 1)
        it = rblib.load(self.state)["items"][0]
        self.assertNotIn("chosen", it["decision"])
        self.assertNotIn("other", it["decision"])
        self.assertIsNone(it["chosen"])
        self.assertEqual(it["other"], "")

    def test_sweep_decision_source_kept(self):
        self.drop("repoA", "1.json", item(
            title="d", kind="decision", steps=[], verify="", source="my-app/Plans/x.md",
            decision={"options": [{"label": "A", "detail": "a", "recommended": False},
                                  {"label": "B", "detail": "b", "recommended": True}]}))
        self.assertEqual(server.sweep_inboxes(self.state, [self.dir]), 1)
        self.assertEqual(rblib.load(self.state)["items"][0]["source"], "my-app/Plans/x.md")

    def test_sweep_type_validation(self):
        opt = {"label": "A", "detail": "", "recommended": False}
        cases = {
            "after string": item(after="rb-1"),
            "after non-str": item(after=[1]),
            "tags string": item(tags="x"),
            "tags non-str": item(tags=[1]),
            "priority": item(priority="whenever"),
            "due format": item(due="12/01/2026"),
            "due type": item(due=20261201),
            "step not object": item(steps=["echo"]),
            "step cmd type": item(steps=[{"shell": "wsl", "cmd": 5, "expect": "", "prompts": ""}]),
            "step expect type": item(steps=[{"shell": "wsl", "cmd": "c", "expect": None, "prompts": ""}]),
            "step no shell": item(steps=[{"cmd": "c"}]),
            "options not list": item(decision={"options": "A"}),
            "option not object": item(decision={"options": ["A", "B"]}),
            "option label type": item(decision={"options": [dict(opt, label=1), opt]}),
            "option detail type": item(decision={"options": [dict(opt, detail=[]), opt]}),
            "option recommended type": item(decision={"options": [dict(opt, recommended="yes"), opt]}),
            "why type": item(why=["w"]),
        }
        for name, content in cases.items():
            with self.subTest(name):
                self.assert_bad(content)
                self.clear_inbox()

    def test_sweep_accepts_valid_optionals(self):
        self.drop("repoA", "1.json", item(after=["rb-0001"], tags=["a"], priority="urgent",
                                          due="2026-12-01"))
        self.drop("repoA", "2.json", item(title="t2", due=None))
        self.assertEqual(server.sweep_inboxes(self.state, [self.dir]), 2)

    def test_sweep_accepts_cli_fallback_payload(self):
        args = runbook._parser().parse_args([
            "add", "--repo", "my-app", "--title", "T", "--why", "W", "--step", "wsl|echo hi|ok",
            "--verify", "V", "--tag", "a", "--due", "2026-12-01", "--rollback", "undo"])
        self.drop("repoA", "1.json", runbook._build_add(args))
        args = runbook._parser().parse_args([
            "add-decision", "--repo", "my-app", "--title", "D", "--source", "S",
            "--option", "A|a", "--option", "B|b*"])
        self.drop("repoA", "2.json", runbook._build_decision(args))
        self.assertEqual(server.sweep_inboxes(self.state, [self.dir]), 2)

    def test_sweep_loop_survives_exception(self):
        stop = threading.Event()
        calls = []

        def flaky(state_path, roots):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            stop.set()
            return 0

        with mock.patch.object(server, "sweep_inboxes", flaky),                 mock.patch.object(server, "SWEEP_EVERY_S", 0.01):
            server._sweep_loop(self.state, [self.dir], stop)
        self.assertEqual(len(calls), 2)
        self.assertTrue(any("boom" in m for m in self.logged))


if __name__ == "__main__":
    unittest.main()
