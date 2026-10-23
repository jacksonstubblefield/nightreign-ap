# Elden Ring Nightreign

This is early alpha and these pages are still being developed. No third party mods needed, this runs straight out of the client.

## What is the goal / victory condition?

Configurable via the `goal` option:

- **Night Aspect** (default): defeat Night Aspect, the vanilla game's own ending/credits boss - any
  one of your opted-into characters' wins counts.
- **All Bosses All Characters**: defeat every Nightlord you opted into, with every character you
  opted into (only applies when `check_style` is `boss_per_character` - in `boss`
  mode this is just "defeat every Nightlord you opted into").
- **All Bosses**: defeat every Nightlord you opted into at least once, with any
  one of your opted-into characters - no need to clear every character x Nightlord
  combination.
- **Random**: at generation time, a random number of objectives (bounded by
  `goal_random_min`/`goal_random_max`) are chosen as the required set. With `check_style` set to
  `boss_per_character`, each objective is a specific "Defeat X as Y" drawn from your included
  characters and Nightlords; in `boss` mode, each is just "Defeat X" for one of your included
  Nightlords.

For every goal except Night Aspect, "Nightlords you opted into" means everything in
`included_nightlords`, and each Everdark Sovereign you include there counts as its own boss.

Whichever goal is picked, every included character x Nightlord combination still generates as
a location check - the goal option only changes which of them are required to finish.

## DeathLink

**New and not yet tested with other players - please report any feedback or bugs.**

Set with the `death_link` option:

- **Off** (default): no DeathLink.
- **Dead**: a DeathLink goes out only when you fully die. Being downed and then saved (a
  teammate's revive, Wending Grace, the solo boss-fight revive) doesn't count.
- **Downed**: a DeathLink goes out as soon as you're downed, even if you're saved a moment later.

Solo, outside the three boss fights, there's no downed state - you die outright, so both modes
behave the same there.

When someone else's DeathLink reaches you, your HP drops to 0 and the game handles it exactly like
a fatal hit: in a boss fight or in co-op you're downed and can still be saved, otherwise you die. A
full death in the Nightlord fight ends the expedition. A red banner on the game shows who died.
DeathLinks that arrive while you're in the Roundtable Hold, already down, or flying in are skipped.

If several linked players are in the same co-op party, a down caused by a received DeathLink is
never sent back out, so one death doesn't bounce around the party.

Type `/deathlink` in the client to turn it on or off mid-session, or `/deathlink dead` /
`/deathlink downed` / `/deathlink off` to pick a mode.

## Otherworld Offerings

**New and not yet tested in a real game - please report any feedback or bugs.**

With the `otherworld_offerings` option on, received weapons, talismans and runes don't arrive on
their own. They're held as offerings, gifts sent from other worlds to aid you against the Night,
until you accept them. Save them for a run that needs them, like a tough Nightlord or catching up
after a death, instead of spending them on an easy run.

Accept offerings from the client's **Offerings** tab (only shown when the option is on), or type:

- `/offerings`: list the offerings you're holding.
- `/accept weapon`, `/accept talisman`, `/accept runes` (a 5,000 Rune Bundle) or
  `/accept heroic` (a 100,000 Heroic Rune Bundle), followed by a count or `all`. For example,
  `/accept runes 3`.
- `/accept cancel`: take back every accepted offering that hasn't arrived yet.

An accepted offering arrives the same way any other received item does: once you're in an
Expedition and it has started, and for weapons and talismans, once you're on the ground. One
accepted in the Roundtable Hold waits for your next Expedition. Nothing arrives on a run whose
boss or character you haven't unlocked yet. Accepted offerings that haven't arrived yet are
forgotten when the client closes, but the offerings themselves are kept.

## Credits

Thanks to the Cheat Engine data miners who laid the foundation
for this work.
