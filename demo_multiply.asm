; Multiply 3 x 4 using repeated addition

LDI 3
STR R0

LDI 4
STR R1

LDI 0
STR R2

loop:
LDR R2
ADDR R0
STR R2

LDR R1
SUBI 1
STR R1

JZ done
JMP loop

done:
LDR R2
HALT
