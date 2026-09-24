# Rust Griffin Backend

Prototype Rust backend for the CAPSS Griffin permutation and sponge hash.

The first goal is compatibility with the existing Python/Sage implementation:
Python still builds the Griffin parameters and passes the field modulus,
round constants, MDS matrix, and alpha/beta constants into Rust. The optimized
arithmetic path uses the fixed-width Montgomery representation provided by
`ark_bn254::Fr`; unsupported fields automatically remain on the Sage path.

## Build

```bash
cd Implementation/rust-griffin
python -m pip install maturin
maturin develop --release
```

For local experiments without installing `maturin`, the current Python code can
also import a copied extension module directly from this directory:

```bash
cd Implementation/rust-griffin
cargo build --release
cp target/release/librust_griffin.so rust_griffin.so
```

## Current API

- `griffin_permutation(...)`: one Griffin permutation.
- `griffin_sponge(...)`: SpongeHashFunction-compatible hash.
- `griffin_sponge_bytes(...)`: same sponge hash with field elements passed and
  returned as fixed-width bytes.
- `griffin_decs_leaf_hashes(...)`: batch helper for DECS leaf hashes.
- `griffin_truncated_merkle_tree(...)`: parallel Merkle tree builder for
  Griffin-based truncation compression.
- `griffin_decs_commit_tree_bytes(...)`: fused DECS helper that hashes all
  leaves and builds the Merkle tree in one Rust call.
- `griffin_expanded_merkle_root_from_auth_path_bytes(...)`: verifier-side
  helper that recomputes an expanded Merkle authentication path in Rust.

The older compatibility functions pass field elements as decimal or `0x`
strings. The hot-path helpers use 32-byte big-endian field-element buffers to
avoid Python/Rust hex conversion overhead.

## Checks and Benchmarks

```bash
cd Implementation/rust-griffin
PYTHONPATH="$PWD" sage --python3 python/compare_with_sage.py \
  --scheme G256-5.fast.extended --input-size 8 --output-size 1
PYTHONPATH="$PWD" sage --python3 python/bench_leaf_hashes.py \
  --scheme G256-5.fast.extended --leaves 1024 --check-sage
RAYON_NUM_THREADS=16 PYTHONPATH="$PWD" sage --python3 python/compare_merkle_with_sage.py \
  --scheme G256-5.fast.extended --leaves 1024
PYTHONPATH="$PWD" sage --python3 python/bench_signature.py \
  --scheme G256-5.fast.extended --warmups 1 --runs 5
PYTHONPATH="$PWD" sage --python3 python/bench_signature.py \
  --smallwood-path ../external/smallwood-python-official \
  --scheme G256-5.fast.extended --disable-rust --warmups 1 --runs 5
PYTHONPATH="$PWD" sage --python3 python/bench_signature.py \
  --scheme G256-5.fast.extended --disable-rust
```

## Next step

The optional backend is now auto-detected by the Python/Sage code. Set
`CAPSS_DISABLE_RUST_GRIFFIN=1` to force the Sage fallback, or
`CAPSS_RUST_GRIFFIN_STRICT=1` to raise backend errors instead of falling back.
For narrower comparisons, set `CAPSS_DISABLE_RUST_COMMIT_TREE=1` to disable
only the fused leaf-hash-plus-Merkle path, or `CAPSS_DISABLE_RUST_SPONGE=1` to
disable only the generic sponge hook. Set `CAPSS_DISABLE_RUST_AUTH_PATH=1` to
disable only the verifier-side expanded Merkle authentication-path helper.

Leaf hashing uses Rayon. Set `RAYON_NUM_THREADS=<n>` to choose the number of
worker threads for the batch hash, fused commit tree, and Merkle compression,
for example:

```bash
RAYON_NUM_THREADS=4 PYTHONPATH="$PWD" sage --python3 python/bench_signature.py \
  --scheme G256-5.fast.extended
```

The paper-facing comparison against the official Python checkout can be run
from `Implementation` with:

```bash
PYTHONPATH=. sage --python3 -m BDAC.benchmarks.compare_griffin_upstream \
  --runs 30 --threads 14
```
