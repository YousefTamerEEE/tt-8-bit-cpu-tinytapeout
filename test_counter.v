`timescale 1ns/1ps

// End-to-end RTL test of demo_counter.hex through the actual Tiny Tapeout pins.
// Run from the repository root:
//   iverilog -g2012 -s test_counter -o counter_sim test_counter.v src/*.v
//   vvp counter_sim
module test_counter;
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
    integer counter_observations;

    initial begin
        $dumpfile("counter.vcd");
        $dumpvars(0, test_counter);
        $readmemh("demo_counter.hex", program_words);

        // Reset before programming. The CPU clears memory-valid flags on reset,
        // so do NOT reset again after uploading the program_words.
        repeat (3) @(negedge clk);
        rst_n = 1'b1;

        // Actual programming interface:
        // uio_in[6]=program_words mode, [5]=strobe, [4]=0 low byte / 1 high byte.
        for (index = 0; index < 10; index = index + 1) begin
            @(negedge clk);
            uio_in = 8'h60 | index[3:0];
            ui_in  = program_words[index][7:0];
            @(negedge clk);
            uio_in = 8'h70 | index[3:0];
            ui_in  = program_words[index][15:8];
            @(negedge clk); // High byte was written on the preceding rising edge.

            if (dut.cpu_unit.memory_unit.memory[index] !== program_words[index])
                $fatal(1, "Programming failed at address %0d: expected %04h got %04h",
                       index, program_words[index], dut.cpu_unit.memory_unit.memory[index]);
        end

        // Enter execution mode; program_words counter is still zero.
        uio_in = 8'h00;
        ui_in  = 8'h00;
        counter_observations = 0;
        $display("Program loaded successfully: 10 words verified via programming pins.");

        for (cycles = 0; cycles < 100; cycles = cycles + 1) begin
            @(posedge clk);
            #1; // Wait for nonblocking-register updates.

            // After ADDI 1 executes at address 3, PC advances to address 4.
            if (dut.cpu_unit.pc_out == 4 && counter_observations < 5) begin
                counter_observations = counter_observations + 1;
                if (uo_out !== counter_observations)
                    $fatal(1, "Count #%0d: expected %0d, got %0d",
                           counter_observations, counter_observations, uo_out);
                $display("Counter step %0d PASS (accumulator = %0d)",
                         counter_observations, uo_out);
            end

            if (dut.cpu_unit.halted) begin
                if (counter_observations != 5)
                    $fatal(1, "HALT arrived after only %0d counter increments",
                           counter_observations);
                if (uo_out !== 8'd5)
                    $fatal(1, "Expected final output 5, got %0d", uo_out);
                if (dut.cpu_unit.pc_out !== 4'd9)
                    $fatal(1, "Expected HALT at PC=9, got PC=%0d",
                           dut.cpu_unit.pc_out);
                $display("PASS: actual CPU executed 0->5 and HALTed with output=5 at PC=9.");
                $finish;
            end
        end
        $fatal(1, "TIMEOUT: CPU did not reach HALT within 100 clock cycles");
    end
endmodule
