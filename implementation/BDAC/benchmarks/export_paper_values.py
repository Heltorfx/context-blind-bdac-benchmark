"""Export checked benchmark means to LaTeX; sizes are decimal KB."""
import argparse
import hashlib
import json
from pathlib import Path


BACKENDS = {
    "normal": "aurora92-full-transcript-absorption",
    "v2": "aurora-v2-salted-prefix",
}


def render(data, source_name, digest, expected_version):
    metadata = data["metadata"]
    actual_version = metadata.get("aurora_version", "normal")
    if actual_version != expected_version:
        raise ValueError(f"Expected Aurora {expected_version}, got {actual_version}")
    if metadata.get("backend_revision") != BACKENDS[expected_version]:
        raise ValueError("Refusing results from an unknown or uncorrected backend")
    if data["metadata"]["issuance_iterations"] != 30:
        raise ValueError("Expected 30 issuance trials")
    micro = data["capss_microbench"]
    if micro["iterations"] != 30:
        raise ValueError("Expected 30 CAPSS trials")
    scaling = data["scaling"]
    if {row["disclosed_count"] for row in scaling} != {4}:
        raise ValueError("Expected the default four-disclosure configuration")
    for row in scaling:
        if row["iterations"] != 30 or len(row["samples"]) != 30 or not row["valid"]:
            raise ValueError("Expected 30 successful presentations per configuration")
        if not all(sample["valid"] for sample in row["samples"]):
            raise ValueError("Invalid sample")
    flow = data["full_flow"]
    default = flow["show_d4"]
    issuance = flow["issuance_summary"]
    mean = lambda name: issuance[name]["mean_seconds"]
    values = {
        "KeygenMS": 1000 * micro["keygen_avg_seconds"],
        "SignMS": 1000 * micro["sign_avg_seconds"],
        "SigVerifyMS": 1000 * micro["verify_avg_seconds"],
        "IssuanceMean": mean("Issuance total"),
        "IssuanceSD": issuance["Issuance total"]["stddev_seconds"],
        "UserCommitMean": mean("Issuer builds Merkle root || dpk"),
        "IssuerMean": mean("Issuer signs credential"),
        "CredVerifyMean": mean("Issuer verifies credential"),
        "IssuanceKB": flow["issuance_message_sizes"]["total"] / 1000,
        "StaticSeconds": default["static_export_seconds"] + next(
            item["seconds"] for item in flow["timings"]
            if item["name"] == "Precompute Show R1CS template d=4"),
        "WitnessMean": default["show_instance_seconds"],
        "WitnessSD": default["show_instance_stddev_seconds"],
        "ExportMean": default["export_seconds"],
        "ExportSD": default["export_stddev_seconds"],
        "ProveMean": default["prove_seconds"],
        "ProveSD": default["prove_stddev_seconds"],
        "VerifyMean": default["verify_seconds"],
        "VerifySD": default["verify_stddev_seconds"],
        "UserMean": default["user_online_seconds"],
        "UserSD": default["user_online_stddev_seconds"],
        "ProofKB": default["proof_size_bytes"] / 1000,
        "ProofMinKB": default["proof_size_min_bytes"] / 1000,
        "ProofMaxKB": default["proof_size_max_bytes"] / 1000,
        "TotalKB": default["total_sent_bytes"] / 1000,
        "Constraints": default["constraints"],
        "Variables": default["variables"],
        "PrimaryInputs": default["primary_inputs"],
    }
    integer_values = {"Constraints", "Variables", "PrimaryInputs"}
    lines = [f"% Generated from {source_name}", f"% SHA256: {digest}"]
    for key, value in values.items():
        rendered = str(int(value)) if key in integer_values else f"{value:.2f}"
        lines.append(r"\newcommand{\bench" + key + "}{" + rendered + "}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected-version", choices=tuple(BACKENDS), required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    result = render(
        json.loads(raw), args.input.name, hashlib.sha256(raw).hexdigest(), args.expected_version
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="ascii")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
