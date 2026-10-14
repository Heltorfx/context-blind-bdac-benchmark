from __future__ import annotations

import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from BDAC.proofs.aurora_backend import ProofResult
from BDAC.proofs.show_r1cs import export_show_r1cs


def parse_longfellow_output(stdout: str) -> tuple[dict[str, str], dict[str, str]]:
    records = []
    for line in stdout.splitlines():
        if line.startswith("constraints=") or line.startswith("run="):
            records.append(dict(item.split("=", 1) for item in line.split()))
    if len(records) != 2 or records[1].get("valid") != "1":
        raise RuntimeError(f"Longfellow did not produce a valid proof:\n{stdout}")
    if "modified_public_input_accepted=0" not in stdout.splitlines():
        raise RuntimeError(f"Longfellow public-input check failed:\n{stdout}")
    return records[0], records[1]


class LongfellowBackend:
    """Run the BDAC R1CS with the Longfellow sumcheck/Ligero backend."""

    def __init__(self, binary: str | Path, *, block_enc: int = 15677, queries: int = 160):
        self.binary = Path(binary).expanduser().resolve(strict=True)
        if block_enc < 1 or not 1 <= queries <= 256:
            raise ValueError("Invalid Longfellow parameters")
        self.block_enc = block_enc
        self.queries = queries

    def prove_show(self, instance) -> ProofResult:
        with TemporaryDirectory(prefix="bdac-longfellow-") as tmp:
            start = perf_counter()
            exported = export_show_r1cs(instance, tmp)
            export_seconds = perf_counter() - start
            proc = subprocess.run(
                [str(self.binary), tmp, str(self.block_enc), "1", str(self.queries)],
                capture_output=True,
                text=True,
                check=True,
                env=os.environ.copy(),
            )
        circuit, proof = parse_longfellow_output(proc.stdout)
        if int(circuit["constraints"]) != exported.nb_constraints:
            raise RuntimeError("Longfellow circuit dimensions differ from the exported R1CS")
        if int(circuit["queries"]) != self.queries or int(circuit["block_enc"]) != self.block_enc:
            raise RuntimeError("Longfellow used unexpected proof parameters")
        return ProofResult({
            "verifier_result": "valid",
            "proof_size_bytes": int(proof["proof_bytes"]),
            "export_seconds": export_seconds,
            "compile_seconds": float(circuit["compile_s"]),
            "prove_seconds": float(proof["prove_s"]),
            "verify_seconds": float(proof["verify_s"]),
            "block_enc": self.block_enc,
            "queries": self.queries,
            "backend": "Longfellow (sumcheck + Ligero)",
        })
