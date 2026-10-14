from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from BDAC.proofs.show_backend import run_aurora_show, run_aurora_show_zk


@dataclass(frozen=True)
class ProofResult:
    raw: dict[str, Any]

    @property
    def verifier_result(self) -> str:
        return str(self.raw.get("verifier_result", "unknown"))

    @property
    def ok(self) -> bool:
        return self.verifier_result == "valid"


AuroraResult = ProofResult


class AuroraBackend:
    """Thin proof backend wrapper used by the BDAC protocol layer."""

    def __init__(self, make_zk: bool = True, version: str = "normal"):
        if version not in ("normal", "v2"):
            raise ValueError("Aurora version must be 'normal' or 'v2'")
        if version == "v2" and not make_zk:
            raise ValueError("Aurora v2 requires ZK mode")
        self.make_zk = make_zk
        self.version = version

    def prove_show(self, instance) -> ProofResult:
        raw = run_aurora_show_zk(instance, version=self.version) if self.make_zk else run_aurora_show(instance)
        return ProofResult(raw)
