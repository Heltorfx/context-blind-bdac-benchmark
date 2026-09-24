from __future__ import annotations

from dataclasses import replace

from BDAC.entities.governance import GovernanceAuthority
from BDAC.entities.issuer import Issuer
from BDAC.entities.se import SE
from BDAC.entities.user import User
from BDAC.entities.verifier import Verifier
from BDAC.initialization import Setup
from BDAC.proofs.show_backend import build_show_proof_instance, prove_show_r1cs
from BDAC.proofs.show_r1cs import use_auxiliary_branch
from BDAC.protocols.enrollment import Enrollment
from BDAC.protocols.issuance import Issuance


def test_show_r1cs_reuses_the_issued_device_public_key() -> None:
    pp = Setup()
    se_1 = SE(pp)
    se_2 = SE(pp)
    user = User(pp, se_1)
    issuer = Issuer(pp)

    Enrollment().run(user, GovernanceAuthority(pp))
    issuance = Issuance().run(user, issuer)

    verifier_nonce, indexes = Verifier(pp).challenge()
    disclosure = user.disclose_attributes(indexes)

    coherent_instance = build_show_proof_instance(
        credential_message=user.credential_message,
        disclosure=disclosure,
        verifier_nonce=verifier_nonce,
        credential_signature=issuance.credential_signature,
        device=se_1.backend,
    )
    swapped_device_instance = build_show_proof_instance(
        credential_message=user.credential_message,
        disclosure=disclosure,
        verifier_nonce=verifier_nonce,
        credential_signature=issuance.credential_signature,
        device=se_2.backend,
    )

    coherent_result = prove_show_r1cs(coherent_instance)
    swapped_device_result = prove_show_r1cs(swapped_device_instance)

    assert coherent_result.proof_ok
    assert not swapped_device_result.proof_ok


def _flip_first(values: tuple[int, ...], modulus: int) -> tuple[int, ...]:
    return ((values[0] + 1) % modulus, *values[1:])


def test_show_r1cs_or_relation() -> None:
    pp = Setup()
    se = SE(pp)
    user = User(pp, se)
    issuer = Issuer(pp)

    Enrollment().run(user, GovernanceAuthority(pp))
    issuance = Issuance().run(user, issuer)
    verifier_nonce, indexes = Verifier(pp).challenge()
    disclosure = user.disclose_attributes(indexes)
    honest = build_show_proof_instance(
        credential_message=user.credential_message,
        disclosure=disclosure,
        verifier_nonce=verifier_nonce,
        credential_signature=issuance.credential_signature,
        device=se.backend,
    )

    assert prove_show_r1cs(honest).proof_ok

    auxiliary = use_auxiliary_branch(honest)
    broken_credential = replace(
        auxiliary,
        issuer_signature=_flip_first(auxiliary.issuer_signature, pp.field_order),
    )
    assert prove_show_r1cs(broken_credential).proof_ok

    neither_branch = replace(
        broken_credential,
        simulation_signature=_flip_first(
            broken_credential.simulation_signature,
            pp.field_order,
        ),
    )
    assert not prove_show_r1cs(neither_branch).proof_ok

    changed_statement = replace(auxiliary, verifier_nonce=(auxiliary.verifier_nonce + 1) % pp.field_order)
    assert not prove_show_r1cs(changed_statement).proof_ok

    changed_dpk_bytes = bytearray(auxiliary.credential_message.device_public_key)
    changed_dpk_bytes[-1] ^= 1
    changed_dpk = replace(
        auxiliary,
        credential_message=replace(
            auxiliary.credential_message,
            device_public_key=bytes(changed_dpk_bytes),
        ),
    )
    assert not prove_show_r1cs(changed_dpk).proof_ok

    changed_aux_signature = replace(
        auxiliary,
        simulation_signature=_flip_first(auxiliary.simulation_signature, pp.field_order),
    )
    assert not prove_show_r1cs(changed_aux_signature).proof_ok


def main() -> None:
    test_show_r1cs_reuses_the_issued_device_public_key()
    test_show_r1cs_or_relation()
    print("BDAC device-binding R1CS check: ok")


if __name__ == "__main__":
    main()
