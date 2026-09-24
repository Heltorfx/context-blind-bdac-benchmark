"""Benchmark Aurora verification on a fixed public instance and proof."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
from statistics import fmean, pstdev
import subprocess
import tempfile
from time import perf_counter


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--disclosures", type=int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be positive")

    root = Path(__file__).resolve().parents[2]
    verifier = (
        root
        / "capss-aggregation/build-openmp/capss/aurora_verify_r1cs_256_zk_bin"
    )
    env = dict(os.environ, OMP_NUM_THREADS="8", OMP_DYNAMIC="FALSE")

    results = {}
    for disclosures in args.disclosures:
        source = root / f"aurora_workspace/show_zk_v2_d{disclosures}"
        with tempfile.TemporaryDirectory(prefix="bdac-verifier-bench-") as tmp:
            work = Path(tmp)
            for name in (
                "r1cs-field.txt",
                "r1cs-primary-inputs.txt",
                "r1cs-constraints.txt",
            ):
                shutil.copyfile(source / name, work / name)
            shutil.copyfile(source / "proof-bdac-zk.bin", work / "proof.bin")

            samples = []
            for trial in range(args.iterations + 1):
                start = perf_counter()
                result = subprocess.run(
                    [str(verifier), "proof.bin", "v2"],
                    cwd=work,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=180,
                )
                elapsed = perf_counter() - start
                if result.returncode or not result.stdout.strip().endswith("[OK] VALID"):
                    raise RuntimeError((result.stdout + result.stderr)[-5000:])
                if trial:
                    samples.append(elapsed)
        results[str(disclosures)] = {
            "mean_seconds": fmean(samples),
            "standard_deviation_seconds": pstdev(samples),
            "minimum_seconds": min(samples),
            "maximum_seconds": max(samples),
            "samples_seconds": samples,
        }

    payload = {
        "iterations": args.iterations,
        "warmups": 1,
        "aurora_version": "v2",
        "auxiliary_witness_available_to_verifier": False,
        "disclosures": results,
    }
    rendered = json.dumps(payload, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
