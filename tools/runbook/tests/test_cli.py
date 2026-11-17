import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rblib  # noqa: E402
import runbook  # noqa: E402
import errno  # noqa: E402

from tests.fakes import FAKE_AWS  # noqa: E402


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.state = self.dir / "runbook.json"
        env = mock.patch.dict(os.environ, {"RUNBOOK_AGENT": "tester"})
        env.start()
        self.addCleanup(env.stop)

    def run_cli(self, *argv, cwd=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = runbook.main(list(argv), self.state, cwd or self.dir)
        return code, out.getvalue(), err.getvalue()

    def add(self, title="T", why="W", *extra):
        return self.run_cli(
            "add", "--repo", "my-app", "--title", title, "--why", why,
            "--step", "wsl|echo hi|prints hi", "--verify", "V", *extra,
        )

    def items(self):
        return rblib.load(self.state)["items"]


class TestCli(CliCase):
    def test_add_steps_item(self):
        code, out, _ = self.add()
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "rb-0001")
        item = self.items()[0]
        self.assertEqual(item["id"], "rb-0001")
        self.assertEqual(item["kind"], "steps")
        self.assertEqual(
            item["steps"][0],
            {"shell": "wsl", "cmd": "echo hi", "expect": "prints hi", "prompts": ""},
        )
        self.assertEqual(item["state"], "open")
        self.assertEqual(item["added_by"], "tester")
        self.assertEqual(item["tags"], [])
        self.assertEqual(item["priority"], "normal")

    def test_added_by_defaults_unknown(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("RUNBOOK_AGENT", None)
            self.add()
        self.assertEqual(self.items()[0]["added_by"], "unknown")

    def test_step_cmd_may_contain_pipe(self):
        self.run_cli(
            "add", "--repo", "my-app", "--title", "T", "--why", "W",
            "--step", "wsl|ls | wc -l|counts lines", "--verify", "V",
        )
        st = self.items()[0]["steps"][0]
        self.assertEqual((st["cmd"], st["expect"]), ("ls | wc -l", "counts lines"))

    def test_step_empty_expect_ok(self):
        code, _, _ = self.run_cli(
            "add", "--repo", "my-app", "--title", "T", "--why", "W",
            "--step", "wsl|ls | wc -l|", "--verify", "V",
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.items()[0]["steps"][0]["cmd"], "ls | wc -l")

    def test_step_without_expect_field_refused(self):
        code, _, err = self.run_cli(
            "add", "--repo", "my-app", "--title", "T", "--why", "W",
            "--step", "wsl|echo hi", "--verify", "V",
        )
        self.assertEqual(code, 2)
        self.assertIn("--step", err)
        self.assertFalse(self.state.exists())

    def test_options_tags_due_after(self):
        code, _, _ = self.add(
            "T", "W", "--tag", "found-by-sweep", "--tag", "x", "--due", "2026-12-01",
            "--after", "rb-0009", "--priority", "urgent", "--rollback", "undo", "--source", "S",
        )
        self.assertEqual(code, 0)
        it = self.items()[0]
        self.assertEqual(it["tags"], ["found-by-sweep", "x"])
        self.assertEqual(it["due"], "2026-12-01")
        self.assertEqual(it["after"], ["rb-0009"])
        self.assertEqual(it["priority"], "urgent")
        self.assertEqual((it["rollback"], it["source"]), ("undo", "S"))

    def test_bad_due_and_priority_refused(self):
        code, _, err = self.add("T", "W", "--due", "12/01/2026")
        self.assertEqual(code, 2)
        self.assertIn("--due", err)
        code, _, _ = self.add("T", "W", "--priority", "whenever")
        self.assertEqual(code, 2)
        self.assertFalse(self.state.exists())

    def test_add_refuses_secret(self):
        code, _, err = self.run_cli(
            "add", "--repo", "my-app", "--title", "T", "--why", "W",
            "--step", f"wsl|export K={FAKE_AWS}|", "--verify", "V",
        )
        self.assertEqual(code, 2)
        self.assertIn("aws-access-key", err)
        self.assertNotIn(FAKE_AWS, err)
        self.assertFalse(self.state.exists())

    def test_add_refuses_placeholder(self):
        code, _, err = self.run_cli(
            "add", "--repo", "my-app", "--title", "T", "--why", "W",
            "--step", "wsl|cd <repo>|", "--verify", "V",
        )
        self.assertEqual(code, 2)
        self.assertIn("<repo>", err)
        self.assertFalse(self.state.exists())

    def test_add_refuses_placeholder_in_verify(self):
        code, _, err = self.run_cli(
            "add", "--repo", "my-app", "--title", "T", "--why", "W",
            "--step", "wsl|echo|", "--verify", "check <thing>",
        )
        self.assertEqual(code, 2)
        self.assertIn("<thing>", err)

    def test_paste_placeholder_allowed(self):
        code, _, _ = self.run_cli(
            "add", "--repo", "my-app", "--title", "T", "--why", "W",
            "--step", "wsl|set K=<PASTE-KEY>|", "--verify", "V",
        )
        self.assertEqual(code, 0)

    def test_add_dedupes(self):
        self.add("Same", "first")
        code, out, _ = self.add("Same", "second")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "rb-0001")
        items = self.items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["why"], "second")
        self.assertEqual(items[0]["id"], "rb-0001")

    def test_add_decision(self):
        code, out, _ = self.run_cli(
            "add-decision", "--repo", "my-app", "--title", "Pick",
            "--option", "A|first", "--option", "B|second*",
        )
        self.assertEqual(code, 0)
        it = self.items()[0]
        self.assertEqual(it["kind"], "decision")
        opts = it["decision"]["options"]
        self.assertEqual([o["label"] for o in opts], ["A", "B"])
        self.assertEqual(opts[1]["detail"], "second")
        self.assertEqual([o["recommended"] for o in opts], [False, True])
        self.assertNotIn("chosen", it["decision"])
        self.assertNotIn("other", it["decision"])
        self.assertIsNone(it["chosen"])

    def test_verified_moves_to_done_log(self):
        self.add()
        code, _, _ = self.run_cli("verified", "rb-0001", "--note", "ok")
        self.assertEqual(code, 0)
        st = rblib.load(self.state)
        self.assertEqual(st["items"], [])
        self.assertEqual(st["done_log"][0]["reason"], "verified: ok")
        self.assertEqual(st["done_log"][0]["by"], "tester")

    def test_unknown_id_refused(self):
        self.add()
        for argv in (
            ("verified", "rb-0099", "--note", "x"),
            ("reopen", "rb-0099", "--note", "x"),
            ("restore", "rb-0099"),
            ("show", "rb-0099"),
            ("reply", "n-9", "--text", "x"),
        ):
            code, _, err = self.run_cli(*argv)
            self.assertEqual(code, 2, argv)
            self.assertTrue(err)

    def test_reopen_sets_note(self):
        self.add()
        code, _, _ = self.run_cli("reopen", "rb-0001", "--note", "still 403")
        self.assertEqual(code, 0)
        it = self.items()[0]
        self.assertEqual(it["state"], "open")
        self.assertEqual(it["agent_note"], "still 403")

    def test_reply_and_asked_back(self):
        def seed(st):
            st["notes_claude"] = [
                {"id": "n-1", "text": "a", "at": "x", "status": "new", "reply": ""},
                {"id": "n-2", "text": "b", "at": "x", "status": "new", "reply": ""},
            ]
        rblib.mutate(seed, self.state)
        self.assertEqual(self.run_cli("reply", "n-1", "--text", "T")[0], 0)
        self.assertEqual(
            self.run_cli("reply", "n-2", "--text", "Q?", "--asked-back")[0], 0
        )
        notes = {n["id"]: n for n in rblib.load(self.state)["notes_claude"]}
        self.assertEqual((notes["n-1"]["status"], notes["n-1"]["reply"]), ("answered", "T"))
        self.assertEqual(notes["n-2"]["status"], "asked-back")

    def test_restore(self):
        self.add()
        self.run_cli("verified", "rb-0001", "--note", "ok")
        code, _, _ = self.run_cli("restore", "rb-0001")
        self.assertEqual(code, 0)
        st = rblib.load(self.state)
        self.assertEqual(st["items"][0]["state"], "open")
        self.assertEqual(st["done_log"], [])

    def test_list_and_show(self):
        self.add("One")
        self.add("Two")
        self.run_cli("verified", "rb-0002", "--note", "ok")
        code, out, _ = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip().splitlines(), ["rb-0001  open  my-app  One"])
        code, out, _ = self.run_cli("list", "--state", "done")
        self.assertEqual(out.strip(), "")
        code, out, _ = self.run_cli("show", "rb-0001")
        self.assertEqual(json.loads(out)["title"], "One")

class TestReAdd(CliCase):
    """A re-add (same repo+title) refreshes only what the caller passed."""

    def test_readd_keeps_agent_note(self):
        self.add("Same")
        self.run_cli("reopen", "rb-0001", "--note", "diag")
        self.assertEqual(self.add("Same", "again")[0], 0)
        it = self.items()[0]
        self.assertEqual(it["agent_note"], "diag")
        self.assertEqual(it["why"], "again")

    def test_readd_keeps_tags_priority_due_after(self):
        self.add("Same", "W", "--tag", "found-by-sweep", "--tag", "urgent", "--priority", "urgent",
                 "--due", "2026-12-01", "--after", "rb-0009")
        self.add("Same", "W")
        it = self.items()[0]
        self.assertEqual(it["tags"], ["found-by-sweep", "urgent"])
        self.assertEqual(it["priority"], "urgent")
        self.assertEqual(it["due"], "2026-12-01")
        self.assertEqual(it["after"], ["rb-0009"])

    def test_readd_unions_tags(self):
        self.add("Same", "W", "--tag", "a", "--tag", "b")
        self.add("Same", "W", "--tag", "b", "--tag", "c")
        self.assertEqual(self.items()[0]["tags"], ["a", "b", "c"])

    def test_readd_keeps_added_by(self):
        self.add("Same")
        with mock.patch.dict(os.environ, {"RUNBOOK_AGENT": "other"}):
            self.add("Same")
        self.assertEqual(self.items()[0]["added_by"], "tester")

    def test_readd_explicit_values_replace(self):
        self.add("Same", "W", "--priority", "urgent", "--source", "S1")
        self.add("Same", "W", "--priority", "later", "--source", "S2")
        it = self.items()[0]
        self.assertEqual((it["priority"], it["source"]), ("later", "S2"))

    def test_merge_inbox_readd_keeps_note_and_unions_tags(self):
        state = rblib.empty_state()
        runbook.merge_inbox(state, {"repo": "my-app", "title": "T", "tags": ["found-by-sweep"],
                                    "priority": "urgent"})
        state["items"][0]["agent_note"] = "diag"
        runbook.merge_inbox(state, {"repo": "my-app", "title": "T", "tags": ["x"], "agent_note": ""})
        it = state["items"][0]
        self.assertEqual(it["agent_note"], "diag")
        self.assertEqual(it["tags"], ["found-by-sweep", "x"])
        self.assertEqual(it["priority"], "urgent")


class TestTextScanning(CliCase):
    def refused(self, *argv):
        code, _, err = self.run_cli(*argv)
        self.assertEqual(code, 2, (argv, err))
        self.assertNotIn(FAKE_AWS, err)
        self.assertFalse(self.state.exists())
        return err

    def test_add_refuses_secret_in_every_text_field(self):
        base = {"--repo": "my-app", "--title": "T", "--why": "W", "--source": "S"}
        for flag in ("--repo", "--title", "--why", "--source", "--tag"):
            argv = ["add"]
            for k, v in base.items():
                argv += [k, f"x {FAKE_AWS}" if k == flag else v]
            if flag == "--tag":
                argv += ["--tag", FAKE_AWS]
            argv += ["--step", "wsl|echo hi|ok", "--verify", "V"]
            with self.subTest(flag=flag):
                self.assertIn("aws-access-key", self.refused(*argv))

    def test_add_refuses_placeholder_in_title_and_tag(self):
        self.assertIn("<x>", self.refused(
            "add", "--repo", "my-app", "--title", "do <x>", "--why", "W",
            "--step", "wsl|echo|", "--verify", "V"))
        self.assertIn("YOUR_TAG", self.refused(
            "add", "--repo", "my-app", "--title", "T", "--why", "W", "--tag", "YOUR_TAG",
            "--step", "wsl|echo|", "--verify", "V"))

    def test_add_decision_refuses_secret(self):
        opts = ["--option", "A|a", "--option", "B|b"]
        for argv in (
            ["--title", f"T {FAKE_AWS}"],
            ["--title", "T", "--why", FAKE_AWS],
            ["--title", "T", "--source", FAKE_AWS],
            ["--title", "T", "--option", f"{FAKE_AWS}|c"],
            ["--title", "T", "--option", f"C|{FAKE_AWS}"],
        ):
            with self.subTest(argv=argv):
                self.refused("add-decision", "--repo", "my-app", *argv, *opts)

    def test_reopen_note_redacted(self):
        self.add()
        code, _, err = self.run_cli("reopen", "rb-0001", "--note", f"saw {FAKE_AWS}")
        self.assertEqual(code, 0)
        self.assertIn("aws-access-key", err)
        self.assertNotIn(FAKE_AWS, err)
        self.assertNotIn(FAKE_AWS, self.state.read_text(encoding="utf-8"))
        self.assertIn("[REDACTED:aws-access-key]", self.items()[0]["agent_note"])

    def test_verified_note_redacted(self):
        self.add()
        code, _, err = self.run_cli("verified", "rb-0001", "--note", f"key {FAKE_AWS}")
        self.assertEqual(code, 0)
        self.assertIn("aws-access-key", err)
        self.assertNotIn(FAKE_AWS, self.state.read_text(encoding="utf-8"))

    def test_reply_text_redacted(self):
        rblib.mutate(lambda st: st["notes_claude"].append(
            {"id": "n-1", "text": "a", "at": "x", "status": "new", "reply": ""}), self.state)
        code, _, err = self.run_cli("reply", "n-1", "--text", f"it is {FAKE_AWS}")
        self.assertEqual(code, 0)
        self.assertIn("aws-access-key", err)
        self.assertNotIn(FAKE_AWS, self.state.read_text(encoding="utf-8"))

    def test_clean_note_prints_nothing(self):
        self.add()
        code, _, err = self.run_cli("reopen", "rb-0001", "--note", "fine")
        self.assertEqual((code, err), (0, ""))


class TestDecisionSource(CliCase):
    def test_add_decision_source(self):
        code, _, _ = self.run_cli(
            "add-decision", "--repo", "my-app", "--title", "Pick", "--source", "my-app/Plans/x.md",
            "--option", "A|a", "--option", "B|b",
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.items()[0]["source"], "my-app/Plans/x.md")


class TestInbox(CliCase):
    def make_repo(self):
        repo = self.dir / "repo"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        return repo

    def test_unwritable_state_falls_back_to_inbox(self):
        repo = self.make_repo()
        with mock.patch.object(rblib, "mutate", side_effect=PermissionError("ro")):
            code, out, _ = self.run_cli(
                "add", "--repo", "my-app", "--title", "T", "--why", "W",
                "--step", "wsl|echo hi|ok", "--verify", "V", cwd=repo,
            )
        self.assertEqual(code, 3)
        files = list((repo / ".runbook" / "inbox").glob("*.json"))
        self.assertEqual(len(files), 1)
        item = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(item["title"], "T")
        self.assertIn(files[0].name, out)

    def test_no_git_repo_no_fallback(self):
        bare = self.dir / "nogit"
        bare.mkdir()
        with mock.patch.object(rblib, "mutate", side_effect=PermissionError("ro")):
            code, _, err = self.run_cli(
                "add", "--repo", "my-app", "--title", "T", "--why", "W",
                "--step", "wsl|echo hi|ok", "--verify", "V", cwd=bare,
            )
        self.assertEqual(code, 1)
        self.assertTrue(err)
        self.assertFalse((bare / ".runbook").exists())

    def test_missing_state_dir_is_error_not_inbox(self):
        repo = self.make_repo()
        state = self.dir / "no" / "such" / "dir" / "runbook.json"
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = runbook.main(["add", "--repo", "my-app", "--title", "T", "--why", "W",
                                 "--step", "wsl|echo hi|ok", "--verify", "V"], state, repo)
        self.assertEqual(code, 1)
        self.assertTrue(err.getvalue())
        self.assertFalse((repo / ".runbook").exists())

    def test_readonly_errno_falls_back(self):
        repo = self.make_repo()
        for no in (errno.EACCES, errno.EROFS, errno.EPERM):
            with self.subTest(errno=no), mock.patch.object(
                    rblib, "mutate", side_effect=OSError(no, "ro")):
                code, _, _ = self.run_cli(
                    "add", "--repo", "my-app", "--title", "T", "--why", "W",
                    "--step", "wsl|echo hi|ok", "--verify", "V", cwd=repo,
                )
                self.assertEqual(code, 3)

    def test_other_oserror_no_fallback(self):
        repo = self.make_repo()
        with mock.patch.object(rblib, "mutate", side_effect=OSError(errno.ENOSPC, "full")):
            code, _, _ = self.run_cli(
                "add", "--repo", "my-app", "--title", "T", "--why", "W",
                "--step", "wsl|echo hi|ok", "--verify", "V", cwd=repo,
            )
        self.assertEqual(code, 1)
        self.assertFalse((repo / ".runbook").exists())

    def test_inbox_payload_is_only_what_was_passed(self):
        repo = self.make_repo()
        with mock.patch.object(rblib, "mutate", side_effect=PermissionError("ro")):
            self.run_cli("add", "--repo", "my-app", "--title", "T", "--why", "W",
                         "--step", "wsl|echo hi|ok", "--verify", "V", cwd=repo)
        f = next((repo / ".runbook" / "inbox").glob("*.json"))
        item = json.loads(f.read_text(encoding="utf-8"))
        for k in ("agent_note", "priority", "due", "tags", "chosen", "state"):
            self.assertNotIn(k, item)
        self.assertEqual(item["added_by"], "tester")

    def test_write_inbox_path(self):
        repo = self.make_repo()
        p = runbook.write_inbox({"title": "x"}, repo)
        self.assertEqual(p.parent, repo / ".runbook" / "inbox")
        self.assertEqual(json.loads(p.read_text(encoding="utf-8")), {"title": "x"})

    def test_merge_inbox_assigns_id(self):
        state = rblib.empty_state()
        item = {"repo": "my-app", "title": "T", "why": "w1", "kind": "steps", "state": "open"}
        self.assertEqual(runbook.merge_inbox(state, dict(item)), "rb-0001")
        self.assertEqual(state["items"][0]["id"], "rb-0001")
        state["items"][0]["state"] = "problem"
        again = dict(item, why="w2")
        self.assertIsNone(runbook.merge_inbox(state, again))
        self.assertEqual(len(state["items"]), 1)
        self.assertEqual(state["items"][0]["why"], "w2")
        self.assertEqual(state["items"][0]["state"], "problem")
        self.assertEqual(state["items"][0]["id"], "rb-0001")


if __name__ == "__main__":
    unittest.main()


class StateFromEnv(unittest.TestCase):
    def test_script_honours_runbook_state(self):
        # process.py points the model's CLI calls at a non-default state this way.
        with tempfile.TemporaryDirectory() as d:
            st = Path(d) / "alt.json"
            s = rblib.empty_state()
            s["items"] = [{"id": "rb-0042", "repo": "CL", "title": "only-in-alt", "state": "open"}]
            rblib.save(s, st)
            r = subprocess.run(
                [sys.executable, str(Path(runbook.__file__)), "list"],
                capture_output=True, text=True, timeout=60,
                env=dict(os.environ, RUNBOOK_STATE=str(st), RUNBOOK_AGENT="tester"),
            )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("rb-0042", r.stdout)
