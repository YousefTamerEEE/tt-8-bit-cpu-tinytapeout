# Programmable 8-Bit CPU — Verilog ASIC Design

**A custom 8-bit processor taken from RTL to a verified GF180MCU ASIC layout, with a Python assembler, executable demonstration programs, and automated hardware/software regression tests.**

[![CPU V2 regression](https://github.com/YousefTamerEEE/tt-8-bit-cpu-tinytapeout/actions/workflows/cpu-v2-regression.yml/badge.svg?branch=cpu-v2)](https://github.com/YousefTamerEEE/tt-8-bit-cpu-tinytapeout/actions/workflows/cpu-v2-regression.yml)
[![GDS build](https://github.com/YousefTamerEEE/tt-8-bit-cpu-tinytapeout/actions/workflows/gds.yaml/badge.svg?branch=main)](https://github.com/YousefTamerEEE/tt-8-bit-cpu-tinytapeout/actions/workflows/gds.yaml)

**Author:** Yousef Tamer · **Hardware:** Verilog · **Toolchain:** Python, Icarus Verilog, GitHub Actions, LibreLane, Tiny Tapeout · **Process:** GF180MCU (180 nm)

> **Project status:** The RTL-based design has passed Tiny Tapeout's GDS build, precheck, gate-level test and viewer workflows for a **1×2-tile** implementation. The Python assembler and three end-to-end program demonstrations also pass automated regression on the `cpu-v2` branch. **Fabrication has not yet taken place.**

## Highlights

| Feature | Implementation |
| --- | --- |
| Datapath | 8-bit accumulator-based CPU |
| Registers | Four 8-bit general-purpose registers (R0–R3) |
| Instruction word | 16 bits |
| Program storage | 16 × 16-bit programmable instruction memory |
| Program counter | 4 bits (addresses 0–15) |
| Instruction set | 15 assembler mnemonics: immediate, arithmetic, logic, register, branch, halt |
| Control flow | Unconditional `JMP` and zero-conditional `JZ` |
| Chip interface | Two-byte programming over Tiny Tapeout input pins; accumulator on eight output pins |
| Silicon target | GF180MCU, Tiny Tapeout 1×2 tile |
| Physical-design configuration | 45 ns clock-period target; 60% placement-density target |
| Verification | 14 Python assembler unit tests + counter, multiplication and Fibonacci RTL simulations |

## CPU architecture

```text
          8-bit input data + programming controls
                         |
                 Programming interface
                  (low / high byte)
                         |
              +---------------------+
              | 16 × 16-bit         |<--- 4-bit program counter
              | instruction memory  |           ^
              +----------+----------+           |
                         |                      |
                  Instruction decoder ----------+--- JMP / JZ / HALT
                         |
              +----------v----------+
              | 8-bit ALU +         |<--- R0–R3 register file
              | accumulator         |---- zero flag
              +----------+----------+
                         |
                    uo_out[7:0]
```

The CPU executes instructions sequentially after external programming. The ALU supports load, addition, subtraction, bitwise AND/OR/XOR and shifts. A zero flag derived from the accumulator controls `JZ`. A `HALT` instruction stops program-counter advancement. Unprogrammed instruction addresses behave as `HALT` until written.

**RTL sources:** [`src/`](src/) contains `cpu.v`, `processor.v`, `instruction_decoder.v`, `instruction_memory.v`, `program_counter.v`, `register_file.v`, and the Tiny Tapeout top-level wrapper.

## Demonstrated programs

Each program is assembled to 16-bit instructions, loaded into the **actual RTL CPU through the simulated programming pins**, executed in Icarus Verilog, and checked by a dedicated self-checking Verilog testbench.

| Program | What it demonstrates | Verified result | Files |
| --- | --- | --- | --- |
| Counter | Looping, branch-on-zero, register storage | Counts **0 → 5** and halts with accumulator **5**, PC **9** | [`demo_counter.asm`](demo_counter.asm) · [`test_counter.v`](test_counter.v) |
| Multiplication | **3 × 4** via repeated addition | Accumulator **12**, PC **15**, halted | [`demo_multiply.asm`](demo_multiply.asm) · [`test_multiply.v`](test_multiply.v) |
| Fibonacci | Register updates, loop, arithmetic and branching | **0, 1, 1, 2, 3, 5, 8, 13**; accumulator **13**, PC **15**, halted | [`demo_fibonacci.asm`](demo_fibonacci.asm) · [`test_fibonacci.v`](test_fibonacci.v) |

### Fibonacci execution waveform

![Fibonacci CPU RTL simulation: accumulator, clock, halt flag, and program counter](images/fibonacci-waveform.png)

*Waveform captured from the Icarus Verilog simulation using Surfer. The selected final state shows `accumulator_out = 13`, `halted = 1`, and `pc_out = 0xF`.*

## Python assembler

[`assembler.py`](assembler.py) converts readable assembly into three useful outputs:

- **`.hex`** — 16 instruction words, 16 bits each (unused locations filled with `F000` = HALT).
- **`.lst`** — annotated source-to-machine-code listing.
- **`.csv`** — the per-clock pin values to write the low byte and high byte of each instruction through the external programming interface.

```bash
python3 assembler.py demo_counter.asm
python3 assembler.py demo_multiply.asm
python3 assembler.py demo_fibonacci.asm
```

Optional output prefix:

```bash
python3 assembler.py demo_fibonacci.asm -o build/fibonacci
```

The assembler resolves forward/backward labels, validates operands and register names, rejects invalid instructions, and enforces the 16-word program capacity. Its behavior is covered by **14 automated Python unit tests** in [`test_assembler.py`](test_assembler.py).

### Instruction set

The 16-bit instruction format is:

```text
15          12 11        10 9          8 7                    0
+-------------+------------+------------+----------------------+
| opcode (4)  | dest (2)   | source (2) | immediate / addr (8) |
+-------------+------------+------------+----------------------+
```

| Opcode (hex) | Assembly | Operation |
| --- | --- | --- |
| `0` | `LDI n` | Accumulator ← immediate `n` |
| `1` | `ADDI n` | Accumulator ← accumulator + `n` |
| `2` | `SUBI n` | Accumulator ← accumulator − `n` |
| `3` | `ANDI n` | Accumulator ← accumulator AND `n` |
| `4` | `ORI n` | Accumulator ← accumulator OR `n` |
| `5` | `XORI n` | Accumulator ← accumulator XOR `n` |
| `6` | `SHL` | Shift accumulator left by one |
| `7` | `SHR` | Shift accumulator right by one |
| `8` | `STR Rn` | Register `Rn` ← accumulator |
| `9` | `LDR Rn` | Accumulator ← register `Rn` |
| `A` | `JMP label` | Jump to address/label |
| `B` | `JZ label` | Jump if accumulator is zero |
| `D` | `ADDR Rn` | Accumulator ← accumulator + register `Rn` |
| `E` | `XORR Rn` | Accumulator ← accumulator XOR register `Rn` |
| `F` | `HALT` | Stop execution |

Arithmetic is 8-bit modular arithmetic (results wrap at 256). Opcode `C` is not currently implemented.

## Programming interface

Tiny Tapeout pins are used as follows:

| Signal | Purpose |
| --- | --- |
| `ui_in[7:0]` | Instruction byte supplied to the CPU |
| `uio_in[3:0]` | Instruction address (0–15) |
| `uio_in[4]` | Byte select: **0 = low**, **1 = high** |
| `uio_in[5]` | Programming write strobe |
| `uio_in[6]` | Programming-mode enable |
| `uo_out[7:0]` | 8-bit accumulator output |
| `clk`, `rst_n` | Clock and active-low reset |

For each instruction, drive the **low byte** first (`uio_in = 0x60 | address`) and pulse the clock; then drive the **high byte** (`uio_in = 0x70 | address`) and pulse the clock again. The second clock edge writes the full instruction. The assembler-generated CSV contains these pin patterns.

Reset clears instruction-valid flags, so **do not reset after loading the program** unless you intend to reprogram it. Set `uio_in[6] = 0` to leave programming mode and execute.

> Current I/O is intentionally minimal: the CPU **outputs its accumulator** but does not yet provide a general-purpose program-controlled GPIO instruction. Adding that capability is a potential future revision.

## Reproduce the verification

Requirements: Python 3 and Icarus Verilog (`iverilog` and `vvp`). Run from the repository root.

**1. Run the assembler's 14 unit tests**

```bash
python3 -m unittest -v test_assembler.py
```

**2. Generate the three programs**

```bash
python3 assembler.py demo_counter.asm
python3 assembler.py demo_multiply.asm
python3 assembler.py demo_fibonacci.asm
```

**3. Run the RTL simulations**

```bash
iverilog -g2012 -s test_counter -o counter_sim test_counter.v src/*.v && vvp counter_sim
iverilog -g2012 -s test_multiply -o multiply_sim test_multiply.v src/*.v && vvp multiply_sim
iverilog -g2012 -s test_fibonacci -o fibonacci_sim test_fibonacci.v src/*.v && vvp fibonacci_sim
```

The testbenches check program loading, intermediate behavior and final results. They generate `.vcd` waveforms for inspection in Surfer or GTKWave.

**4. Continuous integration**

The [CPU V2 Automated Regression](https://github.com/YousefTamerEEE/tt-8-bit-cpu-tinytapeout/actions/workflows/cpu-v2-regression.yml) GitHub Actions workflow runs on pushes to `cpu-v2` and includes the assembler unit tests plus all three CPU simulations. The original Tiny Tapeout GDS/precheck/test workflows remain separate.

## ASIC implementation and engineering trade-offs

The CPU targets the **GF180MCU 180 nm** process through the Tiny Tapeout/LibreLane digital flow. The original **1×1 tile** implementation encountered placement constraints. Moving to a **1×2 tile**, and refining placement density and antenna-repair settings, enabled the verified physical-design workflow to complete. This is an intentional area-versus-routability engineering trade-off.

- **Physical implementation:** successful GDS workflow, followed by successful Tiny Tapeout precheck and gate-level test jobs on the verified baseline design.
- **Configuration:** `src/config.json` records a **45 ns** layout clock-period target and **60%** placement-density target; `info.yaml` specifies a **1×2** tile.
- **Reproducibility:** [`cpu-v1-stable`](https://github.com/YousefTamerEEE/tt-8-bit-cpu-tinytapeout/tree/cpu-v1-stable) preserves the previously passing RTL design, while [`cpu-v2`](https://github.com/YousefTamerEEE/tt-8-bit-cpu-tinytapeout/tree/cpu-v2) adds the assembler, demonstration programs and tests.
- **Fabrication status:** layout and verification are **not** equivalent to manufacturing. The design has not yet been fabricated or physically tested on silicon.

## Repository guide

```text
src/                       Verilog CPU, ALU, registers, memory, control, top-level
assembler.py                Python assembly-to-machine-code compiler
test_assembler.py           14 Python assembler unit tests
demo_counter.asm            Counter demonstration
demo_multiply.asm           Repeated-addition multiplication
demo_fibonacci.asm          Fibonacci demonstration
test_counter.v              Counter self-checking RTL simulation
test_multiply.v             Multiplication self-checking RTL simulation
test_fibonacci.v            Fibonacci self-checking RTL simulation
images/fibonacci-waveform.png   Captured simulation waveform
.github/workflows/cpu-v2-regression.yml   Automated CI regression
info.yaml                   Tiny Tapeout project metadata and pinout
src/config.json             ASIC physical-design configuration
docs/info.md                Tiny Tapeout documentation / usage
```

## Next steps

- Extend RTL verification with more corner cases and independent instruction-level reference checks.
- Consider program-controlled external I/O and carry/overflow status flags as optional new hardware features **on a separate development branch**, with fresh RTL and physical verification.
- Review shuttle requirements and submit for fabrication when ready; perform physical bench testing only after silicon is received.

---

**Project by Yousef Tamer.** Developed to explore digital logic, computer architecture, hardware verification and ASIC implementation in a practical, reproducible design.
