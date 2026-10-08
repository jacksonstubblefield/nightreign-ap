import unittest

from worlds.nightreign.game_data import DRIFT_TOLERANCE, KNOWN_BOSS_IDS, OBSERVED_BOSS_IDS, boss_id_candidates


class TestBossIds(unittest.TestCase):
    def test_observed_ids_resolve_to_their_boss(self) -> None:
        for raw, name in OBSERVED_BOSS_IDS.items():
            with self.subTest(raw=raw):
                self.assertEqual(boss_id_candidates(raw), {name})

    def test_out_of_window_sighting_falls_back_to_observed(self) -> None:
        self.assertEqual(boss_id_candidates(1095), {"Dreglord"})

    def test_unsighted_out_of_window_id_stays_unknown(self) -> None:
        self.assertEqual(boss_id_candidates(1096), set())

    def test_windows_do_not_overlap(self) -> None:
        bases = sorted(KNOWN_BOSS_IDS)
        for low, high in zip(bases, bases[1:]):
            with self.subTest(low=low, high=high):
                self.assertGreater(high - low, 2 * DRIFT_TOLERANCE)
