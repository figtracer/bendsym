from __future__ import annotations

from dataclasses import dataclass

from .assembly import Program
from .vm import MASK, _binary


class ExpressionLimit(Exception):
    pass


@dataclass(frozen=True)
class Expr:
    op: str
    value: int | None = None
    left: "Expr | None" = None
    right: "Expr | None" = None
    nodes: int = 1

    def render(self) -> str:
        if self.op == "CONST":
            return str(self.value)
        if self.op == "INPUT":
            return f"input[{self.value}]"
        if self.op == "NOT":
            return f"(~{self.left.render()})"
        if self.op == "IS_ZERO":
            return f"({self.left.render()} == 0)"
        if self.op == "IS_NONZERO":
            return f"({self.left.render()} != 0)"
        symbol = {"BOOL_AND": "&&", "AND": "&", "OR": "|", "XOR": "^", "EQ": "==", "ULT": "<"}.get(self.op, self.op.lower())
        return f"({self.left.render()} {symbol} {self.right.render()})"


class ExprFactory:
    def __init__(self, simplify: bool = True, max_nodes: int = 1024):
        self.simplify = simplify
        self.max_nodes = max_nodes

    def const(self, value: int) -> Expr:
        return Expr("CONST", value=value & MASK)

    def input(self, index: int) -> Expr:
        return Expr("INPUT", value=index)

    def unary(self, op: str, item: Expr) -> Expr:
        if self.simplify and item.op == "CONST":
            if op == "NOT":
                return self.const(~item.value)
            if op == "IS_ZERO":
                return self.const(int(item.value == 0))
            if op == "IS_NONZERO":
                return self.const(int(item.value != 0))
        return self._checked(Expr(op, left=item, nodes=1 + item.nodes))

    def binary(self, op: str, left: Expr, right: Expr) -> Expr:
        if self.simplify:
            folded = self._simplify_binary(op, left, right)
            if folded is not None:
                return folded
        return self._checked(Expr(op, left=left, right=right, nodes=1 + left.nodes + right.nodes))

    def conjunction(self, conditions: tuple[Expr, ...], extra: Expr | None = None) -> Expr:
        result = self.const(1)
        for condition in (*conditions, *((extra,) if extra is not None else ())):
            result = self.binary("BOOL_AND", result, condition)
        return result

    def _checked(self, expr: Expr) -> Expr:
        if expr.nodes > self.max_nodes:
            raise ExpressionLimit
        return expr

    def _simplify_binary(self, op: str, left: Expr, right: Expr) -> Expr | None:
        if left.op == right.op == "CONST":
            if op == "BOOL_AND":
                return self.const(int(left.value != 0 and right.value != 0))
            return self.const(_binary(op, left.value, right.value))
        if op == "BOOL_AND":
            if left.op == "CONST":
                return right if left.value != 0 else self.const(0)
            if right.op == "CONST":
                return left if right.value != 0 else self.const(0)
        if op in {"ADD", "OR", "XOR"}:
            if right.op == "CONST" and right.value == 0:
                return left
            if left.op == "CONST" and left.value == 0:
                return right
        if op == "SUB" and right.op == "CONST" and right.value == 0:
            return left
        if op == "MUL":
            if (left.op == "CONST" and left.value == 0) or (right.op == "CONST" and right.value == 0):
                return self.const(0)
            if left.op == "CONST" and left.value == 1:
                return right
            if right.op == "CONST" and right.value == 1:
                return left
        if op == "AND":
            if (left.op == "CONST" and left.value == 0) or (right.op == "CONST" and right.value == 0):
                return self.const(0)
            if left.op == "CONST" and left.value == MASK:
                return right
            if right.op == "CONST" and right.value == MASK:
                return left
        if left == right:
            if op in {"SUB", "XOR", "ULT"}:
                return self.const(0)
            if op == "EQ":
                return self.const(1)
        return None


def evaluate(expr: Expr, inputs: tuple[int, ...] | list[int]) -> int:
    if expr.op == "CONST":
        return expr.value
    if expr.op == "INPUT":
        return inputs[expr.value]
    left = evaluate(expr.left, inputs)
    if expr.op == "NOT":
        return (~left) & MASK
    if expr.op == "IS_ZERO":
        return int(left == 0)
    if expr.op == "IS_NONZERO":
        return int(left != 0)
    right = evaluate(expr.right, inputs)
    if expr.op == "BOOL_AND":
        return int(left != 0 and right != 0)
    return _binary(expr.op, left, right)


@dataclass(frozen=True)
class BadQuery:
    id: int
    pc: int
    kind: str
    predicate: Expr


@dataclass(frozen=True)
class ExploreResult:
    queries: tuple[BadQuery, ...]
    expansions: int
    halted_paths: int
    rejected_paths: int
    bounded_paths: int
    incomplete_paths: int

    @property
    def incomplete(self) -> bool:
        return self.incomplete_paths > 0


@dataclass(frozen=True)
class _State:
    pc: int
    fuel: int
    stack: tuple[Expr, ...]
    memory: tuple[Expr, ...]
    constraints: tuple[Expr, ...]


def explore(program: Program, steps: int = 256, state_budget: int = 4096, max_expr_nodes: int = 1024, simplify: bool = True) -> ExploreResult:
    if steps < 0 or state_budget < 0 or max_expr_nodes < 1:
        raise ValueError("bounds must be non-negative and expression limit must be positive")
    factory = ExprFactory(simplify=simplify, max_nodes=max_expr_nodes)
    initial = _State(0, steps, (), tuple(factory.const(0) for _ in range(program.memory)), ())
    work = [initial]
    queries: list[BadQuery] = []
    expansions = halted = rejected = bounded = incomplete = 0

    def add_query(state: _State, kind: str, extra: Expr | None = None) -> None:
        predicate = factory.conjunction(state.constraints, extra)
        if predicate.op != "CONST" or predicate.value != 0:
            queries.append(BadQuery(len(queries), state.pc, kind, predicate))

    while work:
        if expansions >= state_budget:
            incomplete += len(work)
            break
        state = work.pop()
        expansions += 1
        if state.fuel == 0:
            bounded += 1
            continue
        if state.pc < 0 or state.pc >= len(program.instructions):
            try:
                add_query(state, "vm_trap")
            except ExpressionLimit:
                incomplete += 1
            continue
        ins = program.instructions[state.pc]
        stack = list(state.stack)
        memory = list(state.memory)
        constraints = state.constraints
        opcode = ins.opcode
        required = 2 if opcode in {"SWAP", "ADD", "SUB", "MUL", "AND", "OR", "XOR", "EQ", "ULT"} else 1 if opcode in {"DUP", "DROP", "NOT", "STORE", "JNZ", "ASSUME", "ASSERT"} else 0
        if len(stack) < required:
            try:
                add_query(state, "vm_trap")
            except ExpressionLimit:
                incomplete += 1
            continue

        next_pc = state.pc + 1
        next_fuel = state.fuel - 1
        try:
            if opcode == "PUSH":
                stack.append(factory.const(ins.operand))
            elif opcode == "INPUT":
                stack.append(factory.input(ins.operand))
            elif opcode == "DUP":
                stack.append(stack[-1])
            elif opcode == "SWAP":
                stack[-1], stack[-2] = stack[-2], stack[-1]
            elif opcode == "DROP":
                stack.pop()
            elif opcode in {"ADD", "SUB", "MUL", "AND", "OR", "XOR", "EQ", "ULT"}:
                rhs, lhs = stack.pop(), stack.pop()
                stack.append(factory.binary(opcode, lhs, rhs))
            elif opcode == "NOT":
                stack[-1] = factory.unary("NOT", stack[-1])
            elif opcode == "LOAD":
                stack.append(memory[ins.operand])
            elif opcode == "STORE":
                memory[ins.operand] = stack.pop()
            elif opcode == "JMP":
                next_pc = ins.operand
            elif opcode in {"JNZ", "ASSUME", "ASSERT"}:
                condition = stack.pop()
                zero = factory.unary("IS_ZERO", condition)
                nonzero = factory.unary("IS_NONZERO", condition)
                base = _State(next_pc, next_fuel, tuple(stack), tuple(memory), constraints)
                if opcode == "ASSERT":
                    add_query(state, "assertion_failed", zero)
                if opcode == "JNZ":
                    zero_state = _State(next_pc, next_fuel, tuple(stack), tuple(memory), constraints + (() if zero.op == "CONST" else (zero,)))
                    nonzero_state = _State(ins.operand, next_fuel, tuple(stack), tuple(memory), constraints + (() if nonzero.op == "CONST" else (nonzero,)))
                    if nonzero.op != "CONST" or nonzero.value != 0:
                        work.append(nonzero_state)
                    if zero.op != "CONST" or zero.value != 0:
                        work.append(zero_state)
                    continue
                if opcode == "ASSUME" and zero.op == "CONST" and zero.value != 0:
                    rejected += 1
                    continue
                if opcode == "ASSERT" and zero.op == "CONST" and zero.value != 0:
                    continue
                if nonzero.op == "CONST" and nonzero.value == 0:
                    if opcode == "ASSUME":
                        rejected += 1
                    continue
                if nonzero.op != "CONST":
                    base = _State(base.pc, base.fuel, base.stack, base.memory, constraints + (nonzero,))
                work.append(base)
                continue
            elif opcode == "HALT":
                halted += 1
                continue
            work.append(_State(next_pc, next_fuel, tuple(stack), tuple(memory), constraints))
        except ExpressionLimit:
            incomplete += 1

    return ExploreResult(tuple(queries), expansions, halted, rejected, bounded, incomplete)
