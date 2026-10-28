"""CLI smoke tests, generated from _tools/smoke.json.

Every documented command must run in-process, exit with a domain status code
(0 ok, 1 nothing found / failing grade, 2 denied) instead of crashing, and print
output a legacy Windows console (cp1252) can encode.
"""

import contextlib
import io
import os
import pathlib
import tempfile
import unittest

from robot_rental.__main__ import main

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMMANDS = [
    ["fleet"],
    ["quote", "move", "--rooms", "3", "--heaviest", "80", "--stairs", "--date", "2026-11-07", "--km", "12"],
    ["quote", "event", "--guests", "120", "--hours", "5", "--date", "2026-11-07"],
]


class CliSmokeTests(unittest.TestCase):
    def test_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            for template in COMMANDS:
                argv = [a.replace("{root}", str(ROOT)).replace("{tmp}", tmp) for a in template]
                with self.subTest(argv=template):
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                        code = main(argv)
                    self.assertIn(code, (0, 1, 2))
                    self.assertTrue(out.getvalue().strip(), "command printed nothing")
                    out.getvalue().encode("cp1252")


class BookingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("ROBOT_RENTAL_HOME")
        os.environ["ROBOT_RENTAL_HOME"] = self.tmp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("ROBOT_RENTAL_HOME", None)
        else:
            os.environ["ROBOT_RENTAL_HOME"] = self.old
        self.tmp.cleanup()

    def run_cli(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(argv)
        return code, out.getvalue()

    def test_book_quote_return_flow_persists_across_runs(self):
        code, out = self.run_cli(["book", "deep_clean", "--sqft", "3000", "--date", "2026-11-07", "--customer", "acme"])
        self.assertEqual(code, 0)
        self.assertIn("Booked R0001", out)
        code, out = self.run_cli(["quote", "deep_clean", "--sqft", "3000", "--date", "2026-11-07"])
        self.assertEqual(code, 0)
        self.assertIn("K-02", out)  # K-01 is booked, so the next quote picks K-02
        code, out = self.run_cli(["return", "R0001", "--damages", "scratched brush=150", "--late-days", "1"])
        self.assertEqual(code, 0)
        self.assertIn("deposit refund $110.00", out)
        code, out = self.run_cli(["quote", "deep_clean", "--sqft", "3000", "--date", "2026-11-07"])
        self.assertIn("K-01", out)
        code, _ = self.run_cli(["return", "R9999"])
        self.assertEqual(code, 1)
        code, _ = self.run_cli(["return", "R0001"])
        self.assertEqual(code, 1)  # already returned


if __name__ == "__main__":
    unittest.main()
