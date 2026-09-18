from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


U32_MAX = 2**32 - 1


class AssemblyError(ValueError):
    pass


@dataclass(frozen=True)
class Instruction:
    opcode: str
    operand: int | None
    line: int


@dataclass(frozen=True)
class Program:
    instructions: tuple[Instruction, ...]
    inputs: int
    memory: int
    source: str

    def canonical(self) -> str:
        lines = [f".inputs {self.inputs}", f".memory {self.memory}"]
        for ins in self.instructions:
            suffix = "" if ins.operand is None else f" {ins.operand}"
            lines.append(f"{ins.opcode}{suffix}")
        return "\n".join(lines) + "\n"


NO_OPERAND = {
    "DUP", "SWAP", "DROP", "ADD", "SUB", "MUL", "AND", "OR", "XOR",
    "NOT", "EQ", "ULT", "ASSUME", "ASSERT", "HALT",
}
U32_OPERAND = {"PUSH"}
INDEX_OPERAND = {"INPUT", "LOAD", "STORE"}
LABEL_OPERAND = {"JMP", "JNZ"}
ALL_OPS = NO_OPERAND | U32_OPERAND | INDEX_OPERAND | LABEL_OPERAND


def parse_file(path: str | Path) -> Program:
    source = Path(path).read_text(encoding="utf-8")
    return parse(source)


def parse(source: str) -> Program:
    inputs = None
    memory = None
    labels: dict[str, int] = {}
    pending: list[tuple[str, str | None, int]] = []

    for line_no, original in enumerate(source.splitlines(), 1):
        text = original.split("#", 1)[0].strip()
        if not text:
            continue
        if text.startswith("."):
            parts = text.split()
            if len(parts) != 2 or parts[0] not in {".inputs", ".memory"}:
                raise AssemblyError(f"line {line_no}: invalid declaration")
            try:
                value = int(parts[1], 0)
            except ValueError as error:
                raise AssemblyError(f"line {line_no}: invalid declaration value") from error
            if value < 0 or value > U32_MAX:
                raise AssemblyError(f"line {line_no}: declaration is outside U32")
            if parts[0] == ".inputs":
                if inputs is not None:
                    raise AssemblyError(f"line {line_no}: duplicate .inputs")
                inputs = value
            else:
                if memory is not None:
                    raise AssemblyError(f"line {line_no}: duplicate .memory")
                memory = value
            continue
        if text.endswith(":"):
            label = text[:-1].strip()
            if not label or not label.replace("_", "a").isalnum():
                raise AssemblyError(f"line {line_no}: invalid label")
            if label in labels:
                raise AssemblyError(f"line {line_no}: duplicate label {label}")
            labels[label] = len(pending)
            continue

        parts = text.split()
        opcode = parts[0].upper()
        if opcode not in ALL_OPS:
            raise AssemblyError(f"line {line_no}: unknown opcode {parts[0]}")
        expected = 0 if opcode in NO_OPERAND else 1
        if len(parts) != expected + 1:
            raise AssemblyError(f"line {line_no}: {opcode} expects {expected} operand(s)")
        pending.append((opcode, parts[1] if expected else None, line_no))

    inputs = 0 if inputs is None else inputs
    memory = 0 if memory is None else memory
    instructions: list[Instruction] = []
    for opcode, raw, line_no in pending:
        operand = None
        if opcode in LABEL_OPERAND:
            if raw not in labels:
                raise AssemblyError(f"line {line_no}: unknown label {raw}")
            operand = labels[raw]
        elif raw is not None:
            try:
                operand = int(raw, 0)
            except ValueError as error:
                raise AssemblyError(f"line {line_no}: invalid integer {raw}") from error
            if operand < 0 or operand > U32_MAX:
                raise AssemblyError(f"line {line_no}: operand is outside U32")
            if opcode == "INPUT" and operand >= inputs:
                raise AssemblyError(f"line {line_no}: input {operand} is not declared")
            if opcode in {"LOAD", "STORE"} and operand >= memory:
                raise AssemblyError(f"line {line_no}: memory slot {operand} is not declared")
        instructions.append(Instruction(opcode, operand, line_no))

    return Program(tuple(instructions), inputs, memory, source)
