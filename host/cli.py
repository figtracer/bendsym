from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .assembly import AssemblyError, parse_file
from .backend import BackendError, Domain
from .checker import check, replay_witness, write_witness
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
    check_parser = commands.add_parser("check", help="search finite input domains for a counterexample")
    check_parser.add_argument("program")
    check_parser.add_argument("--domain", action="append", default=[], metavar="I=START..END")
    check_parser.add_argument("--steps", type=int, default=256)
    check_parser.add_argument("--state-budget", type=int, default=4096)
    check_parser.add_argument("--candidate-budget", type=int, default=65536)
    check_parser.add_argument("--backend", choices=["cpu", "gpu"], default="cpu")
    check_parser.add_argument("--threads", type=int, default=0)
    check_parser.add_argument("--gpu-memory", default="1GB")
    check_parser.add_argument("--witness")
    check_parser.add_argument("--json", action="store_true")
    replay_parser = commands.add_parser("replay", help="replay and validate a witness artifact")
    replay_parser.add_argument("witness")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            return doctor()
        if args.command == "replay":
            outcome = replay_witness(args.witness)
            print(f"REPLAYED {outcome.kind.value} pc={outcome.pc} steps={outcome.steps}")
            return 0
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
        if args.command == "check":
            domains = parse_domains(args.domain, program.inputs)
            result = check(program, domains, args.steps, args.state_budget, args.candidate_budget, args.backend, args.threads, args.gpu_memory)
            payload = {
                "status": result.status,
                "checked_candidates": result.checked_candidates,
                "total_candidates": result.total_candidates,
                "domains": [{"start": domain.start, "end": domain.end} for domain in domains],
                "steps": args.steps,
                "bounded_paths": result.bounded_paths,
                "candidate_index": result.candidate_index,
                "inputs": list(result.inputs) if result.inputs is not None else None,
                "detail": result.detail,
            }
            if result.outcome is not None:
                payload["failure"] = {"kind": result.outcome.kind.value, "pc": result.outcome.pc, "steps": result.outcome.steps}
            if args.witness and result.status == "COUNTEREXAMPLE":
                write_witness(args.witness, program, domains, args.steps, args.backend, result)
            print(json.dumps(payload, sort_keys=True) if args.json else format_check(payload))
            return {"EXHAUSTED_SCOPE": 0, "COUNTEREXAMPLE": 1, "INCOMPLETE": 3}[result.status]
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
    except (AssemblyError, BackendError, RuntimeError, ValueError, OSError, json.JSONDecodeError, KeyError) as error:
        if getattr(args, "json", False):
            print(json.dumps({"status": "ERROR", "detail": str(error)}, sort_keys=True))
        else:
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


def parse_domains(specifications: list[str], inputs: int) -> tuple[Domain, ...]:
    parsed: dict[int, Domain] = {}
    for specification in specifications:
        try:
            index_text, bounds = specification.split("=", 1)
            start_text, end_text = bounds.split("..", 1)
            index = int(index_text)
            domain = Domain(int(start_text, 0), int(end_text, 0))
        except ValueError as error:
            raise ValueError(f"invalid domain {specification!r}; expected I=START..END") from error
        if index in parsed:
            raise ValueError(f"duplicate domain for input {index}")
        parsed[index] = domain
    if set(parsed) != set(range(inputs)):
        raise ValueError(f"provide exactly one --domain for each input 0..{inputs - 1}")
    return tuple(parsed[index] for index in range(inputs))


def format_check(payload: dict) -> str:
    lines = [payload["status"], f"checked={payload['checked_candidates']}/{payload['total_candidates']} steps={payload['steps']} domains={payload['domains']} bounded_paths={payload['bounded_paths']}"]
    if payload["inputs"] is not None:
        lines.append(f"candidate={payload['candidate_index']} inputs={payload['inputs']}")
    if payload["detail"]:
        lines.append(payload["detail"])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
