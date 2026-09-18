# Contributing

Run `./scripts/setup-toolchain.sh` once, then `make test`. Every semantic change
must include an asymmetric case where a plausible incorrect implementation
produces a different result. Changes to concrete execution should have a
matching raw-versus-simplified symbolic differential test.

Do not describe bounded exhaustion as safety or solver UNSAT. Counterexamples
must continue to pass concrete replay. GPU changes must preserve deterministic
lowest-candidate selection and be checked on real hardware when available.
