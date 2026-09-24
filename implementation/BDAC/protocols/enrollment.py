from __future__ import annotations

from dataclasses import dataclass

from BDAC.core.types import AttributeVector
from BDAC.entities.governance import GovernanceAuthority
from BDAC.entities.user import User


@dataclass(frozen=True)
class EnrollmentTranscript:
    attributes: AttributeVector
    attribute_count: int


class Enrollment:
    """Pre-issuance phase where the user obtains attributes."""

    def run(
        self,
        user: User,
        governance: GovernanceAuthority,
    ) -> EnrollmentTranscript:
        attributes = governance.issue_attributes()
        user.receive_attributes(attributes.values)
        return EnrollmentTranscript(
            attributes=attributes,
            attribute_count=len(attributes),
        )
