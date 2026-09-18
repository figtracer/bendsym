from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .assembly import Program, U32_MAX


MASK = U32_MAX


class OutcomeKind(str, Enum):
    HALTED = "halted"
    ASSUMPTION_REJECTED = "assumption_rejected"
    ASSERTION_FAILED = "assertion_failed"
    VM_TRAP = "vm_trap"
    STEP_BOUND_REACHED = "step_bound_reached"


@dataclass(frozen=True)
class Outcome:
    kind: OutcomeKind
    pc: int
    steps: int
    stack: tuple[int, ...]
    memory: tuple[int, ...]
    trace: tuple[int, ...]
    reason: str | None = None

    @property
    def bad(self) -> bool:
        return self.kind in {OutcomeKind.ASSERTION_FAILED, OutcomeKind.VM_TRAP}


def run(program: Program, inputs: list[int] | tuple[int, ...], steps: int = 256) -> Outcome:
    if len(inputs) != program.inputs:
        raise ValueError(f"expected {program.inputs} inputs, got {len(inputs)}")
    if steps < 0:
        raise ValueError("steps must be non-negative")
    words = tuple(_word(value) for value in inputs)
    stack: list[int] = []
    memory = [0] * program.memory
    pc = 0
    used = 0
    trace: list[int] = []

    def finish(kind: OutcomeKind, reason: str | None = None) -> Outcome:
        return Outcome(kind, pc, used, tuple(stack), tuple(memory), tuple(trace), reason)

    while True:
        if used >= steps:
            return finish(OutcomeKind.STEP_BOUND_REACHED)
        if pc < 0 or pc >= len(program.instructions):
            return finish(OutcomeKind.VM_TRAP, "program counter fell outside the program")
        ins = program.instructions[pc]
        trace.append(pc)
        used += 1
        opcode = ins.opcode

        required = 2 if opcode in {"SWAP", "ADD", "SUB", "MUL", "AND", "OR", "XOR", "EQ", "ULT"} else 1 if opcode in {"DUP", "DROP", "NOT", "STORE", "JNZ", "ASSUME", "ASSERT"} else 0
        if len(stack) < required:
            return finish(OutcomeKind.VM_TRAP, f"stack underflow in {opcode}")

        if opcode == "PUSH":
            stack.append(ins.operand)
        elif opcode == "INPUT":
            stack.append(words[ins.operand])
        elif opcode == "DUP":
            stack.append(stack[-1])
        elif opcode == "SWAP":
            stack[-1], stack[-2] = stack[-2], stack[-1]
        elif opcode == "DROP":
            stack.pop()
        elif opcode in {"ADD", "SUB", "MUL", "AND", "OR", "XOR", "EQ", "ULT"}:
            rhs = stack.pop()
            lhs = stack.pop()
            stack.append(_binary(opcode, lhs, rhs))
        elif opcode == "NOT":
            stack[-1] = (~stack[-1]) & MASK
        elif opcode == "LOAD":
            stack.append(memory[ins.operand])
        elif opcode == "STORE":
            memory[ins.operand] = stack.pop()
        elif opcode == "JMP":
            pc = ins.operand
            continue
        elif opcode == "JNZ":
            condition = stack.pop()
            if condition != 0:
                pc = ins.operand
                continue
        elif opcode == "ASSUME":
            if stack.pop() == 0:
                return finish(OutcomeKind.ASSUMPTION_REJECTED)
        elif opcode == "ASSERT":
            if stack.pop() == 0:
                return finish(OutcomeKind.ASSERTION_FAILED)
        elif opcode == "HALT":
            return finish(OutcomeKind.HALTED)
        pc += 1


def _word(value: int) -> int:
    if value < 0 or value > MASK:
        raise ValueError(f"input {value} is outside U32")
    return value


def _binary(opcode: str, lhs: int, rhs: int) -> int:
    if opcode == "ADD":
        return (lhs + rhs) & MASK
    if opcode == "SUB":
        return (lhs - rhs) & MASK
    if opcode == "MUL":
        return (lhs * rhs) & MASK
    if opcode == "AND":
        return lhs & rhs
    if opcode == "OR":
        return lhs | rhs
    if opcode == "XOR":
        return lhs ^ rhs
    if opcode == "EQ":
        return int(lhs == rhs)
    if opcode == "ULT":
        return int(lhs < rhs)
    raise AssertionError(opcode)
