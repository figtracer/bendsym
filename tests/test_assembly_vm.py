import unittest

from host.assembly import AssemblyError, parse
from host.vm import OutcomeKind, run


class AssemblyTest(unittest.TestCase):
    def test_labels_and_declarations_are_resolved(self):
        program = parse(".inputs 1\n.memory 0\nINPUT 0\nJNZ yes\nHALT\nyes:\nHALT\n")
        self.assertEqual(program.instructions[1].operand, 3)

    def test_invalid_unreachable_operand_is_rejected(self):
        with self.assertRaisesRegex(AssemblyError, "input 1 is not declared"):
            parse(".inputs 1\nHALT\nINPUT 1\n")

    def test_unknown_label_is_rejected(self):
        with self.assertRaisesRegex(AssemblyError, "unknown label"):
            parse("JMP missing\n")


class ConcreteVmTest(unittest.TestCase):
    def test_wrapping_and_operand_order(self):
        add = parse("PUSH 4294967295\nPUSH 1\nADD\nHALT\n")
        sub = parse("PUSH 2\nPUSH 5\nSUB\nHALT\n")
        self.assertEqual(run(add, []).stack, (0,))
        self.assertEqual(run(sub, []).stack, (4294967293,))

    def test_all_nonzero_words_are_true(self):
        program = parse(".inputs 1\nINPUT 0\nJNZ yes\nPUSH 0\nASSERT\nyes:\nHALT\n")
        self.assertEqual(run(program, [2]).kind, OutcomeKind.HALTED)
        self.assertEqual(run(program, [0]).kind, OutcomeKind.ASSERTION_FAILED)

    def test_false_assumption_is_not_a_failure(self):
        program = parse("PUSH 0\nASSUME\nPUSH 0\nASSERT\n")
        self.assertEqual(run(program, []).kind, OutcomeKind.ASSUMPTION_REJECTED)

    def test_branch_memory_isolation_cases(self):
        program = parse(".inputs 1\n.memory 1\nINPUT 0\nJNZ nz\nPUSH 7\nSTORE 0\nJMP done\nnz:\nPUSH 9\nSTORE 0\ndone:\nLOAD 0\nHALT\n")
        self.assertEqual(run(program, [0]).memory, (7,))
        self.assertEqual(run(program, [3]).memory, (9,))

    def test_fuel_boundary_counts_halt(self):
        program = parse("HALT\n")
        self.assertEqual(run(program, [], 0).kind, OutcomeKind.STEP_BOUND_REACHED)
        self.assertEqual(run(program, [], 1).kind, OutcomeKind.HALTED)

    def test_underflow_is_a_trap(self):
        outcome = run(parse("PUSH 1\nADD\n"), [])
        self.assertEqual(outcome.kind, OutcomeKind.VM_TRAP)
        self.assertEqual(outcome.pc, 1)


if __name__ == "__main__":
    unittest.main()
