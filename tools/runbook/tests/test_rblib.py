import os
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import rblib  # noqa: E402
from tests.fakes import (
    FAKE_ANTHROPIC, FAKE_AWS, FAKE_GITHUB, FAKE_PRIVATE_KEY, FAKE_STRIPE_LIVE,
)


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        self.path = self.tmp / "x.json"
        self.lock = self.tmp / "x.json.lock"


class StateIO(Base):
    def test_load_missing_returns_empty_state(self):
        self.assertEqual(rblib.load(self.path), rblib.empty_state())

    def test_save_bumps_version_and_roundtrips(self):
        s = rblib.empty_state()
        s["notes_self"] = "hi"
        rblib.save(s, self.path)
        got = rblib.load(self.path)
        self.assertEqual(got["version"], 1)
        self.assertEqual(got["notes_self"], "hi")

    def test_save_is_atomic(self):
        rblib.save(rblib.empty_state(), self.path)
        before = self.path.read_bytes()
        s = rblib.load(self.path)
        s["notes_self"] = "changed"
        with mock.patch("os.replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                rblib.save(s, self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(os.listdir(self.tmp), ["x.json"])

    def test_load_corrupt_raises(self):
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaises(rblib.CorruptState):
            rblib.load(self.path)

    def test_mutate_rejects_stale_version(self):
        s = rblib.empty_state()
        rblib.save(s, self.path)
        rblib.save(s, self.path)
        fn = mock.Mock()
        with self.assertRaises(rblib.StaleVersion):
            rblib.mutate(fn, self.path, expect_version=1)
        fn.assert_not_called()

    def test_mutate_applies_and_saves(self):
        def fn(s):
            s["notes_self"] = "z"
            return 7
        self.assertEqual(rblib.mutate(fn, self.path, expect_version=0), 7)
        got = rblib.load(self.path)
        self.assertEqual((got["version"], got["notes_self"]), (1, "z"))
        self.assertFalse(self.lock.exists())


class Lock(Base):
    def test_stale_lock_is_taken_over(self):
        self.lock.write_text("dead")
        old = time.time() - 11
        os.utime(self.lock, (old, old))
        t = time.monotonic()
        with rblib.locked(self.lock):
            self.assertTrue(self.lock.exists())
        self.assertLess(time.monotonic() - t, 1)
        self.assertFalse(self.lock.exists())

    def test_live_lock_times_out(self):
        self.lock.write_text("alive")
        with self.assertRaises(rblib.LockTimeout):
            with rblib.locked(self.lock, wait_s=0.3):
                pass
        self.assertTrue(self.lock.exists())

    def test_release_keeps_foreign_lock(self):
        with rblib.locked(self.lock):
            self.lock.write_text("othertoken 1 2")  # another holder took over
        self.assertEqual(self.lock.read_text(), "othertoken 1 2")

    def test_release_tolerates_missing_lock(self):
        with rblib.locked(self.lock):
            self.lock.unlink()
        self.assertFalse(self.lock.exists())

    def test_unremovable_stale_lock_times_out(self):
        self.lock.write_text("dead")
        old = time.time() - 11
        os.utime(self.lock, (old, old))
        t = time.monotonic()
        with mock.patch("pathlib.Path.unlink", side_effect=PermissionError("busy")):
            with self.assertRaises(rblib.LockTimeout):
                with rblib.locked(self.lock, wait_s=0.3):
                    pass
        self.assertLess(time.monotonic() - t, 1.5)

    def _make_stale(self, path, text="oldtoken 1 2"):
        path.write_text(text)
        old = time.time() - 11
        os.utime(path, (old, old))

    def test_stale_lock_is_broken_and_acquired(self):
        self._make_stale(self.lock)
        with rblib.locked(self.lock, wait_s=1):
            self.assertNotEqual(self.lock.read_text().split()[0], "oldtoken")
        self.assertFalse(self.lock.exists())
        self.assertFalse(self.lock.with_name(self.lock.name + ".break").exists())

    def test_held_break_guard_blocks_takeover(self):
        self._make_stale(self.lock)
        guard = self.lock.with_name(self.lock.name + ".break")
        guard.write_text("someone")  # fresh guard held by another breaker
        with self.assertRaises(rblib.LockTimeout):
            with rblib.locked(self.lock, wait_s=0.3):
                pass
        self.assertEqual(self.lock.read_text(), "oldtoken 1 2")
        self.assertTrue(guard.exists())

    def test_lock_refreshed_before_guard_is_not_deleted(self):
        self._make_stale(self.lock)
        real = getattr(rblib, "_acquire_guard", None)

        def hook(guard):
            # Another holder takes over and creates a live lock after our stat.
            self.lock.write_text("freshtoken 2 3")
            return real(guard) if real else True

        with mock.patch.object(rblib, "_acquire_guard", hook, create=True):
            with self.assertRaises(rblib.LockTimeout):
                with rblib.locked(self.lock, wait_s=0.3):
                    pass
        self.assertEqual(self.lock.read_text(), "freshtoken 2 3")

    def test_stale_break_guard_is_cleared(self):
        self._make_stale(self.lock)
        guard = self.lock.with_name(self.lock.name + ".break")
        self._make_stale(guard, "crashed")
        old = time.time() - 31
        os.utime(guard, (old, old))
        with rblib.locked(self.lock, wait_s=1):
            pass
        self.assertFalse(guard.exists())
        self.assertFalse(self.lock.exists())


class Ids(unittest.TestCase):
    def test_next_ids(self):
        s = rblib.empty_state()
        s["items"] = [{"id": "rb-0002"}]
        s["done_log"] = [{"id": "rb-0005"}]
        s["notes_claude"] = [{"id": "n-3"}]
        self.assertEqual(rblib.next_item_id(s), "rb-0006")
        self.assertEqual(rblib.next_note_id(s), "n-4")
        e = rblib.empty_state()
        self.assertEqual(rblib.next_item_id(e), "rb-0001")
        self.assertEqual(rblib.next_note_id(e), "n-1")


class Scanners(unittest.TestCase):
    def test_find_secrets_kinds(self):
        self.assertEqual(rblib.find_secrets(FAKE_AWS), ["aws-access-key"])
        self.assertEqual(rblib.find_secrets(FAKE_ANTHROPIC), ["anthropic-key"])
        self.assertEqual(rblib.find_secrets(FAKE_STRIPE_LIVE), ["stripe-live-key"])
        self.assertEqual(rblib.find_secrets(FAKE_GITHUB), ["github-token"])
        self.assertEqual(rblib.find_secrets(FAKE_PRIVATE_KEY), ["private-key"])
        self.assertEqual(rblib.find_secrets('read -rs -p "Key: " K'), [])

    def test_assigned_secret(self):
        self.assertEqual(rblib.find_secrets("password=" + "hunter2hunter2"), ["assigned-secret"])
        self.assertEqual(rblib.find_secrets("TOKEN=$TOKEN_VALUE_HERE"), [])
        self.assertEqual(rblib.find_secrets("token: <PASTE-TOKEN-HERE>"), [])

    def test_redact(self):
        self.assertEqual(
            rblib.redact(f"x {FAKE_AWS} y"),
            ("x [REDACTED:aws-access-key] y", ["aws-access-key"]),
        )
        self.assertEqual(rblib.redact("clean"), ("clean", []))

    def test_find_placeholders(self):
        self.assertEqual(rblib.find_placeholders("--repo <repo>"), ["<repo>"])
        self.assertEqual(rblib.find_placeholders("<PASTE-KEY-HERE>"), [])
        self.assertEqual(rblib.find_placeholders("cat <<'EOF'"), [])
        self.assertEqual(rblib.find_placeholders("YOUR_API_KEY"), ["YOUR_API_KEY"])
        self.assertEqual(rblib.find_placeholders("TODO fix"), ["TODO"])


class Hash(unittest.TestCase):
    TODAY = date(2026, 11, 15)

    def base(self):
        s = rblib.empty_state()
        s["items"] = [{
            "id": "rb-0001", "state": "open", "output": "", "chosen": None,
            "other": "", "agent_note": "a", "due": "2026-12-01",
        }]
        return s

    def h(self, s):
        return rblib.owner_hash(s, self.TODAY)

    def test_owner_hash_changes_only_on_owner_fields(self):
        s = self.base()
        h0 = self.h(s)
        self.assertTrue(h0.startswith("sha256:"))
        s["items"][0]["agent_note"] = "different"
        self.assertEqual(self.h(s), h0)
        for field, val in (("state", "done"), ("output", "ok"), ("chosen", "A"), ("other", "x")):
            t = self.base()
            t["items"][0][field] = val
            self.assertNotEqual(self.h(t), h0, field)
        t = self.base()
        t["notes_claude"] = [{"id": "n-1", "text": "hey", "status": "new"}]
        self.assertNotEqual(self.h(t), h0)
        t["notes_claude"][0]["status"] = "read"
        self.assertEqual(self.h(t), h0)
        t = self.base()
        t["items"][0]["due"] = "2026-11-15"
        self.assertNotEqual(self.h(t), h0)


class DoneLog(unittest.TestCase):
    def test_done_log_move_restore_prune(self):
        now = datetime(2026, 11, 15, 12, 0, 0)
        s = rblib.empty_state()
        s["items"] = [{"id": "rb-0001", "state": "done"}]
        entry = rblib.move_to_done_log(s, "rb-0001", "finished", "owner", now)
        self.assertEqual(s["items"], [])
        self.assertEqual(s["done_log"][0], entry)
        self.assertEqual(entry["reason"], "finished")
        self.assertEqual(entry["by"], "owner")
        self.assertIn("removed_at", entry)
        item = rblib.restore_from_done_log(s, "rb-0001")
        self.assertEqual(s["done_log"], [])
        self.assertEqual(s["items"], [item])
        self.assertNotIn("removed_at", item)
        rblib.move_to_done_log(s, "rb-0001", "again", "agent", now)
        self.assertEqual(rblib.prune_done_log(s, now + timedelta(days=29)), 0)
        self.assertEqual(rblib.prune_done_log(s, now + timedelta(days=31)), 1)
        self.assertEqual(s["done_log"], [])

    def test_missing_id_raises(self):
        s = rblib.empty_state()
        with self.assertRaises(KeyError):
            rblib.move_to_done_log(s, "rb-9999", "r", "b", datetime.now())
        with self.assertRaises(KeyError):
            rblib.restore_from_done_log(s, "rb-9999")


class ProjectsRootCase(unittest.TestCase):
    def test_env_then_config_then_parent(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "config.json"
            with mock.patch.object(rblib, "CONFIG", cfg), \
                    mock.patch.dict(os.environ, {"RUNBOOK_PROJECTS_ROOT": ""}):
                self.assertEqual(rblib.projects_root(), rblib.ROOT.parent)
                cfg.write_text('{"projects_root": "%s"}' % Path(d).as_posix(), encoding="utf-8")
                self.assertEqual(rblib.projects_root(), Path(d))
                with mock.patch.dict(os.environ, {"RUNBOOK_PROJECTS_ROOT": str(Path(d) / "env")}):
                    self.assertEqual(rblib.projects_root(), Path(d) / "env")


if __name__ == "__main__":
    unittest.main()
