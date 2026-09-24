from __future__ import annotations

import argparse
import json
import sys
from time import perf_counter

from BDAC.parameters import SMALLWOOD_PATH


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--labels",
        nargs="+",
        default=[
            "G256-5.fast.extended",
            "A256-3.default.extended",
        ],
    )
    parser.add_argument("--message-size", type=int, default=3)
    args = parser.parse_args()

    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))

    from capss.sign.instances import get_scheme
    from capss.sign.r1cs import build_r1cs_for_verification
    from utils.log import Log

    Log.set_verbose(False)
    rows = []
    for label in args.labels:
        scheme = get_scheme(label)
        build_start = perf_counter()
        r1cs = build_r1cs_for_verification(scheme, args.message_size)
        build_seconds = perf_counter() - build_start
        rows.append(
            {
                "label": label,
                "message_size": args.message_size,
                "security_bits": float(scheme.get_security()[0]),
                "public_key_elements": scheme.get_public_key_size(),
                "signature_elements": scheme.get_signature_size(),
                "signature_bytes_32": scheme.get_signature_size() * 32,
                "r1cs_variables": r1cs.get_nb_variables(),
                "r1cs_constraints": r1cs.get_nb_equations(),
                "r1cs_build_seconds": build_seconds,
            }
        )
    print(json.dumps(rows, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
