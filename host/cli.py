from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .assembly import AssemblyError, parse_file
from .symbolic import explore
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
    explore_parser = commands.add_parser("explore", help="enumerate symbolic failure paths")
    explore_parser.add_argument("program")
    explore_parser.add_argument("--steps", type=int, default=256)
    explore_parser.add_argument("--state-budget", type=int, default=4096)
    explore_parser.add_argument("--expr-nodes", type=int, default=1024)
    explore_parser.add_argument("--no-simplify", action="store_true")
    explore_parser.add_argument("--json", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            return doctor()
        program = parse_file(args.program)
        if args.command == "explore":
            result = explore(program, args.steps, args.state_budget, args.expr_nodes, not args.no_simplify)
            payload = {
                "status": "incomplete" if result.incomplete else "explored",
                "expansions": result.expansions,
                "halted_paths": result.halted_paths,
                "rejected_paths": result.rejected_paths,
                "bounded_paths": result.bounded_paths,
                "incomplete_paths": result.incomplete_paths,
                "queries": [{"id": query.id, "pc": query.pc, "kind": query.kind, "predicate": query.predicate.render(), "nodes": query.predicate.nodes} for query in result.queries],
            }
            if args.json:
                print(json.dumps(payload, sort_keys=True))
            else:
                print(payload["status"].upper())
                print(f"expansions={result.expansions} queries={len(result.queries)} halted={result.halted_paths} rejected={result.rejected_paths} bounded={result.bounded_paths} incomplete={result.incomplete_paths}")
                for query in result.queries:
                    print(f"query {query.id}: {query.kind} at pc={query.pc}: {query.predicate.render()}")
            return 3 if result.incomplete else 0
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
