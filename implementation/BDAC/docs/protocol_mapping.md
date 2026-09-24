# BDAC protocol mapping

This note maps the paper-level algorithms to the current code.

## Instantiation

The current concrete instantiation is:

- `BDAC.instantiations.capss_aurora.CapssAuroraBDAC`
- CAPSS signatures for issuer and SE/device signatures
- Griffin-based Merkle trees for attribute commitments
- Aurora-ZK for the Show proof

The stable public API is `BDAC.scheme.BDACScheme`.

## Policies and Wallets

`IssuerPolicy` controls issuance:

- issuer identifier
- credential type

`VerifierPolicy` controls presentation:

- verifier identifier
- disclosed presentation indexes
- accepted issuer identifiers

The user stores issued credentials as `CredentialRecord` objects in
`user.credentials`. This supports several issuers and several credentials for
the same user.

## Algorithms

- `Setup(lambda,l)`
  - Code: `BDAC.initialization.Setup`
  - Public API: `scheme.setup()`

- Entity initialization
  - Code: `scheme.setup_entities(pp)`
  - Entities: `GovernanceAuthority`, `Issuer`, `SE`, `User`, `Verifier`

- Enrollment
  - Code: `BDAC.protocols.enrollment.Enrollment`
  - Public API: `scheme.enroll(entities)`
  - Purpose: obtain attributes before issuance.

- Issue
  - Code: `BDAC.protocols.issuance.Issuance`
  - Public API: `scheme.issue(entities)`
  - Flow: the user supplies its complete attribute vector and `dpk`; the
    issuer constructs the Merkle commitment, signs `root || dpk`, and returns
    the credential with the commitment state used for later openings.

- Present / Show
  - Code: `BDAC.protocols.presentation.Presentation`
  - Public API: `scheme.present(entities)`
  - Flow: verifier sends `nonce_P, idx_P`; user obtains an SE signature on the
    challenge commitment, selects a credential accepted by the verifier, and
    proves in zero knowledge that the credential, attribute openings, and SE
    signature are consistent.

## Show witness and public inputs

The Show R1CS lives in `BDAC.proofs.show_r1cs`.

The hidden witness includes:

- `root`
- `dpk`
- presentation-commitment randomness
- Merkle authentication path
- issuer signature
- SE/device signature

The same private `dpk` register is reused for:

- issuer signature verification on `root || dpk`
- SE/device signature verification on the presentation challenge commitment

The public verifier-facing values are the verifier context, disclosed indexes,
disclosed attributes, and issuer public key. The Merkle root, `dpk`, credential,
context commitment, and device signature remain private.

## Benchmarks

Use:

- `python -m BDAC.benchmarks.profile_full`
- `python -m BDAC.benchmarks.profile_protocols`
- `python -m BDAC.benchmarks.profile_population`

`profile_full` is the preferred script for paper-facing performance numbers
because it reports setup, enrollment, issuance, presentation, Aurora internals,
message sizes, and end-to-end totals.

`profile_population` is the preferred script for scalability experiments. It
creates several users, issuers, and verifiers, then reports average/min/max
costs over all generated issuances and presentations.
