"""Operator-defined job types, robot kinds and rates."""

import contextlib
import io
import os
import tempfile
import unittest

from robot_rental.__main__ import main


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, out.getvalue()


class CustomJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = os.path.join(self.tmp.name, "r.json")

    def tearDown(self):
        self.tmp.cleanup()

    def r(self, *argv):
        return run(*argv, "--store", self.store)

    def fleet(self):
        self.assertEqual(
            self.r("robot-add", "W1", "--model", "Spot", "--kind", "security", "--daily", "400", "--deposit", "3000")[
                0
            ],
            0,
        )
        for rid in ("F1", "F2"):
            self.r(
                "robot-add",
                rid,
                "--model",
                "Lift",
                "--kind",
                "cargo",
                "--daily",
                "250",
                "--deposit",
                "900",
                "--lift-kg",
                "300",
            )

    def test_custom_job_prices_with_custom_rates_and_survives_restart(self):
        self.fleet()
        code, out = self.r(
            "job-add",
            "warehouse_inventory",
            "--robot",
            "cargo:2:200",
            "--hours",
            "1",
            "--hours-per-unit",
            "0.25",
            "--unit",
            "pallet",
        )
        self.assertEqual(code, 0, out)
        self.r("rates", "--km-rate", "3.2", "--operator-hourly", "60")
        code, out = self.r(
            "reserve", "acme", "warehouse_inventory", "--date", "2099-01-10", "--units", "20", "--km", "15"
        )
        self.assertEqual(code, 0, out)
        self.assertIn("F1, F2 (~6.0 h)", out)
        self.assertIn("$596.00", out)  # 2 x 250 + 15 km x 3.20 x 2
        self.assertIn("$1,800", out)
        _, out = self.r("jobs")
        self.assertIn("2x cargo (lifts 200 kg); 1 h + 0.25 h per pallet", out)
        _, out = self.r("rates")
        self.assertIn("$3.20/km", out)

    def test_lift_requirement_and_double_booking(self):
        self.fleet()
        self.r("job-add", "heavy", "--robot", "cargo:1:500", "--hours", "2")
        code, out = self.r("reserve", "acme", "heavy", "--date", "2099-01-10")
        self.assertEqual(code, 1)
        self.assertIn("no cargo robot", out)
        self.r("job-add", "patrol", "--robot", "security", "--hours", "10")
        self.assertEqual(self.r("reserve", "a", "patrol", "--date", "2099-02-01")[0], 0)
        self.assertEqual(self.r("reserve", "b", "patrol", "--date", "2099-02-01")[0], 1)

    def test_bad_definitions_are_refused(self):
        self.fleet()
        for args in (
            ("job-add", "move", "--robot", "cargo", "--hours", "1"),  # built-in name
            ("job-add", "Bad Name", "--robot", "cargo", "--hours", "1"),
            ("job-add", "x", "--robot", "cargo:0", "--hours", "1"),
            ("job-add", "x", "--robot", "cargo:2:-5", "--hours", "1"),
            ("job-add", "x", "--robot", "cargo"),  # no hours at all
            ("job-add", "x", "--robot", "cargo", "--hours", "30"),
            ("rates", "--km-rate", "-1"),
            ("robot-add", "Z", "--model", "m", "--kind", "Not A Kind", "--daily", "1", "--deposit", "1"),
        ):
            self.assertEqual(self.r(*args)[0], 1, args)
        _, out = self.r("reserve", "acme", "gardening")
        self.assertIn("jobs: move, deep_clean, event", out)
        self.assertEqual(self.r("job-remove", "nothing")[0], 1)

    def test_job_for_a_kind_not_in_the_fleet_warns(self):
        self.fleet()
        _, out = self.r("job-add", "drone_survey", "--robot", "drone", "--hours", "3")
        self.assertIn("no drone robot in the fleet yet", out)
        self.assertEqual(self.r("job-remove", "drone_survey")[0], 0)


if __name__ == "__main__":
    unittest.main()
