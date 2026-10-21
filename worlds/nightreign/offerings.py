"""Otherworld Offerings for Elden Ring Nightreign, kept free of any memory/AP access so it can be
tested on its own (see test/test_offerings.py).

With otherworld_offerings on, received in-run items (Randomized Weapon/Talisman, Rune bundles) are
held as offerings instead of delivered automatically - gifts from other worlds that the Nightfarer
accepts when they need them. They're already held for free: an item stays pending until its
(index, player) key lands in one of client.py's _delivered_* sets, and those are persisted per
seed. All this module adds is the player's accept requests - how many of each held offering to let
through. client.py's normal delivery path still decides when an accepted offering can actually
land (in an Expedition, settled, not mid-flight, not a locked run), so one accepted in the
Roundtable Hold just waits for the next Expedition.

Requests are session-only on purpose: an offering left accepted-but-undelivered when the client
closes shouldn't arrive unannounced at the start of some later session.
"""
from __future__ import annotations

from .game_data import currency_bundle_names

OFFERING_WEAPON = "Randomized Weapon"
OFFERING_TALISMAN = "Randomized Talisman"
OFFERING_RUNES = tuple(currency_bundle_names("Runes"))
OFFERING_ITEMS = (OFFERING_WEAPON, OFFERING_TALISMAN, *OFFERING_RUNES)

# /accept's short names for each offering.
ACCEPT_ALIASES = {
    "weapon": OFFERING_WEAPON,
    "talisman": OFFERING_TALISMAN,
    "runes": "Rune Bundle",
    "heroic": "Heroic Rune Bundle",
}
assert set(ACCEPT_ALIASES.values()) == set(OFFERING_ITEMS), "Every offering needs an /accept alias."


class OfferingQueue:
    """How many of each held offering the player has accepted and isn't delivered yet."""

    def __init__(self) -> None:
        self._requested: dict[str, int] = {}

    def request(self, name: str, count: int, held: int) -> int:
        """Accepts up to `count` more of `name`, never more in total than the `held` copies
        actually waiting. Returns how many were added."""
        before = self.queued(name)
        after = max(before, min(before + count, held))
        self._requested[name] = after
        return after - before

    def queued(self, name: str) -> int:
        return self._requested.get(name, 0)

    def take(self, name: str, pending: set) -> list:
        """The pending keys to deliver now for `name` - the oldest first, at most as many as are
        accepted. Doesn't consume the request: call delivered() once each one actually lands."""
        return sorted(pending)[:self.queued(name)]

    def delivered(self, name: str, count: int = 1) -> None:
        self._requested[name] = max(0, self.queued(name) - count)

    def clear(self) -> None:
        self._requested.clear()

    def any_queued(self) -> bool:
        return any(self._requested.values())
