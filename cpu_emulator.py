#!/usr/bin/env python3
"""Cycle-accurate architectural reference for the existing Tiny Tapeout 8-bit CPU.

Models the current cpu-v2 RTL (not hypothetical future features): 16x16 instruction
words, four 8-bit registers, 8-bit accumulator and 4-bit program counter.

Usage:
    python3 cpu_emulator.py demo_fibonacci.asm --expect-acc 13
    python3 cpu_emulator.py demo_counter.hex --trace

The model is independent of Verilog simulation. Later, its per-cycle states can
be compared against Icarus Verilog as differential verification.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

HALT_WORD = 0xF000
DEPTH = 16
MASK8 = 0xFF
MASK4 = 0xF


@dataclass(frozen=True)
class Cycle:
    index: int
    pc_before: int
    word: int
    acc_before: int
    acc_after: int
    pc_after: int
    regs_after: tuple[int, ...]
    halted: bool


@dataclass
class CPU:
    memory: list[int] = field(default_factory=lambda: [HALT_WORD] * DEPTH)
    pc: int = 0
    acc: int = 0
    registers: list[int] = field(default_factory=lambda: [0] * 4)
    cycles: int = 0

    def load(self, words: list[int]) -> None:
        """Preload words as if programmed before execution; pad with HALT."""
        if len(words) > DEPTH:
            raise ValueError("Program exceeds 16 instruction words")
        if any(not 0 <= w <= 0xFFFF for w in words):
            raise ValueError("Instruction words must be unsigned 16-bit numbers")
        self.memory = list(words) + [HALT_WORD] * (DEPTH - len(words))
        self.reset()

    def reset(self) -> None:
        """Reset accumulator/register/PC state, matching RTL after programming."""
        self.pc = self.acc = self.cycles = 0
        self.registers = [0] * 4

    @property
    def halted(self) -> bool:
        # In RTL, halted is combinationally decoded from the current word.
        return (self.memory[self.pc] >> 12) == 0xF

    def step(self) -> Cycle:
        """One positive clock edge, using pre-edge values for all updates."""
        pc_before = self.pc
        word = self.memory[pc_before]
        opcode = (word >> 12) & 0xF
        dest = (word >> 10) & 0x3
        source = (word >> 8) & 0x3
        imm = word & 0xFF
        acc_before = self.acc
        old_zero = (acc_before == 0)
        next_acc = acc_before
        next_pc = pc_before

        if opcode == 0xF:
            # HALT holds PC and the ALU state. It is decoded, not latched.
            pass
        else:
            # ALU register update: only opcodes 0..7, 9, D, E execute.
            if opcode == 0x0:  # LDI
                next_acc = imm
            elif opcode == 0x1:  # ADDI
                next_acc = (acc_before + imm) & MASK8
            elif opcode == 0x2:  # SUBI
                next_acc = (acc_before - imm) & MASK8
            elif opcode == 0x3:  # ANDI
                next_acc = acc_before & imm
            elif opcode == 0x4:  # ORI
                next_acc = acc_before | imm
            elif opcode == 0x5:  # XORI
                next_acc = acc_before ^ imm
            elif opcode == 0x6:  # SHL
                next_acc = (acc_before << 1) & MASK8
            elif opcode == 0x7:  # SHR
                next_acc = acc_before >> 1
            elif opcode == 0x8:  # STR: uses OLD accumulator as in RTL
                self.registers[dest] = acc_before
            elif opcode == 0x9:  # LDR
                next_acc = self.registers[source]
            elif opcode == 0xD:  # ADDR
                next_acc = (acc_before + self.registers[source]) & MASK8
            elif opcode == 0xE:  # XORR
                next_acc = acc_before ^ self.registers[source]
            # Unsupported opcode C has no ALU effect and advances PC.
            if opcode == 0xA or (opcode == 0xB and old_zero):
                next_pc = imm & MASK4
            else:
                next_pc = (pc_before + 1) & MASK4

        self.acc = next_acc
        self.pc = next_pc
        self.cycles += 1
        return Cycle(self.cycles, pc_before, word, acc_before, self.acc,
                     self.pc, tuple(self.registers), self.halted)

    def run(self, max_cycles: int = 1000) -> list[Cycle]:
        if max_cycles <= 0:
            raise ValueError("max_cycles must be positive")
        trace: list[Cycle] = []
        while not self.halted and len(trace) < max_cycles:
            trace.append(self.step())
        if not self.halted:
            raise RuntimeError(f"CPU did not reach HALT in {max_cycles} cycles (pc={self.pc})")
        return trace


def load_program(path: Path) -> list[int]:
    if path.suffix.lower() == '.asm':
        # Use the existing project assembler to derive actual machine words.
        from assembler import assemble
        words, _listing = assemble(path.read_text(encoding='utf-8'))
        return words
    if path.suffix.lower() == '.hex':
        words = []
        for line_no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            entry = line.split('#', 1)[0].strip()
            if entry:
                try:
                    words.append(int(entry, 16))
                except ValueError as exc:
                    raise ValueError(f"Invalid hex at line {line_no}: {entry!r}") from exc
        return words
    raise ValueError("Input must be an assembler .asm or machine-code .hex file")


def main() -> int:
    parser = argparse.ArgumentParser(description='Reference emulator for the verified 8-bit CPU')
    parser.add_argument('program', type=Path, help='.asm or .hex program')
    parser.add_argument('--trace', action='store_true', help='Print execution for every instruction')
    parser.add_argument('--expect-acc', type=lambda x: int(x, 0), help='Fail if final accumulator differs')
    parser.add_argument('--max-cycles', type=int, default=1000)
    args = parser.parse_args()

    cpu = CPU()
    try:
        cpu.load(load_program(args.program))
        trace = cpu.run(args.max_cycles)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')

    if args.trace:
        print('Cycle  PC  Word  Acc(before -> after)  PC(next)  Regs(after)')
        for t in trace:
            print(f'{t.index:5}  {t.pc_before:02X}  {t.word:04X}  '
                  f'{t.acc_before:3} -> {t.acc_after:3}           '
                  f'{t.pc_after:02X}        {t.regs_after}')
    print(f'PASS: HALT reached | cycles={len(trace)} | ACC={cpu.acc} | '
          f'PC={cpu.pc} | Registers={cpu.registers}')
    if args.expect_acc is not None and cpu.acc != args.expect_acc:
        print(f'FAIL: expected ACC={args.expect_acc}, got {cpu.acc}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
