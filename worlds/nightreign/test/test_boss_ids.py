import unittest

from worlds.nightreign.game_data import DRIFT_TOLERANCE, KNOWN_BOSS_IDS, OBSERVED_BOSS_IDS


def _candidates(raw: int) -> set:
    # Mirrors memory_reader.match_boss_id()'s window check without importing pymem
    return {name for base, name in KNOWN_BOSS_IDS.items() if abs(raw - base) <= DRIFT_TOLERANCE}


class TestBossIds(unittest.TestCase):
    def test_observed_ids_resolve_to_their_boss(self) -> None:
        for raw, name in OBSERVED_BOSS_IDS.items():
            with self.subTest(raw=raw):
                self.assertEqual(_candidates(raw), {name})

    def test_windows_do_not_overlap(self) -> None:
        bases = sorted(KNOWN_BOSS_IDS)
        for low, high in zip(bases, bases[1:]):
            with self.subTest(low=low, high=high):
                self.assertGreater(high - low, 2 * DRIFT_TOLERANCE)
