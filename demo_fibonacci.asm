; Fibonacci sequence using our custom 8-bit CPU

LDI 0
STR R0

LDI 1
STR R1

loop:
LDR R0
ADDR R1
STR R2

LDR R1
STR R0

LDR R2
STR R1

SUBI 13
JZ done
JMP loop

done:
LDR R2
HALT
