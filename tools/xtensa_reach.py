#!/usr/bin/env python3
"""Check Xtensa CALL8/L32R reach from pinned Ghidra SLEIGH; never patches bytes."""


def decode_call8(pc: int, raw: bytes) -> int:
    if len(raw) != 3:
        raise ValueError('CALL8 requires three bytes')
    value = int.from_bytes(raw, 'little')
    if value & 0x3f != 0x25:
        raise ValueError('not a CALL8 opcode')
    immediate = value >> 6
    if immediate & (1 << 17):
        immediate -= 1 << 18
    return ((pc & ~3) + 4 + (immediate << 2)) & 0xffffffff


def call8_reachable(pc: int, target: int) -> bool:
    delta = target - ((pc & ~3) + 4)
    return delta % 4 == 0 and -(1 << 17) <= delta // 4 < (1 << 17)


def decode_l32r(pc: int, raw: bytes) -> int:
    if len(raw) != 3:
        raise ValueError('L32R requires three bytes')
    value = int.from_bytes(raw, 'little')
    if value & 0xf != 1:
        raise ValueError('not an L32R opcode')
    immediate = (value >> 8) - (1 << 16)
    return (((pc + 3) & ~3) + (immediate << 2)) & 0xffffffff


def l32r_reachable(pc: int, literal_address: int) -> bool:
    delta = literal_address - ((pc + 3) & ~3)
    return delta % 4 == 0 and -(1 << 16) <= delta // 4 <= -1
