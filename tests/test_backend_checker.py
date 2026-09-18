import json
import pathlib
import sys
import tempfile
import unittest

from host.assembly import parse
from host.backend import Domain, balanced_search, decode_candidate
from host.checker import check, replay_witness, write_witness
from host.symbolic import ExprFactory


class BendBackendTest(unittest.TestCase):
    def test_mixed_radix_and_right_subtree_hit(self):
        self.assertEqual(decode_candidate(7, (Domain(10, 12), Domain(20, 24))), (11, 22))
        factory = ExprFactory()
        predicate = factory.binary("EQ", factory.input(0), factory.const(11))
        hit = balanced_search((predicate,), (Domain(0, 15),), 16, "cpu", threads=4)
        self.assertEqual(hit, 11)

    def test_cpu_and_metal_choose_same_lowest_hit(self):
        factory = ExprFactory()
        x = factory.input(0)
        predicate = factory.binary("ULT", factory.const(13), x)
        domains = (Domain(0, 31),)
        self.assertEqual(balanced_search((predicate,), domains, 32, "cpu"), 14)
        if sys.platform == "darwin":
            self.assertEqual(balanced_search((predicate,), domains, 32, "gpu"), 14)

    def test_full_u32_domain_does_not_emit_out_of_range_literal(self):
        factory = ExprFactory()
        predicate = factory.binary("EQ", factory.input(0), factory.const(3))
        self.assertEqual(balanced_search((predicate,), (Domain(0, 4294967295),), 4, "cpu"), 3)


class CheckerTest(unittest.TestCase):
    def test_counterexample_is_replayed_and_portable(self):
        program = parse(".inputs 1\nINPUT 0\nDUP\nPUSH 1\nADD\nULT\nASSERT\nHALT\n")
        result = check(program, (Domain(4294967290, 4294967295),), 32, 100, 6, "cpu")
        self.assertEqual(result.status, "COUNTEREXAMPLE")
        self.assertEqual(result.inputs, (4294967295,))
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "witness.json"
            write_witness(path, program, (Domain(4294967290, 4294967295),), 32, "cpu", result)
            replayed = replay_witness(path)
            self.assertEqual(replayed.pc, 5)

    def test_candidate_truncation_is_incomplete(self):
        program = parse(".inputs 1\nPUSH 1\nASSERT\nHALT\n")
        result = check(program, (Domain(0, 9),), 8, 100, 3, "cpu")
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertEqual(result.checked_candidates, 3)

    def test_exhausted_scope_is_qualified(self):
        program = parse(".inputs 1\nPUSH 1\nASSERT\nHALT\n")
        result = check(program, (Domain(3, 5),), 8, 100, 3, "cpu")
        self.assertEqual(result.status, "EXHAUSTED_SCOPE")

    def test_corrupt_witness_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "witness.json"
            path.write_text(json.dumps({"artifact_version": 1, "vm_semantics": "bendsym-u32-v1", "program": "HALT\n", "program_sha256": "bad"}))
            with self.assertRaisesRegex(ValueError, "digest"):
                replay_witness(path)

    def test_branch_witness_round_trips(self):
        program = parse(".inputs 1\nINPUT 0\nJNZ bad\nHALT\nbad:\nPUSH 0\nASSERT\n")
        result = check(program, (Domain(0, 1),), 16, 100, 2, "cpu")
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "branch.json"
            write_witness(path, program, (Domain(0, 1),), 16, "cpu", result)
            self.assertEqual(replay_witness(path).pc, 4)

    def test_replay_rejects_non_integer_and_inconsistent_scope(self):
        program = parse(".inputs 1\nPUSH 0\nASSERT\n")
        result = check(program, (Domain(0, 1),), 8, 100, 2, "cpu")
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "witness.json"
            write_witness(path, program, (Domain(0, 1),), 8, "cpu", result)
            payload = json.loads(path.read_text())
            payload["inputs"] = [0.0]
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "U32 integers"):
                replay_witness(path)
            payload["inputs"] = [0]
            payload["candidate_index"] = 1
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "disagree"):
                replay_witness(path)

    def test_replay_rejects_non_object(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "witness.json"
            path.write_text("[]")
            with self.assertRaisesRegex(ValueError, "JSON object"):
                replay_witness(path)


if __name__ == "__main__":
    unittest.main()
