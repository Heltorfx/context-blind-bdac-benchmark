from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import random
from time import perf_counter
from typing import Callable, TypeVar

from BDAC.core.policies import IssuerPolicy, VerifierPolicy
from BDAC.core.types import IssuedCredential
from BDAC.instantiations.capss_aurora import create_scheme
from BDAC.proofs.aurora_backend import AuroraBackend
from BDAC.proofs.show_backend import (
    build_show_proof_instance,
    compute_show_message_sizes,
    precompute_show_r1cs_template,
    prove_show_r1cs,
)
from BDAC.protocols.enrollment import Enrollment
from BDAC.scheme import SchemeConfig


T = TypeVar("T")


@dataclass
class ActorSet:
    user_id: str
    se: object
    user: object


@dataclass
class IssuanceOutcome:
    ok: bool
    user_id: str
    issuer_id: str
    credential_id: str


@dataclass
class PresentationOutcome:
    ok: bool
    user_id: str
    issuer_id: str
    verifier_id: str
    credential_id: str
    indexes: tuple[int, ...]
    proof_size_bytes: int
    total_sent_bytes: int


class Metrics:
    def __init__(self):
        self.values: dict[str, list[float]] = defaultdict(list)

    def timed(self, name: str, fn: Callable[[], T]) -> T:
        start = perf_counter()
        result = fn()
        self.values[name].append(perf_counter() - start)
        return result

    def add(self, name: str, value: float) -> None:
        self.values[name].append(float(value))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=1)
    parser.add_argument("--issuers", type=int, default=2)
    parser.add_argument("--verifiers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--max-presentations", type=int, default=None)
    parser.add_argument("--skip-presentations", action="store_true")
    parser.add_argument("--no-zk", action="store_true")
    parser.add_argument("--debug-r1cs-check", action="store_true")
    parser.add_argument("--no-precompute-r1cs-template", action="store_true")
    args = parser.parse_args()

    if args.users <= 0 or args.issuers <= 0 or args.verifiers <= 0:
        raise ValueError("users, issuers, and verifiers must be positive")
    if args.max_presentations is not None and args.max_presentations < 0:
        raise ValueError("max-presentations must be non-negative")

    rng = random.Random(args.seed)
    metrics = Metrics()
    total_start = perf_counter()

    config = SchemeConfig(
        make_zk=not args.no_zk,
        debug_r1cs_check=args.debug_r1cs_check,
        precompute_r1cs_template=not args.no_precompute_r1cs_template,
    )
    scheme = create_scheme(config)
    pp = metrics.timed("setup.public_parameters", scheme.setup)
    governance = metrics.timed("setup.governance", lambda: scheme.create_governance(pp))

    issuer_ids = [f"issuer-{i}" for i in range(args.issuers)]
    issuers = []
    for issuer_id in issuer_ids:
        policy = IssuerPolicy(
            issuer_id=issuer_id,
            credential_type=f"type-{issuer_id}",
        )
        issuers.append(
            metrics.timed(
                "setup.issuer_keygen",
                lambda policy=policy: scheme.create_issuer(pp, policy),
            )
        )

    verifiers = []
    for verifier_index in range(args.verifiers):
        indexes = _sample_indexes(rng, pp.attribute_count, pp.default_disclosure_count)
        policy = VerifierPolicy(
            verifier_id=f"verifier-{verifier_index}",
            presentation_indexes=indexes,
            accepted_issuers=tuple(issuer_ids),
        )
        verifiers.append(scheme.create_verifier(pp, policy))

    actors: list[ActorSet] = []
    for user_index in range(args.users):
        se = metrics.timed("setup.se_keygen", lambda: scheme.create_se(pp))
        user = scheme.create_user(pp, se)
        actors.append(ActorSet(user_id=f"user-{user_index}", se=se, user=user))

    if config.precompute_r1cs_template and not args.skip_presentations:
        metrics.timed("setup.precompute_show_r1cs", precompute_show_r1cs_template)

    for actor in actors:
        metrics.timed(
            "enrollment.governance_to_user",
            lambda actor=actor: Enrollment().run(actor.user, governance),
        )

    issuance_outcomes: list[IssuanceOutcome] = []
    for actor in actors:
        for issuer in issuers:
            issuance_outcomes.append(
                _run_profiled_issuance(
                    metrics=metrics,
                    actor=actor,
                    issuer=issuer,
                )
            )

    presentation_outcomes: list[PresentationOutcome] = []
    if not args.skip_presentations:
        jobs = [
            (actor, issuer, verifier)
            for actor in actors
            for issuer in issuers
            for verifier in verifiers
        ]
        rng.shuffle(jobs)
        if args.max_presentations is not None:
            jobs = jobs[: args.max_presentations]

        aurora_backend = AuroraBackend(make_zk=config.make_zk)
        for actor, issuer, verifier in jobs:
            presentation_outcomes.append(
                _run_profiled_presentation(
                    metrics=metrics,
                    actor=actor,
                    issuer=issuer,
                    verifier=verifier,
                    aurora_backend=aurora_backend,
                    debug_r1cs_check=config.debug_r1cs_check,
                )
            )

    total_seconds = perf_counter() - total_start
    _print_report(
        args=args,
        pp=pp,
        metrics=metrics,
        issuance_outcomes=issuance_outcomes,
        presentation_outcomes=presentation_outcomes,
        total_seconds=total_seconds,
    )


def _run_profiled_issuance(metrics: Metrics, actor: ActorSet, issuer) -> IssuanceOutcome:
    credential_message, commitment_state = metrics.timed(
        "issuance.issuer_build_message",
        lambda: issuer.build_credential_message(
            actor.user.attributes,
            actor.user.device_public_key,
        ),
    )
    credential_signature = metrics.timed(
        "issuance.issuer_sign_credential",
        lambda: issuer.sign_credential_message(credential_message),
    )
    credential_id = issuer.issuer_id
    actor.user.receive_issued_credential(
        issuer,
        IssuedCredential(credential_message, credential_signature, commitment_state),
    )
    credential_signature_ok = metrics.timed(
        "issuance.issuer_verify_credential",
        lambda: issuer.verify_credential_signature(
            credential_message,
            credential_signature,
        ),
    )
    return IssuanceOutcome(
        ok=credential_signature_ok,
        user_id=actor.user_id,
        issuer_id=issuer.issuer_id,
        credential_id=credential_id,
    )


def _run_profiled_presentation(
    metrics: Metrics,
    actor: ActorSet,
    issuer,
    verifier,
    aurora_backend: AuroraBackend,
    debug_r1cs_check: bool,
) -> PresentationOutcome:
    credential_id = issuer.issuer_id
    credential = actor.user.get_credential_record(credential_id)
    if not verifier.accepts_credential(credential):
        return PresentationOutcome(
            ok=False,
            user_id=actor.user_id,
            issuer_id=issuer.issuer_id,
            verifier_id=verifier.verifier_id,
            credential_id=credential_id,
            indexes=(),
            proof_size_bytes=0,
            total_sent_bytes=0,
        )

    nonce_p, indexes_p = metrics.timed(
        "presentation.verifier_nonce_and_indexes",
        verifier.challenge,
    )
    disclosure = metrics.timed(
        "presentation.user_open_attributes",
        lambda: actor.user.disclose_attributes(indexes_p),
    )
    instance = metrics.timed(
        "presentation.user_build_show_instance",
        lambda: build_show_proof_instance(
            credential_message=credential.message,
            disclosure=disclosure,
            verifier_nonce=nonce_p,
            credential_signature=credential.signature,
            device=actor.se.backend,
        ),
    )
    r1cs_ok = True
    if debug_r1cs_check:
        r1cs_result = metrics.timed(
            "presentation.debug_evaluate_r1cs",
            lambda: prove_show_r1cs(instance),
        )
        r1cs_ok = r1cs_result.proof_ok
    aurora_result = metrics.timed(
        "presentation.aurora_total",
        lambda: aurora_backend.prove_show(instance),
    )
    raw = aurora_result.raw
    metrics.add("aurora.export", float(raw["export_seconds"]))
    metrics.add("aurora.prove", float(raw["prove_seconds"]))
    metrics.add("aurora.verify", float(raw["verify_seconds"]))
    for name, seconds in raw.get("export_timings", {}).items():
        metrics.add(f"aurora.export.{name}", float(seconds))

    message_sizes = metrics.timed(
        "presentation.compute_message_sizes",
        lambda: compute_show_message_sizes(instance, disclosure, raw),
    )
    metrics.add("sizes.proof_bytes", float(raw["proof_size_bytes"]))
    metrics.add("sizes.total_sent_bytes", float(message_sizes["total"]))

    return PresentationOutcome(
        ok=aurora_result.ok and r1cs_ok,
        user_id=actor.user_id,
        issuer_id=issuer.issuer_id,
        verifier_id=verifier.verifier_id,
        credential_id=credential_id,
        indexes=indexes_p,
        proof_size_bytes=int(raw["proof_size_bytes"]),
        total_sent_bytes=int(message_sizes["total"]),
    )


def _sample_indexes(
    rng: random.Random,
    attribute_count: int,
    disclosure_count: int,
) -> tuple[int, ...]:
    return tuple(sorted(rng.sample(range(attribute_count), disclosure_count)))


def _print_report(
    args,
    pp,
    metrics: Metrics,
    issuance_outcomes: list[IssuanceOutcome],
    presentation_outcomes: list[PresentationOutcome],
    total_seconds: float,
) -> None:
    print("=== BDAC population profile ===")
    print(f"users: {args.users}")
    print(f"issuers: {args.issuers}")
    print(f"verifiers: {args.verifiers}")
    print(f"attributes: {pp.attribute_count}")
    print(f"disclosed_per_policy: {pp.default_disclosure_count}")
    print(f"backend: {'Aurora ZK optimized' if not args.no_zk else 'Aurora non-ZK debug'}")
    print(f"seed: {args.seed}")
    print()

    _print_group("setup", metrics, "setup.")
    _print_group("enrollment", metrics, "enrollment.")
    _print_group("issuance", metrics, "issuance.")
    if not args.skip_presentations:
        _print_group("presentation", metrics, "presentation.")
        _print_group("aurora detail", metrics, "aurora.")
        _print_group("sizes", metrics, "sizes.", formatter=_format_bytes)

    issuance_ok = sum(1 for outcome in issuance_outcomes if outcome.ok)
    presentation_ok = sum(1 for outcome in presentation_outcomes if outcome.ok)
    print("[outcomes]")
    print(f"    issuances:     {issuance_ok}/{len(issuance_outcomes)} ok")
    if args.skip_presentations:
        print("    presentations: skipped")
    else:
        print(f"    presentations: {presentation_ok}/{len(presentation_outcomes)} ok")
    print()
    print("[summary]")
    print(f"    total_wall_time: {_format_seconds(total_seconds)}")


def _print_group(
    title: str,
    metrics: Metrics,
    prefix: str,
    formatter: Callable[[float], str] = None,
) -> None:
    formatter = formatter or _format_seconds
    rows = [
        (name, values)
        for name, values in sorted(metrics.values.items())
        if name.startswith(prefix)
    ]
    if not rows:
        return
    print(f"[{title}]")
    for name, values in rows:
        label = name[len(prefix) :]
        total = sum(values)
        mean = total / len(values)
        print(
            f"    {label:<34} "
            f"n={len(values):<4} "
            f"avg={formatter(mean):>18} "
            f"min={formatter(min(values)):>18} "
            f"max={formatter(max(values)):>18} "
            f"total={formatter(total):>18}"
        )
    print()


def _format_seconds(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    return f"{seconds:.2f} s"


def _format_bytes(size: float) -> str:
    size = int(size)
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.2f} KiB"
    return f"{size / (1024 * 1024):.2f} MiB"


if __name__ == "__main__":
    main()
