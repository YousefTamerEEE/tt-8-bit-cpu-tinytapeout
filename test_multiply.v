`timescale 1ns/1ps

// End-to-end test: assemble demo_multiply.asm first to generate demo_multiply.hex.
// Run in Codespaces:
//   iverilog -g2012 -s test_multiply -o multiply_sim test_multiply.v src/*.v
//   vvp multiply_sim
module test_multiply;
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;
    reg ena = 1'b1;
    reg [7:0] ui_in = 8'h00;
    reg [7:0] uio_in = 8'h00;
    wire [7:0] uo_out;
    wire [7:0] uio_out;
    wire [7:0] uio_oe;

    tt_um_youseftamereee_8_bit_cpu_tinytapeout dut (
        .ui_in(ui_in), .uo_out(uo_out),
        .uio_in(uio_in), .uio_out(uio_out), .uio_oe(uio_oe),
        .ena(ena), .clk(clk), .rst_n(rst_n)
    );

    reg [15:0] program_words [0:15];
    integer index;
    integer cycles;
    integer additions_seen;

    initial begin
        $dumpfile("multiply.vcd");
        $dumpvars(0, test_multiply);
        $readmemh("demo_multiply.hex", program_words);

        // Reset first; memory-valid flags reset with the CPU.
        // The program must be written AFTER reset and NOT reset again.
        repeat (3) @(negedge clk);
        rst_n = 1'b1;

        // Load 16 instructions, low byte first, then high byte.
        for (index = 0; index < 16; index = index + 1) begin
            @(negedge clk);
            uio_in = 8'h60 | index[3:0];
            ui_in  = program_words[index][7:0];
            @(negedge clk);
            uio_in = 8'h70 | index[3:0];
            ui_in  = program_words[index][15:8];
            @(negedge clk);
            if (dut.cpu_unit.memory_unit.memory[index] !== program_words[index])
                $fatal(1, "Program load failed at address %0d: expected %04h, got %04h",
                       index, program_words[index], dut.cpu_unit.memory_unit.memory[index]);
        end

        uio_in = 8'h00;
        ui_in  = 8'h00;
        additions_seen = 0;
        $display("Loaded and checked 16 instructions through programming pins.");

        for (cycles = 0; cycles < 150; cycles = cycles + 1) begin
            @(posedge clk);
            #1;
            // ADDR R0 executes at address 7; after it PC becomes 8.
            if (dut.cpu_unit.pc_out == 4'd8 && additions_seen < 4) begin
                additions_seen = additions_seen + 1;
                if (uo_out !== 3 * additions_seen)
                    $fatal(1, "Addition #%0d: expected %0d, got %0d",
                           additions_seen, 3 * additions_seen, uo_out);
                $display("Addition #%0d PASS (accumulator = %0d)", additions_seen, uo_out);
            end

            if (dut.cpu_unit.halted) begin
                if (additions_seen != 4)
                    $fatal(1, "Unexpected number of additions: %0d (expected 4)", additions_seen);
                if (uo_out !== 8'd12)
                    $fatal(1, "Wrong multiplication result: expected 12, got %0d", uo_out);
                if (dut.cpu_unit.pc_out !== 4'd15)
                    $fatal(1, "HALT at wrong address: expected 15, got %0d", dut.cpu_unit.pc_out);
                $display("PASS: CPU computed 3 x 4 = 12 by repeated addition and halted at PC=15.");
                $finish;
            end
        end
        $fatal(1, "TIMEOUT: CPU never halted within 150 cycles");
    end
endmodule
