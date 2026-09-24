"""Capture inclusive libff block timings for a pre-exported Aurora instance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from time import perf_counter


def parse_blocks(output):
    blocks = {}
    for match in re.finditer(r"\(leave\)\s+(.+?)\s+\[([0-9.]+)s x[0-9.]+\]", output):
        name, elapsed = match.groups()
        item = blocks.setdefault(name, {"calls": 0, "inclusive_seconds": 0.0})
        item["calls"] += 1
        item["inclusive_seconds"] += float(elapsed)
    return blocks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--disclosed", type=int, default=4)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    work = root / f"aurora_workspace/show_zk_d{args.disclosed}"
    binaries = root / "capss-aggregation/build-openmp/capss"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, OMP_NUM_THREADS="8", OMP_DYNAMIC="FALSE")
    payload = {"disclosed": args.disclosed, "threads": 8,
               "note": "Single run; nested inclusive blocks must not be summed."}
    with tempfile.TemporaryDirectory(prefix="bdac-profile-") as tmp:
        proof = Path(tmp) / "proof.bin"
        for role, binary in (
            ("prover", "aurora_prove_r1cs_256_zk_save_bin"),
            ("verifier", "aurora_verify_r1cs_256_zk_bin"),
        ):
            exe = binaries / binary
            start = perf_counter()
            run = subprocess.run([str(exe), str(proof)], cwd=work, env=env,
                                 text=True, capture_output=True, check=True, timeout=300)
            elapsed = perf_counter() - start
            args.out.with_suffix(f".{role}.log").write_text(run.stdout + run.stderr)
            payload[role] = {
                "wall_seconds": elapsed,
                "blocks": parse_blocks(run.stdout),
                "binary_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
            }
            if role == "verifier" and run.stdout.strip().splitlines()[-1:] != ["[OK] VALID"]:
                raise RuntimeError("missing explicit verifier success")
        payload["proof_size_bytes"] = proof.stat().st_size
    args.out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
