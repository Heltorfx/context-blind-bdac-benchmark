from __future__ import annotations

import argparse

from BDAC.core.policies import IssuerPolicy, VerifierPolicy
from BDAC.instantiations.capss_aurora import create_scheme
from BDAC.protocols.enrollment import Enrollment
from BDAC.protocols.issuance import Issuance
from BDAC.protocols.presentation import Presentation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--present",
        action="store_true",
        help="Also run one presentation proof for the bank credential.",
    )
    parser.add_argument(
        "--no-zk",
        action="store_true",
        help="Use the non-ZK Aurora debug backend when --present is enabled.",
    )
    args = parser.parse_args()

    scheme = create_scheme()
    pp = scheme.setup()
    governance = scheme.create_governance(pp)
    se = scheme.create_se(pp)
    user = scheme.create_user(pp, se)

    university = scheme.create_issuer(
        pp,
        IssuerPolicy(
            issuer_id="university",
            credential_type="student",
        ),
    )
    bank = scheme.create_issuer(
        pp,
        IssuerPolicy(
            issuer_id="bank",
            credential_type="account",
        ),
    )
    verifier = scheme.create_verifier(
        pp,
        VerifierPolicy(
            verifier_id="bank-verifier",
            presentation_indexes=(4, 5, 6, 7),
            accepted_issuers=("bank",),
        ),
    )

    enrollment = Enrollment().run(user, governance)
    university_issuance = Issuance().run(user, university)
    bank_issuance = Issuance().run(user, bank)

    print("=== BDAC multi-issuer demo ===")
    print(f"attribute_count: {enrollment.attribute_count}")
    print()
    print("[issuers]")
    print(
        "    university:",
        f"ok={university_issuance.ok}",
    )
    print(
        "    bank:",
        f"ok={bank_issuance.ok}",
    )
    print()
    print("[user wallet]")
    for credential_id, credential in user.credentials.items():
        print(
            f"    {credential_id}:",
            f"issuer={credential.issuer_id}",
            f"type={credential.credential_type}",
        )

    if args.present:
        print()
        print("[presentation]")
        presentation = Presentation(make_zk=not args.no_zk).run(
            user,
            verifier,
            se,
            credential_id="bank",
        )
        print(f"    verifier: {verifier.verifier_id}")
        print(f"    credential_id: {presentation.credential_id}")
        print(f"    issuer_id: {presentation.issuer_id}")
        print(f"    idx_P: {list(presentation.requested_indexes)}")
        print(f"    aurora_result: {presentation.aurora_result['verifier_result']}")
        print(f"    presentation_ok: {presentation.ok}")


if __name__ == "__main__":
    main()
