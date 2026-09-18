# Limitations

BendSym 0.1 is a bounded research workbench, not an SMT solver or a claim of
unrestricted program safety.

- Values are U32; there is no U256, division, remainder, or symbolic address.
- Memory has fixed immediate-indexed slots.
- Symbolic exploration has no feasibility solver, path merging, or state
  deduplication. Contradictory symbolic paths may survive until candidate
  evaluation.
- Search is exhaustive only for the explicitly supplied domains and candidate
  budget. `INCOMPLETE` never becomes `EXHAUSTED_SCOPE`.
- The instruction bound defines the analyzed scope. Reports disclose how many
  paths reached it.
- GPU search is currently verified on Apple Metal. CUDA is unverified.
- Generated Bend compilation dominates small searches; binaries are cached.
- Bend 2 is young and the pinned source revision is part of the product's
  compatibility contract.
