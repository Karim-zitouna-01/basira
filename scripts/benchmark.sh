#!/usr/bin/env bash
set -euo pipefail
# Use a separate directory: never touch A's data or the delivered sample.
cd "$(dirname "$0")/.."
benchmark_dir=$(mktemp -d /tmp/basira-b-benchmark.XXXXXX)
python -m signaux.demo --data-dir "$benchmark_dir/data" --n 5250
python -m signaux.run --data-dir "$benchmark_dir/data"
python -m signaux.checks --data-dir "$benchmark_dir/data" --strict
cp "$benchmark_dir/data/signaux/rapport_execution.json" docs/benchmark_5250.json
printf 'Résultats et entrées du benchmark conservés : %s\n' "$benchmark_dir"
