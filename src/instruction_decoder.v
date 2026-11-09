module instruction_decoder (
    input wire [15:0] instruction,

    output wire [3:0] opcode,
    output wire [1:0] destination,
    output wire [1:0] source,
    output wire [7:0] immediate
);

    assign opcode      = instruction[15:12];
    assign destination = instruction[11:10];
    assign source      = instruction[9:8];
    assign immediate   = instruction[7:0];

endmodule
