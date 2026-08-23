# nightreign_spike/

Throwaway live memory-reverse-engineering tooling for Elden Ring Nightreign, used to find and
verify AOBs/struct offsets *before* porting a confirmed finding into the actual apworld
(`worlds/nightreign/game_data.py`, `memory_reader.py`, `memory_writer.py`). Nothing in this
folder is imported by or required for the shipped Archipelago world - it exists purely so future
RE sessions (mostly around Everdark, so far) have working tooling and prior capture data instead
of starting from scratch each time.

This folder currently lives only on the `everdark-data-mining` branch, not `main` - it's
intentionally not merged, since it's dev-only scratch work, not shipped code.

## Requirements

- A real, running `nightreign.exe`, launched **offline**. Online (or even solo with a debug/mod
  menu active) puts the process behind anti-cheat protection - `CreateToolhelp32Snapshot` will
  return `ERROR_ACCESS_DENIED` for every caller, elevated or not, until relaunched offline.
- Python 3.12+ (this machine's default `python` is 3.10 and doesn't have what's needed here -
  use `C:\Users\TC\AppData\Local\Programs\Python\Python312\python.exe`). No pip dependencies -
  everything here is raw `ctypes`, deliberately independent of `pymem` (unlike the production
  `memory_reader.py`), so it stays runnable even if the production read path is broken.

## Scripts

- `spike_common.py` - shared ctypes/AOB boilerplate (process/module resolution, raw
  `ReadProcessMemory`, AOB-to-regex, the `mov reg,[rip+disp32]` pointer-slot math). Import this
  rather than copy-pasting boilerplate into a new script.
- `nightreign_poc.py` - the original boss-ID discovery PoC; polls `GameMan`'s hub/boss-select
  fields and logs to `boss_id_log.csv`.
- `boss_state_once.py` - one-shot spot-check of the known `GameMan`/`GameDataMan` fields
  (boss_id, everdark flag, hub state, etc.) without a full dump-and-diff cycle. The fastest way to
  check a single candidate offset's live value.
- `gameman_dump.py` - dumps a resolved struct's raw bytes twice, ~3s apart (the gap lets
  `gameman_diff.py` exclude offsets that drift on their own - timers, animation, position - from
  offsets that differ because state actually changed). `--target gameman|gamedataman` selects
  which struct.
- `pointer_target_dump.py` - like `gameman_dump.py`, but dumps the object a struct-relative
  pointer field points to, rather than the struct itself.
- `gameman_diff.py` - diffs two labeled dump pairs (from either dump script above) for
  stable-but-different byte offsets. Struct-agnostic - works on any two labels regardless of what
  produced them.
- `disasm_context.py` - capstone disassembly around a live AOB match, for reading code context.
- `string_search.py` - ASCII/UTF-16LE string search across the live module (mostly useful for
  ruling things out - FromSoft games keep UI/localization text in packed resource files, not
  embedded in the exe, so this rarely finds what you'd hope).
- `boss_id_log.csv`, `dumps/` - accumulated capture data from past sessions. Keep adding to these
  rather than starting fresh each time - `dumps/` in particular has already saved real time by
  letting a later session re-diff without needing to reload expeditions in-game.

## Hard-earned methodology notes

- **Corroborate across 3+ independent bosses before trusting a candidate offset**, not 2 - every
  2-boss "hit" found in this project's history turned out to be noise once a 3rd boss was added.
- **Also diff the same mode against itself** (e.g. two separate normal-mode captures) before
  trusting a normal-vs-Everdark diff. A real-looking, even 3-boss-corroborated difference can still
  be per-instance noise (procedural expedition content, UI interaction counters, etc.) rather than
  a genuine state flag - this has produced multiple false leads that only same-mode-against-itself
  diffing caught. See the `nightreign-roadmap` project memory for the full incident history behind
  both of these rules.
