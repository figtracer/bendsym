# Witness artifact format

Version 1 witness files are JSON containing the canonical program, SHA-256
digest, VM semantic version, finite domains, instruction bound, backend,
candidate index, decoded inputs, and the concrete failure trace.

`bendsym replay` verifies the digest, reparses the embedded program, executes it
from scratch, and requires the outcome kind, PC, step count, and complete trace
to match. A mismatch is an operational error rather than a counterexample.
