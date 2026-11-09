module cpu (
    input wire clk,
    input wire rst_n,
    input wire [7:0] data_in,
    input wire [2:0] opcode,
    input wire execute,
    output reg [7:0] accumulator,
    output wire zero
);

    reg [7:0] alu_result;

    // Share one adder between addition and subtraction
    wire subtract = (opcode == 3'b010);

    wire [7:0] arithmetic_b =
        data_in ^ {8{subtract}};

    wire [7:0] arithmetic_result =
        accumulator + arithmetic_b + {7'b0, subtract};

    always @(*) begin
        case (opcode)
            3'b000: alu_result = data_in;
            3'b001: alu_result = arithmetic_result;
            3'b010: alu_result = arithmetic_result;
            3'b011: alu_result = accumulator & data_in;
            3'b100: alu_result = accumulator | data_in;
            3'b101: alu_result = accumulator ^ data_in;
            3'b110: alu_result = accumulator << 1;
            3'b111: alu_result = accumulator >> 1;
            default: alu_result = 8'b0;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            accumulator <= 8'b0;
        else if (execute)
            accumulator <= alu_result;
    end

    assign zero = (accumulator == 8'b0);

endmodule
