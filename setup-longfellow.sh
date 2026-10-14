#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/longfellow-zk"
REVISION="35720f145b2128e0322d04561d4578d4d31e82a1"

for tool in git cmake; do
    command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 2; }
done

if [[ ! -e "$SOURCE_DIR" ]]; then
    git clone https://github.com/google/longfellow-zk.git "$SOURCE_DIR"
    git -C "$SOURCE_DIR" checkout --detach "$REVISION"
elif [[ "$(git -C "$SOURCE_DIR" rev-parse HEAD)" != "$REVISION" ]]; then
    echo "Existing Longfellow source has a different revision: $SOURCE_DIR" >&2
    exit 2
fi

ADAPTER="$SOURCE_DIR/lib/zk/bdac_r1cs_bench.cc"
if [[ -e "$ADAPTER" ]] && ! cmp -s "$ADAPTER" "$SCRIPT_DIR/longfellow/bdac_r1cs_bench.cc"; then
    echo "Existing Longfellow adapter differs; refusing to overwrite it: $ADAPTER" >&2
    exit 2
fi
cp "$SCRIPT_DIR/longfellow/bdac_r1cs_bench.cc" "$ADAPTER"

CMAKE_FILE="$SOURCE_DIR/lib/zk/CMakeLists.txt"
if ! grep -q '^add_executable(bdac_r1cs_bench ' "$CMAKE_FILE"; then
    printf '\nadd_executable(bdac_r1cs_bench bdac_r1cs_bench.cc)\ntarget_link_libraries(bdac_r1cs_bench PRIVATE algebra util crypto zstd)\n' >> "$CMAKE_FILE"
fi

cmake -DCMAKE_BUILD_TYPE=Release -S "$SOURCE_DIR/lib" -B "$SOURCE_DIR/build-bdac"
cmake --build "$SOURCE_DIR/build-bdac" --target bdac_r1cs_bench -j "${BUILD_JOBS:-4}"
echo "Longfellow backend ready. Run: ./demo.sh presentation longfellow"
