from __future__ import annotations

from dataclasses import dataclass

from BDAC.core.types import DeviceSignature
from BDAC.crypto.commitments import (
    PresentationContextOpening,
    commit_presentation_context,
)
from BDAC.crypto.randomness import random_field_element_int
from BDAC.parameters import CAPSS_FIELD_ORDER


@dataclass(frozen=True)
class SEBlindSignatureTranscript:
    context: int
    commitment: int
    randomness: int
    signature: DeviceSignature


class SEBlindSignature:
    """Fused commit-sign step used by the presentation proof."""

    def commit(
        self,
        context: int,
        randomness: int | None = None,
    ) -> PresentationContextOpening:
        randomness = (
            random_field_element_int(CAPSS_FIELD_ORDER)
            if randomness is None
            else randomness
        )
        return PresentationContextOpening(
            context=context,
            randomness=randomness,
            commitment=commit_presentation_context(context, randomness),
        )

    def sign(self, se, commitment: int) -> DeviceSignature:
        return se.sign_field_elements((commitment,))

    def run(
        self,
        se,
        context: int,
        randomness: int | None = None,
    ) -> SEBlindSignatureTranscript:
        opening = self.commit(context, randomness)
        signature = self.sign(se, opening.commitment)
        return SEBlindSignatureTranscript(
            context=context,
            commitment=opening.commitment,
            randomness=opening.randomness,
            signature=signature,
        )
