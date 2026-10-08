import unittest

from worlds.nightreign.death_link import RECEIVED_LINK_WINDOW_SECONDS, DeathLinkDetector

# (hp, animation) poll readings recorded live on 2026-10-08 (solo, max HP 240), collapsed to one
# reading per change.
FIELD_DEATH = [
    (10, 2022100), (0, 2022100), (0, 17022), (0, 18022),
    (240, 18022), (240, 63000), (240, 2000000),                # respawn, flying back in
]
REVIVE_SAVE = [                                                # Night 1 boss, once-per-day revive
    (9, 2020100), (0, 2020100), (0, 17342), (0, 70020),
    (120, 70020), (120, 18300), (133, 17650), (240, 2000000),
]
GRACE_SAVE = [                                                 # Night 1 boss, Wending Grace
    (5, 2000000), (0, 2000000), (0, 17302),
    (120, 17302), (120, 18300), (133, 17650), (240, 2000000),
]
BOSS_DEATH = [                                                 # Night 1 boss, no saves left
    (44, 5102), (0, 5122), (0, 17002), (0, 18002), (0, 17002), (0, 18002),
]
MAX_HP = 240


def _replay(detector: DeathLinkDetector, trace: list, mode: str, start: float = 0.0) -> list:
    """Indices in `trace` where the detector says to send, polling once per second."""
    return [i for i, (hp, anim) in enumerate(trace)
            if detector.update(hp, MAX_HP, anim, mode, start + i)]


class TestDeathLinkSend(unittest.TestCase):
    def test_off_never_sends(self) -> None:
        for trace in (FIELD_DEATH, REVIVE_SAVE, GRACE_SAVE, BOSS_DEATH):
            self.assertEqual(_replay(DeathLinkDetector(), trace, "off"), [])

    def test_downed_sends_once_when_hp_hits_zero(self) -> None:
        for trace in (FIELD_DEATH, REVIVE_SAVE, GRACE_SAVE, BOSS_DEATH):
            self.assertEqual(_replay(DeathLinkDetector(), trace, "downed"), [1])

    def test_dead_sends_on_dying_animation(self) -> None:
        self.assertEqual(_replay(DeathLinkDetector(), FIELD_DEATH, "dead"), [2])
        self.assertEqual(_replay(DeathLinkDetector(), BOSS_DEATH, "dead"), [2])

    def test_dead_ignores_saved_downs(self) -> None:
        self.assertEqual(_replay(DeathLinkDetector(), REVIVE_SAVE, "dead"), [])
        self.assertEqual(_replay(DeathLinkDetector(), GRACE_SAVE, "dead"), [])

    def test_dead_falls_back_to_full_hp_respawn(self) -> None:
        # An unseen dying animation (e.g. a co-op death) still counts once you respawn at max HP.
        trace = [(30, 2000000), (0, 2000000), (0, 99999), (240, 63000)]
        self.assertEqual(_replay(DeathLinkDetector(), trace, "dead"), [3])

    def test_dead_falls_back_to_run_lost_while_down(self) -> None:
        detector = DeathLinkDetector()
        _replay(detector, [(30, 2000000), (0, 2000000), (0, 70020)], "dead")
        self.assertTrue(detector.run_ended("dead", won=False))

    def test_no_send_when_run_won_while_down(self) -> None:
        detector = DeathLinkDetector()
        _replay(detector, [(30, 2000000), (0, 70020)], "dead")
        self.assertFalse(detector.run_ended("dead", won=True))

    def test_consecutive_deaths_each_send(self) -> None:
        detector = DeathLinkDetector()
        sends = _replay(detector, FIELD_DEATH + FIELD_DEATH, "dead")
        self.assertEqual(sends, [2, len(FIELD_DEATH) + 2])


class TestDeathLinkReceived(unittest.TestCase):
    def test_down_caused_by_received_link_is_never_sent(self) -> None:
        for mode in ("dead", "downed"):
            detector = DeathLinkDetector()
            detector.link_applied(now=0.0)
            sends = _replay(detector, [(240, 2000000)] + FIELD_DEATH[1:], mode, start=0.5)
            self.assertEqual(sends, [], mode)
            self.assertFalse(detector.run_ended(mode, won=False))

    def test_stale_received_link_does_not_swallow_a_later_real_death(self) -> None:
        detector = DeathLinkDetector()
        detector.link_applied(now=0.0)
        start = RECEIVED_LINK_WINDOW_SECONDS + 1
        self.assertEqual(_replay(detector, FIELD_DEATH, "downed", start=start), [1])

    def test_real_death_after_received_link_episode_sends(self) -> None:
        detector = DeathLinkDetector()
        detector.link_applied(now=0.0)
        first = [(240, 2000000)] + FIELD_DEATH[1:]
        sends = _replay(detector, first + FIELD_DEATH, "downed", start=0.5)
        self.assertEqual(sends, [len(first) + 1])

    def test_downed_flag(self) -> None:
        detector = DeathLinkDetector()
        detector.update(0, MAX_HP, 17302, "dead", 0.0)
        self.assertTrue(detector.downed)
        detector.update(120, MAX_HP, 18300, "dead", 1.0)
        self.assertFalse(detector.downed)


if __name__ == "__main__":
    unittest.main()
