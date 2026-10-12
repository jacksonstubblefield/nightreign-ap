import unittest
from unittest.mock import patch

from worlds.nightreign.game_data import (
    DLC_BOSS_ID_OFFSET, DRIFT_TOLERANCE, KNOWN_BOSS_IDS, OBSERVED_BOSS_IDS, UNSET_SENTINEL,
    boss_id_candidates,
)


class TestBossIds(unittest.TestCase):
    def test_observed_ids_resolve_to_their_boss(self) -> None:
        for raw, name in OBSERVED_BOSS_IDS.items():
            with self.subTest(raw=raw):
                self.assertEqual(boss_id_candidates(raw), {name})

    def test_out_of_window_sighting_falls_back_to_observed(self) -> None:
        with patch.dict(OBSERVED_BOSS_IDS, {1100: "Dreglord"}):
            self.assertEqual(boss_id_candidates(1100), {"Dreglord"})

    def test_unsighted_out_of_window_id_stays_unknown(self) -> None:
        self.assertEqual(boss_id_candidates(1100), set())

    def test_every_boss_matches_base_and_dlc_form(self) -> None:
        for base, name in KNOWN_BOSS_IDS.items():
            with self.subTest(name=name):
                self.assertEqual(boss_id_candidates(base), {name})
                self.assertEqual(boss_id_candidates(base + DLC_BOSS_ID_OFFSET), {name})

    def test_below_base_does_not_match(self) -> None:
        self.assertEqual(boss_id_candidates(999), set())
        self.assertEqual(boss_id_candidates(UNSET_SENTINEL), set())

    def test_windows_do_not_overlap(self) -> None:
        bases = sorted(KNOWN_BOSS_IDS)
        self.assertGreater(DLC_BOSS_ID_OFFSET - bases[-1], DRIFT_TOLERANCE)
        for low, high in zip(bases, bases[1:]):
            with self.subTest(low=low, high=high):
                self.assertGreater(high - low, DRIFT_TOLERANCE)
