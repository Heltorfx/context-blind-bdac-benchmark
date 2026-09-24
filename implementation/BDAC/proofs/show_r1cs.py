from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import json
from pathlib import Path
import sys
from time import perf_counter

from BDAC.core.types import CredentialMessage, CredentialSignature, SelectiveDisclosure
from BDAC.crypto.randomness import random_field_element_int, sample_index_set
from BDAC.entities.governance import GovernanceAuthority
from BDAC.entities.issuer import Issuer
from BDAC.entities.se import SE
from BDAC.entities.user import User
from BDAC.initialization import Setup
from BDAC.protocols.se_blind_signature import SEBlindSignature
from BDAC.parameters import (
    ATTRIBUTE_COUNT,
    CAPSS_FIELD_ORDER,
    CAPSS_GRIFFIN_ALPHA,
    CAPSS_SCHEME_LABEL,
    MERKLE_ARITY,
    MERKLE_HASH_GRIFFIN,
    PRESENTATION_DOMAIN_TAG,
    SIMULATION_DOMAIN_TAG,
    SECURITY_LEVEL,
    SMALLWOOD_PATH,
)


SHOW_DISCLOSURE_COUNT = 4
_SHOW_R1CS_TEMPLATE_CACHE = {}


@dataclass(frozen=True)
class ShowProofInstance:
    credential_message: CredentialMessage
    disclosure: SelectiveDisclosure
    verifier_nonce: int
    issuer_public_key: tuple[int, ...]
    issuer_signature: tuple[int, ...]
    device_signature: tuple[int, ...]
    device_randomness: int
    device_commitment: int
    branch: int
    simulation_public_key: tuple[int, ...]
    simulation_signature: tuple[int, ...]


@dataclass(frozen=True)
class ShowR1CSResult:
    nb_variables: int
    nb_constraints: int
    nb_primary_inputs: int
    nb_satisfied_constraints: int
    proof_ok: bool


@dataclass(frozen=True)
class ShowR1CSExport:
    output_dir: Path
    nb_variables: int
    nb_constraints: int
    nb_primary_inputs: int
    proof_ok: bool
    timings: dict[str, float] | None = None


def make_show_proof_instance() -> ShowProofInstance:
    pp = Setup()
    governance = GovernanceAuthority(pp)
    se = SE(pp)
    issuer = Issuer(pp)
    user = User(pp, se)

    attributes = governance.issue_attributes()
    user.receive_attributes(attributes)
    issued = issuer.issue(user.attributes, user.device_public_key)
    credential_signature = user.receive_issued_credential(issuer, issued)
    credential_message = issued.message

    indexes = sample_index_set(pp.attribute_count, SHOW_DISCLOSURE_COUNT)
    disclosure = user.disclose_attributes(indexes)

    verifier_nonce = _random_field_int()
    return build_show_proof_instance(
        credential_message=credential_message,
        disclosure=disclosure,
        verifier_nonce=verifier_nonce,
        credential_signature=credential_signature,
        device=se.backend,
    )


def build_show_proof_instance(
    credential_message: CredentialMessage,
    disclosure: SelectiveDisclosure,
    verifier_nonce: int,
    credential_signature: CredentialSignature,
    device,
    device_randomness: int | None = None,
    branch: int = 0,
    simulation_signature: tuple[int, ...] | None = None,
) -> ShowProofInstance:
    device_randomness = _random_field_int() if device_randomness is None else device_randomness
    if branch not in (0, 1):
        raise ValueError("presentation branch must be 0 or 1")
    simulation_public_key, _, dummy_signature = _simulation_material()
    simulation_signature = simulation_signature or dummy_signature
    authorization = SEBlindSignature().run(
        device,
        verifier_nonce,
        randomness=device_randomness,
    )

    return ShowProofInstance(
        credential_message=credential_message,
        disclosure=disclosure,
        verifier_nonce=verifier_nonce,
        issuer_public_key=tuple(int(x) for x in credential_signature.issuer_public_key),
        issuer_signature=tuple(int(x) for x in credential_signature.signature),
        device_signature=authorization.signature.signature,
        device_randomness=device_randomness,
        device_commitment=authorization.commitment,
        branch=branch,
        simulation_public_key=simulation_public_key,
        simulation_signature=simulation_signature,
    )


def use_auxiliary_branch(instance: ShowProofInstance) -> ShowProofInstance:
    """Return an instance whose valid witness uses the auxiliary OR branch."""
    public_key, secret_key, _ = _simulation_material()
    scheme = _capss_scheme()
    field = scheme.get_field()
    signature = scheme.sign(
        secret_key,
        [field(value) for value in _auxiliary_message_values(instance)],
    )
    return replace(
        instance,
        branch=1,
        simulation_public_key=public_key,
        simulation_signature=tuple(int(value) for value in signature),
    )


def prove_show_r1cs(instance: ShowProofInstance) -> ShowR1CSResult:
    r1cs, witness = build_show_r1cs(instance)
    assignment = r1cs.resolve(witness)
    nb_satisfied = r1cs.evaluate(assignment, output_nb_true=True)
    proof_ok = nb_satisfied == r1cs.get_nb_equations()
    return ShowR1CSResult(
        nb_variables=r1cs.get_nb_variables(),
        nb_constraints=r1cs.get_nb_equations(),
        nb_primary_inputs=r1cs.get_nb_primary_inputs(),
        nb_satisfied_constraints=nb_satisfied,
        proof_ok=proof_ok,
    )


def export_show_r1cs(
    instance: ShowProofInstance,
    output_dir: str | Path,
) -> ShowR1CSExport:
    timings: dict[str, float] = {}
    start = perf_counter()
    r1cs, witness = build_show_r1cs(instance)
    timings["build_r1cs"] = perf_counter() - start
    start = perf_counter()
    assignment = r1cs.resolve(witness)
    timings["resolve_witness"] = perf_counter() - start

    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))
    from capss.libiop.export_r1cs import export_variables

    output_dir = Path(output_dir)
    start = perf_counter()
    _prepare_show_r1cs_static(instance, r1cs, output_dir)
    timings["export_static_r1cs"] = perf_counter() - start
    start = perf_counter()
    export_variables(
        r1cs,
        [witness],
        output_dir / "r1cs-primary-inputs.txt",
        output_dir / "r1cs-auxiliary-inputs.txt",
        precomputed_variables=[assignment],
        validate=False,
    )
    timings["export_variables"] = perf_counter() - start
    return ShowR1CSExport(
        output_dir=output_dir,
        nb_variables=r1cs.get_nb_variables(),
        nb_constraints=r1cs.get_nb_equations(),
        nb_primary_inputs=r1cs.get_nb_primary_inputs(),
        proof_ok=True,
        timings=timings,
    )


def prepare_show_r1cs_static(
    instance: ShowProofInstance,
    output_dir: str | Path,
    *,
    force: bool = False,
) -> float:
    r1cs = get_show_r1cs_template(
        merkle_hash=instance.credential_message.merkle_hash,
        opened_count=len(instance.disclosure.indexes),
    )
    start = perf_counter()
    _prepare_show_r1cs_static(instance, r1cs, Path(output_dir), force=force)
    return perf_counter() - start


def _prepare_show_r1cs_static(
    instance: ShowProofInstance,
    r1cs,
    output_dir: Path,
    *,
    force: bool = False,
) -> None:
    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))
    from sage.all import ZZ
    from capss.libiop.export_r1cs import export_field_params, export_r1cs

    output_dir.mkdir(parents=True, exist_ok=True)
    field_path = output_dir / "r1cs-field.txt"
    constraints_path = output_dir / "r1cs-constraints.txt"
    cache_metadata = _show_r1cs_cache_metadata(instance, r1cs)
    if force or not _show_r1cs_static_cache_is_valid(output_dir, cache_metadata):
        export_field_params(ZZ(CAPSS_FIELD_ORDER), field_path, verbose=False)
        export_r1cs(r1cs, constraints_path)
        (output_dir / "r1cs-cache-metadata.json").write_text(
            json.dumps(cache_metadata, indent=2, sort_keys=True),
            encoding="ascii",
        )


def build_show_r1cs(instance: ShowProofInstance):
    r1cs = get_show_r1cs_template(
        merkle_hash=instance.credential_message.merkle_hash,
        opened_count=len(instance.disclosure.indexes),
    )
    return r1cs, build_show_r1cs_witness(instance)


def precompute_show_r1cs_template(
    merkle_hash: str = MERKLE_HASH_GRIFFIN,
    opened_count: int = SHOW_DISCLOSURE_COUNT,
):
    return get_show_r1cs_template(merkle_hash=merkle_hash, opened_count=opened_count)


def get_show_r1cs_template(merkle_hash: str, opened_count: int):
    cache_key = (CAPSS_SCHEME_LABEL, merkle_hash, opened_count)
    if cache_key not in _SHOW_R1CS_TEMPLATE_CACHE:
        _SHOW_R1CS_TEMPLATE_CACHE[cache_key] = _build_show_r1cs_template(
            merkle_hash=merkle_hash,
            opened_count=opened_count,
        )
    return _SHOW_R1CS_TEMPLATE_CACHE[cache_key]


def build_show_r1cs_witness(instance: ShowProofInstance) -> dict[str, object]:
    if instance.credential_message.merkle_hash != MERKLE_HASH_GRIFFIN:
        raise ValueError("Show proof currently supports only Griffin Merkle trees.")
    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))
    from sage.all import FiniteField

    field = FiniteField(CAPSS_FIELD_ORDER)
    return {
        "verifier_nonce": field(instance.verifier_nonce),
        "opened_indexes": [field(index) for index in instance.disclosure.indexes],
        "opened_leaves": [
            [field(int.from_bytes(attribute, "big"))]
            for attribute in instance.disclosure.attributes
        ],
        "issuer_pk": [field(value) for value in instance.issuer_public_key],
        "branch": field(instance.branch),
        "simulation_pk": [field(value) for value in instance.simulation_public_key],
        "root": field(int.from_bytes(instance.credential_message.root, "big")),
        "dpk": [
            field(int.from_bytes(instance.credential_message.device_public_key[i : i + 32], "big"))
            for i in range(0, len(instance.credential_message.device_public_key), 32)
        ],
        "device_randomness": field(instance.device_randomness),
        "auth": [field(value) for value in _expect_int_tuple(instance.disclosure.authentication_path)],
        "issuer_sig": [field(value) for value in instance.issuer_signature],
        "device_sig": [field(value) for value in instance.device_signature],
        "simulation_sig": [field(value) for value in instance.simulation_signature],
    }


def _build_show_r1cs_template(merkle_hash: str, opened_count: int):
    if merkle_hash != MERKLE_HASH_GRIFFIN:
        raise ValueError("Show proof currently supports only Griffin Merkle trees.")
    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))

    from capss.hash import JiveCompressionFunction
    from capss.hash.griffin import Griffin
    from capss.sign.instances import get_scheme
    from r1cs.commit.merkle import MerkleTreeFactoryWithAOHash_R1CS
    from r1cs.r1cs import R1CS
    from r1cs.variable import Variable
    from sage.all import FiniteField

    field = FiniteField(CAPSS_FIELD_ORDER)
    issuer_scheme = get_scheme(CAPSS_SCHEME_LABEL)
    device_scheme = get_scheme(CAPSS_SCHEME_LABEL)
    auxiliary_scheme = get_scheme(CAPSS_SCHEME_LABEL)

    permutation = Griffin.get(CAPSS_FIELD_ORDER, CAPSS_GRIFFIN_ALPHA, 4, 1, SECURITY_LEVEL)
    compression = JiveCompressionFunction(permutation)
    tree_factory = MerkleTreeFactoryWithAOHash_R1CS(
        nb_leaves=ATTRIBUTE_COUNT,
        arity=MERKLE_ARITY,
        compression_method={4: compression},
        output_size=1,
        is_expanded=True,
    )

    r1cs = R1CS(field)
    nb_opened = opened_count
    auth_size = tree_factory.get_authentication_path_max_size(nb_opened)

    verifier_nonce = r1cs.new_register("verifier_nonce", is_primary=True)
    opened_indexes = r1cs.new_registers(nb_opened, "opened_indexes", is_primary=True)
    opened_leaves = r1cs.new_registers((nb_opened, 1), "opened_leaves", is_primary=True)
    issuer_pk = r1cs.new_registers(issuer_scheme.get_public_key_size(), "issuer_pk", is_primary=True)
    simulation_pk = r1cs.new_registers(
        issuer_scheme.get_public_key_size(),
        "simulation_pk",
        is_primary=True,
    )
    branch = r1cs.new_register("branch")
    branch.force_binary()

    root = r1cs.new_register("root")
    dpk = r1cs.new_registers(device_scheme.get_public_key_size(), "dpk")
    device_randomness = r1cs.new_register("device_randomness")
    auth = r1cs.new_registers(auth_size, "auth")
    issuer_sig = r1cs.new_registers(issuer_scheme.get_signature_size(), "issuer_sig")
    device_sig = r1cs.new_registers(device_scheme.get_signature_size(), "device_sig")
    simulation_sig = r1cs.new_registers(
        issuer_scheme.get_signature_size(),
        "simulation_sig",
    )

    # Build the auxiliary branch first. CAPSS' R1CS adapter memoizes powers on
    # Variable objects, so each later gadget receives fresh linear views.
    fresh = lambda value: value + Variable(r1cs, field(0))
    auxiliary_start = len(r1cs.equations)
    auxiliary_message = [
        Variable(r1cs, field(SIMULATION_DOMAIN_TAG)),
        *(fresh(value) for value in issuer_pk),
        fresh(verifier_nonce),
        *(fresh(value) for value in opened_indexes),
        *(fresh(leaf[0]) for leaf in opened_leaves),
        *(fresh(value) for value in dpk),
    ]
    auxiliary_ok = auxiliary_scheme.verify(
        [fresh(value) for value in simulation_pk],
        auxiliary_message,
        [fresh(value) for value in simulation_sig],
    )
    if auxiliary_ok is not True:
        raise ValueError("CAPSS auxiliary verification gadget did not return True.")
    _gate_assertion_equations(r1cs, auxiliary_start, branch)

    credential_start = len(r1cs.equations)
    credential_selector = Variable(r1cs, field(1)) - branch
    computed_root = tree_factory.get_root_from_authentication_path(
        [
            (opened_indexes[num], opened_leaves[num])
            for num in range(nb_opened)
        ],
        auth,
    )[0]
    r1cs.register_equation(
        Variable(r1cs, field(1)),
        computed_root,
        root,
        is_assertion=True,
    )

    issuer_ok = issuer_scheme.verify(
        [fresh(value) for value in issuer_pk],
        [fresh(root), fresh(dpk[0]), fresh(dpk[1])],
        [fresh(value) for value in issuer_sig],
    )
    if issuer_ok is not True:
        raise ValueError("CAPSS issuer verification gadget did not return True.")

    device_commitment = compression(
        [
            Variable(r1cs, field(PRESENTATION_DOMAIN_TAG)),
            verifier_nonce,
            device_randomness,
            Variable(r1cs, field(0)),
        ],
        output_size=1,
    )[0]
    device_ok = device_scheme.verify(
        [fresh(value) for value in dpk],
        [device_commitment],
        [fresh(value) for value in device_sig],
    )
    if device_ok is not True:
        raise ValueError("CAPSS device verification gadget did not return True.")
    _gate_assertion_equations(r1cs, credential_start, credential_selector)
    return r1cs


def _show_r1cs_cache_metadata(instance: ShowProofInstance, r1cs) -> dict[str, object]:
    return {
        "version": 6,
        "scheme_label": CAPSS_SCHEME_LABEL,
        "field_order": str(CAPSS_FIELD_ORDER),
        "merkle_hash": instance.credential_message.merkle_hash,
        "opened_count": len(instance.disclosure.indexes),
        "attribute_count": ATTRIBUTE_COUNT,
        "merkle_arity": list(MERKLE_ARITY),
        "presentation_domain_tag": PRESENTATION_DOMAIN_TAG,
        "simulation_domain_tag": SIMULATION_DOMAIN_TAG,
        "nb_variables": r1cs.get_nb_variables(),
        "nb_constraints": r1cs.get_nb_equations(),
        "nb_primary_inputs": r1cs.get_nb_primary_inputs(),
    }


def _show_r1cs_static_cache_is_valid(
    output_dir: Path,
    expected_metadata: dict[str, object],
) -> bool:
    metadata_path = output_dir / "r1cs-cache-metadata.json"
    field_path = output_dir / "r1cs-field.txt"
    constraints_path = output_dir / "r1cs-constraints.txt"
    if not metadata_path.exists() or not field_path.exists() or not constraints_path.exists():
        return False
    try:
        actual_metadata = json.loads(metadata_path.read_text(encoding="ascii"))
    except (OSError, json.JSONDecodeError):
        return False
    return actual_metadata == expected_metadata


def _random_field_int() -> int:
    return random_field_element_int(CAPSS_FIELD_ORDER)


def _expect_int_tuple(value: bytes | tuple[int, ...]) -> tuple[int, ...]:
    if isinstance(value, bytes):
        raise TypeError("Expected Griffin authentication path as field elements.")
    return value


def _gate_assertion_equations(r1cs, start: int, selector) -> None:
    """Gate assertions while leaving hint-defining computation equations active."""
    from r1cs.variable import Variable

    equations = list(r1cs.equations[start:])
    del r1cs.equations[start:]
    zero = Variable(r1cs, r1cs.field(0))
    for equation in equations:
        if not equation.is_assertion and _is_direct_hint_output(r1cs, equation.c):
            r1cs.equations.append(equation)
            continue
        product = r1cs.new_register(
            hint_inputs=[equation.a, equation.b],
            hint=lambda left, right: left * right,
        )
        r1cs.register_equation(equation.a, equation.b, product)
        r1cs.register_equation(selector, product - equation.c, zero)


def _is_direct_hint_output(r1cs, value) -> bool:
    terms = {key: factor for key, factor in value.terms.items() if key is not None}
    if value.terms.get(None) != r1cs.field(0) or len(terms) != 1:
        return False
    variable_id, factor = next(iter(terms.items()))
    if factor != r1cs.field(1):
        return False
    return r1cs.hint_register.get_num_hint(value.terms_obj[variable_id]) is not None


def _auxiliary_message_values(instance: ShowProofInstance) -> tuple[int, ...]:
    return (
        SIMULATION_DOMAIN_TAG,
        *instance.issuer_public_key,
        instance.verifier_nonce,
        *instance.disclosure.indexes,
        *(int.from_bytes(attribute, "big") for attribute in instance.disclosure.attributes),
        *(
            int.from_bytes(instance.credential_message.device_public_key[i : i + 32], "big")
            for i in range(0, len(instance.credential_message.device_public_key), 32)
        ),
    )


def _capss_scheme():
    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))
    from capss.sign.instances import get_scheme

    return get_scheme(CAPSS_SCHEME_LABEL)


@lru_cache(maxsize=1)
def _simulation_material():
    scheme = _capss_scheme()
    field = scheme.get_field()
    public_key, secret_key = scheme.keygen()
    # CAPSS' witness parser requires a structurally valid inactive signature.
    # This fixed dummy is prepared once with setup material, not per showing.
    dummy_message = [field(0)] * (1 + scheme.get_public_key_size() + 1 + 2 * SHOW_DISCLOSURE_COUNT + 2)
    dummy_signature = scheme.sign(secret_key, dummy_message)
    return (
        tuple(int(value) for value in public_key),
        tuple(secret_key),
        tuple(int(value) for value in dummy_signature),
    )
