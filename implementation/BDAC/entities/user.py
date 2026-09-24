from __future__ import annotations

from BDAC.core.errors import ProtocolError
from BDAC.core.types import (
    AttributeVector,
    Credential,
    CredentialMessage,
    CredentialRecord,
    CredentialSignature,
    IssuedCredential,
    SelectiveDisclosure,
)
from BDAC.crypto.encoding import (
    canonical_index_set,
    normalize_attribute_vector,
)
from BDAC.crypto.merkle import MerkleSuite

from .base import Entity
from .se import SE


class User(Entity):
    def __init__(self, pp, se: SE):
        super().__init__(pp)
        self.se = se
        self.device_public_key = se.public_key_bytes
        self.merkle_hash = pp.merkle_hash
        self.attributes: tuple[bytes, ...] | None = None
        self.credential_message: CredentialMessage | None = None
        self.credential_signature: CredentialSignature | None = None
        self.credentials: dict[str, CredentialRecord] = {}
        self.default_credential_id: str | None = None
        self._merkle_suite = MerkleSuite(
            pp.merkle_hash,
            attribute_count=pp.attribute_count,
            arity=pp.merkle_arity,
            field_order=pp.field_order,
            griffin_alpha=pp.griffin_alpha,
            security_level=pp.security_parameter,
        )
        self._tree = None

    @property
    def is_enrolled(self) -> bool:
        return self.attributes is not None

    def receive_attributes(self, attributes) -> None:
        if isinstance(attributes, AttributeVector):
            attributes = attributes.values
        self.attributes = normalize_attribute_vector(
            attributes,
            self.pp.field_order,
            self.pp.attribute_count,
            self.pp.attribute_size,
        )
        self._tree = None

    def require_enrolled(self) -> None:
        if not self.is_enrolled:
            raise ProtocolError("User must complete enrollment before issuance.")

    def build_merkle_tree(self):
        self.require_enrolled()
        self._tree = self._merkle_suite.build_tree(self.attributes)
        return self._tree

    def get_merkle_root(self) -> bytes:
        if self._tree is None:
            self.build_merkle_tree()
        return self._merkle_suite.get_root_bytes(self._tree)

    def disclose_attributes(self, indexes) -> SelectiveDisclosure:
        self.require_enrolled()
        indexes = canonical_index_set(indexes, self.pp.attribute_count)
        if self._tree is None:
            self.build_merkle_tree()
        attributes = tuple(self.attributes[index] for index in indexes)
        authentication_path = self._merkle_suite.get_authentication_path(self._tree, indexes)
        return SelectiveDisclosure(
            indexes=indexes,
            attributes=attributes,
            authentication_path=authentication_path,
            merkle_hash=self.merkle_hash,
        )

    def receive_issued_credential(
        self,
        issuer,
        issued: IssuedCredential,
        credential_id: str | None = None,
    ) -> CredentialSignature:
        self.require_enrolled()
        self._tree = issued.commitment_state
        expected_root = self._merkle_suite.get_root_bytes(self._tree)
        if issued.message.root != expected_root:
            raise ProtocolError("Issuer returned an inconsistent commitment state.")
        if issued.message.device_public_key != self.device_public_key:
            raise ProtocolError("Issuer returned a credential for another device key.")
        record = CredentialRecord(
            credential_id=credential_id or issuer.issuer_id,
            issuer_id=issuer.issuer_id,
            issuer_public_key=issuer.public_key,
            credential_type=issuer.credential_type,
            message=issued.message,
            signature=issued.signature,
        )
        self.store_credential(record)
        return issued.signature

    def store_credential(self, record: CredentialRecord) -> None:
        self.credentials[record.credential_id] = record
        self.default_credential_id = record.credential_id
        self.credential_message = record.message
        self.credential_signature = record.signature

    def get_credential_record(self, credential_id: str | None = None) -> CredentialRecord:
        selected_id = credential_id or self.default_credential_id
        if selected_id is None or selected_id not in self.credentials:
            raise ProtocolError("User has no matching issued credential.")
        return self.credentials[selected_id]

    def credential(self, credential_id: str | None = None) -> Credential:
        record = self.get_credential_record(credential_id)
        return Credential(
            message=record.message,
            signature=record.signature,
        )
