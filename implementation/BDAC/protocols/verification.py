from __future__ import annotations

from dataclasses import dataclass
from BDAC.core.errors import ProtocolError
from BDAC.core.types import PresentationRequest
from BDAC.entities.se import SE
from BDAC.entities.user import User
from BDAC.entities.verifier import Verifier
from BDAC.proofs.aurora_backend import AuroraBackend
from BDAC.proofs.show_backend import (
    build_show_proof_instance,
    compute_show_message_sizes,
    prove_show_r1cs,
)


@dataclass(frozen=True)
class VerificationTranscript:
    credential_id: str
    issuer_id: str
    request: PresentationRequest
    verifier_nonce: int
    requested_indexes: tuple[int, ...]
    disclosure: object
    proof_instance: object
    r1cs_result: object | None
    aurora_result: dict[str, object]
    message_sizes: dict[str, int]
    r1cs_seconds: float | None
    ok: bool


class Verification:
    def __init__(
        self,
        make_zk: bool = True,
        proof_backend: AuroraBackend | None = None,
        debug_r1cs_check: bool = False,
        aurora_version: str = "normal",
    ):
        self.make_zk = make_zk
        self.proof_backend = proof_backend or AuroraBackend(make_zk=make_zk, version=aurora_version)
        self.debug_r1cs_check = debug_r1cs_check

    def run(
        self,
        user: User,
        verifier: Verifier,
        se: SE,
        credential_signature=None,
        credential_id: str | None = None,
    ) -> VerificationTranscript:
        credential_record = user.get_credential_record(credential_id)
        if not verifier.accepts_credential(credential_record):
            raise ProtocolError(
                f"Verifier {verifier.verifier_id} does not accept issuer "
                f"{credential_record.issuer_id}."
            )
        credential_signature = credential_signature or credential_record.signature
        nonce, indexes = verifier.challenge()
        request = PresentationRequest(nonce=nonce, disclosed_indexes=indexes)
        disclosure = user.disclose_attributes(indexes)
        instance = build_show_proof_instance(
            credential_message=credential_record.message,
            disclosure=disclosure,
            verifier_nonce=nonce,
            credential_signature=credential_signature,
            device=se.backend,
        )
        r1cs_result = None
        r1cs_seconds = None
        if self.debug_r1cs_check:
            r1cs_start = perf_counter()
            r1cs_result = prove_show_r1cs(instance)
            r1cs_seconds = perf_counter() - r1cs_start
        aurora_result = self.proof_backend.prove_show(instance)
        raw_result = dict(aurora_result.raw)
        message_sizes = compute_show_message_sizes(instance, disclosure, raw_result)
        ok = aurora_result.ok and (r1cs_result is None or r1cs_result.proof_ok)
        return VerificationTranscript(
            credential_id=credential_record.credential_id,
            issuer_id=credential_record.issuer_id,
            request=request,
            verifier_nonce=nonce,
            requested_indexes=indexes,
            disclosure=disclosure,
            proof_instance=instance,
            r1cs_result=r1cs_result,
            aurora_result=raw_result,
            message_sizes=message_sizes,
            r1cs_seconds=r1cs_seconds,
            ok=ok,
        )
