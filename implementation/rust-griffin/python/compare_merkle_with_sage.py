from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from compare_with_sage import _extract_griffin_params, _hex_vec  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", default="G256-5.fast.extended")
    parser.add_argument("--leaves", type=int, default=1024)
    args = parser.parse_args()

    try:
        import rust_griffin
    except ImportError as error:
        raise SystemExit(
            "rust_griffin is not installed. Build it with `cargo build --release` "
            "and copy target/release/librust_griffin.so to rust_griffin.so."
        ) from error

    params = _extract_griffin_params(args.scheme)
    scheme = params["scheme"]
    sw = scheme._blank_sw
    factory = sw.pcs.lvcs.decs.tree_factory
    arity = factory.get_arity()
    if len(set(arity)) != 1:
        raise SystemExit(f"mixed arities are not supported by this comparison: {arity}")

    compression = factory.compression_function[arity[0]]
    compression_perm = compression.perm
    from sage.all import xgcd

    modulus = int(compression_perm.get_field().order())
    _, root_exp, _ = xgcd(compression_perm.alpha, modulus - 1)
    root_exp = int(root_exp % (modulus - 1))

    field = compression_perm.get_field()
    leaves = [
        [field.random_element() for _ in range(factory.output_size)]
        for _ in range(args.leaves)
    ]

    previous_disable = os.environ.get("CAPSS_DISABLE_RUST_GRIFFIN")
    os.environ["CAPSS_DISABLE_RUST_GRIFFIN"] = "1"
    try:
        py_tree = factory.expand_tree(leaves)
        py_root = _hex_vec(py_tree.get_root())
    finally:
        if previous_disable is None:
            os.environ.pop("CAPSS_DISABLE_RUST_GRIFFIN", None)
        else:
            os.environ["CAPSS_DISABLE_RUST_GRIFFIN"] = previous_disable

    rust_tree = rust_griffin.griffin_truncated_merkle_tree(
        hex(modulus),
        int(compression_perm.alpha),
        hex(root_exp),
        _hex_vec(compression_perm.round_constants),
        [_hex_vec(row) for row in compression_perm.MDS_matrix.rows()],
        _hex_vec(compression_perm.alphas),
        _hex_vec(compression_perm.betas),
        [_hex_vec(leaf) for leaf in leaves],
        arity[0],
        factory.output_size,
    )
    rust_root = rust_tree[0][0]

    print(f"scheme: {args.scheme}")
    print(f"leaves: {args.leaves}")
    print(f"python_root: {py_root}")
    print(f"rust_root:   {rust_root}")
    if [value.lower() for value in rust_root] != py_root:
        raise SystemExit("mismatch")
    print("match: yes")


if __name__ == "__main__":
    main()
