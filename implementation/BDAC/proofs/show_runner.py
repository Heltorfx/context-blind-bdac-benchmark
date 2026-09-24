from __future__ import annotations

import os
import subprocess
from pathlib import Path
from time import perf_counter

from BDAC.proofs.show_r1cs import export_show_r1cs, prepare_show_r1cs_static


FIELD_ELEMENT_SIZE = 32
INDEX_SIZE = 4


def aurora_run_is_valid(prove, verify) -> bool:
    return (
        prove.returncode == 0
        and verify.returncode == 0
        and verify.stdout.strip().splitlines()[-1:] == ["[OK] VALID"]
    )


def run_aurora_show(instance) -> dict[str, object]:
    output_dir = show_output_dir(instance, make_zk=False)
    export_start = perf_counter()
    export_show_r1cs(instance, output_dir)
    export_elapsed = perf_counter() - export_start
    prove_exe = (
        output_dir
        / ".."
        / ".."
        / "capss-aggregation"
        / "build"
        / "capss"
        / "aurora_prove_r1cs_256"
    ).resolve()
    verify_exe = (
        output_dir
        / ".."
        / ".."
        / "capss-aggregation"
        / "build"
        / "capss"
        / "aurora_verify_r1cs_256"
    ).resolve()
    prove_start = perf_counter()
    prove = subprocess.run(
        [str(prove_exe)],
        cwd=output_dir,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    prove_elapsed = perf_counter() - prove_start
    verify_start = perf_counter()
    verify = subprocess.run(
        [str(verify_exe), "proof-transcript.txt"],
        cwd=output_dir,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    verify_elapsed = perf_counter() - verify_start
    return {
        "output_dir": output_dir,
        "proof_size_bytes": (output_dir / "proof-transcript.txt").stat().st_size,
        "export_seconds": export_elapsed,
        "prove_seconds": prove_elapsed,
        "verify_seconds": verify_elapsed,
        "prove_returncode": prove.returncode,
        "verify_returncode": verify.returncode,
        "verifier_result": "valid" if aurora_run_is_valid(prove, verify) else "invalid",
    }


def run_aurora_show_zk(instance, *, version: str = "normal") -> dict[str, object]:
    output_dir = show_output_dir(instance, make_zk=True, version=version)
    export_start = perf_counter()
    export_info = export_show_r1cs(instance, output_dir)
    export_elapsed = perf_counter() - export_start
    proof_path = output_dir / "proof-bdac-zk.bin"
    if proof_path.exists():
        proof_path.unlink()
    prove_exe = (
        output_dir
        / ".."
        / ".."
        / "capss-aggregation"
        / "build-openmp"
        / "capss"
        / "aurora_prove_r1cs_256_zk_save_bin"
    ).resolve()
    verify_exe = (
        output_dir
        / ".."
        / ".."
        / "capss-aggregation"
        / "build-openmp"
        / "capss"
        / "aurora_verify_r1cs_256_zk_bin"
    ).resolve()
    aurora_env = aurora_environment()

    prove_start = perf_counter()
    prove = subprocess.run(
        [str(prove_exe), str(proof_path), version],
        cwd=output_dir,
        check=False,
        env=aurora_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    prove_elapsed = perf_counter() - prove_start
    verify_start = perf_counter()
    verify = subprocess.run(
        [str(verify_exe), str(proof_path), version],
        cwd=output_dir,
        check=False,
        env=aurora_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    verify_elapsed = perf_counter() - verify_start
    return {
        "output_dir": output_dir,
        "proof_path": proof_path,
        "aurora_version": version,
        "omp_num_threads": aurora_env.get("OMP_NUM_THREADS"),
        "proof_size_bytes": proof_path.stat().st_size if proof_path.exists() else 0,
        "export_seconds": export_elapsed,
        "export_timings": export_info.timings or {},
        "prove_seconds": prove_elapsed,
        "verify_seconds": verify_elapsed,
        "prove_returncode": prove.returncode,
        "verify_returncode": verify.returncode,
        "verifier_result": "valid" if aurora_run_is_valid(prove, verify) else "invalid",
    }


def aurora_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", os.environ.get("BDAC_AURORA_OMP_THREADS", "8"))
    env.setdefault("OMP_DYNAMIC", "FALSE")
    return env


def show_output_dir(instance, *, make_zk: bool, version: str = "normal") -> Path:
    if version not in ("normal", "v2"):
        raise ValueError("Aurora version must be 'normal' or 'v2'")
    if version == "v2" and not make_zk:
        raise ValueError("Aurora v2 requires ZK mode")
    suffix = "show_zk" if make_zk else "show"
    if version == "v2":
        suffix += "_v2"
    disclosed_count = len(instance.disclosure.indexes)
    return Path(__file__).resolve().parents[2] / "aurora_workspace" / f"{suffix}_d{disclosed_count}"


def prepare_aurora_show(instance, *, make_zk: bool = True, force: bool = False, version: str = "normal") -> float:
    return prepare_show_r1cs_static(
        instance,
        show_output_dir(instance, make_zk=make_zk, version=version),
        force=force,
    )


def compute_show_message_sizes(
    instance,
    disclosure,
    aurora_result: dict[str, object],
) -> dict[str, int]:
    proof_size = int(aurora_result["proof_size_bytes"])
    sizes = {
        "verifier_to_user": FIELD_ELEMENT_SIZE + len(disclosure.indexes) * INDEX_SIZE,
        "user_to_device": FIELD_ELEMENT_SIZE,
        "device_to_user": len(instance.device_signature) * FIELD_ELEMENT_SIZE,
        "user_to_verifier": (
            len(disclosure.attributes) * FIELD_ELEMENT_SIZE
            + proof_size
        ),
    }
    sizes["total"] = sum(sizes.values())
    return sizes


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.2f} KiB ({size} B)"
    return f"{size / (1024 * 1024):.2f} MiB ({size} B)"
