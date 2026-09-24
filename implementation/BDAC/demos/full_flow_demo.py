from __future__ import annotations

import argparse
from time import perf_counter

from BDAC import (
    Enrollment,
    GovernanceAuthority,
    Issuance,
    Issuer,
    Presentation,
    SE,
    Setup,
    User,
    Verifier,
)
from BDAC.proofs import precompute_show_r1cs_template


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aurora-version", choices=("normal", "v2"), default="normal")
    parser.add_argument(
        "--skip-presentation",
        action="store_true",
        help="Run only enrollment and issuance.",
    )
    parser.add_argument(
        "--no-zk",
        action="store_true",
        help="Use the old non-ZK Aurora backend for debugging only.",
    )
    parser.add_argument(
        "--debug-r1cs-check",
        action="store_true",
        help="Run the local Python/Sage R1CS satisfaction check before Aurora.",
    )
    parser.add_argument(
        "--no-precompute-r1cs-template",
        action="store_true",
        help="Do not precompute the static Show R1CS template before presentation.",
    )
    args = parser.parse_args()
    if args.no_zk and args.aurora_version == "v2":
        parser.error("Aurora v2 requires ZK mode")

    start = perf_counter()
    pp = Setup()
    governance = GovernanceAuthority(pp)
    issuer = Issuer(pp)
    se = SE(pp)
    user = User(pp, se)
    verifier = Verifier(pp)
    precompute_seconds = None
    if not args.skip_presentation and not args.no_precompute_r1cs_template:
        precompute_start = perf_counter()
        precompute_show_r1cs_template()
        precompute_seconds = perf_counter() - precompute_start

    enrollment = Enrollment().run(user, governance)
    issuance = Issuance().run(user, issuer)

    print("=== BDAC full flow ===")
    print(f"capss_scheme: {pp.capss_scheme_label}")
    if precompute_seconds is not None:
        print(f"show_r1cs_template_precompute: {precompute_seconds:.2f}s")
    else:
        print("show_r1cs_template_precompute: skipped")
    print()
    print("[1] Enrollment")
    print("    Governance -> User: attributes")
    print(f"    attribute_count: {enrollment.attribute_count}")
    print()
    print("[2] Issuance")
    print("    User -> Issuer: attributes, dpk")
    print("    Issuer -> User: root, commitment state, cred = SigI(root || dpk)")
    print(f"    credential_signature_ok: {issuance.credential_signature_ok}")
    print(f"    total_sent_size: {issuance.message_sizes['total']} bytes")
    print(f"    issuance_ok: {issuance.ok}")
    flow_ok = issuance.ok

    if not args.skip_presentation:
        print()
        print("[3] Presentation")
        presentation_start = perf_counter()
        make_zk = not args.no_zk
        presentation = Presentation(
            make_zk=make_zk,
            debug_r1cs_check=args.debug_r1cs_check,
            aurora_version=args.aurora_version,
        ).run(user, verifier, se)
        presentation_elapsed = perf_counter() - presentation_start
        print("    Verifier -> User: nonce_P, idx_P")
        print("    User -> SE: c_P = Com(nonce_P; r_P)")
        print("    SE -> User: sig_D(c_P)")
        print("    User -> Verifier: disclosed attrs, Aurora proof")
        print(f"    proof_backend: {'Aurora ZK optimized' if make_zk else 'Aurora non-ZK debug'}")
        print(f"    aurora_version: {args.aurora_version}")
        print(f"    requested_indexes: {list(presentation.requested_indexes)}")
        if presentation.r1cs_result is None:
            print("    debug_r1cs_check: skipped")
        else:
            print(f"    debug_r1cs_check: {presentation.r1cs_result.proof_ok}")
            print(f"    debug_r1cs_seconds: {presentation.r1cs_seconds:.2f}")
        print(f"    aurora_result: {presentation.aurora_result['verifier_result']}")
        print(f"    aurora_omp_threads: {presentation.aurora_result.get('omp_num_threads')}")
        print(f"    aurora_prove_seconds: {presentation.aurora_result['prove_seconds']:.2f}")
        print(f"    aurora_verify_seconds: {presentation.aurora_result['verify_seconds']:.2f}")
        print(f"    proof_size: {presentation.aurora_result['proof_size_bytes']} bytes")
        print(f"    presentation_ok: {presentation.ok}")
        print(f"    presentation_seconds: {presentation_elapsed:.2f}")
        print(f"    total_sent_size: {presentation.message_sizes['total']} bytes")
        flow_ok = flow_ok and presentation.ok

    print()
    print("[summary]")
    print(f"    flow_ok: {flow_ok}")
    print(f"    elapsed_seconds: {perf_counter() - start:.2f}")


if __name__ == "__main__":
    main()
