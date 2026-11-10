`timescale 1ns/1ps

// End-to-end RTL test for demo_fibonacci.asm / demo_fibonacci.hex.
// From the repository root:
//   python3 assembler.py demo_fibonacci.asm
//   iverilog -g2012 -s test_fibonacci -o fibonacci_sim test_fibonacci.v src/*.v
//   vvp fibonacci_sim
module test_fibonacci;
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
    reg [7:0] expected [0:5];
    integer index;
    integer cycles;
    integer values_seen;

    initial begin
        expected[0] = 8'd1;
        expected[1] = 8'd2;
        expected[2] = 8'd3;
        expected[3] = 8'd5;
        expected[4] = 8'd8;
        expected[5] = 8'd13;

        $dumpfile("fibonacci.vcd");
        $dumpvars(0, test_fibonacci);
        $readmemh("demo_fibonacci.hex", program_words);

        // Reset BEFORE programming: resetting again would clear valid bits.
        repeat (3) @(negedge clk);
        rst_n = 1'b1;

        // Program through real Tiny Tapeout pins: LOW byte then HIGH byte.
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
        values_seen = 0;
        $display("Loaded and checked all 16 Fibonacci instructions through programming pins.");
        $display("Fibonacci sequence starts with initial register values 0, 1.");

        // ADDR R1 is instruction address 5; after executing, PC is 6.
        for (cycles = 0; cycles < 200; cycles = cycles + 1) begin
            @(posedge clk);
            #1;
            if (dut.cpu_unit.pc_out == 4'd6) begin
                if (values_seen >= 6)
                    $fatal(1, "Unexpected extra Fibonacci iteration");
                if (uo_out !== expected[values_seen])
                    $fatal(1, "Fibonacci #%0d: expected %0d, got %0d",
                           values_seen + 1, expected[values_seen], uo_out);
                $display("Fibonacci value #%0d PASS (accumulator = %0d)", values_seen + 1, uo_out);
                values_seen = values_seen + 1;
            end
            if (dut.cpu_unit.halted) begin
                if (values_seen != 6)
                    $fatal(1, "HALT after %0d Fibonacci sums; expected 6", values_seen);
                if (uo_out !== 8'd13)
                    $fatal(1, "Final value should be 13, got %0d", uo_out);
                if (dut.cpu_unit.pc_out !== 4'd15)
                    $fatal(1, "HALT should be at PC=15, got PC=%0d", dut.cpu_unit.pc_out);
                $display("PASS: CPU generated Fibonacci 0,1,1,2,3,5,8,13 and HALTed with output=13 at PC=15.");
                $finish;
            end
        end
        $fatal(1, "TIMEOUT: CPU did not finish Fibonacci within 200 cycles");
    end
endmodule
