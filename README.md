# BendSym

BendSym is a bounded symbolic-execution workbench built with
[Bend 2](https://github.com/bendlang/bend). It explores irregular program paths
on the CPU and evaluates finite candidate domains as balanced parallel workloads
on CPUs or GPUs.

The repository is under active construction. The initial toolchain spike pins
Bend 2.0.5 and verifies that reusable expression trees produce identical
witnesses in interpreted and native parallel execution.

## Toolchain

Clone Bend beside this repository and check out the pinned revision:

```sh
git clone https://github.com/bendlang/bend.git ../bend
git -C ../bend checkout 0b7e2b11c1054f5d0f4eb955cadb47997ef1115d
make test
```

Requires Bun and Apple Clang 17 or newer for Metal builds.
