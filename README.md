# BendSym

BendSym is a bounded symbolic-execution workbench that turns irregular program
paths into balanced finite-domain searches for [Bend 2](https://github.com/bendlang/bend).
It can inspect symbolic failure predicates, search them on multicore CPUs or
Apple GPUs, and produce counterexamples that are always replayed concretely.

```text
assembly → symbolic paths → Bend CPU/GPU search → concrete replay → witness
```

## Quick start

Requires Python 3.11+, Bun, Git, and Clang. Metal additionally requires current
Xcode command-line tools.

```sh
git clone https://github.com/figtracer/bendsym.git
cd bendsym
./scripts/setup-toolchain.sh

./bendsym doctor
./bendsym explore examples/wrapping-counter.bsvm

./bendsym check examples/wrapping-counter.bsvm \
  --domain 0=4294967290..4294967295 \
  --backend gpu --witness witness.json

./bendsym replay witness.json
```

The check reports candidate 5, input `4294967295`, where the claim `x < x + 1`
fails under wrapping U32 arithmetic. Replace `--backend gpu` with `cpu` on any
supported machine.

## VM programs

Programs are small stack-machine assemblies:

```text
.inputs 1
.memory 0
INPUT 0
DUP
PUSH 1
ADD
ULT
ASSERT
HALT
```

The VM has arithmetic, bitwise operations, branches, assumptions, assertions,
fixed memory, and explicit instruction fuel. See [the exact semantics](docs/semantics.md)
and the [`examples`](examples) directory.

## Commands

- `bendsym run PROGRAM --inputs 1,2 --trace` executes concretely.
- `bendsym explore PROGRAM` prints symbolic bad-path predicates.
- `bendsym check PROGRAM --domain 0=0..255 ...` performs bounded search.
- `bendsym replay WITNESS.json` independently verifies an artifact.
- `bendsym doctor` checks Bun, Bend, and Clang.

`check` exits 0 for `EXHAUSTED_SCOPE`, 1 for `COUNTEREXAMPLE`, 3 for
`INCOMPLETE`, and 2 for operational errors. It never prints unqualified “safe”
or “UNSAT.” Input zero varies fastest when multiple domains are supplied.

## Development

```sh
make test
```

The suite includes raw-versus-simplified symbolic differential checks, an
independent concrete VM, CLI/artifact integration tests, native Bend execution,
and CPU/Metal witness parity on macOS. See [architecture](docs/architecture.md),
[limitations](docs/limitations.md), and [contributing](CONTRIBUTING.md).

Licensed under MIT.
