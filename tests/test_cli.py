import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CliTest(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([str(ROOT / "bendsym"), *args], cwd=ROOT, text=True, capture_output=True)

    def test_run_and_explore_json(self):
        run = self.invoke("run", "examples/wrapping-counter.bsvm", "--inputs", "0", "--json")
        self.assertEqual(run.returncode, 0)
        self.assertEqual(json.loads(run.stdout)["outcome"], "halted")
        explored = self.invoke("explore", "examples/wrapping-counter.bsvm", "--json")
        self.assertEqual(explored.returncode, 0)
        self.assertEqual(len(json.loads(explored.stdout)["queries"]), 1)

    def test_check_exit_code_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            witness = pathlib.Path(directory) / "witness.json"
            checked = self.invoke(
                "check", "examples/wrapping-counter.bsvm", "--domain", "0=4294967294..4294967295",
                "--witness", str(witness), "--json",
            )
            self.assertEqual(checked.returncode, 1)
            self.assertEqual(json.loads(checked.stdout)["inputs"], [4294967295])
            replay = self.invoke("replay", str(witness))
            self.assertEqual(replay.returncode, 0)
            self.assertIn("REPLAYED assertion_failed", replay.stdout)

    def test_missing_domain_is_an_error(self):
        result = self.invoke("check", "examples/wrapping-counter.bsvm")
        self.assertEqual(result.returncode, 2)
        self.assertIn("provide exactly one", result.stderr)


if __name__ == "__main__":
    unittest.main()
