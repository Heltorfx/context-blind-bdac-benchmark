from __future__ import annotations

import argparse
import json
from math import ceil, log2
from time import perf_counter

from BDAC.parameters import SMALLWOOD_PATH
from BDAC.proofs.show_r1cs import build_show_r1cs, make_show_proof_instance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["toy", "show-estimate"], default="toy")
    parser.add_argument("--batch-cols", type=int, default=256)
    parser.add_argument("--security", type=int, default=128)
    parser.add_argument("--decs-queries", type=int, default=10)
    parser.add_argument("--decs-eta", type=int, default=2)
    parser.add_argument("--decs-pow-opening", type=int, default=0)
    parser.add_argument("--layout-beta", type=int, default=1)
    parser.add_argument("--piop-queries", type=int, default=1)
    parser.add_argument("--piop-rho", type=int, default=2)
    parser.add_argument("--tree-leaves", type=int, default=None)
    args = parser.parse_args()

    ensure_smallwood_path()
    if args.mode == "toy":
        payload = run_toy(args)
    else:
        payload = estimate_show(args)
    print(json.dumps(payload, indent=2, sort_keys=True))


def ensure_smallwood_path() -> None:
    import sys

    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))


def run_toy(args) -> dict[str, object]:
    from r1cs.r1cs import R1CS
    from sage.all import FiniteField
    from smallwood.pacs.constraints.pacs_r1cs import PACSFromR1CS

    field = FiniteField(101)
    r1cs = R1CS(field)
    y = r1cs.new_register("y", is_primary=True)
    x = r1cs.new_register("x")
    r1cs.register_equation(x, x, y)

    assignment = r1cs.resolve({"x": field(9), "y": field(81)})
    assert r1cs.evaluate(assignment)
    mapping = {var_id: assignment[var_id] for var_id in range(r1cs.get_nb_primary_inputs())}
    pacs = PACSFromR1CS(r1cs, nb_batched=1, mapping=mapping)
    witness = pacs.build_witness(assignment)
    assert pacs.test_witness(witness)

    sw = make_smallwood_shake(
        pacs,
        security_level=32,
        decs_queries=2,
        decs_eta=1,
        decs_pow_opening=0,
        layout_beta=1,
        piop_queries=1,
        piop_rho=1,
        tree_leaves=None,
    )

    prove_start = perf_counter()
    proof = sw.prove(witness)
    prove_seconds = perf_counter() - prove_start
    verify_start = perf_counter()
    valid = bool(sw.verify(proof))
    verify_seconds = perf_counter() - verify_start

    return {
        "mode": "toy",
        "r1cs": r1cs_stats(r1cs),
        "pacs": pacs_stats(pacs),
        "smallwood": {
            "proof_bytes": len(proof),
            "declared_proof_bytes": sw.get_proof_size(),
            "prove_seconds": prove_seconds,
            "verify_seconds": verify_seconds,
            "valid": valid,
        },
    }


def estimate_show(args) -> dict[str, object]:
    from smallwood.pacs.constraints.pacs_r1cs import PACSFromR1CS

    build_start = perf_counter()
    instance = make_show_proof_instance()
    r1cs, witness_labels = build_show_r1cs(instance)
    assignment = r1cs.resolve(witness_labels)
    build_seconds = perf_counter() - build_start
    mapping = {var_id: assignment[var_id] for var_id in range(r1cs.get_nb_primary_inputs())}
    pacs = PACSFromR1CS(r1cs, nb_batched=args.batch_cols, mapping=mapping)
    sw = make_smallwood_shake(
        pacs,
        security_level=args.security,
        decs_queries=args.decs_queries,
        decs_eta=args.decs_eta,
        decs_pow_opening=args.decs_pow_opening,
        layout_beta=args.layout_beta,
        piop_queries=args.piop_queries,
        piop_rho=args.piop_rho,
        tree_leaves=args.tree_leaves,
    )

    dense_theta_entries = (
        3
        * r1cs.get_nb_equations()
        * (pacs._nb_rows_wit + 2)
        * pacs.get_nb_wit_cols()
    )
    primary_theta_entries = (
        r1cs.get_nb_primary_inputs()
        * 2
        * pacs.get_nb_wit_cols()
    )
    averaged_proof_bytes = None
    try:
        averaged_proof_bytes = sw.get_averaged_proof_size()
    except NotImplementedError:
        averaged_proof_bytes = None

    return {
        "mode": "show-estimate",
        "build_seconds": build_seconds,
        "r1cs": r1cs_stats(r1cs),
        "pacs": pacs_stats(pacs),
        "smallwood_parameters": {
            "security": args.security,
            "batch_cols": args.batch_cols,
            "tree_nb_leaves": choose_tree_nb_leaves(sw),
            "decs_queries": args.decs_queries,
            "decs_eta": args.decs_eta,
            "decs_pow_opening": args.decs_pow_opening,
            "layout_beta": args.layout_beta,
            "piop_queries": args.piop_queries,
            "piop_rho": args.piop_rho,
        },
        "smallwood_estimate": {
            "proof_bytes": sw.get_proof_size(),
            "proof_kib": sw.get_proof_size() / 1024,
            "averaged_proof_bytes": averaged_proof_bytes,
            "security_bits": float(sw.get_security()[0]),
            "stable_security": stable_security_estimate(sw),
        },
        "dense_bridge_cost": {
            "aggregated_theta_entries": dense_theta_entries,
            "primary_theta_entries": primary_theta_entries,
            "estimated_field_bytes_for_theta": 32 * (dense_theta_entries + primary_theta_entries),
            "note": "Current PACSFromR1CS exposes dense theta data; proving Show this way is expected to be impractical without a sparse/native bridge.",
        },
    }


def make_smallwood_shake(
    pacs,
    *,
    security_level: int,
    decs_queries: int,
    decs_eta: int,
    decs_pow_opening: int,
    layout_beta: int,
    piop_queries: int,
    piop_rho: int,
    tree_leaves: int | None,
):
    from smallwood.shake import SmallWoodWithShake

    tree_nb_leaves = tree_leaves or choose_tree_nb_leaves_for_pacs(
            pacs,
            decs_queries=decs_queries,
            layout_beta=layout_beta,
            piop_queries=piop_queries,
            piop_rho=piop_rho,
        )
    return SmallWoodWithShake(
        pacs=pacs,
        security_level=security_level,
        tree_nb_leaves=tree_nb_leaves,
        tree_arity=power_of_two_arity(tree_nb_leaves),
        tree_truncated=None,
        decs_nb_queries=decs_queries,
        decs_eta=decs_eta,
        decs_pow_opening=decs_pow_opening,
        layout_beta=layout_beta,
        piop_nb_queries=piop_queries,
        piop_rho=piop_rho,
    )


def choose_tree_nb_leaves_for_pacs(
    pacs,
    *,
    decs_queries: int,
    layout_beta: int,
    piop_queries: int,
    piop_rho: int,
) -> int:
    nb_cols = pacs.get_nb_wit_cols()
    input_degree = piop_queries + nb_cols - 1
    deg_q = pacs.get_constraint_degree() * input_degree + nb_cols
    poly_col_size = input_degree - piop_queries + 1
    split_inputs = ceil((input_degree + 1 - piop_queries) / poly_col_size)
    split_masks = ceil((deg_q + 1 - piop_queries) / poly_col_size)
    unstacked_row_length = (
        pacs.get_nb_wit_rows() * split_inputs
        + piop_rho * split_masks
    )
    row_length = ceil(unstacked_row_length / layout_beta)
    decs_degree = row_length + decs_queries - 1
    target = max(16, decs_degree + decs_queries + 4)
    return 1 << ceil(log2(target))


def choose_tree_nb_leaves(sw) -> int:
    return sw.pcs.lvcs.decs.tree_factory.get_nb_leaves()


def stable_security_estimate(sw) -> dict[str, float]:
    from utils.challenges import get_rlc_bit_security
    from math import log2

    decs = sw.pcs.lvcs.decs
    fpp = get_rlc_bit_security(
        sw.field,
        sw.rho,
        sw.pacs.get_nb_parallel_constraints() * sw.pacs.get_nb_wit_cols()
        + sw.pacs.get_nb_aggregated_constraints(),
        sw.format_challenge,
    )
    query = sw.nb_queries * log2(sw.field.order() / sw.deg_q)
    decs_check = get_rlc_bit_security(
        sw.field,
        decs.eta,
        decs.nb_polys,
        decs.format_challenge,
    ) - log2_binom(decs.nb_evals, decs.degree + 2)
    decs_opening = (
        log2_binom(decs.nb_evals, decs.nb_queries)
        - log2_binom(decs.degree, decs.nb_queries)
        + decs.pow_opening
    )
    return {
        "iop_fpp": fpp,
        "iop_query": query,
        "decs_check": decs_check,
        "decs_opening": decs_opening,
        "min": min(fpp, query, decs_check, decs_opening),
    }


def log2_binom(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("inf")
    from math import lgamma, log

    return (lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)) / log(2)


def power_of_two_arity(nb_leaves: int) -> tuple[int, ...]:
    log_n = ceil(log2(nb_leaves))
    return tuple(4 for _ in range(log_n // 2)) + ((2,) if log_n % 2 else ())


def r1cs_stats(r1cs) -> dict[str, int]:
    return {
        "variables": r1cs.get_nb_variables(),
        "constraints": r1cs.get_nb_equations(),
        "primary_inputs": r1cs.get_nb_primary_inputs(),
    }


def pacs_stats(pacs) -> dict[str, int]:
    return {
        "witness_rows": pacs.get_nb_wit_rows(),
        "witness_cols": pacs.get_nb_wit_cols(),
        "witness_size": pacs.get_witness_size(),
        "parallel_constraints": pacs.get_nb_parallel_constraints(),
        "aggregated_constraints": pacs.get_nb_aggregated_constraints(),
        "constraint_degree": pacs.get_constraint_degree(),
    }


if __name__ == "__main__":
    main()
