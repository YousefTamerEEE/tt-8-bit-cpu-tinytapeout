#!/usr/bin/env python3
"""Compare each executed instruction of the Python CPU model against Verilog RTL.

From the repository root:
    python3 test_differential.py

Uses Icarus Verilog. Does not alter the RTL or run a physical-design flow.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cpu_emulator import CPU, HALT_WORD, DEPTH, load_program

ROOT = Path(__file__).resolve().parent
DEMOS = (
    ('demo_counter.asm', 5),
    ('demo_multiply.asm', 12),
    ('demo_fibonacci.asm', 13),
)

TB = r'''`timescale 1ns/1ps
module differential_tb;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0;
    reg ena = 1;
    reg [7:0] ui_in = 0;
    reg [7:0] uio_in = 0;
    wire [7:0] uo_out;
    wire [7:0] uio_out;
    wire [7:0] uio_oe;

    tt_um_youseftamereee_8_bit_cpu_tinytapeout dut (
        .ui_in(ui_in), .uo_out(uo_out),
        .uio_in(uio_in), .uio_out(uio_out), .uio_oe(uio_oe),
        .ena(ena), .clk(clk), .rst_n(rst_n)
    );
    reg [15:0] program_words [0:15];
    integer i;
    integer cycle;

    initial begin
        $readmemh("program.hex", program_words);
        repeat (3) @(negedge clk);
        rst_n = 1'b1;
        // Program all 16 words via exactly the same physical pin interface
        // used by our existing end-to-end Verilog tests.
        for (i = 0; i < 16; i = i + 1) begin
            @(negedge clk);
            uio_in = 8'h60 | i[3:0];
            ui_in = program_words[i][7:0];
            @(negedge clk);
            uio_in = 8'h70 | i[3:0];
            ui_in = program_words[i][15:8];
            @(negedge clk);
            if (dut.cpu_unit.memory_unit.memory[i] !== program_words[i])
                $fatal(1, "Memory load failed at %0d", i);
        end
        uio_in = 8'h00;
        ui_in = 8'h00;

        // Sample AFTER nonblocking-register updates have settled.
        for (cycle = 0; cycle < 1000; cycle = cycle + 1) begin
            @(posedge clk);
            #1;
            $display("DIFF,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
                cycle+1, dut.cpu_unit.pc_out, uo_out,
                dut.cpu_unit.registers_unit.registers[0],
                dut.cpu_unit.registers_unit.registers[1],
                dut.cpu_unit.registers_unit.registers[2],
                dut.cpu_unit.registers_unit.registers[3],
                dut.cpu_unit.halted);
            if (dut.cpu_unit.halted) $finish;
        end
        $fatal(1, "CPU did not reach HALT within 1000 cycles");
    end
endmodule
'''


def check_demo(name: str, expected_acc: int) -> int:
    asm_path = ROOT / name
    if not asm_path.is_file():
        raise RuntimeError(f'Missing demonstration program: {name}')
    words = load_program(asm_path)
    model = CPU()
    model.load(words)
    predicted = model.run(max_cycles=1000)
    if model.acc != expected_acc:
        raise RuntimeError(f'Emulator {name}: final ACC {model.acc}, expected {expected_acc}')

    with tempfile.TemporaryDirectory(prefix='cpu-differential-') as temp:
        scratch = Path(temp)
        (scratch / 'program.hex').write_text(
            ''.join(f'{w:04X}\n' for w in (words + [HALT_WORD] * (DEPTH-len(words)))),
            encoding='ascii',
        )
        (scratch / 'differential_tb.v').write_text(TB, encoding='utf-8')
        source_files = sorted((ROOT / 'src').glob('*.v'))
        if not source_files:
            raise RuntimeError('Missing Verilog source files in src/')
        build = subprocess.run(
            ['iverilog', '-g2012', '-s', 'differential_tb', '-o', str(scratch / 'sim'),
             str(scratch / 'differential_tb.v'), *map(str, source_files)],
            capture_output=True, text=True,
        )
        if build.returncode != 0:
            raise RuntimeError('Icarus compilation failed:\n'+build.stdout+build.stderr)
        simulated = subprocess.run(
            ['vvp', str(scratch / 'sim')], cwd=scratch,
            capture_output=True, text=True,
        )
        if simulated.returncode != 0:
            raise RuntimeError('RTL simulation failed:\n'+simulated.stdout+simulated.stderr)

    actual = []
    for line in simulated.stdout.splitlines():
        if line.startswith('DIFF,'):
            values = line.split(',')[1:]
            if len(values) != 8 or any(not re.fullmatch(r'\d+', v) for v in values):
                raise RuntimeError(f'Non-numeric or unknown RTL state: {line}')
            actual.append(tuple(map(int, values)))
    if len(actual) != len(predicted):
        raise RuntimeError(
            f'{name}: number of cycles differs: RTL {len(actual)} != emulator {len(predicted)}\n'
            + '\n'.join(simulated.stdout.splitlines()[-10:])
        )
    for cycle, (rtl, ref) in enumerate(zip(actual, predicted), 1):
        want = (ref.index, ref.pc_after, ref.acc_after, *ref.regs_after, int(ref.halted))
        if rtl != want:
            fields = ('cycle', 'PC', 'ACC', 'R0', 'R1', 'R2', 'R3', 'HALT')
            mismatches = ', '.join(f'{f}: RTL={a}, emulator={b}'
                                   for f, a, b in zip(fields, rtl, want) if a != b)
            raise RuntimeError(f'{name} at cycle {cycle}: {mismatches}')
    print(f'PASS {name}: {len(predicted)} cycles matched; final ACC={model.acc} PC={model.pc}')
    return len(predicted)


def main() -> int:
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        print('ERROR: Icarus Verilog not available. Use your GitHub Codespaces terminal.', file=sys.stderr)
        return 1
    try:
        total = sum(check_demo(name, acc) for name, acc in DEMOS)
    except (RuntimeError, ValueError, OSError) as exc:
        print('FAIL:', exc, file=sys.stderr)
        return 1
    print(f'PASS: All 3 programs match RTL on every execution cycle ({total} cycles).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
