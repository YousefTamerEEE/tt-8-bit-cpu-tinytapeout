#!/usr/bin/env python3
"""Assembler for the original YousefTamerEEE 8-bit Tiny Tapeout CPU (cpu-v2 branch).

Reads a 16-instruction assembly program and produces:
  - .hex: 16 lines of 16-bit words for simulation/reference (unwritten = F000)
  - .lst: annotated instruction listing
  - .csv: byte-level pin values to load each instruction into the real chip

Usage: python assembler.py program.asm
       python assembler.py program.asm -o build/program

Instruction bits: [15:12] opcode, [11:10] dest, [9:8] source, [7:0] imm.
This tool follows the checked RTL, not a generic 8-bit CPU instruction set.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DEPTH = 16
HALT_WORD = 0xF000

# name: (four-bit opcode, operand kind)
INSTRUCTIONS = {
    "LDI": (0x0, "imm"),
    "ADDI": (0x1, "imm"),
    "SUBI": (0x2, "imm"),
    "ANDI": (0x3, "imm"),
    "ORI": (0x4, "imm"),
    "XORI": (0x5, "imm"),
    "SHL": (0x6, "none"),
    "SHR": (0x7, "none"),
    "STR": (0x8, "dest"),  # Reg[dest] <- accumulator
    "LDR": (0x9, "source"), # accumulator <- Reg[source]
    "JMP": (0xA, "addr"),
    "JZ": (0xB, "addr"),
    "ADDR": (0xD, "source"),# accumulator <- accumulator + Reg[source]
    "XORR": (0xE, "source"),
    "HALT": (0xF, "none"),
}

@dataclass(frozen=True)
class SourceInstruction:
    address: int
    line: int
    text: str
    mnemonic: str
    operand: str

class AssemblyError(Exception):
    pass


def numeric(text: str, line: int) -> int:
    try:
        return int(text, 0) if not re.fullmatch(r"\d+", text) else int(text, 10)
    except ValueError:
        raise AssemblyError(f"line {line}: expected number, received {text!r}") from None


def parse(source: str) -> tuple[list[SourceInstruction], dict[str, int]]:
    instructions: list[SourceInstruction] = []
    labels: dict[str, int] = {}
    for line_number, raw in enumerate(source.splitlines(), 1):
        clean = raw.split(';', 1)[0].split('#', 1)[0].strip()
        if not clean:
            continue
        label_match = re.match(r"^([A-Za-z_][A-Za-z_0-9]*):", clean)
        if label_match:
            label = label_match.group(1).upper()
            if label in labels:
                raise AssemblyError(f"line {line_number}: duplicate label {label}")
            labels[label] = len(instructions)
            clean = clean[label_match.end():].strip()
            if not clean:
                continue
        if len(instructions) >= DEPTH:
            raise AssemblyError(f"line {line_number}: program exceeds {DEPTH} instruction words")
        parts = clean.replace(',', ' ').split()
        if not parts:
            continue
        mnemonic = parts[0].upper()
        if mnemonic not in INSTRUCTIONS:
            raise AssemblyError(f"line {line_number}: unknown instruction {mnemonic!r}")
        if len(parts) > 2:
            raise AssemblyError(f"line {line_number}: too many operands in {clean!r}")
        instructions.append(SourceInstruction(len(instructions), line_number,
                                               clean, mnemonic, parts[1] if len(parts) == 2 else ''))
    return instructions, labels


def encode(item: SourceInstruction, labels: dict[str, int]) -> int:
    op, kind = INSTRUCTIONS[item.mnemonic]
    operand = item.operand.upper()
    if kind == 'none':
        if operand:
            raise AssemblyError(f"line {item.line}: {item.mnemonic} takes no operand")
        return op << 12
    if not operand:
        raise AssemblyError(f"line {item.line}: {item.mnemonic} requires an operand")
    if kind in {'dest', 'source'}:
        match = re.fullmatch(r'R([0-3])', operand)
        if not match:
            raise AssemblyError(f"line {item.line}: register must be R0, R1, R2, or R3")
        reg = int(match.group(1))
        return (op << 12) | (reg << (10 if kind == 'dest' else 8))
    value = labels[operand] if kind == 'addr' and operand in labels else numeric(operand, item.line)
    limit = 15 if kind == 'addr' else 255
    if not 0 <= value <= limit:
        raise AssemblyError(f"line {item.line}: {item.mnemonic} operand must be 0..{limit}, got {value}")
    return (op << 12) | value


def assemble(source: str) -> tuple[list[int], list[tuple[int, str, int]]]:
    instructions, labels = parse(source)
    result = [HALT_WORD] * DEPTH
    listing: list[tuple[int, str, int]] = []
    for item in instructions:
        word = encode(item, labels)
        result[item.address] = word
        listing.append((item.address, item.text, word))
    return result, listing


def write_outputs(base: Path, words: list[int], listing: list[tuple[int, str, int]]) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    base.with_suffix('.hex').write_text(''.join(f'{w:04X}\n' for w in words), encoding='utf-8')
    base.with_suffix('.lst').write_text(
        'Address  Word  Source\n' +
        ''.join(f'{addr:02X}       {word:04X}  {src}\n' for addr, src, word in listing),
        encoding='utf-8')
    # Chip interface: uio_in[6]=program mode, [5]=program strobe,
    # [4]=0 low byte / 1 high byte, [3:0]=word address.
    # Hold each row for a rising clock edge; low MUST be captured before high.
    with base.with_suffix('.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['address', 'phase', 'ui_in_hex', 'uio_in_hex', 'expected_word'])
        for addr, _src, word in listing:
            writer.writerow([addr, 'LOW', f'{word & 0xFF:02X}', f'{0x60 | addr:02X}', f'{word:04X}'])
            writer.writerow([addr, 'HIGH', f'{word >> 8:02X}', f'{0x70 | addr:02X}', f'{word:04X}'])


def main() -> int:
    parser = argparse.ArgumentParser(description='Assemble programs for the 8-bit Tiny Tapeout CPU')
    parser.add_argument('input', type=Path, help='assembly source file (.asm)')
    parser.add_argument('-o', '--output', type=Path, help='output basename (default: same as input)')
    args = parser.parse_args()
    try:
        words, listing = assemble(args.input.read_text(encoding='utf-8'))
        out = args.output if args.output else args.input.with_suffix('')
        write_outputs(out, words, listing)
    except (AssemblyError, OSError) as exc:
        print(f'Assembly error: {exc}', file=sys.stderr)
        return 1
    print(f'Assembled {len(listing)} instruction(s); wrote {out}.hex, {out}.lst, {out}.csv')
    print('Each CSV row describes pin levels for ONE rising clock edge during programming.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
