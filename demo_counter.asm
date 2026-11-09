; 8-bit CPU simple loop demo (ALU result displayed on uo_out)
; Counts up by one until accumulator reaches 5; then halts.
; Program uses the zero flag to detect acc - 5 == 0.
start:
    LDI 0       ; acc = 0
    STR R0      ; R0 = acc (counter)
loop:
    LDR R0      ; acc = counter
    ADDI 1      ; acc = counter + 1
    STR R0      ; counter = acc
    SUBI 5      ; acc = counter - 5
    JZ done     ; stop once counter = 5
    JMP loop    ; repeat

done:
    LDR R0      ; display final count (5)
    HALT
