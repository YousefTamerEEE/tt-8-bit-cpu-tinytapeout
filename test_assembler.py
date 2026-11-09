#!/usr/bin/env python3
"""Regression tests for the Tiny Tapeout 8-bit CPU Python assembler.

Run from the repository root on the cpu-v2 branch:
    python3 -m unittest -v test_assembler.py

These check assembly encoding, labels, input validation, output formats and
chip-programming CSV generation. Hardware execution is separately checked
by the Verilog test_counter.v, test_multiply.v and test_fibonacci.v benches.
"""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from assembler import AssemblyError, assemble, write_outputs

ROOT = Path(__file__).resolve().parent
ASSEMBLER = ROOT / 'assembler.py'


class AssemblerTests(unittest.TestCase):
    def single(self, line, expected):
        words, listing = assemble(line + '\n')
        self.assertEqual(words[0], expected, msg=line)
        self.assertEqual(len(words), 16)
        self.assertEqual(len(listing), 1)
        self.assertEqual(words[1:], [0xF000] * 15)

    def test_all_instruction_encodings(self):
        # Each expectation is independent of assembler.INSTRUCTIONS.
        instructions = {
            'LDI 42': 0x002A,
            'ADDI 5': 0x1005,
            'SUBI 3': 0x2003,
            'ANDI 255': 0x30FF,
            'ORI 15': 0x400F,
            'XORI 0xAA': 0x50AA,
            'SHL': 0x6000,
            'SHR': 0x7000,
            'STR R3': 0x8C00,
            'LDR R3': 0x9300,
            'JMP 15': 0xA00F,
            'JZ 1': 0xB001,
            'ADDR R3': 0xD300,
            'XORR R3': 0xE300,
            'HALT': 0xF000,
        }
        for source, expected in instructions.items():
            with self.subTest(source=source):
                self.single(source, expected)

    def test_four_register_encodings(self):
        for register in range(4):
            with self.subTest(register=register):
                self.single(f'STR R{register}', 0x8000 | (register << 10))
                self.single(f'LDR R{register}', 0x9000 | (register << 8))
                self.single(f'ADDR R{register}', 0xD000 | (register << 8))
                self.single(f'XORR R{register}', 0xE000 | (register << 8))

    def test_immediate_and_jump_boundaries(self):
        self.single('LDI 0', 0x0000)
        self.single('LDI 255', 0x00FF)
        self.single('JMP 0', 0xA000)
        self.single('JZ 15', 0xB00F)

    def test_decimal_hex_and_binary_literals(self):
        self.single('LDI 010', 0x000A)     # Plain digits mean decimal.
        self.single('LDI 0xA5', 0x00A5)
        self.single('LDI 0b101', 0x0005)

    def test_case_insensitive_mnemonics_and_registers(self):
        self.single('ldi 17', 0x0011)
        self.single('str r2', 0x8800)

    def test_forward_and_backward_labels(self):
        words, listing = assemble('''
start: LDI 3   ; initialise
       JZ done
       JMP start
 done: HALT
''')
        self.assertEqual(words[:4], [0x0003, 0xB003, 0xA000, 0xF000])
        self.assertEqual(len(listing), 4)

    def test_comments_and_commas(self):
        words, listing = assemble('''
# comment
LDI 5   ; comment
STR, R1 # accepted comma separator
HALT
''')
        self.assertEqual(words[:3], [0x0005, 0x8400, 0xF000])
        self.assertEqual(len(listing), 3)

    def test_short_program_padded_with_halt(self):
        words, listing = assemble('LDI 9\n')
        self.assertEqual(len(words), 16)
        self.assertEqual(words[:2], [0x0009, 0xF000])
        self.assertEqual(len(listing), 1)

    def test_exactly_sixteen_words_allowed(self):
        words, listing = assemble('SHL\n' * 16)
        self.assertEqual(len(listing), 16)
        self.assertEqual(words, [0x6000] * 16)

    def test_empty_program_padded_with_halt(self):
        words, listing = assemble(' ; nothing to execute\n')
        self.assertEqual(listing, [])
        self.assertEqual(words, [0xF000] * 16)

    def test_bad_assembly_rejected(self):
        cases = [
            ('LDQ 1', 'unknown instruction'),
            ('LDI', 'requires an operand'),
            ('HALT 1', 'takes no operand'),
            ('SHL R0', 'takes no operand'),
            ('LDI 1 2', 'too many operands'),
            ('LDI 256', '0..255'),
            ('ADDI -1', '0..255'),
            ('JMP 16', '0..15'),
            ('JZ -1', '0..15'),
            ('STR R4', 'register must be'),
            ('LDR R-1', 'register must be'),
            ('ADDR R9', 'register must be'),
            ('JMP missing_label', 'expected number'),
            ('LDI nope', 'expected number'),
            ('entry: HALT\nentry: HALT', 'duplicate label'),
            ('HALT\n' * 17, 'exceeds 16'),
        ]
        for source, expected_message in cases:
            with self.subTest(source=source[:40]):
                with self.assertRaises(AssemblyError) as caught:
                    assemble(source)
                self.assertIn(expected_message, str(caught.exception))

    def test_csv_pin_sequence_and_hex_listing(self):
        words, listing = assemble('LDI 0xAB\nHALT\n')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / 'output'
            write_outputs(base, words, listing)
            hex_lines = base.with_suffix('.hex').read_text().splitlines()
            self.assertEqual(len(hex_lines), 16)
            self.assertEqual(hex_lines[:3], ['00AB', 'F000', 'F000'])
            listing_text = base.with_suffix('.lst').read_text()
            self.assertIn('00AB', listing_text)
            self.assertIn('F000', listing_text)
            with base.with_suffix('.csv').open(newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4)
            self.assertEqual([row['phase'] for row in rows],
                             ['LOW', 'HIGH', 'LOW', 'HIGH'])
            self.assertEqual([row['ui_in_hex'] for row in rows],
                             ['AB', '00', '00', 'F0'])
            self.assertEqual([row['uio_in_hex'] for row in rows],
                             ['60', '70', '61', '71'])
            self.assertEqual([row['expected_word'] for row in rows],
                             ['00AB', '00AB', 'F000', 'F000'])
            self.assertEqual([row['address'] for row in rows],
                             ['0', '0', '1', '1'])

    def test_cli_success_with_output_override(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'example.asm'
            output = Path(directory) / 'outputs' / 'custom'
            source.write_text('LDI 5\nHALT\n')
            completed = subprocess.run(
                [sys.executable, str(ASSEMBLER), str(source), '-o', str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for extension in ['.hex', '.lst', '.csv']:
                self.assertTrue(output.with_suffix(extension).is_file())

    def test_cli_reports_error_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'bad.asm'
            source.write_text('LDI 999\n')
            completed = subprocess.run(
                [sys.executable, str(ASSEMBLER), str(source)],
                text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn('Assembly error', completed.stderr)
            self.assertFalse(source.with_suffix('.hex').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
