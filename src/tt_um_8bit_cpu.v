module tt_um_youseftamereee_8_bit_cpu_tinytapeout (
    input wire [7:0] ui_in,
    output wire [7:0] uo_out,

    input wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,

    input wire ena,
    input wire clk,
    input wire rst_n
);

    wire program_mode;
    wire program_write;

    wire [3:0] program_address;
    wire [15:0] program_data;

    wire [7:0] accumulator_out;
    wire [3:0] pc_out;
    wire halted;

    reg [7:0] low_byte;

    // Programming controls
    assign program_mode = uio_in[6];

    assign program_address = uio_in[3:0];

    // Write instruction when high byte arrives
    assign program_write =
        program_mode &&
        uio_in[5] &&
        uio_in[4];

    // Capture the low byte first
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            low_byte <= 8'b0;
        else if (program_mode &&
                 uio_in[5] &&
                 !uio_in[4])
            low_byte <= ui_in;
    end

    // Combine two bytes into one instruction
    assign program_data = {ui_in, low_byte};

    // Our 8-bit processor
    processor cpu_unit (
        .clk(clk),
        .rst_n(rst_n),

        .program_mode(program_mode),
        .program_write(program_write),
        .program_address(program_address),
        .program_data(program_data),

        .accumulator_out(accumulator_out),
        .pc_out(pc_out),
        .halted(halted)
    );

    // Display accumulator on output pins
    assign uo_out = accumulator_out;

    // Bidirectional pins used as inputs
    assign uio_out = 8'b0;
    assign uio_oe = 8'b0;

    // Unused signals
    wire _unused = &{
        ena,
        uio_in[7],
        pc_out,
        halted,
        1'b0
    };

endmodule
