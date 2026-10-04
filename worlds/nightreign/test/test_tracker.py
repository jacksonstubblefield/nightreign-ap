import unittest

from worlds.nightreign import tracker
from worlds.nightreign.Locations import location_name_to_id, location_name_win_count
from worlds.nightreign.tracker import AVAILABLE, DONE, LOCKED, boss_location_names


def _ids(nightlord, character=None, everdark=False) -> set:
    return {location_name_to_id[n] for n in boss_location_names(nightlord, character, everdark)}


class TestBossOnlyRows(unittest.TestCase):
    def _rows(self, owned, sent, gate=True):
        slot = _ids("Tricephalos") | _ids("Gaping Jaw")
        return {
            r.name: r.status for r in tracker.boss_rows(
                owned, slot, sent, ["Tricephalos", "Gaping Jaw"], set(), [], False, gate, False,
            )
        }

    def test_locked_available_done(self) -> None:
        rows = self._rows({"Tricephalos Access"}, set())
        self.assertEqual(rows, {"Tricephalos": AVAILABLE, "Gaping Jaw": LOCKED})
        rows = self._rows({"Tricephalos Access"}, _ids("Tricephalos"))
        self.assertEqual(rows["Tricephalos"], DONE)

    def test_unsent_night_check_keeps_boss_green(self) -> None:
        night2 = location_name_to_id["Clear Night 2 vs Tricephalos"]
        rows = self._rows({"Tricephalos Access"}, _ids("Tricephalos") - {night2})
        self.assertEqual(rows["Tricephalos"], AVAILABLE)

    def test_all_sent_is_gray_even_without_access(self) -> None:
        self.assertEqual(self._rows(set(), _ids("Gaping Jaw"))["Gaping Jaw"], DONE)

    def test_ungated_bosses_are_available(self) -> None:
        self.assertEqual(set(self._rows(set(), set(), gate=False).values()), {AVAILABLE})

    def test_bosses_without_slot_locations_are_skipped(self) -> None:
        rows = tracker.boss_rows(set(), _ids("Tricephalos"), set(), ["Tricephalos", "Gaping Jaw"],
                                 set(), [], False, True, False)
        self.assertEqual([r.name for r in rows], ["Tricephalos"])


class TestPerCharacterRows(unittest.TestCase):
    characters = ["Wylder", "Guardian"]

    def _boss(self, owned, sent, everdark=False):
        slot = set()
        for c in self.characters:
            slot |= _ids("Gaping Jaw", c, everdark)
        rows = tracker.boss_rows(
            owned, slot, sent, [] if everdark else ["Gaping Jaw"],
            {"Gaping Jaw"} if everdark else set(), self.characters, True, True, True,
        )
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_boss_green_if_any_character_green(self) -> None:
        boss = self._boss({"Gaping Jaw Access", "Wylder Character Access"}, set())
        self.assertEqual(boss.status, AVAILABLE)
        self.assertEqual({c.name: c.status for c in boss.children},
                         {"Wylder": AVAILABLE, "Guardian": LOCKED})

    def test_boss_red_when_only_red_remains(self) -> None:
        owned = {"Gaping Jaw Access", "Wylder Character Access"}
        boss = self._boss(owned, _ids("Gaping Jaw", "Wylder"))
        self.assertEqual(boss.status, LOCKED)
        self.assertEqual({c.name: c.status for c in boss.children},
                         {"Wylder": DONE, "Guardian": LOCKED})

    def test_missing_boss_access_locks_every_character(self) -> None:
        boss = self._boss({"Wylder Character Access", "Guardian Character Access"}, set())
        self.assertEqual({c.status for c in boss.children}, {LOCKED})
        self.assertEqual(boss.status, LOCKED)

    def test_boss_gray_once_every_character_cleared(self) -> None:
        sent = _ids("Gaping Jaw", "Wylder") | _ids("Gaping Jaw", "Guardian")
        self.assertEqual(self._boss(set(), sent).status, DONE)

    def test_everdark_uses_its_own_access_item(self) -> None:
        owned = {"Gaping Jaw Access", "Wylder Character Access", "Guardian Character Access"}
        self.assertEqual(self._boss(owned, set(), everdark=True).status, LOCKED)
        boss = self._boss(owned | {"Everdark Gaping Jaw Access"}, set(), everdark=True)
        self.assertEqual((boss.name, boss.status), ("Everdark Gaping Jaw", AVAILABLE))


class TestOtherRows(unittest.TestCase):
    def test_character_rows(self) -> None:
        rows = tracker.character_rows({"Wylder Character Access"}, ["Wylder", "Guardian"])
        self.assertEqual([(r.name, r.status) for r in rows],
                         [("Wylder", AVAILABLE), ("Guardian", LOCKED)])

    def test_win_count_rows_only_green_or_gray(self) -> None:
        one, five = (location_name_to_id[location_name_win_count(n)] for n in (1, 5))
        rows = tracker.win_count_rows({one, five}, {one}, [1, 5, 10])
        self.assertEqual([(r.name, r.status) for r in rows],
                         [("Win 1 Expedition", DONE), ("Win 5 Expeditions", AVAILABLE)])
