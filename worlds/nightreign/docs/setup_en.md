# Elden Ring Nightreign Setup Guide

## Required Software

- Elden Ring Nightreign (Steam), no mods or game files need to be modified. The client mostly reads the running
  game's memory to detect what you're doing; if you have the `gate_boss_access` option enabled (on by default), it
  also writes to the game's memory to set the same event flags the game itself uses, revealing secondary Nightlords
  as you receive their "Access" items. It never touches game files on disk.
- Archipelago, from the [Archipelago releases page](https://github.com/ArchipelagoMW/Archipelago/releases), plus
  this game's `.apworld` file installed via the Launcher's "Install APWorld" button (or dropped into your
  Archipelago install's `custom_worlds` folder if running from source).

## Turning off Anti-Cheat
This can't be run with Anti-Cheat because it modifies the game's memory. There's a guide on how to disable Anti-Cheat [here](https://www.nexusmods.com/eldenringnightreign/mods/5).

## Other Mods
Play with other mods at your own risk - given how early access this is, this should be compatible with mods.