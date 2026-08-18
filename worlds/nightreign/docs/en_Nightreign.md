# Elden Ring Nightreign

## Where is the options page?

The [player options page for this game](../player-options) contains all the options you need to configure and export
a config file.

## What does this randomizer do?

This is an early-alpha **tracker-only** integration for Elden Ring Nightreign. The game itself is not modified and
nothing is locked or gated in-game - you play a completely normal game. A location check is "defeat Nightlord X as
character Y", detected by an external client that passively reads the running game's memory (no code injection, no
game files touched). Received items are flavorful "trophy" items with **no in-game effect** in this version - real
item/character gating is a separate, unresearched effort for a future version.

## What is considered a location check?

Defeating a given Nightlord while playing as a given character, for every character x Nightlord combination you
opted into via the `included_characters` and `included_nightlords` options. Defaults to all characters and all
currently-supported Nightlords.

## When the player receives an item, what happens?

Nothing in-game. You'll see a log message/toast for flavor, but items in this version don't affect the game.

## What is the goal / victory condition?

Configurable via the `goal` option:

- **all_bosses** (default): defeat every Nightlord you opted into, with every character you
  opted into (only applies when `bosses_with_characters` is `boss_and_character` - in `boss`
  mode this is just "defeat every Nightlord you opted into").
- **night_aspect**: defeat Night Aspect, the vanilla game's own ending/credits boss - any one
  of your opted-into characters' wins counts.
- **all_bosses_any_character**: defeat every Nightlord you opted into at least once, with any
  one of your opted-into characters - no need to clear every character x Nightlord
  combination.
- **random_subset**: at generation time, a random number of specific "Defeat X as Y" objectives
  (bounded by `goal_random_min`/`goal_random_max`) are chosen from your included characters
  and Nightlords as the required set. Requires `bosses_with_characters` to be
  `boss_and_character`.

Whichever goal is picked, every included character x Nightlord combination still generates as
a location check - the goal option only changes which of them are required to finish.

## A note on detection accuracy (early alpha)

Boss identification is based on a game-memory value that was found and tested by hand across several live sessions,
not something FromSoftware documents or guarantees. It's solid for the currently-supported roster, but if the client
ever can't confidently identify which Nightlord you just defeated, it will **tell you** instead of guessing - you'll
see a message like `boss_id 72 not found - please report this to the mod owner with your Expedition's Nightlord`.
If you see this, please report it (with the Nightlord you actually fought) so the roster can be corrected. This is
by design: an early alpha should surface uncertainty rather than silently mis-record a check.

## Credits

Thanks to **thefifthmatt**, for their work on Elden Ring Nightreign randomization, which laid groundwork this
project builds on.
