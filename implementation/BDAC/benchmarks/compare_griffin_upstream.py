from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


IMPLEMENTATION_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_SCRIPT = IMPLEMENTATION_ROOT / "rust-griffin" / "python" / "bench_signature.py"
LOCAL_SMALLWOOD = IMPLEMENTATION_ROOT / "smallwood-python"
UPSTREAM_SMALLWOOD = IMPLEMENTATION_ROOT / "external" / "smallwood-python-official"


def _parse_output(output: str) -> dict[str, str]:
    values = {}
    for line in output.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip()
    return values


def _run_benchmark(
    smallwood_path: Path,
    *,
    scheme: str,
    warmups: int,
    runs: int,
    threads: int,
    disable_rust: bool,
) -> dict[str, str]:
    command = [
        sys.executable,
        str(BENCHMARK_SCRIPT),
        "--smallwood-path",
        str(smallwood_path),
        "--scheme",
        scheme,
        "--warmups",
        str(warmups),
        "--runs",
        str(runs),
    ]
    if disable_rust:
        command.append("--disable-rust")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(IMPLEMENTATION_ROOT / "rust-griffin")
    environment["RAYON_NUM_THREADS"] = str(threads)
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return _parse_output(completed.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare identical CAPSS-Griffin instances in BDAC and upstream Python."
    )
    parser.add_argument("--scheme", default="G256-5.fast.extended")
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--threads", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()

    local = _run_benchmark(
        LOCAL_SMALLWOOD,
        scheme=args.scheme,
        warmups=args.warmups,
        runs=args.runs,
        threads=args.threads,
        disable_rust=False,
    )
    upstream = _run_benchmark(
        UPSTREAM_SMALLWOOD,
        scheme=args.scheme,
        warmups=args.warmups,
        runs=args.runs,
        threads=1,
        disable_rust=True,
    )

    if local.get("ok") != "True" or upstream.get("ok") != "True":
        raise SystemExit("at least one implementation rejected its own signature")
    if local["signature_bytes"] != upstream["signature_bytes"]:
        raise SystemExit(
            "signature sizes differ; the selected implementations are not directly comparable"
        )

    local_sign = float(local["sign_seconds_avg"])
    local_verify = float(local["verify_seconds_avg"])
    upstream_sign = float(upstream["sign_seconds_avg"])
    upstream_verify = float(upstream["verify_seconds_avg"])

    print("=== CAPSS-Griffin implementation comparison ===")
    print(f"scheme: {args.scheme}")
    print(f"runs: {args.runs}")
    print(f"signature_size: {local['signature_kb']} KB")
    print()
    print("implementation            sign       verify")
    print(f"BDAC Python/Rust       {local_sign:8.3f}s   {local_verify:8.3f}s")
    print(f"upstream Python        {upstream_sign:8.3f}s   {upstream_verify:8.3f}s")
    print()
    print(f"sign_speedup: {upstream_sign / local_sign:.2f}x")
    print(f"verify_speedup: {upstream_verify / local_verify:.2f}x")


if __name__ == "__main__":
    main()
