"""One-shot read of GameMan's existing HUB_FLAG/NIGHTLORD_A/NIGHTLORD_B/BOSS_ID
fields, plus the GameDataMan+0xFA candidate byte found during the Everdark spike
(a counter that increments on Everdark-target selection in the pre-launch Target
menu - see nightreign-roadmap memory). Useful for spot-checking either field's
live value without a full dump-and-diff cycle, e.g. once actually loaded into an
Everdark expedition (GameMan's boss_id reads -1 from the Target menu alone, only
populating once an expedition is actually entered).

Usage: python boss_state_once.py
"""
import struct
import sys

from spike_common import AOB_TARGETS, kernel32, read_bytes, resolve_pid_module_slot

HUB_FLAG_OFFSET = 0xB40
NIGHTLORD_A_OFFSET = 0xB48
NIGHTLORD_B_OFFSET = 0xB4C
BOSS_ID_OFFSET = 0xB50

GAMEDATAMAN_EVERDARK_COUNTER_OFFSET = 0xFA

# Candidate Everdark boolean: 0x00 normal / 0x01 Everdark, survived a normal-vs-normal
# noise-control subtraction for Tricephalos (2026-08-23) - unlike +0xFA, this one is NOT known to
# populate at the pre-launch Target menu, only once actually loaded into an expedition. Still needs
# 2 more independent bosses before being trusted (see nightreign-roadmap memory).
GAMEDATAMAN_EVERDARK_FLAG_CANDIDATE_OFFSET = 0xE0


def main():
    try:
        h_process, gameman_slot = resolve_pid_module_slot(AOB_TARGETS["gameman"])
    except LookupError as e:
        print(e)
        sys.exit(1)

    try:
        gameman_addr = struct.unpack("<Q", read_bytes(h_process, gameman_slot, 8))[0]
        hub_flag = struct.unpack("<I", read_bytes(h_process, gameman_addr + HUB_FLAG_OFFSET, 4))[0]
        nl_a = struct.unpack("<i", read_bytes(h_process, gameman_addr + NIGHTLORD_A_OFFSET, 4))[0]
        nl_b = struct.unpack("<i", read_bytes(h_process, gameman_addr + NIGHTLORD_B_OFFSET, 4))[0]
        boss_id = struct.unpack("<i", read_bytes(h_process, gameman_addr + BOSS_ID_OFFSET, 4))[0]
        print(f"GameMan={gameman_addr:#x}  hub_flag={hub_flag:#x} ({hub_flag})  nightlord_a={nl_a}  nightlord_b={nl_b}  boss_id={boss_id}")
    finally:
        kernel32.CloseHandle(h_process)

    try:
        h_process, gamedataman_slot = resolve_pid_module_slot(AOB_TARGETS["gamedataman"])
    except LookupError as e:
        print(e)
        sys.exit(1)

    try:
        gamedataman_addr = struct.unpack("<Q", read_bytes(h_process, gamedataman_slot, 8))[0]
        counter = read_bytes(h_process, gamedataman_addr + GAMEDATAMAN_EVERDARK_COUNTER_OFFSET, 1)[0]
        flag_candidate = read_bytes(h_process, gamedataman_addr + GAMEDATAMAN_EVERDARK_FLAG_CANDIDATE_OFFSET, 1)[0]
        print(f"GameDataMan={gamedataman_addr:#x}  everdark_select_counter@+0xfa={counter}  everdark_flag_candidate@+0xe0={flag_candidate}")
    finally:
        kernel32.CloseHandle(h_process)


if __name__ == "__main__":
    main()
