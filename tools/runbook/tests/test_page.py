import re
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
