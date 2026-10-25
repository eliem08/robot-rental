import unittest
from datetime import date

from robot_rental import Counter, RentalError, job_requirements

D = date(2026, 11, 7)


class Tests(unittest.TestCase):
    def setUp(self):
        self.c = Counter()

    def test_move_with_stairs_needs_big_cargo_and_humanoid(self):
        q = self.c.quote("move", D, km=10, rooms=3, heaviest=150, stairs=True)
        self.assertEqual(q["robots"], ["C-01", "H-01"])
        self.assertGreater(q["operator"], 0)
        self.assertEqual(q["delivery"], 50)

    def test_small_move_uses_cheapest_cargo(self):
        q = self.c.quote("move", D, rooms=1, heaviest=60)
        self.assertEqual(q["robots"], ["C-02"])
        self.assertEqual(q["operator"], 0)

    def test_event_server_count(self):
        self.assertEqual(len(job_requirements("event", guests=120, hours=2)["needs"]), 2)
        with self.assertRaises(RentalError):
            self.c.quote("event", D, guests=1000, hours=1)

    def test_booking_conflicts_and_return(self):
        q = self.c.quote("deep_clean", D, sqft=3000)
        bid = self.c.book(q, "acme")
        q2 = self.c.quote("deep_clean", D, sqft=3000)
        self.assertEqual(q2["robots"], ["K-02"])
        with self.assertRaises(RentalError):
            self.c.book(q, "other")
        r = self.c.return_robots(bid, damages={"scratched brush": 150}, late_days=1)
        self.assertEqual(r["deposit_refund"], 400 - 150 - 140)
        self.assertEqual(self.c.quote("deep_clean", D, sqft=3000)["robots"], ["K-01"])

    def test_huge_event_fails_fast_instead_of_hanging(self):
        with self.assertRaisesRegex(RentalError, "fleet has 3"):
            job_requirements("event", guests=10**20, hours=5)

    def test_jobs_longer_than_a_day_are_rejected_not_priced_as_one_day(self):
        with self.assertRaisesRegex(RentalError, "split it into days"):
            self.c.quote("event", D, guests=120, hours=48)
        with self.assertRaisesRegex(RentalError, "split it into days"):
            self.c.quote("move", D, rooms=20, heaviest=80)

    def test_nonsense_inputs_are_rejected(self):
        for bad in ({"rooms": -1}, {"rooms": 0}, {"rooms": float("nan")}, {"heaviest": -5}):
            with self.subTest(bad=bad), self.assertRaises(RentalError):
                self.c.quote("move", D, **bad)
        with self.assertRaises(RentalError):
            self.c.quote("event", D, guests=50, hours=float("inf"))
        with self.assertRaises(RentalError):
            self.c.quote("move", D, km=-10, rooms=2)

    def test_negative_damages_cannot_inflate_the_refund(self):
        bid = self.c.book(self.c.quote("deep_clean", D, sqft=3000), "acme")
        with self.assertRaises(RentalError):
            self.c.return_robots(bid, damages={"credit": -1000})
        with self.assertRaises(RentalError):
            self.c.return_robots(bid, late_days=-3)


if __name__ == "__main__":
    unittest.main()
