from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SMALLWOOD = ROOT / "smallwood-python"
sys.path.insert(0, str(SMALLWOOD))


def _hex_vec(values):
    return [hex(int(value)) for value in values]


def _extract_griffin_params(scheme_label: str):
    from capss.sign.instances import get_scheme
    from sage.all import xgcd

    scheme = get_scheme(scheme_label)
    sw = scheme._blank_sw
    xof = sw._hash_xof
    sponge = list(xof._perms.values())[0] if hasattr(xof, "_perms") else xof
    perm = sponge.perm
    modulus = int(perm.get_field().order())
    _, root_exp, _ = xgcd(perm.alpha, modulus - 1)
    root_exp = int(root_exp % (modulus - 1))
    return {
        "scheme": scheme,
        "sponge": sponge,
        "perm": perm,
        "modulus": hex(modulus),
        "alpha": int(perm.alpha),
        "root_exponent": hex(root_exp),
        "round_constants": _hex_vec(perm.round_constants),
        "mds": [_hex_vec(row) for row in perm.MDS_matrix.rows()],
        "alphas": _hex_vec(perm.alphas),
        "betas": _hex_vec(perm.betas),
        "rate": int(sponge.get_rate()),
        "capacity": int(sponge.get_capacity()),
        "using_tweak_hir18": bool(sponge.using_tweak_hir18),
        "capacity_last": bool(sponge.capacity_last),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", default="G256-5.fast.extended")
    parser.add_argument("--output-size", type=int, default=1)
    parser.add_argument("--input-size", type=int, default=8)
    args = parser.parse_args()

    try:
        import rust_griffin
    except ImportError as error:
        raise SystemExit(
            "rust_griffin is not installed. Build it with `maturin develop --release` first."
        ) from error

    params = _extract_griffin_params(args.scheme)
    field = params["perm"].get_field()
    inputs = [field.random_element() for _ in range(args.input_size)]

    previous_disable = os.environ.get("CAPSS_DISABLE_RUST_SPONGE")
    os.environ["CAPSS_DISABLE_RUST_SPONGE"] = "1"
    try:
        sage_output = params["sponge"](inputs, output_size=args.output_size)
    finally:
        if previous_disable is None:
            os.environ.pop("CAPSS_DISABLE_RUST_SPONGE", None)
        else:
            os.environ["CAPSS_DISABLE_RUST_SPONGE"] = previous_disable

    rust_output = rust_griffin.griffin_sponge(
        params["modulus"],
        params["alpha"],
        params["root_exponent"],
        params["round_constants"],
        params["mds"],
        params["alphas"],
        params["betas"],
        _hex_vec(inputs),
        args.output_size,
        params["rate"],
        params["capacity"],
        params["using_tweak_hir18"],
        params["capacity_last"],
    )

    sage_hex = _hex_vec(sage_output)
    print(f"scheme: {args.scheme}")
    print(f"inputs: {args.input_size} field elements")
    print(f"sage: {sage_hex}")
    print(f"rust: {rust_output}")
    if [value.lower() for value in rust_output] != sage_hex:
        raise SystemExit("mismatch")
    print("match: yes")


if __name__ == "__main__":
    main()
