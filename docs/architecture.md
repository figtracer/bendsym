# Architecture

```text
assembly → validated program → symbolic CPU exploration → bad-path predicates
                                                        ↓
                         concrete replay ← Bend balanced CPU/GPU search
```

Python's standard library owns assembly parsing, irregular DFS exploration,
artifacts, and process orchestration. The pure candidate predicate generated
from symbolic paths is compiled by pinned Bend 2.0.5. Bend evaluates a complete
binary tree of candidate slots and deterministically reduces it to the lowest
matching index. GPU runs use Bend's `!` call marker; CPU builds omit it so they
do not require a GPU toolchain.

Input zero varies fastest in mixed-radix enumeration. Padded leaves are masked.
Search does not cancel lanes, use atomics, or maintain shared best-witness
state. A hit is published only after the original VM reproduces the failure.

Generated Bend programs are content-addressed under `.build/cache`. They are
implementation artifacts, not a stable API.
