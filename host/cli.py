from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .assembly import AssemblyError, parse_file
from .vm import run


ROOT = Path(__file__).resolve().parents[1]
BEND = Path(os.environ.get("BEND_ROOT", ROOT.parent / "bend")) / "bend2/main.ts"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="bendsym", description="Bounded symbolic execution powered by Bend")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="check the local toolchain")
    run_parser = commands.add_parser("run", help="execute a program concretely")
    run_parser.add_argument("program")
    run_parser.add_argument("--inputs", default="", help="comma-separated U32 values")
    run_parser.add_argument("--steps", type=int, default=256)
    run_parser.add_argument("--trace", action="store_true")
    run_parser.add_argument("--json", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            return doctor()
        program = parse_file(args.program)
        inputs = [] if not args.inputs else [int(item.strip(), 0) for item in args.inputs.split(",")]
        outcome = run(program, inputs, args.steps)
        result = {
            "outcome": outcome.kind.value,
            "pc": outcome.pc,
            "steps": outcome.steps,
            "stack": list(outcome.stack),
            "memory": list(outcome.memory),
            "reason": outcome.reason,
        }
        if args.trace:
            result["trace"] = list(outcome.trace)
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(outcome.kind.value.upper())
            print(f"pc={outcome.pc} steps={outcome.steps} stack={list(outcome.stack)} memory={list(outcome.memory)}")
            if outcome.reason:
                print(outcome.reason)
            if args.trace:
                print("trace=" + ",".join(map(str, outcome.trace)))
        return 1 if outcome.bad else 0
    except (AssemblyError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def doctor() -> int:
    checks = [("bun", ["bun", "--version"]), ("bend", ["bun", str(BEND), "--version"]), ("clang", ["clang", "--version"])]
    failed = False
    for name, command in checks:
        try:
            result = subprocess.run(command, text=True, capture_output=True, check=True)
            print(f"{name}: {result.stdout.splitlines()[0]}")
        except (OSError, subprocess.CalledProcessError) as error:
            failed = True
            print(f"{name}: unavailable ({error})")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
