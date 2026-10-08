"""DeathLink send-side detection for Elden Ring Nightreign, kept free of any memory/AP access so it
can be replayed against recorded HP/animation traces (see test/test_death_link.py).

Every time the local player's HP hits 0 starts one "down episode", which lasts until HP is back
above 0 (saved, or respawned) or the run ends. At most one DeathLink is sent per episode:
  - "downed" mode sends as soon as HP hits 0.
  - "dead" mode sends once the episode is known to be a full death - a dying animation (see
    game_data.DYING_ANIMATION_RANGE), a respawn at full HP, or the run ending while still down
    without a win (e.g. a co-op wipe).
An episode that a received DeathLink started (client.py calls link_applied() right after writing
HP 0) never sends anything, all the way through to its end - so a party of linked players going
down together off one DeathLink doesn't echo it back out.
"""
from __future__ import annotations

from typing import Optional

from .game_data import is_dying_animation

DEATH_LINK_MODES = ("off", "dead", "downed")

# How long after a received DeathLink's HP write a fresh down is still attributed to it - only a
# few poll ticks are needed, the write lands on the very next read.
RECEIVED_LINK_WINDOW_SECONDS = 2.0


class DeathLinkDetector:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._in_episode = False
        self._caused_by_link = False
        self._sent = False
        self._link_applied_at: Optional[float] = None

    @property
    def downed(self) -> bool:
        """True while the local player is down (HP 0) - a received DeathLink is ignored then."""
        return self._in_episode

    def link_applied(self, now: float) -> None:
        """A received DeathLink just wrote HP 0 - the down it causes mustn't be sent back out."""
        self._link_applied_at = now

    def update(self, hp: Optional[int], max_hp: Optional[int], animation: Optional[int], mode: str,
               now: float) -> bool:
        """Feed one in-Expedition poll reading. True means send a DeathLink now."""
        if (self._link_applied_at is not None
                and now - self._link_applied_at > RECEIVED_LINK_WINDOW_SECONDS):
            self._link_applied_at = None
        if hp is None:
            return False

        if hp > 0:
            # A save comes back at 50% HP; a respawn after a full death comes back at max.
            respawned = bool(max_hp) and hp >= max_hp
            send = self._in_episode and mode == "dead" and respawned and self._may_send()
            self._in_episode = False
            return send

        if not self._in_episode:
            self._in_episode = True
            self._caused_by_link = self._link_applied_at is not None
            self._link_applied_at = None
            self._sent = False
        if not self._may_send():
            return False
        if mode == "downed" or (mode == "dead" and animation is not None
                                and is_dying_animation(animation)):
            self._sent = True
            return True
        return False

    def run_ended(self, mode: str, won: bool) -> bool:
        """Call when the run ends (back to the hub). True means send a DeathLink now: still down,
        never saved, and the run wasn't won (a teammate can win while you're down)."""
        send = self._in_episode and mode == "dead" and not won and self._may_send()
        self.reset()
        return send

    def _may_send(self) -> bool:
        return not self._caused_by_link and not self._sent
