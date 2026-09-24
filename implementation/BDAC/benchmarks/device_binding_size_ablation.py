from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from statistics import fmean, pstdev

from BDAC.parameters import (
    ATTRIBUTE_COUNT,
    CAPSS_FIELD_ORDER,
    CAPSS_GRIFFIN_ALPHA,
    CAPSS_SCHEME_LABEL,
    MERKLE_ARITY,
    SECURITY_LEVEL,
    SMALLWOOD_PATH,
)
from BDAC.proofs.show_r1cs import make_show_proof_instance


ROOT = Path(__file__).resolve().parents[2]
FULL_WORKSPACE = ROOT / "aurora_workspace" / "show_zk_v2_d4"
BASELINE_WORKSPACE = ROOT / "aurora_workspace" / "ablation_credential_only_matched_v2_d4"


def build_credential_only_r1cs(instance, target_shape: dict[str, int]):
    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))

    from capss.hash import JiveCompressionFunction
    from capss.hash.griffin import Griffin
    from capss.sign.instances import get_scheme
    from r1cs.commit.merkle import MerkleTreeFactoryWithAOHash_R1CS
    from r1cs.r1cs import R1CS
    from r1cs.variable import Variable
    from sage.all import FiniteField

    field = FiniteField(CAPSS_FIELD_ORDER)
    scheme = get_scheme(CAPSS_SCHEME_LABEL)
    permutation = Griffin.get(
        CAPSS_FIELD_ORDER,
        CAPSS_GRIFFIN_ALPHA,
        4,
        1,
        SECURITY_LEVEL,
    )
    compression = JiveCompressionFunction(permutation)
    tree_factory = MerkleTreeFactoryWithAOHash_R1CS(
        nb_leaves=ATTRIBUTE_COUNT,
        arity=MERKLE_ARITY,
        compression_method={4: compression},
        output_size=1,
        is_expanded=True,
    )

    opened_count = len(instance.disclosure.indexes)
    auth_size = tree_factory.get_authentication_path_max_size(opened_count)
    r1cs = R1CS(field)
    opened_indexes = r1cs.new_registers(opened_count, "opened_indexes", is_primary=True)
    opened_leaves = r1cs.new_registers(
        (opened_count, 1),
        "opened_leaves",
        is_primary=True,
    )
    issuer_pk = r1cs.new_registers(
        scheme.get_public_key_size(),
        "issuer_pk",
        is_primary=True,
    )
    root = r1cs.new_register("root")
    auth = r1cs.new_registers(auth_size, "auth")
    issuer_sig = r1cs.new_registers(scheme.get_signature_size(), "issuer_sig")

    computed_root = tree_factory.get_root_from_authentication_path(
        [
            (opened_indexes[index], opened_leaves[index])
            for index in range(opened_count)
        ],
        auth,
    )[0]
    r1cs.register_equation(Variable(r1cs, field(1)), computed_root, root)
    if scheme.verify(issuer_pk, [root], issuer_sig) is not True:
        raise ValueError("CAPSS credential verification gadget did not return True")

    padding_variables = target_shape["variables"] - r1cs.get_nb_variables()
    padding_constraints = target_shape["constraints"] - r1cs.get_nb_equations()
    if padding_variables < 0 or padding_constraints < 0:
        raise ValueError("Credential-only circuit exceeds the device-bound circuit")
    padding_registers = r1cs.new_registers(padding_variables, "padding_variables")
    zero = Variable(r1cs, field(0))
    if padding_constraints > 0:
        # Make every padding variable part of the exported assignment while
        # keeping the equation identically true.
        r1cs.register_equation(Variable(r1cs, padding_registers), zero, zero)
    for _ in range(max(0, padding_constraints - 1)):
        r1cs.register_equation(zero, zero, zero)

    root_value = field(int.from_bytes(instance.credential_message.root, "big"))
    pk, sk = scheme.keygen()
    signature = scheme.sign(sk, [root_value])
    if not scheme.verify(pk, [root_value], signature):
        raise RuntimeError("Credential-only CAPSS signature failed verification")

    auth_value = instance.disclosure.authentication_path
    if isinstance(auth_value, bytes):
        raise TypeError("Expected Griffin authentication path as field elements")
    witness = {
        "opened_indexes": [field(index) for index in instance.disclosure.indexes],
        "opened_leaves": [
            [field(int.from_bytes(attribute, "big"))]
            for attribute in instance.disclosure.attributes
        ],
        "issuer_pk": [field(value) for value in pk],
        "root": root_value,
        "auth": [field(value) for value in auth_value],
        "issuer_sig": [field(value) for value in signature],
        "padding_variables": [field(0)] * padding_variables,
    }
    return r1cs, witness


def export_baseline(instance, target_shape: dict[str, int]) -> dict[str, int]:
    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))
    from capss.libiop.export_r1cs import export_field_params, export_r1cs, export_variables
    from sage.all import ZZ

    r1cs, witness = build_credential_only_r1cs(instance, target_shape)
    assignment = r1cs.resolve(witness, verbose=False)
    if not bool(r1cs.evaluate(assignment)):
        raise RuntimeError("Credential-only R1CS is not satisfied")

    BASELINE_WORKSPACE.mkdir(parents=True, exist_ok=True)
    export_field_params(
        ZZ(CAPSS_FIELD_ORDER),
        str(BASELINE_WORKSPACE / "r1cs-field.txt"),
        verbose=False,
    )
    export_r1cs(r1cs, str(BASELINE_WORKSPACE / "r1cs-constraints.txt"))
    export_variables(
        r1cs,
        [witness],
        str(BASELINE_WORKSPACE / "r1cs-primary-inputs.txt"),
        str(BASELINE_WORKSPACE / "r1cs-auxiliary-inputs.txt"),
        precomputed_variables=[assignment],
        validate=False,
    )
    return {
        "constraints": r1cs.get_nb_equations(),
        "variables": r1cs.get_nb_variables(),
        "primary_inputs": r1cs.get_nb_primary_inputs(),
    }


def workspace_shape(workspace: Path) -> dict[str, int]:
    metadata_path = workspace / "r1cs-cache-metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="ascii"))
        return {
            "constraints": int(metadata["nb_constraints"]),
            "variables": int(metadata["nb_variables"]),
            "primary_inputs": int(metadata["nb_primary_inputs"]),
        }
    return {}


def run_proofs(workspace: Path, iterations: int, label: str) -> dict[str, object]:
    prove = ROOT / "capss-aggregation" / "build-openmp" / "capss" / "aurora_prove_r1cs_256_zk_save_bin"
    verify = ROOT / "capss-aggregation" / "build-openmp" / "capss" / "aurora_verify_r1cs_256_zk_bin"
    if not prove.exists() or not verify.exists():
        raise FileNotFoundError("Build the Aurora-CF prover and verifier first")

    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", "8")
    env.setdefault("OMP_DYNAMIC", "FALSE")
    sizes: list[int] = []
    for index in range(iterations):
        proof_path = workspace / f"proof-{label}-{index + 1:02d}.bin"
        prover = subprocess.run(
            [str(prove), str(proof_path), "v2"],
            cwd=workspace,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if prover.returncode != 0:
            raise RuntimeError(f"Prover failed for {label} run {index + 1}:\n{prover.stdout}")
        verifier = subprocess.run(
            [str(verify), str(proof_path), "v2"],
            cwd=workspace,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if verifier.returncode != 0 or verifier.stdout.strip().splitlines()[-1:] != ["[OK] VALID"]:
            raise RuntimeError(f"Verifier failed for {label} run {index + 1}:\n{verifier.stdout}")
        sizes.append(proof_path.stat().st_size)
        print(f"{label}: {index + 1}/{iterations} valid ({sizes[-1]} bytes)", flush=True)

    return {
        "iterations": iterations,
        "proof_size_bytes_mean": fmean(sizes),
        "proof_size_bytes_stddev": pstdev(sizes),
        "proof_size_bytes_min": min(sizes),
        "proof_size_bytes_max": max(sizes),
        "samples": sizes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).with_name("device_binding_size_ablation.json"),
    )
    args = parser.parse_args()
    if args.iterations <= 0:
        raise ValueError("iterations must be positive")
    if not FULL_WORKSPACE.exists():
        raise FileNotFoundError(FULL_WORKSPACE)

    instance = make_show_proof_instance()
    full_shape = workspace_shape(FULL_WORKSPACE)
    baseline_shape = export_baseline(instance, full_shape)
    baseline = run_proofs(BASELINE_WORKSPACE, args.iterations, "credential-only")
    full = run_proofs(FULL_WORKSPACE, args.iterations, "device-bound")
    baseline_mean = float(baseline["proof_size_bytes_mean"])
    full_mean = float(full["proof_size_bytes_mean"])
    result = {
        "aurora_version": "v2",
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS", "8"),
        "credential_only": {"r1cs": baseline_shape, **baseline},
        "device_bound": {"r1cs": full_shape, **full},
        "observed_device_binding_delta": {
            "proof_size_bytes": full_mean - baseline_mean,
            "proof_size_ratio": full_mean / baseline_mean,
            "proof_size_percent": 100.0 * (full_mean / baseline_mean - 1.0),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="ascii")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
