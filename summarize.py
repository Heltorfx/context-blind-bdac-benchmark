#!/usr/bin/env python3
"""Turn raw benchmark output into Markdown and CSV summaries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def milliseconds(value: float) -> str:
    return f"{1000.0 * value:.2f} ms"


def seconds(value: float) -> str:
    return f"{value:.3f} s"


def decimal_kb(value: float) -> str:
    return f"{value / 1000.0:.2f} KB"


def add_metric(rows: list[tuple[str, str, str]], group: str, metric: str, value: str) -> None:
    rows.append((group, metric, value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("environment", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    raw = args.benchmark.read_bytes()
    data = json.loads(raw)
    environment = json.loads(args.environment.read_text(encoding="utf-8"))
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    metadata = data["metadata"]
    flow = data["full_flow"]
    show = flow["show_d4"]
    issuance = flow["issuance_summary"]
    capss = data["capss_microbench"]
    issuance_total = issuance["Issuance total"]

    rows: list[tuple[str, str, str]] = []
    add_metric(rows, "CAPSS", "Key generation", milliseconds(capss["keygen_avg_seconds"]))
    add_metric(rows, "CAPSS", "Signing", milliseconds(capss["sign_avg_seconds"]))
    add_metric(rows, "CAPSS", "Verification", milliseconds(capss["verify_avg_seconds"]))
    add_metric(rows, "Issuance", "Total", seconds(issuance_total["mean_seconds"]))
    add_metric(rows, "Issuance", "Communication", decimal_kb(flow["issuance_message_sizes"]["total"]))
    add_metric(rows, "Presentation", "Witness construction", seconds(show["show_instance_seconds"]))
    add_metric(rows, "Presentation", "R1CS export", seconds(show["export_seconds"]))
    add_metric(rows, "Presentation", "Aurora proving", seconds(show["prove_seconds"]))
    add_metric(rows, "Presentation", "Aurora verification", seconds(show["verify_seconds"]))
    add_metric(rows, "Presentation", "User online total", seconds(show["user_online_seconds"]))
    add_metric(rows, "Presentation", "Proof size", decimal_kb(show["proof_size_bytes"]))
    add_metric(rows, "Presentation", "Total communication", decimal_kb(show["total_sent_bytes"]))
    add_metric(rows, "Circuit", "Constraints", str(show["constraints"]))
    add_metric(rows, "Circuit", "Variables", str(show["variables"]))
    add_metric(rows, "Circuit", "Primary inputs", str(show["primary_inputs"]))

    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("group", "metric", "value"))
        writer.writerows(rows)

    with (output / "presentation-samples.csv").open("w", newline="", encoding="utf-8") as handle:
        samples = show["samples"]
        fieldnames = [
            "trial",
            "witness_seconds",
            "export_seconds",
            "prove_seconds",
            "verify_seconds",
            "user_online_seconds",
            "proof_size_bytes",
            "total_sent_bytes",
            "valid",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for trial, sample in enumerate(samples, start=1):
            writer.writerow({"trial": trial, **{key: sample[key] for key in fieldnames[1:]}})

    system = environment["system"]
    lines = [
        "# Context-Blind BDAC benchmark report",
        "",
        "## Configuration",
        "",
        f"- Mode: `{environment['benchmark']['mode']}`",
        f"- Aurora implementation: `{metadata['aurora_version']}`",
        f"- CAPSS instance: `{metadata['capss_scheme']}`",
        f"- Security parameter: `{metadata['security_parameter']}`",
        f"- Attributes / disclosed attributes: `{metadata['attribute_count']}` / `{metadata['default_disclosure_count']}`",
        f"- Issuance / CAPSS / presentation trials: `{metadata['issuance_iterations']}` / `{capss['iterations']}` / `{show['iterations']}`",
        f"- Threads: `{environment['benchmark']['threads']}`",
        f"- Raw-result SHA-256: `{hashlib.sha256(raw).hexdigest()}`",
        "",
        "## Machine",
        "",
        f"- CPU: `{system.get('cpu') or 'unavailable'}`",
        f"- Logical CPUs: `{system.get('logical_cpus')}`",
        f"- Platform: `{system.get('platform')}`",
        "",
        "## Results",
        "",
        "| Group | Metric | Result |",
        "|---|---|---:|",
    ]
    lines.extend(f"| {group} | {metric} | {value} |" for group, metric, value in rows)
    lines.extend(
        [
            "",
            "All sizes use decimal kilobytes. The benchmark performs an untimed warm-up before measured presentation trials. Raw samples and complete environment metadata are retained beside this report.",
            "",
        ]
    )
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    checksums = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            checksums.append(f"{digest}  {path.name}")
    (output / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="ascii")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
