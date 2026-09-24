from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from time import perf_counter


ROOT = Path(__file__).resolve().parents[2]
SMALLWOOD = ROOT / "smallwood-python"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", default="G256-5.fast.extended")
    parser.add_argument(
        "--smallwood-path",
        type=Path,
        default=SMALLWOOD,
        help="SmallWood/CAPSS Python checkout to benchmark",
    )
    parser.add_argument("--disable-rust", action="store_true")
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()
    if args.warmups < 0:
        raise SystemExit("--warmups must be non-negative")
    if args.runs < 1:
        raise SystemExit("--runs must be positive")

    smallwood_path = args.smallwood_path.resolve()
    if not (smallwood_path / "capss").is_dir():
        raise SystemExit(f"CAPSS package not found below {smallwood_path}")
    sys.path.insert(0, str(smallwood_path))

    if args.disable_rust:
        os.environ["CAPSS_DISABLE_RUST_GRIFFIN"] = "1"
    else:
        os.environ.pop("CAPSS_DISABLE_RUST_GRIFFIN", None)

    from capss.sign.instances import get_scheme
    from utils.log.section import Log

    Log.set_verbose(False)

    scheme = get_scheme(args.scheme)
    field = scheme.get_field()
    msg = [field.random_element()]
    pk, sk = scheme.keygen()

    for _ in range(args.warmups):
        warm_sig = scheme.sign(sk, msg)
        if not scheme.verify(pk, msg, warm_sig):
            raise SystemExit("warm-up signature failed to verify")

    sign_times = []
    verify_times = []
    ok = True
    sig = None
    for _ in range(args.runs):
        start = perf_counter()
        sig = scheme.sign(sk, msg)
        sign_times.append(perf_counter() - start)

        start = perf_counter()
        ok = ok and scheme.verify(pk, msg, sig)
        verify_times.append(perf_counter() - start)

    mode = "rust_off" if args.disable_rust else "rust_on"
    print(f"mode: {mode}")
    print(f"implementation: {smallwood_path}")
    print(f"scheme: {args.scheme}")
    print(f"warmup_runs: {args.warmups}")
    print(f"measured_runs: {args.runs}")
    print(f"signature_felts: {len(sig)}")
    print(f"signature_bytes: {len(sig) * 32}")
    print(f"signature_kb: {len(sig) * 32 / 1000:.3f}")
    print(f"sign_seconds: {sign_times[-1]:.3f}")
    print(f"sign_seconds_avg: {sum(sign_times) / len(sign_times):.3f}")
    print(f"sign_seconds_min: {min(sign_times):.3f}")
    print(f"verify_seconds: {verify_times[-1]:.3f}")
    print(f"verify_seconds_avg: {sum(verify_times) / len(verify_times):.3f}")
    print(f"verify_seconds_min: {min(verify_times):.3f}")
    print(f"ok: {ok}")


if __name__ == "__main__":
    main()
