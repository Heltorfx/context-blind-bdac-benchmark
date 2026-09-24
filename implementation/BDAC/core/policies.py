from __future__ import annotations

from dataclasses import dataclass
from BDAC.core.types import CredentialRecord
from BDAC.crypto.encoding import canonical_index_set


@dataclass(frozen=True)
class IssuerPolicy:
    issuer_id: str
    credential_type: str = "default"


@dataclass(frozen=True)
class VerifierPolicy:
    verifier_id: str
    presentation_indexes: tuple[int, ...] | None = None
    accepted_issuers: tuple[str, ...] = ()

    def select_presentation_indexes(
        self,
        attribute_count: int,
        fallback_indexes: tuple[int, ...],
    ) -> tuple[int, ...]:
        if self.presentation_indexes is None:
            return canonical_index_set(fallback_indexes, attribute_count)
        return canonical_index_set(self.presentation_indexes, attribute_count)

    def accepts_credential(self, credential: CredentialRecord) -> bool:
        return not self.accepted_issuers or credential.issuer_id in self.accepted_issuers
