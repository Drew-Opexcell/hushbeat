import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT = HERE / "hushbeat.py"


def run(*args, cwd):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=cwd)


class TestHushbeat(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = Path(tempfile.mkdtemp())
        self.config = self.dir / "hushbeat.json"
        self.state = self.dir / ".hushbeat-pings.json"

    def write_config(self, cfg):
        self.config.write_text(json.dumps(cfg), encoding="utf-8")

    def test_ping_records_timestamp(self):
        r = run("ping", "backup", cwd=self.dir)
        self.assertEqual(r.returncode, 0)
        state = json.loads(self.state.read_text())
        self.assertIn("backup", state)
        self.assertAlmostEqual(state["backup"], time.time(), delta=5)

    def test_fresh_ping_passes(self):
        self.write_config({"urls": [], "pings": {"backup": 1}})
        run("ping", "backup", cwd=self.dir)
        r = run("check", cwd=self.dir)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "")

    def test_stale_ping_fails(self):
        self.write_config({"urls": [], "pings": {"backup": 1}})
        self.state.write_text(json.dumps({"backup": time.time() - 7200}))
        r = run("check", cwd=self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("backup", r.stdout)
        self.assertIn("2.0h ago", r.stdout)

    def test_never_pinged_fails(self):
        self.write_config({"urls": [], "pings": {"backup": 1}})
        r = run("check", cwd=self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("never pinged", r.stdout)

    def test_unreachable_url_fails(self):
        self.write_config({"urls": [{"name": "dead", "url": "http://127.0.0.1:1"}],
                           "pings": {}, "timeout_seconds": 2})
        r = run("check", cwd=self.dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("dead", r.stdout)


if __name__ == "__main__":
    unittest.main()
