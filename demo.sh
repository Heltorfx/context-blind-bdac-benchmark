#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
IMPLEMENTATION_ROOT="${IMPLEMENTATION_ROOT:-$SCRIPT_DIR/implementation}"
COMMAND="${1:-presentation}"
BACKEND="${2:-aurora}"
AURORA_VERSION="${AURORA_VERSION:-normal}"
THREADS="${DEMO_THREADS:-8}"

if [[ "$COMMAND" != "issuance" && "$COMMAND" != "presentation" ]]; then
    echo "Usage: ./demo.sh [issuance|presentation] [aurora|longfellow]" >&2
    exit 2
fi
if [[ "$BACKEND" != "aurora" && "$BACKEND" != "longfellow" ]]; then
    echo "Backend must be aurora or longfellow" >&2
    exit 2
fi

if [[ ! -d "$IMPLEMENTATION_ROOT/BDAC" ]]; then
    echo "Implementation not found at $IMPLEMENTATION_ROOT" >&2
    exit 2
fi

if [[ -n "${BENCHMARK_PYTHON:-}" ]]; then
    PYTHON=("$BENCHMARK_PYTHON")
elif command -v sage >/dev/null 2>&1; then
    PYTHON=(sage --python3)
elif python3 -c 'import sage.all' >/dev/null 2>&1; then
    PYTHON=(python3)
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
    if [[ ${#PYTHON[@]} -eq 0 ]]; then
        echo "A Sage-enabled Python environment is required." >&2
        echo "Activate it or set BENCHMARK_PYTHON=/path/to/python." >&2
        exit 2
    fi
fi

export OMP_NUM_THREADS="$THREADS"
export OMP_DYNAMIC=FALSE
export RAYON_NUM_THREADS="$THREADS"
export PYTHONPATH="$IMPLEMENTATION_ROOT${PYTHONPATH:+:$PYTHONPATH}"

cd "$IMPLEMENTATION_ROOT"

if [[ "$COMMAND" == "issuance" ]]; then
    exec "${PYTHON[@]}" -u -m BDAC.demos.full_flow_demo --skip-presentation
fi

if [[ "$BACKEND" == "longfellow" ]]; then
    BINARY="${LONGFELLOW_BINARY:-$SCRIPT_DIR/longfellow-zk/build-bdac/zk/bdac_r1cs_bench}"
    if [[ ! -x "$BINARY" ]]; then
        echo "Longfellow binary not found at $BINARY; run ./setup-longfellow.sh first." >&2
        exit 2
    fi
    exec "${PYTHON[@]}" -u -m BDAC.demos.full_flow_demo \
        --backend longfellow --longfellow-binary "$BINARY"
fi

exec "${PYTHON[@]}" -u -m BDAC.demos.full_flow_demo \
    --aurora-version "$AURORA_VERSION"
