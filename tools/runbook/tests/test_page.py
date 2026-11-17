import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import rblib

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
DEMO = ROOT / "tests" / "fixtures" / "demo.json"


class PageTests(unittest.TestCase):
    def test_page_has_no_innerhtml(self):
        for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML"):
            self.assertNotIn(bad, PAGE)

    def test_page_has_token_placeholder(self):
        self.assertIn('const TOKEN = "{{TOKEN}}"', PAGE)

    def test_page_no_external_assets(self):
        self.assertIsNone(re.search(r"""(?:src|href)\s*=\s*["']?\s*https?://""", PAGE, re.I))

    def test_page_has_dark_theme(self):
        self.assertIn("prefers-color-scheme: dark", PAGE)

    def test_page_guards_unsaved_text_on_unload(self):
        self.assertIn('"beforeunload"', PAGE)
        self.assertIn('"pagehide"', PAGE)
        self.assertIn("keepalive: true", PAGE)

    def test_idempotent_clicks_retry_on_stale(self):
        # Tick, Problem, Back to open and a radio choice resend once after a 409.
        calls = re.findall(r"patchItem\(item\.id, \{ (?:state|chosen): [^}]*\}(, true)?\)", PAGE)
        self.assertGreaterEqual(len(calls), 4)
        self.assertTrue(all(calls), "a state/chosen patch does not retry on stale")
        dismiss = re.search(r'"/dismiss", \{\}(, true)?\)', PAGE)
        self.assertTrue(dismiss and dismiss.group(1), "Dismiss does not retry on stale")
        # Submit is not idempotent, so it never retries.
        self.assertIsNone(re.search(r'"/api/submit", \{[^)]*\}, true\)', PAGE))

    def test_submit_and_ticks_wait_for_every_edit_to_save(self):
        self.assertIn("if (!(await flushAll()))", PAGE)
        # afterFlush is the one caller; every click goes through it.
        self.assertEqual(PAGE.count("flushAll().then("), 1)
        self.assertGreaterEqual(PAGE.count("afterFlush(() =>"), 5)
        # Reopening (Back to open, un-ticking) is a recovery action and is never gated.
        self.assertIn('afterFlush(() => patchItem(item.id, { state: "open" }, true), true)', PAGE)
        self.assertIn('{ state: want }, true), want === "open")', PAGE)

    @unittest.skipUnless(shutil.which("node"), "node not found")
    def test_failed_autosave_is_retried_before_submit(self):
        start = PAGE.index("// ---------------------------------------------------------------- autosave")
        end = PAGE.index("// ---------------------------------------------------------------- rendering")
        harness = (
            "const drafts = new Map(), timers = new Map(), senders = new Map();\n"
            "let queue = Promise.resolve(); const toasts = [];\n"
            "function toast(m) { toasts.push(m); } function updateHeader() {}\n"
            + PAGE[start:end] +
            "\n(async () => {\n"
            "  const tick = () => new Promise((r) => setTimeout(r, 20));\n"
            "  let ok = false; const sent = [];\n"
            "  const a = autosaveField('k', '', async (t) => { sent.push(t); return ok ? {} : null; });\n"
            "  a.onInput('hello'); a.onBlur(); await tick();\n"
            "  const failedTimerGone = !timers.has('k') && drafts.has('k');\n"
            "  const r1 = await flushAll();\n"
            "  let ran = false; await afterFlush(() => { ran = true; });\n"
            "  let reopened = false; await afterFlush(() => { reopened = true; }, true);\n"
            "  ok = true;\n"
            "  const r2 = await flushAll();\n"
            "  let ran2 = false; await afterFlush(() => { ran2 = true; });\n"
            "  drafts.set('new_note', 'typed but not sent');  // sent by hand: no sender\n"
            "  const r3 = await flushAll();\n"
            "  drafts.delete('new_note');\n"
            "  console.log(JSON.stringify({ failedTimerGone, r1, ran, reopened, r2, ran2, r3, sent, left: drafts.size, toasts: toasts.length }));\n"
            "})();\n"
        )
        r = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertTrue(got["failedTimerGone"])
        self.assertFalse(got["r1"])       # still failing: not saved, so not submitted
        self.assertFalse(got["ran"])
        self.assertTrue(got["reopened"])  # reopening is how a locked item's draft becomes savable
        self.assertTrue(got["r2"])        # the failed draft is resent once the service answers
        self.assertTrue(got["ran2"])
        self.assertEqual(got["left"], 0)
        self.assertTrue(got["r3"])        # an unsent note to Claude never blocks Submit
        self.assertGreaterEqual(len(got["sent"]), 5)  # initial save + 4 retries

    def test_demo_fixture_loads(self):
        st = rblib.load(DEMO)
        self.assertEqual(st["version"], 1)
        items = st["items"]
        by = lambda f: [i for i in items if f(i)]
        self.assertTrue(by(lambda i: i["priority"] == "urgent" and i["state"] == "open"))
        self.assertTrue(by(lambda i: i["state"] == "done"))
        self.assertTrue(by(lambda i: i["state"] == "problem" and i["output"]))
        self.assertTrue(by(lambda i: i["kind"] == "decision" and i["decision"]["options"]))
        gated = by(lambda i: i.get("after"))
        self.assertTrue(gated)
        ids = {i["id"] for i in items}
        self.assertTrue(any(a in ids for g in gated for a in g["after"]))
        self.assertTrue(by(lambda i: "found-by-sweep" in (i.get("tags") or [])))
        self.assertTrue(by(lambda i: i.get("due")))
        self.assertTrue(st["done_log"])
        self.assertTrue(any(n["status"] == "answered" and n["reply"] for n in st["notes_claude"]))
        for i in items:
            for s in i.get("steps", []):
                self.assertEqual(rblib.find_secrets(s["cmd"]), [])


if __name__ == "__main__":
    unittest.main()
