import contextlib
import io
import os
import tempfile
import unittest

from robot_rental.__main__ import main
from robot_rental.ops import load

VAN = [
    "--model",
    "Atlas Mover",
    "--kind",
    "cargo",
    "--daily",
    "300",
    "--deposit",
    "1000",
    "--lift-kg",
    "250",
    "--stairs",
]
MOVE = ["move", "--date", "2099-01-10", "--rooms", "2", "--stairs"]


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, out.getvalue()


class FleetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "r.json")
        self.s = ["--store", self.path]

    def tearDown(self):
        self.tmp.cleanup()

    def ok(self, *argv):
        code, out = run(*argv, *self.s)
        self.assertEqual(code, 0, out)
        return out

    def test_own_fleet_replaces_the_demo_and_is_used_for_quotes(self):
        self.assertIn("demo fleet", self.ok("robots"))
        self.assertIn("replacing the demo fleet", self.ok("robot-add", "VAN-1", *VAN))
        c = load(self.path)
        self.assertEqual(list(c.fleet), ["VAN-1"])  # restart keeps only the operator's robots
        self.assertIn("robots VAN-1", self.ok("reserve", "Ana", *MOVE))
        self.assertIn("300/day", self.ok("robots"))

    def test_robot_on_a_booking_cannot_be_removed(self):
        self.ok("robot-add", "VAN-1", *VAN)
        self.ok("reserve", "Ana", *MOVE)
        self.assertEqual(run("robot-remove", "VAN-1", *self.s)[0], 1)
        self.ok("return", "R0001")
        self.ok("robot-remove", "VAN-1")
        self.assertEqual(load(self.path).fleet, {})
        self.assertEqual(run("reserve", "Bo", *MOVE, *self.s)[0], 1)  # an empty fleet can quote nothing

    def test_jobs_only_use_robots_that_exist(self):
        self.ok("robot-add", "VAN-1", *VAN)
        code, out = run("reserve", "Bo", "event", "--date", "2099-01-11", *self.s)
        self.assertEqual(code, 1)
        self.assertIn("the fleet has 0", out)

    def test_demo_bookings_must_be_returned_before_switching(self):
        self.ok("reserve", "Ana", *MOVE)  # on the demo fleet
        self.assertEqual(run("robot-add", "VAN-1", *VAN, *self.s)[0], 1)

    def test_bad_robots_are_refused(self):
        self.ok("robot-add", "VAN-1", *VAN)
        for argv in (
            ["robot-add", "VAN-1", *VAN],
            ["robot-add", "X", "--model", "m", "--kind", "cargo", "--daily", "0", "--deposit", "5"],
            ["robot-add", "Y", "--model", "m", "--kind", "cargo", "--daily", "5", "--deposit", "5", "--lift-kg", "-1"],
            ["robot-remove", "NOPE"],
        ):
            with self.subTest(argv=argv[:2]):
                self.assertEqual(run(*argv, *self.s)[0], 1)


if __name__ == "__main__":
    unittest.main()
