from __future__ import annotations

import argparse
from collections import OrderedDict
from time import perf_counter
from typing import Callable, TypeVar

from BDAC import GovernanceAuthority, Issuer, SE, Setup, User, Verifier
from BDAC.core.types import IssuedCredential, PresentationRequest
from BDAC.proofs.aurora_backend import AuroraBackend
from BDAC.proofs.show_backend import (
    build_show_proof_instance,
    compute_show_message_sizes,
    precompute_show_r1cs_template,
    prove_show_r1cs,
)
from BDAC.protocols.enrollment import Enrollment


T = TypeVar("T")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-zk",
        action="store_true",
        help="Profile the old non-ZK Aurora backend instead of the ZK backend.",
    )
    parser.add_argument(
        "--debug-r1cs-check",
        action="store_true",
        help="Include the local Python/Sage R1CS satisfaction check in the profile.",
    )
    parser.add_argument(
        "--no-precompute-r1cs-template",
        action="store_true",
        help="Do not precompute the static Show R1CS template during setup.",
    )
    args = parser.parse_args()

    setup_timings: OrderedDict[str, float] = OrderedDict()
    issuance_timings: OrderedDict[str, float] = OrderedDict()
    presentation_timings: OrderedDict[str, float] = OrderedDict()

    total_start = perf_counter()
    pp = _timed(setup_timings, "Setup(lambda, l)", Setup)
    governance = _timed(setup_timings, "GovernanceAuthority init", lambda: GovernanceAuthority(pp))
    issuer = _timed(setup_timings, "Issuer init / CAPSS keygen", lambda: Issuer(pp))
    se = _timed(setup_timings, "SE init / CAPSS keygen", lambda: SE(pp))
    user = _timed(setup_timings, "User init", lambda: User(pp, se))
    verifier = _timed(setup_timings, "Verifier init", lambda: Verifier(pp))

    enrollment = _timed(setup_timings, "Enrollment attributes", lambda: Enrollment().run(user, governance))
    if not args.no_precompute_r1cs_template:
        _timed(
            setup_timings,
            "Precompute Show R1CS template",
            precompute_show_r1cs_template,
        )

    issuance_start = perf_counter()
    credential_message, commitment_state = _timed(
        issuance_timings,
        "Issuer builds root || dpk",
        lambda: issuer.build_credential_message(
            user.attributes,
            user.device_public_key,
        ),
    )
    credential_signature = _timed(
        issuance_timings,
        "Issuer signs credential",
        lambda: issuer.sign_credential_message(credential_message),
    )
    user.receive_issued_credential(
        issuer,
        IssuedCredential(credential_message, credential_signature, commitment_state),
    )
    credential_signature_ok = _timed(
        issuance_timings,
        "Issuer verifies credential sig",
        lambda: issuer.verify_credential_signature(credential_message, credential_signature),
    )
    issuance_total = perf_counter() - issuance_start

    presentation_start = perf_counter()
    nonce_p, indexes_p = _timed(
        presentation_timings,
        "Verifier request nonce_P, idx_P",
        verifier.challenge,
    )
    request_p = PresentationRequest(nonce=nonce_p, disclosed_indexes=indexes_p)
    disclosure_p = _timed(
        presentation_timings,
        "User opens disclosed attrs",
        lambda: user.disclose_attributes(request_p.disclosed_indexes),
    )
    instance = _timed(
        presentation_timings,
        "User builds Show instance",
        lambda: build_show_proof_instance(
            credential_message=credential_message,
            disclosure=disclosure_p,
            verifier_nonce=request_p.nonce,
            credential_signature=credential_signature,
            device=se.backend,
        ),
    )
    r1cs_result = None
    if args.debug_r1cs_check:
        r1cs_result = _timed(
            presentation_timings,
            "Debug: evaluate Show R1CS",
            lambda: prove_show_r1cs(instance),
        )
    aurora_backend = AuroraBackend(make_zk=not args.no_zk)
    aurora_result = _timed(
        presentation_timings,
        "Aurora backend total",
        lambda: aurora_backend.prove_show(instance),
    )
    message_sizes = _timed(
        presentation_timings,
        "Compute message sizes",
        lambda: compute_show_message_sizes(instance, disclosure_p, aurora_result.raw),
    )
    presentation_total = perf_counter() - presentation_start
    total = perf_counter() - total_start

    aurora_raw = aurora_result.raw
    aurora_other = presentation_timings["Aurora backend total"] - (
        float(aurora_raw["export_seconds"])
        + float(aurora_raw["prove_seconds"])
        + float(aurora_raw["verify_seconds"])
    )

    print("=== BDAC protocol profile ===")
    print(f"backend: {'Aurora ZK optimized' if not args.no_zk else 'Aurora non-ZK debug'}")
    print(f"capss_scheme: {pp.capss_scheme_label}")
    print(f"attributes: {enrollment.attribute_count}")
    print()
    _print_profile("setup/enrollment", setup_timings, sum(setup_timings.values()))
    print()
    print("[issuance]")
    print(f"    credential_signature_ok: {credential_signature_ok}")
    _print_profile("issuance profile", issuance_timings, issuance_total)
    print()
    print("[presentation]")
    print(f"    requested_indexes: {list(indexes_p)}")
    if r1cs_result is None:
        print("    debug_r1cs_check: skipped")
    else:
        print(f"    debug_r1cs_check: {r1cs_result.proof_ok}")
    print(f"    aurora_result: {aurora_raw['verifier_result']}")
    print(f"    aurora_omp_threads: {aurora_raw.get('omp_num_threads')}")
    print(f"    proof_size: {aurora_raw['proof_size_bytes']} bytes")
    print(f"    total_sent_size: {message_sizes['total']} bytes")
    _print_profile("presentation profile", presentation_timings, presentation_total)
    print()
    print("[aurora detail]")
    print(f"    export_r1cs: {_format_seconds(float(aurora_raw['export_seconds']))}")
    for name, seconds in aurora_raw.get("export_timings", {}).items():
        print(f"      - {name:<20} {_format_seconds(float(seconds))}")
    print(f"    prove:       {_format_seconds(float(aurora_raw['prove_seconds']))}")
    print(f"    verify:      {_format_seconds(float(aurora_raw['verify_seconds']))}")
    print(f"    overhead:    {_format_seconds(max(0.0, aurora_other))}")
    print()
    print("[summary]")
    print(f"    setup_enrollment_total: {_format_seconds(sum(setup_timings.values()))}")
    print(f"    issuance_total:         {_format_seconds(issuance_total)}")
    print(f"    presentation_total:     {_format_seconds(presentation_total)}")
    print(f"    end_to_end_total:       {_format_seconds(total)}")


def _timed(timings: OrderedDict[str, float], name: str, fn: Callable[[], T]) -> T:
    start = perf_counter()
    result = fn()
    timings[name] = perf_counter() - start
    return result


def _print_profile(title: str, timings: OrderedDict[str, float], total: float) -> None:
    print(f"[{title}]")
    for name, seconds in timings.items():
        percent = 0.0 if total <= 0 else 100.0 * seconds / total
        print(f"    {name:<34} {_format_seconds(seconds):>10}  {percent:5.1f}%")
    print(f"    {'total':<34} {_format_seconds(total):>10}  {100.0:5.1f}%")


def _format_seconds(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    return f"{seconds:.2f} s"


if __name__ == "__main__":
    main()
