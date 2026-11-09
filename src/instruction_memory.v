module instruction_memory (
    input wire clk,
    input wire rst_n,
    input wire program_mode,
    input wire program_write,
    input wire [3:0] program_address,
    input wire [15:0] program_data,
    input wire [3:0] pc,
    output wire [15:0] instruction
);

    reg [15:0] memory [0:15];
    reg [15:0] valid;

    // One real GF180 integrated clock gate per 16-bit memory word.
    // Explicit TE=0 avoids the unconnected scan/test-enable pins
    // produced by the older automatic clock-gating flow.
    genvar w;
    generate
        for (w = 0; w < 16; w = w + 1) begin : memory_word
            localparam [3:0] WORD_ADDRESS = w;
            wire write_word;
            assign write_word = rst_n && program_mode && program_write &&
                                (program_address == WORD_ADDRESS);
`ifdef SYNTHESIS
            wire gated_clk;
            gf180mcu_fd_sc_mcu7t5v0__icgtp_1 word_clock_gate (
                .CLK(clk),
                .E(write_word),
                .TE(1'b0),
                .Q(gated_clk)
            );
            always @(posedge gated_clk) begin
                memory[w] <= program_data;
            end
`else
            // Cycle-equivalent RTL simulation without foundry models.
            always @(posedge clk) begin
                if (write_word)
                    memory[w] <= program_data;
            end
`endif
        end
    endgenerate

    // Clear instruction-valid flags on reset; data is ignored until valid.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            valid <= 16'b0;
        else if (program_mode && program_write)
            valid[program_address] <= 1'b1;
    end

    // Unprogrammed words behave as HALT.
    assign instruction = valid[pc] ? memory[pc] : 16'hF000;

endmodule
