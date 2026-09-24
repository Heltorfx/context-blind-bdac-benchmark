from __future__ import annotations

from BDAC import Enrollment, GovernanceAuthority, Issuance, Issuer, SE, Setup, User


def main() -> None:
    pp = Setup()
    governance = GovernanceAuthority(pp)
    issuer = Issuer(pp)
    se = SE(pp)
    user = User(pp, se)

    enrollment = Enrollment().run(user, governance)
    issuance = Issuance().run(user, issuer)

    print("=== BDAC issuance demo ===")
    print(f"enrollment.attribute_count: {enrollment.attribute_count}")
    print("issuance.flow: attributes and dpk -> issuer -> credential and commitment state")
    print(f"issuance.credential_signature_ok: {issuance.credential_signature_ok}")
    print(f"issuance.total_sent_bytes: {issuance.message_sizes['total']}")
    print(f"issuance.ok: {issuance.ok}")


if __name__ == "__main__":
    main()
