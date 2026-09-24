from __future__ import annotations

from BDAC.core.policies import IssuerPolicy
from BDAC.core.types import (
    CredentialMessage,
    CredentialSignature,
    IssuedCredential,
)
from BDAC.crypto.capss import CapssIssuerSignatureBackend
from BDAC.crypto.encoding import credential_message_views, normalize_attribute_vector
from BDAC.crypto.merkle import MerkleSuite
from BDAC.initialization import KeyPair

from .base import KeyedEntity


class Issuer(KeyedEntity):
    def __init__(self, pp, policy: IssuerPolicy | None = None):
        super().__init__(pp)
        self.policy = policy or IssuerPolicy(issuer_id="issuer")
        self.signature_backend = CapssIssuerSignatureBackend(pp.capss_scheme_label)
        self.merkle_hash = pp.merkle_hash

    @property
    def issuer_id(self) -> str:
        return self.policy.issuer_id

    @property
    def credential_type(self) -> str:
        return self.policy.credential_type

    @property
    def public_key(self):
        return tuple(int(x) for x in self.signature_backend.public_key)

    def keygen(self) -> KeyPair:
        self.key_pair = KeyPair(
            scheme_label=self.pp.capss_scheme_label,
            public_key=tuple(int(x) for x in self.signature_backend.public_key),
            secret_key=tuple(int(x) for x in self.signature_backend.secret_key),
        )
        return self.key_pair

    def build_credential_message(self, attributes, device_public_key: bytes):
        attributes = normalize_attribute_vector(
            attributes,
            self.pp.field_order,
            self.pp.attribute_count,
            self.pp.attribute_size,
        )
        suite = MerkleSuite(
            self.merkle_hash,
            attribute_count=self.pp.attribute_count,
            arity=self.pp.merkle_arity,
            field_order=self.pp.field_order,
            griffin_alpha=self.pp.griffin_alpha,
            security_level=self.pp.security_parameter,
        )
        commitment_state = suite.build_tree(attributes)
        message = CredentialMessage(
            root=suite.get_root_bytes(commitment_state),
            device_public_key=device_public_key,
            merkle_hash=self.merkle_hash,
        )
        credential_message_views(
            message.root,
            message.device_public_key,
            message.merkle_hash,
            self.pp.field_order,
            element_size=self.pp.field_element_size,
        )
        return message, commitment_state

    def issue(self, attributes, device_public_key: bytes) -> IssuedCredential:
        message, commitment_state = self.build_credential_message(
            attributes,
            device_public_key,
        )
        return IssuedCredential(
            message=message,
            signature=self.sign_credential_message(message),
            commitment_state=commitment_state,
        )

    def sign_credential_message(self, message: CredentialMessage) -> CredentialSignature:
        return self.signature_backend.sign(message)

    def verify_credential_signature(
        self,
        message: CredentialMessage,
        signature: CredentialSignature,
    ) -> bool:
        return self.signature_backend.verify(message, signature)
