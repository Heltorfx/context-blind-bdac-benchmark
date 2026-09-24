from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable, TypeVar

from BDAC.core.types import IssuedCredential
from BDAC.instantiations.capss_aurora import create_scheme
from BDAC.proofs.aurora_backend import AuroraBackend
from BDAC.proofs.show_backend import (
    build_show_proof_instance,
    compute_show_message_sizes,
    precompute_show_r1cs_template,
    prove_show_r1cs,
)
from BDAC.scheme import SchemeConfig


T = TypeVar("T")


@dataclass
class Profile:
    sections: dict[str, OrderedDict[str, float]] = field(default_factory=dict)

    def timed(self, section: str, name: str, fn: Callable[[], T]) -> T:
        timings = self.sections.setdefault(section, OrderedDict())
        start = perf_counter()
        result = fn()
        timings[name] = perf_counter() - start
        return result

    def total(self, section: str) -> float:
        return sum(self.sections.get(section, {}).values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-zk", action="store_true")
    parser.add_argument("--debug-r1cs-check", action="store_true")
    parser.add_argument("--no-precompute-r1cs-template", action="store_true")
    args = parser.parse_args()

    profile = Profile()
    total_start = perf_counter()
    config = SchemeConfig(
        make_zk=not args.no_zk,
        debug_r1cs_check=args.debug_r1cs_check,
        precompute_r1cs_template=not args.no_precompute_r1cs_template,
    )
    scheme = create_scheme(config)

    pp = profile.timed("setup", "Setup(lambda,l)", scheme.setup)
    entities = profile.timed("setup", "Create entities / keygen", lambda: scheme.setup_entities(pp))
    if config.precompute_r1cs_template:
        profile.timed("setup", "Precompute Show R1CS template", precompute_show_r1cs_template)

    enrollment = profile.timed("enrollment", "Governance attributes", lambda: scheme.enroll(entities))

    credential_message, commitment_state = profile.timed(
        "issuance",
        "Issuer builds Merkle root || dpk",
        lambda: entities.issuer.build_credential_message(
            entities.user.attributes,
            entities.user.device_public_key,
        ),
    )
    credential_signature = profile.timed(
        "issuance",
        "Issuer signs credential",
        lambda: entities.issuer.sign_credential_message(credential_message),
    )
    entities.user.receive_issued_credential(
        entities.issuer,
        IssuedCredential(credential_message, credential_signature, commitment_state),
    )
    credential_signature_ok = profile.timed(
        "issuance",
        "Issuer verifies credential",
        lambda: entities.issuer.verify_credential_signature(
            credential_message,
            credential_signature,
        ),
    )

    nonce_p, indexes_p = profile.timed(
        "presentation",
        "Verifier samples nonce_P, idx_P",
        entities.verifier.challenge,
    )
    disclosure_p = profile.timed(
        "presentation",
        "User opens presentation attrs",
        lambda: entities.user.disclose_attributes(indexes_p),
    )
    show_instance = profile.timed(
        "presentation",
        "User builds Show witness instance",
        lambda: build_show_proof_instance(
            credential_message=credential_message,
            disclosure=disclosure_p,
            verifier_nonce=nonce_p,
            credential_signature=credential_signature,
            device=entities.se.backend,
        ),
    )
    r1cs_result = None
    if config.debug_r1cs_check:
        r1cs_result = profile.timed(
            "presentation",
            "Debug evaluate Show R1CS",
            lambda: prove_show_r1cs(show_instance),
        )
    aurora_backend = AuroraBackend(make_zk=config.make_zk)
    aurora_result = profile.timed(
        "presentation",
        "Aurora export+prove+verify",
        lambda: aurora_backend.prove_show(show_instance),
    )
    message_sizes = profile.timed(
        "presentation",
        "Compute message sizes",
        lambda: compute_show_message_sizes(show_instance, disclosure_p, aurora_result.raw),
    )

    total = perf_counter() - total_start
    print("=== BDAC full profile ===")
    print(f"scheme: {scheme.name}")
    print(f"backend: {'Aurora ZK optimized' if config.make_zk else 'Aurora non-ZK debug'}")
    print(f"capss_scheme: {pp.capss_scheme_label}")
    print(f"attributes: {enrollment.attribute_count}")
    print()
    for section in ("setup", "enrollment", "issuance", "presentation"):
        _print_section(section, profile.sections.get(section, OrderedDict()))
        print()

    print("[checks]")
    print(f"    presentation_indexes: {list(indexes_p)}")
    print(f"    credential_signature_ok: {credential_signature_ok}")
    if r1cs_result is not None:
        print(f"    debug_r1cs_ok: {r1cs_result.proof_ok}")
    print(f"    aurora_result: {aurora_result.verifier_result}")
    print()

    _print_aurora_detail(aurora_result.raw)
    print()
    print("[sizes]")
    print(f"    verifier_to_user: {message_sizes['verifier_to_user']} bytes")
    print(f"    user_to_device:   {message_sizes['user_to_device']} bytes")
    print(f"    device_to_user:   {message_sizes['device_to_user']} bytes")
    print(f"    user_to_verifier: {message_sizes['user_to_verifier']} bytes")
    print(f"    total_sent:       {message_sizes['total']} bytes")
    print(f"    proof_size:       {aurora_result.raw['proof_size_bytes']} bytes")
    print()
    print("[summary]")
    print(f"    setup_total:        {_format_seconds(profile.total('setup'))}")
    print(f"    enrollment_total:   {_format_seconds(profile.total('enrollment'))}")
    print(f"    issuance_total:     {_format_seconds(profile.total('issuance'))}")
    print(f"    presentation_total: {_format_seconds(profile.total('presentation'))}")
    print(f"    end_to_end_total:   {_format_seconds(total)}")


def _print_section(title: str, timings: OrderedDict[str, float]) -> None:
    total = sum(timings.values())
    print(f"[{title}]")
    for name, seconds in timings.items():
        percent = 0.0 if total <= 0 else 100.0 * seconds / total
        print(f"    {name:<36} {_format_seconds(seconds):>10}  {percent:5.1f}%")
    print(f"    {'total':<36} {_format_seconds(total):>10}  {100.0:5.1f}%")


def _print_aurora_detail(raw: dict[str, object]) -> None:
    export_seconds = float(raw["export_seconds"])
    prove_seconds = float(raw["prove_seconds"])
    verify_seconds = float(raw["verify_seconds"])
    print("[aurora]")
    print(f"    omp_threads: {raw.get('omp_num_threads')}")
    print(f"    export: {_format_seconds(export_seconds)}")
    for name, seconds in raw.get("export_timings", {}).items():
        print(f"      - {name:<22} {_format_seconds(float(seconds))}")
    print(f"    prove:  {_format_seconds(prove_seconds)}")
    print(f"    verify: {_format_seconds(verify_seconds)}")


def _format_seconds(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    return f"{seconds:.2f} s"


if __name__ == "__main__":
    main()
