# BDAC package layout

This package is the structured implementation layer for the device-bound
anonymous credential prototype. CAPSS, Merkle trees, Show R1CS construction,
and Aurora execution now live behind BDAC modules.

The package now separates the protocol into three phases:

1. `Enrollment`: a governance authority gives attributes to the user.
2. `Issuance`: the issuer commits to the attributes and signs the commitment
   together with the SE public key.
3. `Presentation`: the user proves possession of a valid credential and active SE.

Attributes are intentionally generated before issuance. The issuance protocol
must not create attributes itself.

## Structure

- `core/`
  - domain types, protocol requests, credentials, and protocol errors.
- `entities/`
  - `GovernanceAuthority`, `User`, `Issuer`, `SE`, and `Verifier`.
- `crypto/`
  - canonical encodings, native randomness helpers, the Griffin/Jive context
    commitment, and the current backend adapter boundary.
- `proofs/`
  - Show-proof and Aurora backend wrappers.
- `protocols/`
  - enrollment, issuance, fused SE blind-signature, and presentation.
- `demos/`
  - clean package-level demos.
- `benchmarks/`
  - package-level benchmarks and protocol profiles.

## Initialization

- `initialization.py`
  - `Setup(lambda_security, l)` creates public parameters.
  - `KeyGen(pp)` creates a CAPSS key pair.
  - `IssuerKeyGen(pp)` and `SEKeyGen(pp)` are aliases for the same CAPSS key
    generation algorithm.

The current backend is statically parameterized for `lambda_security = 128` and
`l = 16`. The default CAPSS instance is `G256-5.fast.extended`: `fast` selects
the optimized trade-off, while `extended` keeps the signature format needed by
the R1CS verification gadget.

## Entities

- `entities/governance.py`: upstream source of attributes.
- `entities/user.py`: user state, attributes, issuer-provided Merkle state, and credentials.
- `entities/issuer.py`: direct commitment construction and credential signature.
- `entities/se.py`: secure environment/device signing interface.
- `entities/verifier.py`: verifier challenge for the Show protocol.
- `entities/base.py`: common entity and keyed-entity base classes.

## Protocols

- `protocols/enrollment.py`: pre-issuance attribute enrollment.
- `protocols/se_blind_signature.py`: Griffin/Jive commit-sign flow used by the
  presentation proof.
- `protocols/issuance.py`: issuance protocol.
- `protocols/verification.py`: Show/verification protocol. Aurora-ZK is the
  default backend. The non-ZK path is kept only for debugging.

## Encodings

Canonical encodings live in `crypto/encoding.py`. The current implementation
uses two views of the credential message:

- signature/circuit view: `root || dpk`, interpreted as the field tuple
  `(root, dpk_0, dpk_1)`. This is the value signed by CAPSS and checked by the
  Show circuit.
- transcript view: a versioned, length-delimited encoding with explicit domain
  labels. This is meant for logs, tests, and future wire formats, not for the
  current CAPSS verification gadget.

Attributes are fixed-width field elements. Disclosure indexes are canonicalized
as sorted sets without duplicates and checked against `[0,l-1]` before entering
the protocol backend.

## Main flows

Aurora can be selected with `--aurora-version normal` or `--aurora-version v2`
in the full-flow demo and paper benchmark. Both are ZK modes; `normal` remains
the default. See [Aurora v2](proofs/AURORA_V2.md) for the Python API, build,
format differences and security qualifications.

For the structured API, start with:

- `python -m BDAC.demos.issuance_demo`
- `python -m BDAC.demos.full_flow_demo`
- `python -m BDAC.demos.multi_issuer_demo`
- `python -m BDAC.benchmarks.profile_protocols`
- `python -m BDAC.benchmarks.profile_full`
- `python -m BDAC.benchmarks.profile_population --users 1 --issuers 2 --verifiers 2`

`BDAC.demos.full_flow_demo` runs enrollment, non-anonymous issuance, and
ZK presentation. Use `--skip-presentation` for issuance-only debugging and
`--no-zk` only to compare against the old non-ZK Aurora path. The local
Python/Sage R1CS satisfaction check is disabled by default; use
`--debug-r1cs-check` when debugging circuit construction.

## Backend Boundary

BDAC modules are now the implementation boundary:

- `crypto/capss.py`
- `crypto/merkle.py`
- `proofs/show_backend.py`
- `proofs/show_r1cs.py`
- `proofs/show_runner.py`

The code still uses the external CAPSS, SmallWood, and Aurora binaries/libraries
under the hood, but protocol code no longer depends on `dbac_demo` classes.

Randomness, attribute generation, disclosure-index sampling, challenges, and
encoding checks are native BDAC code. Earlier exploratory code has been moved to
`Implementation/legacy/dbac_demo` and should be treated as archived reference
material.

## Public API

The stable high-level entry point is `BDAC.scheme.BDACScheme`. For the current
concrete implementation, use:

- `BDAC.instantiations.capss_aurora.create_scheme()`
- `BDAC.instantiations.capss_aurora.CapssAuroraBDAC`

The public flow is:

1. `scheme.setup()`
2. `scheme.setup_entities(pp)`
3. `scheme.enroll(entities)`
4. `scheme.issue(entities)`
5. `scheme.present(entities)`

`scheme.run_full_flow()` is a convenience helper for demos and smoke tests.

## Multi-Issuer Wallets

Users now store credentials in a wallet:

- `user.credentials[credential_id]`
- `user.get_credential_record(credential_id)`
- `user.credential(credential_id)`

An issuer can be created with an `IssuerPolicy`:

- `issuer_id`
- `credential_type`

During direct issuance, the user supplies its complete attribute vector and
device public key. The issuer constructs the deterministic Merkle commitment,
signs `(root, dpk)`, and returns the credential together with the commitment
state needed for later selective openings.

A verifier can be created with a `VerifierPolicy`:

- `verifier_id`
- fixed `presentation_indexes`
- accepted issuer ids

This lets one user receive several credentials over the same committed
attribute set and SE public key, for example one credential from `university`
and one from `bank`. The verifier selects which issuer it accepts, and the user
selects the corresponding credential from the wallet.

## Population Benchmarks

`BDAC.benchmarks.profile_population` creates a configurable population and runs
the protocol matrix:

- one enrollment per user
- one issuance per `(user, issuer)`
- one presentation per `(user, issuer credential, verifier)`, unless limited by
  `--max-presentations`

Example:

`python -m BDAC.benchmarks.profile_population --users 2 --issuers 3 --verifiers 2 --max-presentations 4`

Aurora-ZK presentations cost several seconds each, so use `--max-presentations`
when exploring larger populations.

The Show R1CS template is static for a fixed CAPSS instance and disclosure
count. Benchmarks precompute it during setup by default, so presentation timings
focus on witness export and Aurora proving rather than circuit construction.
