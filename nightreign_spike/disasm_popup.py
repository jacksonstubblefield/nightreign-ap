"""Disassemble popupMessageCall (and optionally follow calls a few levels deep) to find what it
actually writes/allocates for the popup banner's own state, since the manager sweep (see
popup_sweep_all.py) proved that state doesn't live in any of the 9 already-known managers.

Usage: python disasm_popup.py [--size 300] [--addr HEX]
    --addr lets you disassemble any other resolved address (e.g. a call target found here),
    without re-resolving popupMessageCall each time.
"""
import argparse

import capstone
import pymem
import pymem.pattern
import pymem.process

from popup_trigger import POPUP_CALL_AOB, PROCESS_NAME, _resolve_function_address


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=lambda s: int(s, 16), default=0x300)
    parser.add_argument("--addr", type=lambda s: int(s, 16), default=None)
    args = parser.parse_args()

    pm = pymem.Pymem(PROCESS_NAME)
    module = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME)

    if args.addr is not None:
        addr = args.addr
    else:
        addr = _resolve_function_address(pm, module, POPUP_CALL_AOB)
    print(f"Disassembling from {addr:#x} ({args.size:#x} bytes):\n")

    code = pm.read_bytes(addr, args.size)

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    for insn in md.disasm(code, addr):
        line = f"{insn.address:#014x}  {insn.bytes.hex():<24}  {insn.mnemonic} {insn.op_str}"
        for op in insn.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                target = insn.address + insn.size + op.mem.disp
                line += f"    ; -> {target:#x}"
        print(line)
        if insn.mnemonic == "ret":
            break


if __name__ == "__main__":
    main()
