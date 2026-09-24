from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter


THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from compare_with_sage import _extract_griffin_params, _hex_vec  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", default="G256-5.fast.extended")
    parser.add_argument("--leaves", type=int, default=1024)
    parser.add_argument("--check-sage", action="store_true")
    args = parser.parse_args()

    try:
        import rust_griffin
    except ImportError as error:
        raise SystemExit(
            "rust_griffin is not installed. Build it with `maturin develop --release` "
            "or copy target/release/librust_griffin.so to rust_griffin.so."
        ) from error

    params = _extract_griffin_params(args.scheme)
    scheme = params["scheme"]
    sw = scheme._blank_sw
    decs = sw.pcs.lvcs.decs
    field = params["perm"].get_field()

    salt = [field.random_element() for _ in range(sw.get_salt_size())]
    leaf_len = decs.nb_polys + decs.eta
    leaves = [
        [field.random_element() for _ in range(leaf_len)]
        for _ in range(args.leaves)
    ]

    t0 = perf_counter()
    rust_hashes = rust_griffin.griffin_decs_leaf_hashes(
        params["modulus"],
        params["alpha"],
        params["root_exponent"],
        params["round_constants"],
        params["mds"],
        params["alphas"],
        params["betas"],
        _hex_vec(salt),
        [_hex_vec(leaf) for leaf in leaves],
        sw.get_hash_digest_size(),
        params["rate"],
        params["capacity"],
        params["using_tweak_hir18"],
        params["capacity_last"],
    )
    rust_time = perf_counter() - t0

    print(f"scheme: {args.scheme}")
    print(f"leaves: {args.leaves}")
    print(f"leaf_len: {leaf_len} field elements")
    print(f"rust_seconds: {rust_time:.3f}")

    if args.check_sage:
        t0 = perf_counter()
        sage_hashes = []
        for idx, leaf in enumerate(leaves):
            domain_separator = salt[:]
            domain_separator[-1] += idx
            sage_hashes.append(
                _hex_vec(params["sponge"](domain_separator + leaf, output_size=sw.get_hash_digest_size()))
            )
        sage_time = perf_counter() - t0
        print(f"sage_seconds: {sage_time:.3f}")
        print(f"speedup: {sage_time / rust_time:.2f}x")
        if rust_hashes != sage_hashes:
            raise SystemExit("mismatch")
        print("match: yes")


if __name__ == "__main__":
    main()
