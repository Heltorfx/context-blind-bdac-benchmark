from __future__ import annotations

from BDAC.core.policies import VerifierPolicy
from BDAC.core.types import CredentialRecord
from BDAC.crypto.randomness import random_field_element_int, sample_index_set

from .base import Entity


class Verifier(Entity):
    def __init__(self, pp, policy: VerifierPolicy | None = None):
        super().__init__(pp)
        self.policy = policy or VerifierPolicy(verifier_id="verifier")

    @property
    def verifier_id(self) -> str:
        return self.policy.verifier_id

    def challenge(self) -> tuple[int, tuple[int, ...]]:
        nonce = random_field_element_int(
            self.pp.field_order,
            self.pp.field_element_size,
        )
        fallback_indexes = sample_index_set(
            self.pp.attribute_count,
            self.pp.default_disclosure_count,
        )
        indexes = self.policy.select_presentation_indexes(
            self.pp.attribute_count,
            fallback_indexes,
        )
        return nonce, indexes

    def accepts_credential(self, credential: CredentialRecord) -> bool:
        return self.policy.accepts_credential(credential)
