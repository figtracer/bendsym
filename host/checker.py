from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from .assembly import Program, U32_MAX, parse
from .backend import Domain, balanced_search, decode_candidate
from .symbolic import explore
from .vm import Outcome, run


ARTIFACT_VERSION = 1


@dataclass(frozen=True)
class CheckResult:
    status: str
    checked_candidates: int
    total_candidates: int
    inputs: tuple[int, ...] | None = None
    candidate_index: int | None = None
    outcome: Outcome | None = None
    bounded_paths: int = 0
    detail: str | None = None


def check(program: Program, domains: tuple[Domain, ...], steps: int, state_budget: int, candidate_budget: int, backend: str, threads: int = 0, gpu_memory: str = "1GB") -> CheckResult:
    _validate_domains(program, domains)
    if candidate_budget < 0:
        raise ValueError("candidate budget must be non-negative")
    total = 1
    for domain in domains:
        total *= domain.size
    checked = min(total, candidate_budget)
    if checked > U32_MAX:
        raise ValueError("a single Bend search is limited to 4294967295 candidates")
    symbolic = explore(program, steps=steps, state_budget=state_budget)
    if symbolic.incomplete:
        return CheckResult("INCOMPLETE", 0, total, bounded_paths=symbolic.bounded_paths, detail="symbolic exploration budget or expression limit reached")
    hit = balanced_search(tuple(query.predicate for query in symbolic.queries), domains, checked, backend, threads, gpu_memory)
    if hit is not None:
        inputs = decode_candidate(hit, domains)
        outcome = run(program, inputs, steps)
        if not outcome.bad:
            raise RuntimeError("symbolic witness did not replay concretely")
        return CheckResult("COUNTEREXAMPLE", checked, total, inputs, hit, outcome, symbolic.bounded_paths)
    if checked < total:
        return CheckResult("INCOMPLETE", checked, total, bounded_paths=symbolic.bounded_paths, detail="candidate budget exhausted")
    return CheckResult("EXHAUSTED_SCOPE", checked, total, bounded_paths=symbolic.bounded_paths)


def write_witness(path: str | Path, program: Program, domains: tuple[Domain, ...], steps: int, backend: str, result: CheckResult) -> None:
    if result.status != "COUNTEREXAMPLE" or result.outcome is None:
        raise ValueError("only a counterexample can be written as a witness")
    canonical = program.canonical()
    payload = {
        "artifact_version": ARTIFACT_VERSION,
        "vm_semantics": "bendsym-u32-v1",
        "program": canonical,
        "program_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "domains": [asdict(domain) for domain in domains],
        "steps": steps,
        "backend": backend,
        "candidate_index": result.candidate_index,
        "inputs": list(result.inputs),
        "failure": {
            "kind": result.outcome.kind.value,
            "pc": result.outcome.pc,
            "steps": result.outcome.steps,
            "reason": result.outcome.reason,
            "trace": list(result.outcome.trace),
        },
    }
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def replay_witness(path: str | Path) -> Outcome:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("witness must be a JSON object")
    if payload.get("artifact_version") != ARTIFACT_VERSION or payload.get("vm_semantics") != "bendsym-u32-v1":
        raise ValueError("unsupported witness version")
    source = payload.get("program")
    if not isinstance(source, str):
        raise ValueError("witness program must be a string")
    if hashlib.sha256(source.encode()).hexdigest() != payload.get("program_sha256"):
        raise ValueError("witness program digest does not match")
    program = parse(source)
    domains_data = payload.get("domains")
    inputs = payload.get("inputs")
    candidate_index = payload.get("candidate_index")
    steps = payload.get("steps")
    if not isinstance(domains_data, list) or len(domains_data) != program.inputs:
        raise ValueError("witness domains do not match declared inputs")
    domains: list[Domain] = []
    for item in domains_data:
        if not isinstance(item, dict) or not _integer(item.get("start")) or not _integer(item.get("end")):
            raise ValueError("witness contains an invalid domain")
        domain = Domain(item["start"], item["end"])
        if domain.start < 0 or domain.end < domain.start or domain.end > U32_MAX:
            raise ValueError("witness contains an invalid U32 domain")
        domains.append(domain)
    if not isinstance(inputs, list) or len(inputs) != program.inputs or any(not _integer(value) or value < 0 or value > U32_MAX for value in inputs):
        raise ValueError("witness inputs must be declared U32 integers")
    if not _integer(candidate_index) or candidate_index < 0:
        raise ValueError("witness candidate index must be non-negative")
    total = 1
    for domain in domains:
        total *= domain.size
    if candidate_index >= total or decode_candidate(candidate_index, tuple(domains)) != tuple(inputs):
        raise ValueError("witness candidate index, domains, and inputs disagree")
    if not _integer(steps) or steps < 0:
        raise ValueError("witness steps must be a non-negative integer")
    failure = payload.get("failure")
    if not isinstance(failure, dict):
        raise ValueError("witness failure must be an object")
    if not isinstance(failure.get("kind"), str) or not _integer(failure.get("pc")) or not _integer(failure.get("steps")):
        raise ValueError("witness failure metadata is invalid")
    trace = failure.get("trace")
    if not isinstance(trace, list) or any(not _integer(pc) or pc < 0 for pc in trace):
        raise ValueError("witness trace must contain non-negative integers")
    if failure.get("reason") is not None and not isinstance(failure.get("reason"), str):
        raise ValueError("witness failure reason is invalid")
    outcome = run(program, inputs, steps)
    if not outcome.bad or outcome.kind.value != failure["kind"] or outcome.pc != failure["pc"] or outcome.steps != failure["steps"] or list(outcome.trace) != failure["trace"]:
        raise RuntimeError("witness replay mismatch")
    return outcome


def _validate_domains(program: Program, domains: tuple[Domain, ...]) -> None:
    if len(domains) != program.inputs:
        raise ValueError(f"expected domains for {program.inputs} inputs, got {len(domains)}")
    for domain in domains:
        if domain.start < 0 or domain.end < domain.start or domain.end > U32_MAX:
            raise ValueError("invalid U32 domain")


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
