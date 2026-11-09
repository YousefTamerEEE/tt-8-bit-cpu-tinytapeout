module processor (
    input wire clk,
    input wire rst_n,

    input wire program_mode,
    input wire program_write,
    input wire [3:0] program_address,
    input wire [15:0] program_data,

    output wire [7:0] accumulator_out,
    output wire [3:0] pc_out,
    output wire halted
);

    wire [15:0] instruction;
    wire [3:0] opcode;
    wire [1:0] destination;
    wire [1:0] source;
    wire [7:0] immediate;

    wire [7:0] register_a;
    wire [7:0] unused_register_b;
    wire zero;

    wire execute;
    wire register_write;
    wire jump;
    wire advance;

    wire [2:0] alu_opcode;
    wire [7:0] alu_input;

// Programmable instruction memory
instruction_memory memory_unit (
    .clk(clk),
    .rst_n(rst_n),
    .program_mode(program_mode),
    .program_write(program_write),
    .program_address(program_address),
    .program_data(program_data),
    .pc(pc_out),
    .instruction(instruction)
);
    // Decode instruction
    instruction_decoder decoder (
        .instruction(instruction),
        .opcode(opcode),
        .destination(destination),
        .source(source),
        .immediate(immediate)
    );

    // Register storage
    register_file registers_unit (
        .clk(clk),
        .rst_n(rst_n),
        .write_enable(register_write),
        .write_address(destination),
        .write_data(accumulator_out),
        .read_address_a(source),
        .read_address_b(destination),
        .read_data_a(register_a),
        .read_data_b(unused_register_b)
            );
    // ALU control
    // ALU control
assign execute =
    !program_mode &&
    ((opcode <= 4'h7) ||
     (opcode == 4'h9) ||
     (opcode == 4'hD) ||
     (opcode == 4'hE));

    assign alu_opcode =
        (opcode == 4'h9) ? 3'b000 :
        (opcode == 4'hD) ? 3'b001 :
        (opcode == 4'hE) ? 3'b101 :
        opcode[2:0];

    assign alu_input =
        ((opcode == 4'h9) ||
         (opcode == 4'hD) ||
         (opcode == 4'hE))
        ? register_a : immediate;

    // Existing 8-bit ALU
    cpu alu_unit (
        .clk(clk),
        .rst_n(rst_n),
        .data_in(alu_input),
        .opcode(alu_opcode),
        .execute(execute),
        .accumulator(accumulator_out),
        .zero(zero)
    );

    // Store accumulator in register
    assign register_write = !program_mode && (opcode == 4'h8);

    // Jump instructions
    assign jump = !program_mode &&
    ((opcode == 4'hA) ||
     ((opcode == 4'hB) && zero));

    // Stop execution
    assign halted = (opcode == 4'hF);

    assign advance = !program_mode && !halted;

    // Program Counter
    program_counter pc_unit (
        .clk(clk),
        .rst_n(rst_n),
        .advance(advance),
        .jump(jump),
        .jump_address(immediate[3:0]),
        .pc(pc_out)
    );

endmodule
