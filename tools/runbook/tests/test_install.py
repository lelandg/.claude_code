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
        self.assertTrue("WSL shim ~/.local/bin/runbook" in out or "skipped: wsl" in out, out)
        self.assertIsNone(re.search(r"[0-9a-f]{64}", out), "output must not contain a token-shaped run")


class InstallScriptText(unittest.TestCase):
    def test_wsl_gets_a_path_shim_not_an_alias(self):
        # A ~/.bashrc alias is invisible to non-interactive shells (wsl.exe bash -lc, agents).
        text = (ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertNotIn("alias runbook=", text)
        self.assertIn('exec python3 __PY__ "$@"', text)
        # the script path is one single-quoted word (spaces survive), and a failed
        # write never reaches mv
        self.assertIn(r"""Replace("'", "'\''")""", text)
        self.assertIn("set -e`ntrap 'rm -f ~/.local/bin/runbook.tmp' EXIT", text)


if __name__ == "__main__":
    unittest.main()
