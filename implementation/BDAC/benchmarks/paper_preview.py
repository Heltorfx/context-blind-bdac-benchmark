from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import random
from statistics import fmean, pstdev
from time import perf_counter
from typing import Callable, TypeVar

from BDAC.core.policies import IssuerPolicy, VerifierPolicy
from BDAC.core.types import IssuedCredential
from BDAC.instantiations.capss_aurora import create_scheme
from BDAC.proofs.aurora_backend import AuroraBackend
from BDAC.proofs.show_backend import (
    build_show_proof_instance,
    compute_show_message_sizes,
    prepare_aurora_show,
    precompute_show_r1cs_template,
)
from BDAC.proofs.show_r1cs import build_show_r1cs
from BDAC.protocols.enrollment import Enrollment
from BDAC.protocols.issuance import compute_issuance_message_sizes
from BDAC.scheme import SchemeConfig


T = TypeVar("T")


@dataclass
class StepTiming:
    section: str
    name: str
    seconds: float


@dataclass
class ShowRun:
    disclosed_count: int
    iterations: int
    constraints: int
    variables: int
    primary_inputs: int
    proof_size_bytes: float
    proof_size_min_bytes: int
    proof_size_max_bytes: int
    total_sent_bytes: float
    static_export_seconds: float
    export_seconds: float
    export_stddev_seconds: float
    prove_seconds: float
    prove_stddev_seconds: float
    verify_seconds: float
    verify_stddev_seconds: float
    show_instance_seconds: float
    show_instance_stddev_seconds: float
    aurora_total_seconds: float
    aurora_total_stddev_seconds: float
    user_online_seconds: float
    user_online_stddev_seconds: float
    samples: list[dict[str, object]]
    valid: bool


@dataclass
class CapssMicrobench:
    label: str
    iterations: int
    keygen_avg_seconds: float
    sign_avg_seconds: float
    verify_avg_seconds: float


class Recorder:
    def __init__(self) -> None:
        self.timings: list[StepTiming] = []

    def timed(self, section: str, name: str, fn: Callable[[], T]) -> T:
        start = perf_counter()
        result = fn()
        self.timings.append(StepTiming(section, name, perf_counter() - start))
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aurora-version", choices=("normal", "v2"), default="normal")
    parser.add_argument("--out", default=None)
    parser.add_argument("--seed", type=int, default=20260721)
    parser.add_argument("--micro-iters", type=int, default=30)
    parser.add_argument("--aurora-iters", type=int, default=30)
    parser.add_argument("--issuance-iters", type=int, default=30)
    parser.add_argument("--issuance-only", action="store_true")
    parser.add_argument("--disclosures", default="1,2,4,8")
    parser.add_argument("--skip-scaling", action="store_true")
    args = parser.parse_args()
    if args.out is None:
        filename = "paper_preview_results.json" if args.aurora_version == "normal" else "paper_preview_v2_results.json"
        args.out = f"BDAC/benchmarks/{filename}"
    if min(args.micro_iters, args.aurora_iters, args.issuance_iters) <= 0:
        parser.error("iteration counts must be positive")
    if not args.skip_scaling and not args.issuance_only and 4 not in parse_disclosures(args.disclosures):
        parser.error("--disclosures must include the default count 4")

    rng = random.Random(args.seed)
    config = SchemeConfig(make_zk=True, precompute_r1cs_template=True, aurora_version=args.aurora_version)
    scheme = create_scheme(config)
    recorder = Recorder()
    total_start = perf_counter()

    pp = recorder.timed("setup", "Setup(lambda,l)", scheme.setup)
    entities = recorder.timed("setup", "Create entities / CAPSS keygen", lambda: scheme.setup_entities(pp))
    enrollment = recorder.timed("enrollment", "Governance attributes", lambda: scheme.enroll(entities))

    issuance_data, issuance_summary = run_repeated_issuance(
        entities,
        args.issuance_iters,
    )
    if args.issuance_only:
        payload = {
            "metadata": {
                "scheme": scheme.name,
                "capss_scheme": pp.capss_scheme_label,
                "security_parameter": pp.security_parameter,
                "attribute_count": pp.attribute_count,
                "iterations": args.issuance_iters,
                "seed": args.seed,
            },
            "issuance": issuance_summary,
            "issuance_checks": issuance_data["checks"],
            "issuance_message_sizes": issuance_data["message_sizes"],
        }
        write_payload(Path(args.out), payload)
        return

    recorder.timed("setup", "Precompute Show R1CS template d=4", precompute_show_r1cs_template)
    scaling: list[ShowRun] = []
    disclosure_counts = (
        [pp.default_disclosure_count]
        if args.skip_scaling
        else parse_disclosures(args.disclosures)
    )
    for disclosed_count in disclosure_counts:
        verifier_policy = VerifierPolicy(
            verifier_id=f"verifier-d{disclosed_count}",
            presentation_indexes=tuple(
                sorted(rng.sample(range(pp.attribute_count), disclosed_count))
            ),
            accepted_issuers=(entities.issuer.issuer_id,),
        )
        scaling.append(
            run_profiled_show(
                disclosed_count=disclosed_count,
                scheme=scheme,
                pp=pp,
                credential=issuance_data["credential"],
                user=entities.user,
                se=entities.se,
                verifier_policy=verifier_policy,
                iterations=args.aurora_iters,
            )
        )
    show_d4 = next(
        run for run in scaling if run.disclosed_count == pp.default_disclosure_count
    )

    micro = run_capss_microbench(pp, args.micro_iters)
    total_seconds = perf_counter() - total_start

    payload = {
        "metadata": {
            "scheme": scheme.name,
            "capss_scheme": pp.capss_scheme_label,
            "security_parameter": pp.security_parameter,
            "attribute_count": pp.attribute_count,
            "default_disclosure_count": pp.default_disclosure_count,
            "seed": args.seed,
            "backend_revision": "aurora92-full-transcript-absorption" if args.aurora_version == "normal" else "aurora-v2-salted-prefix",
            "aurora_version": args.aurora_version,
            "issuance_iterations": args.issuance_iters,
        },
        "full_flow": {
            "timings": [asdict(timing) for timing in recorder.timings],
            "issuance_summary": issuance_summary,
            "issuance_checks": issuance_data["checks"],
            "issuance_message_sizes": issuance_data["message_sizes"],
            "show_d4": asdict(show_d4),
            "total_seconds": total_seconds,
        },
        "scaling": [asdict(run) for run in scaling],
        "capss_microbench": asdict(micro),
    }

    write_payload(Path(args.out), payload)


def write_payload(out_path: Path, payload: dict[str, object]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    out_path.write_text(rendered, encoding="ascii")
    print(rendered)


def run_repeated_issuance(entities, iterations: int):
    if iterations <= 0:
        raise ValueError("issuance iterations must be positive")

    run_profiled_issuance(Recorder(), entities)
    runs = []
    issuance_data = None
    for _ in range(iterations):
        run_recorder = Recorder()
        issuance_data = run_profiled_issuance(run_recorder, entities)
        timings = {
            timing.name: timing.seconds
            for timing in run_recorder.timings
            if timing.section == "issuance"
        }
        timings["Issuance total"] = sum(timings.values())
        runs.append(timings)

    names = runs[0].keys()
    summary = {
        name: {
            "mean_seconds": fmean(run[name] for run in runs),
            "stddev_seconds": pstdev(run[name] for run in runs),
        }
        for name in names
    }
    return issuance_data, summary


def run_profiled_issuance(recorder: Recorder, entities):
    credential_message, commitment_state = recorder.timed(
        "issuance",
        "Issuer builds Merkle root || dpk",
        lambda: entities.issuer.build_credential_message(
            entities.user.attributes,
            entities.user.device_public_key,
        ),
    )
    credential_signature = recorder.timed(
        "issuance",
        "Issuer signs credential",
        lambda: entities.issuer.sign_credential_message(credential_message),
    )
    entities.user.receive_issued_credential(
        entities.issuer,
        IssuedCredential(credential_message, credential_signature, commitment_state),
    )
    credential_signature_ok = recorder.timed(
        "issuance",
        "Issuer verifies credential",
        lambda: entities.issuer.verify_credential_signature(credential_message, credential_signature),
    )
    if not credential_signature_ok:
        raise RuntimeError("Issuance validation failed")
    message_sizes = compute_issuance_message_sizes(
        credential_message,
        credential_signature,
        attribute_count=len(entities.user.attributes),
        attribute_size=entities.user.pp.attribute_size,
    )
    return {
        "credential": entities.user.get_credential_record(entities.issuer.issuer_id),
        "message_sizes": message_sizes,
        "checks": {
            "credential_signature_ok": credential_signature_ok,
        },
    }


def run_profiled_show(
    *,
    disclosed_count: int,
    scheme,
    pp,
    credential,
    user,
    se,
    verifier_policy: VerifierPolicy,
    iterations: int,
) -> ShowRun:
    if iterations <= 0:
        raise ValueError("iterations must be positive")

    verifier = scheme.create_verifier(pp, verifier_policy)

    def fresh_instance():
        nonce_p, indexes_p = verifier.challenge()
        disclosure_p = user.disclose_attributes(indexes_p)
        start_p = perf_counter()
        instance_p = build_show_proof_instance(
            credential_message=credential.message,
            disclosure=disclosure_p,
            verifier_nonce=nonce_p,
            credential_signature=credential.signature,
            device=se.backend,
        )
        return instance_p, disclosure_p, perf_counter() - start_p

    instance, disclosure, _ = fresh_instance()
    r1cs, _ = build_show_r1cs(instance)
    static_export_seconds = prepare_aurora_show(instance, make_zk=True, force=True, version=scheme.config.aurora_version)
    backend = AuroraBackend(make_zk=True, version=scheme.config.aurora_version)

    # Warm the Python, Rust, filesystem, and OpenMP paths without recording them.
    warmup_result = backend.prove_show(instance)
    if not warmup_result.ok:
        raise RuntimeError(f"Aurora warm-up failed for d={disclosed_count}")

    show_instance_times = []
    export_times = []
    prove_times = []
    verify_times = []
    aurora_total_times = []
    proof_sizes = []
    total_sizes = []
    all_valid = True
    samples = []
    for trial in range(iterations):
        instance, disclosure, show_instance_seconds = fresh_instance()
        start = perf_counter()
        aurora_result = backend.prove_show(instance)
        aurora_total_seconds = perf_counter() - start
        raw_result = dict(aurora_result.raw)
        message_sizes = compute_show_message_sizes(instance, disclosure, raw_result)
        if not aurora_result.ok:
            raise RuntimeError(f"Aurora validation failed for d={disclosed_count}, trial={trial + 1}")
        show_instance_times.append(show_instance_seconds)
        export_times.append(float(aurora_result.raw["export_seconds"]))
        prove_times.append(float(aurora_result.raw["prove_seconds"]))
        verify_times.append(float(aurora_result.raw["verify_seconds"]))
        aurora_total_times.append(aurora_total_seconds)
        proof_sizes.append(int(aurora_result.raw["proof_size_bytes"]))
        total_sizes.append(int(message_sizes["total"]))
        all_valid = all_valid and aurora_result.ok
        samples.append({
            "witness_seconds": show_instance_seconds,
            "export_seconds": export_times[-1],
            "prove_seconds": prove_times[-1],
            "verify_seconds": verify_times[-1],
            "user_online_seconds": show_instance_seconds + export_times[-1] + prove_times[-1],
            "proof_size_bytes": proof_sizes[-1],
            "total_sent_bytes": total_sizes[-1],
            "valid": True,
            "export_timings": aurora_result.raw.get("export_timings", {}),
        })
        if (trial + 1) % 5 == 0 or trial + 1 == iterations:
            print(f"d={disclosed_count}: {trial + 1}/{iterations} verified", flush=True)

    return ShowRun(
        disclosed_count=disclosed_count,
        iterations=iterations,
        constraints=r1cs.get_nb_equations(),
        variables=r1cs.get_nb_variables(),
        primary_inputs=r1cs.get_nb_primary_inputs(),
        proof_size_bytes=fmean(proof_sizes),
        proof_size_min_bytes=min(proof_sizes),
        proof_size_max_bytes=max(proof_sizes),
        total_sent_bytes=fmean(total_sizes),
        static_export_seconds=static_export_seconds,
        export_seconds=fmean(export_times),
        export_stddev_seconds=pstdev(export_times),
        prove_seconds=fmean(prove_times),
        prove_stddev_seconds=pstdev(prove_times),
        verify_seconds=fmean(verify_times),
        verify_stddev_seconds=pstdev(verify_times),
        show_instance_seconds=fmean(show_instance_times),
        show_instance_stddev_seconds=pstdev(show_instance_times),
        aurora_total_seconds=fmean(aurora_total_times),
        aurora_total_stddev_seconds=pstdev(aurora_total_times),
        user_online_seconds=fmean(sample["user_online_seconds"] for sample in samples),
        user_online_stddev_seconds=pstdev(sample["user_online_seconds"] for sample in samples),
        samples=samples,
        valid=all_valid,
    )


def run_capss_microbench(pp, iterations: int) -> CapssMicrobench:
    from BDAC.crypto.capss import get_capss_scheme

    scheme = get_capss_scheme(pp.capss_scheme_label)
    field = scheme.get_field()
    warmup_pk, warmup_sk = scheme.keygen()
    warmup_msg = [field.random_element(), field.random_element(), field.random_element()]
    warmup_sig = scheme.sign(warmup_sk, warmup_msg)
    if not scheme.verify(warmup_pk, warmup_msg, warmup_sig):
        raise RuntimeError("CAPSS verification failed during warm-up")
    keygen_times = []
    sign_times = []
    verify_times = []
    for _ in range(iterations):
        start = perf_counter()
        pk, sk = scheme.keygen()
        keygen_times.append(perf_counter() - start)
        msg = [field.random_element(), field.random_element(), field.random_element()]
        start = perf_counter()
        sig = scheme.sign(sk, msg)
        sign_times.append(perf_counter() - start)
        start = perf_counter()
        ok = scheme.verify(pk, msg, sig)
        verify_times.append(perf_counter() - start)
        if not ok:
            raise RuntimeError("CAPSS verification failed during microbench")
    return CapssMicrobench(
        label=pp.capss_scheme_label,
        iterations=iterations,
        keygen_avg_seconds=sum(keygen_times) / iterations,
        sign_avg_seconds=sum(sign_times) / iterations,
        verify_avg_seconds=sum(verify_times) / iterations,
    )


def parse_disclosures(raw: str) -> list[int]:
    values = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            values.append(int(part))
    return values


if __name__ == "__main__":
    main()
