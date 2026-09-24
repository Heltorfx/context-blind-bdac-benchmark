from __future__ import annotations

"""Show-proof adapter for the current Aurora/R1CS backend."""

from BDAC.proofs.show_runner import (
    compute_show_message_sizes,
    prepare_aurora_show,
    run_aurora_show,
    run_aurora_show_zk,
)
from BDAC.proofs.show_r1cs import (
    build_show_proof_instance,
    precompute_show_r1cs_template,
    prove_show_r1cs,
    use_auxiliary_branch,
)

__all__ = [
    "build_show_proof_instance",
    "compute_show_message_sizes",
    "prepare_aurora_show",
    "precompute_show_r1cs_template",
    "prove_show_r1cs",
    "use_auxiliary_branch",
    "run_aurora_show",
    "run_aurora_show_zk",
]
