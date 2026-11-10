#!/usr/bin/env python3
"""Broader, reproducible instruction-level RTL vs Python reference verification.

Run from the Tiny Tapeout project root:
    python3 test_instruction_suite.py

Tests every implemented opcode, all four register addresses, branching,
8-bit arithmetic boundaries, a 16-word program, and deterministic random
programs. The real Tiny Tapeout input pins load each program. Compares PC,
ACC, R0-R3, and HALT after every execution cycle. No RTL or ASIC changes.
"""
from __future__ import annotations

import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from assembler import assemble
from cpu_emulator import CPU
from test_differential import TB

ROOT = Path(__file__).resolve().parent

# Expected values below are independent known results, not values calculated
# by the reference CPU. A mismatch is reported even if RTL and model agree.
DIRECTED: list[tuple[str, str, int]] = [
    ("LDI zero",       "LDI 0\nHALT", 0),
    ("LDI maximum",    "LDI 255\nHALT", 255),
    ("ADDI standard",   "LDI 17\nADDI 25\nHALT", 42),
    ("ADDI overflow",   "LDI 255\nADDI 1\nHALT", 0),
    ("SUBI standard",   "LDI 25\nSUBI 17\nHALT", 8),
    ("SUBI underflow",  "LDI 0\nSUBI 1\nHALT", 255),
    ("ANDI",            "LDI 0xA5\nANDI 0x0F\nHALT", 5),
    ("ORI",             "LDI 0xA0\nORI 0x0F\nHALT", 175),
    ("XORI",            "LDI 0xA5\nXORI 0xFF\nHALT", 90),
    ("SHL normal",      "LDI 21\nSHL\nHALT", 42),
    ("SHL drops bit 7", "LDI 128\nSHL\nHALT", 0),
    ("SHR normal",      "LDI 85\nSHR\nHALT", 42),
    ("SHR drops bit 0", "LDI 1\nSHR\nHALT", 0),
    ("JMP skips code",  "JMP done\nLDI 99\ndone: LDI 42\nHALT", 42),
    ("JZ taken",       "LDI 0\nJZ done\nLDI 99\ndone: LDI 42\nHALT", 42),
    ("JZ not taken",   "LDI 1\nJZ done\nLDI 42\ndone: HALT", 42),
    ("JZ uses old ACC", "LDI 1\nSUBI 1\nJZ done\nLDI 99\ndone: LDI 42\nHALT", 42),
    ("loop and branches", "LDI 0\nSTR R0\nloop: LDR R0\nADDI 1\nSTR R0\nSUBI 4\nJZ done\nJMP loop\ndone: LDR R0\nHALT", 4),
    ("16-word memory",  "\n".join(["LDI 1"] * 14 + ["ADDI 2", "HALT"]), 3),
]

for reg in range(4):
    DIRECTED.extend([
        (f"STR/LDR R{reg}",
         f"LDI {40 + reg}\nSTR R{reg}\nLDI 0\nLDR R{reg}\nHALT", 40 + reg),
        (f"ADDR R{reg}",
         f"LDI {40 + reg}\nSTR R{reg}\nLDI 2\nADDR R{reg}\nHALT", 42 + reg),
        (f"XORR R{reg}",
         f"LDI {40 + reg}\nSTR R{reg}\nLDI {40 + reg}\nXORR R{reg}\nHALT", 0),
    ])


def random_programs(count: int = 30) -> list[tuple[str, list[int], int | None]]:
    """Deterministic programs, no uncontrolled jumps or infinite loops."""
    rng = random.Random(20261110)
    options = ("LDI", "ADDI", "SUBI", "ANDI", "ORI", "XORI", "SHL", "SHR",
               "STR", "LDR", "ADDR", "XORR")
    generated: list[tuple[str, list[int], int | None]] = []
    for i in range(count):
        instructions: list[str] = []
        for _ in range(rng.randint(3, 15)):
            op = rng.choice(options)
            if op in ("STR", "LDR", "ADDR", "XORR"):
                instructions.append(f"{op} R{rng.randrange(4)}")
            elif op in ("SHL", "SHR"):
                instructions.append(op)
            else:
                instructions.append(f"{op} {rng.randrange(256)}")
        # Reserve exactly one word for HALT; never overfill 16-word memory.
        words, _ = assemble("\n".join(instructions[:15] + ["HALT"]))
        generated.append((f"random seed=20261110 #{i+1:02}", words, None))
    return generated


def compare(name: str, words: list[int], expected: int | None, exe: Path, scratch: Path) -> int:
    model = CPU()
    model.load(words)
    trace = model.run(max_cycles=500)
    if expected is not None and model.acc != expected:
        raise RuntimeError(f"{name}: independent expected ACC={expected}, model ACC={model.acc}")
    (scratch / "program.hex").write_text(
        "".join(f"{word:04X}\n" for word in words), encoding="ascii"
    )
    run = subprocess.run(["vvp", str(exe)], cwd=scratch, capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError(f"{name}: RTL simulation failed:\n{run.stdout}{run.stderr}")
    actual = []
    for line in run.stdout.splitlines():
        if line.startswith("DIFF,"):
            fields = line.split(",")[1:]
            if len(fields) != 8 or any(not re.fullmatch(r"\d+", value) for value in fields):
                raise RuntimeError(f"{name}: invalid/unknown RTL state: {line}")
            actual.append(tuple(int(value) for value in fields))
    if len(actual) != len(trace):
        raise RuntimeError(f"{name}: cycle count mismatch RTL={len(actual)} Python={len(trace)}")
    for n, (rtl, ref) in enumerate(zip(actual, trace), 1):
        want = (ref.index, ref.pc_after, ref.acc_after, *ref.regs_after, int(ref.halted))
        if rtl != want:
            labels = ("cycle", "PC", "ACC", "R0", "R1", "R2", "R3", "HALT")
            diff = ", ".join(f"{label} RTL={got} Python={exp}"
                             for label, got, exp in zip(labels, rtl, want) if got != exp)
            raise RuntimeError(f"{name}, cycle {n}: {diff}")
    if expected is not None and actual and actual[-1][2] != expected:
        raise RuntimeError(f"{name}: independent expected ACC={expected}, RTL={actual[-1][2]}")
    print(f"PASS {name}: {len(trace)} cycles, ACC={model.acc}")
    return len(trace)


def main() -> int:
    if not shutil.which("iverilog") or not shutil.which("vvp"):
        print("ERROR: Icarus Verilog is required (available in your Codespace).", file=sys.stderr)
        return 1
    sources = sorted((ROOT / "src").glob("*.v"))
    if not sources:
        print("ERROR: Missing src/*.v. Run from the project repository.", file=sys.stderr)
        return 1
    scenarios = []
    for name, asm, expect in DIRECTED:
        words, _ = assemble(asm)
        scenarios.append((name, words, expect))
    # Opcode C is reserved (unsupported): should not modify state and should advance PC.
    scenarios.append(("reserved opcode C", [0xC000, 0x002A, 0xF000] + [0xF000] * 13, 42))
    scenarios.extend(random_programs())

    with tempfile.TemporaryDirectory(prefix="cpu-instruction-suite-") as work:
        scratch = Path(work)
        (scratch / "differential_tb.v").write_text(TB, encoding="utf-8")
        executable = scratch / "sim"
        build = subprocess.run(
            ["iverilog", "-g2012", "-s", "differential_tb", "-o", str(executable),
             str(scratch / "differential_tb.v"), *map(str, sources)],
            capture_output=True, text=True,
        )
        if build.returncode:
            print("ERROR: Verilog compilation failed:\n" + build.stdout + build.stderr, file=sys.stderr)
            return 1
        cycle_count = 0
        for name, words, expected in scenarios:
            try:
                cycle_count += compare(name, words, expected, executable, scratch)
            except (RuntimeError, ValueError, OSError) as exc:
                print(f"FAIL: {exc}", file=sys.stderr)
                return 1
    print(f"PASS: {len(scenarios)} directed/random CPU programs, "
          f"{cycle_count} instruction cycles matched RTL vs Python.")
    print("Coverage: all 15 supported assembler instructions, reserved opcode C, "
          "all 4 registers, JZ taken/not-taken, JMP, boundaries, loops.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
