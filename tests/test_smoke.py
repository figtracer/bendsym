import os
import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BEND = os.environ.get("BEND", f"bun {ROOT.parent / 'bend/bend2/main.ts'}")


class ToolchainSmokeTest(unittest.TestCase):
    def test_interpreter_finds_deterministic_witness(self):
        result = subprocess.run(
            [*BEND.split(), "src/Smoke.bend"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.stdout.strip(), "44")

    def test_native_finds_same_witness(self):
        subprocess.run(["make", "build"], cwd=ROOT, check=True)
        result = subprocess.run(
            [str(ROOT / ".build/smoke"), "--threads", "4"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.stdout.strip(), "44")


if __name__ == "__main__":
    unittest.main()
