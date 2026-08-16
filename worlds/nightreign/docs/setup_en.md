# Elden Ring Nightreign Setup Guide

## Required Software

- Elden Ring Nightreign (Steam), no mods or game files need to be modified - the client only reads the running
  game's memory, it never writes to it.
- Archipelago, from the [Archipelago releases page](https://github.com/ArchipelagoMW/Archipelago/releases), plus
  this game's `.apworld` file installed via the Launcher's "Install APWorld" button (or dropped into your
  Archipelago install's `custom_worlds` folder if running from source).

## Configuring your YAML file

### What is a YAML file and why do I need one?

See the guide on setting up a basic YAML at the Archipelago setup
guide: [Basic Multiworld Setup Guide](/tutorial/Archipelago/setup/en)

### Where do I get a YAML file?

Once the `.apworld` is installed, use the Launcher's "Generate Template Options" button, or visit the Elden Ring
Nightreign player options page on your Archipelago webhost, to get a starting YAML. The defaults include every
character and every currently-supported Nightlord.

## Joining a MultiWorld Game

1. Launch Elden Ring Nightreign normally and get to the main menu or hub (Roundtable Hold) - the client needs the
   game process running to attach to it, but doesn't require any particular in-game state.
2. Open the Archipelago Launcher and click "Nightreign Client".
3. Enter the server address (and password, if any) when prompted, or pass `--connect` on the command line.
4. Play Nightreign normally. When you defeat a Nightlord, the client detects it within about a quarter-second and
   sends the check automatically - no further action needed.
5. Use the `/status` command in the client at any time to see what it's currently reading from the game (character,
   detected boss, hub/run state) - useful if a check doesn't seem to register.

## Notes

- If the client loses the game process (e.g. the game crashes or closes), it will keep retrying to reconnect - no
  need to restart the client.
- If you restart the client mid-session, it picks up where it left off: it keeps a small local record of what's
  already been checked for your current multiworld seed and slot, so nothing gets lost or double-sent.
