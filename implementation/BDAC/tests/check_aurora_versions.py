"""Exercise both compiled backends on an existing R1CS without changing its files."""
import argparse
import json
import os
from pathlib import Path
import shutil
from statistics import fmean
import subprocess
import tempfile
from time import perf_counter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("BDAC/benchmarks/aurora_v2_comparison.json"))
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be positive")
    root = Path(__file__).resolve().parents[2]
    source = root / "aurora_workspace/show_zk_d4"
    binaries = root / "capss-aggregation/build-openmp/capss"
    env = dict(os.environ, OMP_NUM_THREADS="8", OMP_DYNAMIC="FALSE")
    payload = {"note": "Fixed R1CS and witness; fresh proof randomness; one warmup per mode. Not full protocol timing.", "modes": {}}
    with tempfile.TemporaryDirectory(prefix="bdac-v2-test-") as tmp:
        work = Path(tmp)
        for path in source.glob("r1cs-*.txt"):
            shutil.copyfile(path, work / path.name)

        def run(role, proof, mode):
            binary = "aurora_prove_r1cs_256_zk_save_bin" if role == "prover" else "aurora_verify_r1cs_256_zk_bin"
            start = perf_counter()
            result = subprocess.run([str(binaries / binary), str(proof), mode], cwd=work,
                                    env=env, text=True, capture_output=True, timeout=300)
            elapsed = perf_counter() - start
            valid = result.returncode == 0 and (role == "prover" or result.stdout.strip().splitlines()[-1:] == ["[OK] VALID"])
            return valid, elapsed, result.stdout + result.stderr

        old_ok, _, _ = run("verifier", source / "proof-bdac-zk.bin", "normal")
        if not old_ok:
            raise AssertionError("existing normal proof no longer verifies")
        payload["old_normal_proof_valid"] = True
        for mode in ("normal", "v2"):
            samples = []
            proof = work / f"{mode}.bin"
            for trial in range(args.iterations + 1):
                ok, prove_time, log = run("prover", proof, mode)
                if not ok: raise AssertionError(log[-5000:])
                ok, verify_time, vlog = run("verifier", proof, mode)
                if not ok: raise AssertionError(vlog[-5000:])
                if trial:
                    samples.append({"prove_seconds": prove_time, "verify_seconds": verify_time,
                                    "proof_bytes": proof.stat().st_size})
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.with_suffix(f".{mode}.prover.log").write_text(log)
                args.out.with_suffix(f".{mode}.verifier.log").write_text(vlog)
            payload["modes"][mode] = {
                "samples": samples,
                "prove_mean_seconds": fmean(s["prove_seconds"] for s in samples),
                "verify_mean_seconds": fmean(s["verify_seconds"] for s in samples),
                "proof_mean_KB": fmean(s["proof_bytes"] for s in samples) / 1000,
            }
            other = "v2" if mode == "normal" else "normal"
            if run("verifier", proof, other)[0]: raise AssertionError("cross-version proof accepted")

        proof = work / "v2.bin"
        original_proof = proof.read_bytes()
        if original_proof[:17] != b"LIBIOP_BCS_BIN_V2":
            raise AssertionError("unexpected v2 header")
        rounds = int.from_bytes(original_proof[17:25], "little")
        if rounds != 8: raise AssertionError(f"unexpected round count: {rounds}")
        tests = {}
        for label, offset in (("round_salt", 25), ("proof_payload", len(original_proof)-1)):
            changed = bytearray(original_proof)
            changed[offset] ^= 1
            proof.write_bytes(changed)
            tests[label] = not run("verifier", proof, "v2")[0]
        proof.write_bytes(original_proof)
        primary = work / "r1cs-primary-inputs.txt"
        original_primary = primary.read_text()
        fields = original_primary.split()
        fields[2] = str(int(fields[2]) + 1)
        primary.write_text(" ".join(fields) + "\n")
        tests["public_challenge"] = not run("verifier", proof, "v2")[0]
        primary.write_text(original_primary)
        proof.write_bytes(original_proof + b"unexpected")
        tests["trailing_data"] = not run("verifier", proof, "v2")[0]
        if not all(tests.values()): raise AssertionError(tests)
        payload["rejection_tests"] = tests
        payload["cross_version_rejected"] = True
    args.out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
