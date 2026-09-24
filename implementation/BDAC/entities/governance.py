from __future__ import annotations

from BDAC.core.types import AttributeVector
from BDAC.crypto.encoding import normalize_attribute_vector
from BDAC.crypto.randomness import random_attribute_vector

from .base import Entity


class GovernanceAuthority(Entity):
    """Upstream source of user attributes.

    This entity is intentionally outside issuance: attributes must be obtained
    before the user asks the issuer for a credential.
    """

    def __init__(self, pp):
        super().__init__(pp)

    def issue_attributes(self) -> AttributeVector:
        attributes = normalize_attribute_vector(
            random_attribute_vector(
                self.pp.field_order,
                self.pp.attribute_count,
                self.pp.attribute_size,
            ),
            self.pp.field_order,
            self.pp.attribute_count,
            self.pp.attribute_size,
        )
        return AttributeVector(attributes)
