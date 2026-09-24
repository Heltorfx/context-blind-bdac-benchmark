from __future__ import annotations

from .verification import Verification, VerificationTranscript


class Presentation(Verification):
    """Credential presentation protocol.

    `Verification` is kept as a compatibility name, but `Presentation` is the
    protocol-level name matching the anonymous credential flow.
    """


PresentationTranscript = VerificationTranscript
