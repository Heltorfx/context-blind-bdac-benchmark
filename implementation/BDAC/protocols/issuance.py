from __future__ import annotations

from dataclasses import dataclass

from BDAC.core.errors import ProtocolError
from BDAC.entities.issuer import Issuer
from BDAC.entities.user import User


FIELD_ELEMENT_SIZE = 32
INDEX_SIZE = 4


@dataclass(frozen=True)
class IssuanceTranscript:
    issuer_id: str
    credential_id: str
    credential_message: object
    credential_record: object
    credential_signature: object
    message_sizes: dict[str, int]
    credential_signature_ok: bool

    @property
    def ok(self) -> bool:
        return self.credential_signature_ok


class Issuance:
    def run(
        self,
        user: User,
        issuer: Issuer,
        credential_id: str | None = None,
    ) -> IssuanceTranscript:
        if not user.is_enrolled:
            raise ProtocolError("Issuance requires attributes obtained during enrollment.")

        selected_credential_id = credential_id or issuer.issuer_id
        issued = issuer.issue(user.attributes, user.device_public_key)
        credential_signature = user.receive_issued_credential(
            issuer,
            issued,
            credential_id=selected_credential_id,
        )
        credential_record = user.get_credential_record(selected_credential_id)
        credential_message = credential_record.message
        credential_signature_ok = issuer.verify_credential_signature(
            credential_message,
            credential_signature,
        )
        message_sizes = compute_issuance_message_sizes(
            credential_message,
            credential_signature,
            attribute_count=len(user.attributes),
            attribute_size=user.pp.attribute_size,
        )
        return IssuanceTranscript(
            issuer_id=issuer.issuer_id,
            credential_id=selected_credential_id,
            credential_message=credential_message,
            credential_record=credential_record,
            credential_signature=credential_signature,
            message_sizes=message_sizes,
            credential_signature_ok=credential_signature_ok,
        )


def compute_issuance_message_sizes(
    credential_message,
    credential_signature,
    *,
    attribute_count: int,
    attribute_size: int,
) -> dict[str, int]:
    signature = credential_signature.signature
    signature_size = len(signature) if isinstance(signature, bytes) else len(signature) * FIELD_ELEMENT_SIZE
    sizes = {
        "user_to_issuer": len(credential_message.device_public_key)
        + attribute_count * attribute_size,
        "issuer_to_user_credential": len(credential_message.root) + signature_size,
    }
    sizes["total"] = sum(sizes.values())
    return sizes
