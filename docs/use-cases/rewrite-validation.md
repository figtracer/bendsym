# Bit-vector rewrite validation

BendSym can act as a reduced-width soundness gate for arithmetic rewrites in
symbolic engines, compilers, circuit optimizers, and embedded code.

The first case comes from Foundry's symbolic solver normalization. Its unsigned
addition-overflow rewrite uses the identity:

```text
(base + increment) < base  iff  ~base < increment
```

The bundled model checks the 8-bit analogue while retaining BendSym's U32 host
words. Every addition result is masked with `0xff`, and complement is represented
as `base ^ 0xff`. Run all 65,536 input pairs with:

```sh
./scripts/try-add-overflow-rewrite.sh cpu
./scripts/try-add-overflow-rewrite.sh gpu  # Apple Metal
```

The correct rule reports `EXHAUSTED_SCOPE`. A control model mutates strict `<`
to `<=`; BendSym returns the lowest disagreement, `base=255, increment=0`, and
replays it concretely before saving the witness.

Reduced-width exhaustion is not a proof of the 256-bit rule. Its value is as a
high-sensitivity test for operand reversal, strictness, masking, wraparound, and
boundary mistakes. A counterexample often generalizes immediately; an exhausted
scope gives evidence only for the declared width and domains.

The next reusable layer should parse source/target expressions and generate this
VM comparison automatically. Width sweeps and candidate tiling can then turn a
directory of rewrite rules into a CI soundness corpus.
