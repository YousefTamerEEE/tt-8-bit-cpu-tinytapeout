module register_file (
    input wire clk,
    input wire rst_n,
    input wire write_enable,
    input wire [1:0] write_address,
    input wire [7:0] write_data,
    input wire [1:0] read_address_a,
    input wire [1:0] read_address_b,
    output wire [7:0] read_data_a,
    output wire [7:0] read_data_b
);

    reg [7:0] registers [0:3];

    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < 4; i = i + 1)
                registers[i] <= 8'b0;
        end
        else if (write_enable) begin
            registers[write_address] <= write_data;
        end
    end

    assign read_data_a = registers[read_address_a];
    assign read_data_b = registers[read_address_b];

endmodule
