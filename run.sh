#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
IMPLEMENTATION_ROOT="${IMPLEMENTATION_ROOT:-$REPO_ROOT/Implementation}"

MODE="smoke"
AURORA_VERSION="normal"
THREADS="${BENCHMARK_THREADS:-8}"
OUTPUT_DIR=""
SKIP_BUILD=0
SKIP_TESTS=0

usage() {
    cat <<'EOF'
Usage: ./run.sh [smoke|paper] [options]

Modes:
  smoke                 One measured trial; validates the artifact quickly.
  paper                 Thirty measured trials; reproduces paper-facing values.

Options:
  --aurora-version V    normal (default) or v2.
  --threads N           OpenMP and Rayon worker count (default: 8).
  --output DIR          Result directory (default: results/<timestamp>-<mode>).
  --implementation DIR  Path to the Implementation directory.
  --skip-build          Reuse existing native binaries.
  --skip-tests          Skip the regression test suite.
  -h, --help            Show this help.
EOF
}

if [[ $# -gt 0 && ( "$1" == "smoke" || "$1" == "paper" ) ]]; then
    MODE="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --aurora-version) AURORA_VERSION="$2"; shift 2 ;;
        --threads) THREADS="$2"; shift 2 ;;
        --output) OUTPUT_DIR="$2"; shift 2 ;;
        --implementation) IMPLEMENTATION_ROOT="$2"; shift 2 ;;
        --skip-build) SKIP_BUILD=1; shift ;;
        --skip-tests) SKIP_TESTS=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ "$AURORA_VERSION" != "normal" && "$AURORA_VERSION" != "v2" ]]; then
    echo "--aurora-version must be normal or v2" >&2
    exit 2
fi
if ! [[ "$THREADS" =~ ^[1-9][0-9]*$ ]]; then
    echo "--threads must be a positive integer" >&2
    exit 2
fi
if [[ ! -d "$IMPLEMENTATION_ROOT/BDAC" ]]; then
    echo "BDAC implementation not found at $IMPLEMENTATION_ROOT" >&2
    exit 2
fi

if [[ -n "${BENCHMARK_PYTHON:-}" ]]; then
    if [[ ! -x "$BENCHMARK_PYTHON" ]]; then
        echo "BENCHMARK_PYTHON is not executable: $BENCHMARK_PYTHON" >&2
        exit 2
    fi
    PYTHON=("$BENCHMARK_PYTHON")
elif command -v sage >/dev/null 2>&1; then
    PYTHON=(sage --python3)
elif python3 -c 'import sage.all' >/dev/null 2>&1; then
    PYTHON=(python3)
elif python -c 'import sage.all' >/dev/null 2>&1; then
    PYTHON=(python)
else
    PYTHON=()
    for conda_exe in \
        "$HOME/miniforge3/bin/conda" \
        "$HOME/mambaforge/bin/conda" \
        "$HOME/miniconda3/bin/conda" \
        "$HOME/anaconda3/bin/conda" \
        "/opt/conda/bin/conda"; do
        if [[ -x "$conda_exe" ]] && \
           "$conda_exe" run -n sage python -c 'import sage.all' >/dev/null 2>&1; then
            PYTHON=("$conda_exe" run --no-capture-output -n sage python)
            break
        fi
    done
    for candidate in \
        "$HOME/miniforge3/envs/sage/bin/python" \
        "$HOME/mambaforge/envs/sage/bin/python" \
        "$HOME/miniconda3/envs/sage/bin/python" \
        "$HOME/anaconda3/envs/sage/bin/python" \
        "/opt/conda/envs/sage/bin/python"; do
        if [[ ${#PYTHON[@]} -eq 0 && -x "$candidate" ]] && \
           "$candidate" -c 'import sage.all' >/dev/null 2>&1; then
            PYTHON=("$candidate")
            break
        fi
    done
    if [[ ${#PYTHON[@]} -eq 0 ]]; then
        echo "A Sage-enabled Python environment is required." >&2
        echo "Activate it or set BENCHMARK_PYTHON=/path/to/its/python." >&2
        exit 2
    fi
fi

if [[ -z "$OUTPUT_DIR" ]]; then
    RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-${MODE}-${AURORA_VERSION}"
    OUTPUT_DIR="$SCRIPT_DIR/results/$RUN_ID"
fi
mkdir -p "$OUTPUT_DIR/logs"
OUTPUT_DIR="$(cd -- "$OUTPUT_DIR" && pwd)"

export OMP_NUM_THREADS="$THREADS"
export OMP_DYNAMIC=FALSE
export RAYON_NUM_THREADS="$THREADS"
export PYTHONPATH="$IMPLEMENTATION_ROOT${PYTHONPATH:+:$PYTHONPATH}"

run_logged() {
    local name="$1"
    shift
    echo
    echo "==> $name"
    "$@" 2>&1 | tee "$OUTPUT_DIR/logs/$name.log"
}

build_native() {
    command -v cmake >/dev/null || { echo "cmake is required" >&2; exit 2; }
    command -v cargo >/dev/null || { echo "cargo is required" >&2; exit 2; }

    run_logged build-rust-griffin \
        cargo build --release --manifest-path "$IMPLEMENTATION_ROOT/rust-griffin/Cargo.toml"
    cp "$IMPLEMENTATION_ROOT/rust-griffin/target/release/librust_griffin.so" \
       "$IMPLEMENTATION_ROOT/rust-griffin/rust_griffin.so"

    run_logged build-rust-wots \
        cargo build --release --manifest-path "$IMPLEMENTATION_ROOT/rust-wots/Cargo.toml"
    cp "$IMPLEMENTATION_ROOT/rust-wots/target/release/librust_wots.so" \
       "$IMPLEMENTATION_ROOT/rust-wots/rust_wots.so"

    run_logged configure-aurora \
        cmake -S "$IMPLEMENTATION_ROOT/capss-aggregation" \
              -B "$IMPLEMENTATION_ROOT/capss-aggregation/build-openmp" \
              -DCMAKE_BUILD_TYPE=Release
    run_logged build-aurora \
        cmake --build "$IMPLEMENTATION_ROOT/capss-aggregation/build-openmp" \
              --target test_blake2b_absorption test_bcs_query_binding \
                       aurora_prove_r1cs_256_zk_save_bin \
                       aurora_verify_r1cs_256_zk_bin \
              --parallel "$THREADS"
}

if [[ "$SKIP_BUILD" -eq 0 ]]; then
    build_native
fi

cd "$IMPLEMENTATION_ROOT"

if [[ "$SKIP_TESTS" -eq 0 ]]; then
    run_logged python-tests "${PYTHON[@]}" -m unittest discover -s BDAC/tests -p 'test_*.py'
fi

if [[ "$MODE" == "paper" ]]; then
    ITERS=30
else
    ITERS=1
fi

BENCHMARK_JSON="$OUTPUT_DIR/benchmark.json"
run_logged benchmark \
    "${PYTHON[@]}" -u -m BDAC.benchmarks.paper_preview \
    --aurora-version "$AURORA_VERSION" \
    --aurora-iters "$ITERS" \
    --issuance-iters "$ITERS" \
    --micro-iters "$ITERS" \
    --skip-scaling \
    --out "$BENCHMARK_JSON"

"${PYTHON[@]}" "$SCRIPT_DIR/collect_environment.py" \
    --implementation-root "$IMPLEMENTATION_ROOT" \
    --output "$OUTPUT_DIR/environment.json" \
    --mode "$MODE" \
    --aurora-version "$AURORA_VERSION" \
    --threads "$THREADS"

"${PYTHON[@]}" "$SCRIPT_DIR/summarize.py" \
    "$BENCHMARK_JSON" "$OUTPUT_DIR/environment.json" "$OUTPUT_DIR"

echo
echo "Benchmark completed successfully."
echo "Report: $OUTPUT_DIR/REPORT.md"
echo "Raw data: $BENCHMARK_JSON"
