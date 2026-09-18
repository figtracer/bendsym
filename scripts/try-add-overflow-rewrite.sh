#!/usr/bin/env sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
backend=${1:-cpu}
witness="$root/.build/add-overflow-u8-mutant-$backend.json"
mkdir -p "$root/.build"

case "$backend" in
  cpu|gpu) ;;
  *) echo "usage: $0 [cpu|gpu]" >&2; exit 2 ;;
esac

common="--domain 0=0..255 --domain 1=0..255 --candidate-budget 65536 --backend $backend"

echo "== Correct strict-overflow rewrite: exhaust all 65,536 pairs =="
# The arguments are fixed numeric tokens; deliberate splitting keeps the command readable.
# shellcheck disable=SC2086
"$root/bendsym" check "$root/examples/rewrites/add-overflow-u8.bsvm" $common

echo
echo "== Off-by-one mutant: require a replayed boundary counterexample =="
set +e
# shellcheck disable=SC2086
"$root/bendsym" check "$root/examples/rewrites/add-overflow-u8-mutant.bsvm" $common --witness "$witness"
status=$?
set -e
if [ "$status" -ne 1 ]; then
  echo "error: expected COUNTEREXAMPLE (exit 1), got exit $status" >&2
  exit 1
fi
"$root/bendsym" replay "$witness"
