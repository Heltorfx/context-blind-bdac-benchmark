#!/usr/bin/env python3
"""Collect reproducibility metadata without third-party dependencies."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


def command(*args: str, cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    output = result.stdout.strip()
    return output if output else None


def git_metadata(path: Path) -> dict[str, object]:
    commit = command("git", "rev-parse", "HEAD", cwd=path)
    if commit is None:
        return {"available": False}
    status = command("git", "status", "--short", cwd=path) or ""
    remote = command("git", "remote", "get-url", "origin", cwd=path)
    return {
        "available": True,
        "commit": commit,
        "dirty": bool(status),
        "remote": remote,
    }


def cpu_model() -> str | None:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    value = platform.processor().strip()
    return value or None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--aurora-version", required=True)
    parser.add_argument("--threads", type=int, required=True)
    args = parser.parse_args()

    implementation = args.implementation_root.resolve()
    payload = {
        "benchmark": {
            "mode": args.mode,
            "aurora_version": args.aurora_version,
            "threads": args.threads,
        },
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu": cpu_model(),
            "logical_cpus": os.cpu_count(),
            "python": sys.version.replace("\n", " "),
        },
        "tools": {
            "sage": command("sage", "--version"),
            "cmake": command("cmake", "--version"),
            "compiler": command("c++", "--version"),
            "rustc": command("rustc", "--version"),
            "cargo": command("cargo", "--version"),
        },
        "environment": {
            key: os.environ.get(key)
            for key in (
                "OMP_NUM_THREADS",
                "OMP_DYNAMIC",
                "RAYON_NUM_THREADS",
                "CAPSS_DISABLE_RUST_GRIFFIN",
            )
        },
        "repositories": {
            "artifact": git_metadata(implementation.parent),
            "capss_aggregation": git_metadata(implementation / "capss-aggregation"),
            "smallwood_python": git_metadata(implementation / "smallwood-python"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

