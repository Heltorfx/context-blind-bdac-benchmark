from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from BDAC.core.policies import IssuerPolicy, VerifierPolicy
from BDAC.entities.governance import GovernanceAuthority
from BDAC.entities.issuer import Issuer
from BDAC.entities.se import SE
from BDAC.entities.user import User
from BDAC.entities.verifier import Verifier
from BDAC.initialization import PublicParameters, Setup
from BDAC.parameters import ATTRIBUTE_COUNT, SECURITY_LEVEL
from BDAC.proofs.show_backend import precompute_show_r1cs_template
from BDAC.protocols.enrollment import Enrollment, EnrollmentTranscript
from BDAC.protocols.issuance import Issuance, IssuanceTranscript
from BDAC.protocols.presentation import Presentation, PresentationTranscript


@dataclass(frozen=True)
class SchemeConfig:
    lambda_security: int = SECURITY_LEVEL
    attribute_count: int = ATTRIBUTE_COUNT
    make_zk: bool = True
    debug_r1cs_check: bool = False
    precompute_r1cs_template: bool = True
    aurora_version: str = "normal"


@dataclass(frozen=True)
class SchemeEntities:
    governance: GovernanceAuthority
    issuer: Issuer
    se: SE
    user: User
    verifier: Verifier


@dataclass(frozen=True)
class FullFlowTranscript:
    public_parameters: PublicParameters
    entities: SchemeEntities
    enrollment: EnrollmentTranscript
    issuance: IssuanceTranscript
    presentation: PresentationTranscript | None
    precompute_seconds: float | None

    @property
    def ok(self) -> bool:
        return self.issuance.ok and (
            self.presentation is None or self.presentation.ok
        )


class BDACScheme:
    """Stable public API for the current BDAC anonymous credential scheme."""

    name = "BDAC-CAPSS-Aurora"

    def __init__(self, config: SchemeConfig | None = None):
        self.config = config or SchemeConfig()

    def setup(self) -> PublicParameters:
        return Setup(
            self.config.lambda_security,
            self.config.attribute_count,
        )

    def create_governance(self, pp: PublicParameters) -> GovernanceAuthority:
        return GovernanceAuthority(pp)

    def create_se(self, pp: PublicParameters) -> SE:
        return SE(pp)

    def create_user(self, pp: PublicParameters, se: SE | None = None) -> User:
        return User(pp, se or self.create_se(pp))

    def create_issuer(
        self,
        pp: PublicParameters,
        policy: IssuerPolicy | None = None,
    ) -> Issuer:
        return Issuer(pp, policy=policy)

    def create_verifier(
        self,
        pp: PublicParameters,
        policy: VerifierPolicy | None = None,
    ) -> Verifier:
        return Verifier(pp, policy=policy)

    def setup_entities(
        self,
        pp: PublicParameters | None = None,
        *,
        issuer_policy: IssuerPolicy | None = None,
        verifier_policy: VerifierPolicy | None = None,
    ) -> SchemeEntities:
        pp = pp or self.setup()
        se = self.create_se(pp)
        return SchemeEntities(
            governance=self.create_governance(pp),
            issuer=self.create_issuer(pp, issuer_policy),
            se=se,
            user=self.create_user(pp, se),
            verifier=self.create_verifier(pp, verifier_policy),
        )

    def enroll(self, entities: SchemeEntities) -> EnrollmentTranscript:
        return Enrollment().run(entities.user, entities.governance)

    def issue(
        self,
        entities: SchemeEntities,
        *,
        issuer: Issuer | None = None,
        user: User | None = None,
        credential_id: str | None = None,
    ) -> IssuanceTranscript:
        return Issuance().run(
            user or entities.user,
            issuer or entities.issuer,
            credential_id=credential_id,
        )

    def present(
        self,
        entities: SchemeEntities,
        *,
        user: User | None = None,
        verifier: Verifier | None = None,
        se: SE | None = None,
        credential_id: str | None = None,
    ) -> PresentationTranscript:
        return Presentation(
            make_zk=self.config.make_zk,
            debug_r1cs_check=self.config.debug_r1cs_check,
            aurora_version=self.config.aurora_version,
        ).run(
            user or entities.user,
            verifier or entities.verifier,
            se or entities.se,
            credential_id=credential_id,
        )

    def run_full_flow(
        self,
        *,
        include_presentation: bool = True,
    ) -> FullFlowTranscript:
        pp = self.setup()
        entities = self.setup_entities(pp)
        precompute_seconds = None
        if include_presentation and self.config.precompute_r1cs_template:
            start = perf_counter()
            precompute_show_r1cs_template()
            precompute_seconds = perf_counter() - start

        enrollment = self.enroll(entities)
        issuance = self.issue(entities)
        presentation = self.present(entities) if include_presentation else None
        return FullFlowTranscript(
            public_parameters=pp,
            entities=entities,
            enrollment=enrollment,
            issuance=issuance,
            presentation=presentation,
            precompute_seconds=precompute_seconds,
        )
