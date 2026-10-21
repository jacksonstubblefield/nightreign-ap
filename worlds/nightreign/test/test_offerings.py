import unittest

from worlds.nightreign.offerings import OFFERING_WEAPON, OfferingQueue


class TestOfferingQueue(unittest.TestCase):
    def test_nothing_queued_by_default(self) -> None:
        queue = OfferingQueue()
        self.assertEqual(queue.take(OFFERING_WEAPON, {(0, 1), (3, 1)}), [])
        self.assertFalse(queue.any_queued())

    def test_requests_are_capped_at_what_is_held(self) -> None:
        queue = OfferingQueue()
        self.assertEqual(queue.request(OFFERING_WEAPON, 5, held=2), 2)
        self.assertEqual(queue.request(OFFERING_WEAPON, 1, held=2), 0)
        self.assertEqual(queue.queued(OFFERING_WEAPON), 2)

    def test_take_releases_the_oldest_first(self) -> None:
        queue = OfferingQueue()
        queue.request(OFFERING_WEAPON, 2, held=3)
        self.assertEqual(queue.take(OFFERING_WEAPON, {(9, 1), (2, 1), (5, 2)}), [(2, 1), (5, 2)])

    def test_take_does_not_consume_until_delivered(self) -> None:
        # A failed drop (game not ready) must leave the request queued for the next tick.
        queue = OfferingQueue()
        queue.request(OFFERING_WEAPON, 1, held=1)
        queue.take(OFFERING_WEAPON, {(0, 1)})
        self.assertEqual(queue.queued(OFFERING_WEAPON), 1)
        queue.delivered(OFFERING_WEAPON)
        self.assertEqual(queue.queued(OFFERING_WEAPON), 0)
        self.assertFalse(queue.any_queued())

    def test_delivered_never_goes_negative(self) -> None:
        queue = OfferingQueue()
        queue.delivered(OFFERING_WEAPON, 3)
        self.assertEqual(queue.queued(OFFERING_WEAPON), 0)

    def test_clear_drops_every_request(self) -> None:
        queue = OfferingQueue()
        queue.request(OFFERING_WEAPON, 1, held=1)
        queue.clear()
        self.assertFalse(queue.any_queued())


if __name__ == "__main__":
    unittest.main()
