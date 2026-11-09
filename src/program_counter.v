module program_counter (
    input wire clk,
    input wire rst_n,
    input wire advance,
    input wire jump,
    input wire [3:0] jump_address,
    output reg [3:0] pc
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            pc <= 4'd0;

        else if (jump)
            pc <= jump_address;

        else if (advance)
            pc <= pc + 4'd1;
    end

endmodule
