import contextlib
import io
import os
import tempfile
import unittest

from robot_rental.__main__ import main
from robot_rental.ops import load

MOVE = ["move", "--date", "2099-01-10", "--rooms", "3", "--stairs"]


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, out.getvalue()


class RentalOpsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "rentals.json")
        self.s = ["--store", self.path]

    def tearDown(self):
        self.tmp.cleanup()

    def ok(self, *argv):
        code, out = run(*argv, *self.s)
        self.assertEqual(code, 0, out)
        return out

    def test_reservation_holds_the_robots_across_restarts(self):
        self.assertIn("R0001", self.ok("reserve", "Ana", *MOVE))
        self.assertIn("reserved", self.ok("availability", "--date", "2099-01-10"))
        code, out = run("reserve", "Bo", *MOVE, *self.s)  # the only stair-capable cargo robot is taken
        self.assertEqual(code, 1, out)
        self.assertNotIn("reserved", self.ok("availability", "--date", "2099-01-11"))

    def test_return_settles_the_deposit_and_frees_the_robots(self):
        self.ok("reserve", "Ana", *MOVE)
        robot = load(self.path).bookings["R0001"]["robots"][0]
        out = self.ok("return", "R0001", "--late-days", "1", "--damage", f"{robot}=100")
        self.assertIn("damage $100.00", out)
        b = load(self.path).bookings["R0001"]
        self.assertEqual(b["deposit_refund"], b["deposit"] - 100 - b["rental"])
        self.assertEqual(run("return", "R0001", *self.s)[0], 1)  # settled once
        self.assertIn("R0002", self.ok("reserve", "Bo", *MOVE))  # the day is free again

    def test_refusals(self):
        self.ok("reserve", "Ana", *MOVE)
        for argv in (
            ["reserve", "Ana", "move", "--date", "2001-01-01"],  # in the past
            ["reserve", "Ana", "move", "--date", "next week"],
            ["return", "R9999"],
            ["return", "R0001", "--damage", "ZZ-99=50"],  # not a robot on this booking
            ["return", "R0001", "--damage", "nonsense"],
            ["return", "R0001", "--late-days", "-1"],
        ):
            with self.subTest(argv=argv):
                self.assertEqual(run(*argv, *self.s)[0], 1)
        self.assertEqual(load(self.path).bookings["R0001"]["status"], "booked")


if __name__ == "__main__":
    unittest.main()
