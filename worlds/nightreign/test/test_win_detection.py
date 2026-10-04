import unittest

from worlds.nightreign.game_data import (DAY_PHASE_DAY_1, DAY_PHASE_DAY_2, DAY_PHASE_DAY_3,
                                         DAY_PHASE_NIGHT_1, DAY_PHASE_NIGHT_2,
                                         is_nightlord_kill_tick)


def _kill_ticks(trace: list) -> list:
    """Replays (buff_picks, day_phase) poll readings the way client.py's poll_loop does and
    returns the indices where a Nightlord kill is detected."""
    hits = []
    last = None
    for i, (buff, phase) in enumerate(trace):
        if is_nightlord_kill_tick(last, buff, phase):
            hits.append(i)
        if buff is not None:
            last = buff
    return hits


# Buff-pick counter / day-phase sequences recorded live on 2026-10-04, collapsed to one reading per
# change. Night Aspect's outcome pulse never fired, so this counter is its only win signal.
NIGHT_ASPECT_RUN = [
    (0, DAY_PHASE_DAY_1), (1, DAY_PHASE_DAY_1), (2, DAY_PHASE_DAY_1),
    (2, DAY_PHASE_NIGHT_1), (3, DAY_PHASE_NIGHT_1),            # Night 1 boss
    (3, DAY_PHASE_DAY_2), (4, DAY_PHASE_DAY_2), (5, DAY_PHASE_DAY_2), (6, DAY_PHASE_DAY_2),
    (6, DAY_PHASE_NIGHT_2), (7, DAY_PHASE_NIGHT_2),            # Night 2 boss
    (7, DAY_PHASE_DAY_3),                                      # arena; phase 1 end: no tick
    (8, DAY_PHASE_DAY_3),                                      # Night Aspect killed
]

AUGUR_RUN = [
    (0, DAY_PHASE_DAY_1), (1, DAY_PHASE_DAY_1),                # Perfumer ruin
    (2, DAY_PHASE_DAY_1),                                      # Sentient Pest invasion killed
    (3, DAY_PHASE_DAY_1),
    (3, DAY_PHASE_NIGHT_1), (4, DAY_PHASE_NIGHT_1),            # Night 1 boss
    (4, DAY_PHASE_DAY_2), (5, DAY_PHASE_DAY_2), (6, DAY_PHASE_DAY_2), (7, DAY_PHASE_DAY_2),
    (7, DAY_PHASE_NIGHT_2),                                    # Night 2: Winding Grace, no tick
    (7, DAY_PHASE_DAY_3),
    (8, DAY_PHASE_DAY_3),                                      # Augur killed
]


class TestNightlordKillTick(unittest.TestCase):
    def test_night_aspect_run_detects_only_the_kill(self) -> None:
        self.assertEqual(_kill_ticks(NIGHT_ASPECT_RUN), [len(NIGHT_ASPECT_RUN) - 1])

    def test_augur_run_detects_only_the_kill(self) -> None:
        self.assertEqual(_kill_ticks(AUGUR_RUN), [len(AUGUR_RUN) - 1])

    def test_buff_picks_outside_the_arena_never_count(self) -> None:
        for phase in (DAY_PHASE_DAY_1, DAY_PHASE_NIGHT_1, DAY_PHASE_DAY_2, DAY_PHASE_NIGHT_2):
            with self.subTest(phase=phase):
                self.assertFalse(is_nightlord_kill_tick(3, 4, phase))

    def test_first_reading_is_a_baseline_not_a_kill(self) -> None:
        # The client connecting (or a new Expedition starting) mid-arena must not fire a win.
        self.assertFalse(is_nightlord_kill_tick(None, 8, DAY_PHASE_DAY_3))

    def test_unreadable_or_unchanged_values_never_count(self) -> None:
        self.assertFalse(is_nightlord_kill_tick(7, None, DAY_PHASE_DAY_3))
        self.assertFalse(is_nightlord_kill_tick(7, 8, None))
        self.assertFalse(is_nightlord_kill_tick(8, 8, DAY_PHASE_DAY_3))
