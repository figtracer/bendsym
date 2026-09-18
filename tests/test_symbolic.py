import itertools
import unittest

from host.assembly import parse
from host.symbolic import ExprFactory, evaluate, explore
from host.vm import run


class ExpressionTest(unittest.TestCase):
    def test_asymmetric_operations_and_wrapping(self):
        factory = ExprFactory(simplify=False)
        x = factory.input(0)
        self.assertEqual(evaluate(factory.binary("SUB", x, factory.const(5)), [2]), 4294967293)
        self.assertEqual(evaluate(factory.binary("ULT", x, factory.const(5)), [2]), 1)
        self.assertEqual(evaluate(factory.binary("ULT", factory.const(5), x), [2]), 0)

    def test_simplification_preserves_values(self):
        raw = ExprFactory(simplify=False)
        simple = ExprFactory(simplify=True)
        for value in [0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]:
            x1, x2 = raw.input(0), simple.input(0)
            cases = [
                (raw.binary("ADD", x1, raw.const(0)), simple.binary("ADD", x2, simple.const(0))),
                (raw.binary("MUL", raw.const(1), x1), simple.binary("MUL", simple.const(1), x2)),
                (raw.binary("XOR", x1, x1), simple.binary("XOR", x2, x2)),
                (raw.binary("EQ", x1, x1), simple.binary("EQ", x2, x2)),
            ]
            for before, after in cases:
                self.assertEqual(evaluate(before, [value]), evaluate(after, [value]))


class SymbolicExplorerTest(unittest.TestCase):
    def assert_differential(self, source, domains, steps=64):
        program = parse(source)
        for simplify in [False, True]:
            result = explore(program, steps=steps, simplify=simplify)
            self.assertFalse(result.incomplete)
            for inputs in itertools.product(*domains):
                symbolic_bad = any(evaluate(query.predicate, inputs) != 0 for query in result.queries)
                self.assertEqual(symbolic_bad, run(program, inputs, steps).bad, (simplify, inputs))

    def test_branch_assertion_partition(self):
        self.assert_differential(
            ".inputs 1\nINPUT 0\nJNZ nonzero\nPUSH 1\nASSERT\nHALT\nnonzero:\nPUSH 0\nASSERT\nHALT\n",
            [range(4)],
        )

    def test_constant_false_branch_takes_fallthrough(self):
        self.assert_differential(
            "PUSH 0\nJNZ taken\nPUSH 0\nASSERT\nHALT\ntaken:\nPUSH 1\nASSERT\nHALT\n",
            [],
        )

    def test_assumption_and_two_input_arithmetic(self):
        self.assert_differential(
            ".inputs 2\nINPUT 0\nASSUME\nINPUT 0\nINPUT 1\nSUB\nASSERT\nHALT\n",
            [range(3), range(3)],
        )

    def test_branch_local_memory(self):
        self.assert_differential(
            ".inputs 1\n.memory 1\nINPUT 0\nJNZ nz\nPUSH 7\nSTORE 0\nJMP check\nnz:\nPUSH 9\nSTORE 0\ncheck:\nLOAD 0\nPUSH 7\nEQ\nASSERT\nHALT\n",
            [range(3)],
        )

    def test_resource_limit_is_explicit(self):
        program = parse("loop:\nJMP loop\n")
        result = explore(program, steps=100, state_budget=3)
        self.assertTrue(result.incomplete)


if __name__ == "__main__":
    unittest.main()
