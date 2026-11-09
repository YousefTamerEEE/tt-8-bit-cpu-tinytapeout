## How it works

This project implements a custom programmable 8-bit CPU designed in Verilog and targeting fabrication using the GF180 180 nm semiconductor process.

The processor features an 8-bit arithmetic logic unit (ALU), four 8-bit general-purpose registers, a 4-bit program counter and an internally programmable instruction memory capable of storing 16 instructions of 16 bits each.

The CPU supports arithmetic and logical operations, register storage, conditional and unconditional branching, and program termination using a HALT instruction.

Unlike a fixed-function digital circuit, the processor can execute different programs loaded externally through its input pins.

Programming is performed using an 8-bit data interface, a 4-bit instruction address and dedicated control signals. Each 16-bit instruction is transferred in two 8-bit stages.

After programming, the CPU executes instructions sequentially under clock control. The accumulator's current 8-bit value is continuously available through the output pins.

The design has successfully passed its RTL functional testbenches and completed a GF180 LibreLane physical-design flow, including layout-versus-schematic verification.

## How to test

The CPU can be tested using the Tiny Tapeout digital input/output interface.

1. Apply a clock signal and assert the active-low reset (rst_n = 0). Release reset before programming.

2. Enable programming mode by setting uio[6] = 1.

3. Select the instruction-memory address using uio[3:0].

4. Place the lower 8 bits of the instruction on ui[7:0]. Set uio[4] = 0 and uio[5] = 1. Apply a rising clock edge to capture the lower byte.

5. Place the upper 8 bits on ui[7:0]. Set uio[4] = 1 while keeping the selected address and programming strobe active. Apply another rising clock edge to write the complete 16-bit instruction.

6. Repeat this process for each instruction.

7. Disable programming mode by setting uio[6] = 0, then allow the CPU to execute under clock control.

8. Observe the accumulator output on uo[7:0].

Example program:

Address 0: 0x000A — Load the value 10 into the accumulator.

Address 1: 0x1005 — Add 5 to the accumulator.

Address 2: 0xF000 — HALT.

The expected final accumulator output is decimal 15 (0x0F).

Do not assert reset after loading the program, because reset clears the instruction-memory valid flags.

The Verilog implementation has also been verified using dedicated testbenches covering external programming, arithmetic operations, instruction execution and program termination.

## External hardware

The CPU does not require external RAM or ROM because its instruction memory and registers are implemented internally.

For physical testing, a compatible Tiny Tapeout demonstration board or test setup is required to provide power, clock, reset and digital programming signals.

A microcontroller or equivalent digital interface can be used to program instructions through the input pins.

The accumulator output can be monitored using LEDs, a logic analyser or another compatible digital interface.
