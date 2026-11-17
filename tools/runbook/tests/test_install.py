import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("pwsh"), "pwsh not found")
class InstallWhatIfCase(unittest.TestCase):
    def test_whatif_prints_every_step_and_hides_token(self):
        r = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(ROOT / "install.ps1"), "-WhatIf"],
            capture_output=True, text=True, timeout=120,
        )
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out)
        for needle in ("token", "Startup", "Runbook\\Processor", "runbook.cmd", ".runbook/"):
            self.assertIn(needle, out)
        self.assertTrue(".bashrc" in out or "skipped: wsl" in out, out)
        self.assertIsNone(re.search(r"[0-9a-f]{64}", out), "output must not contain a token-shaped run")


if __name__ == "__main__":
    unittest.main()
