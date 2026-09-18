# BendSym VM semantics

BendSym programs operate on unsigned 32-bit words. `ADD`, `SUB`, and `MUL`
wrap modulo 2³². `NOT` is bitwise complement. `EQ` and unsigned `ULT` produce
exactly zero or one. Zero is false and every nonzero word is true.

Binary instructions pop the right operand and then the left operand. Memory is
declared, fixed-size, and zero-initialized; `LOAD` and `STORE` take immediate
slot indices. Inputs are declared and stable: repeated `INPUT i` instructions
read the same value.

`JNZ`, `ASSUME`, and `ASSERT` consume their condition. A false assumption
rejects the execution. A false assertion is a counterexample. Stack underflow
and falling off the program are VM traps and are also counterexamples. `HALT`
terminates normally.

Fuel is checked before instruction fetch. Every dispatched instruction consumes
one step, including a terminating instruction. Reaching the configured bound is
reported separately and is never described as safety.

## Instruction set

`PUSH`, `INPUT`, `DUP`, `SWAP`, `DROP`, `ADD`, `SUB`, `MUL`, `AND`, `OR`,
`XOR`, `NOT`, `EQ`, `ULT`, `LOAD`, `STORE`, `JMP`, `JNZ`, `ASSUME`, `ASSERT`,
and `HALT`.
