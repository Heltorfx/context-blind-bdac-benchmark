# Selecting Aurora normal or v2

Run from `Implementation`, in the Sage environment:

```sh
python -m BDAC.demos.full_flow_demo --aurora-version normal
python -m BDAC.demos.full_flow_demo --aurora-version v2
```

Both modes use Aurora ZK. `normal` is the default and retains the corrected
backend benchmarked on 2026-08-30. It does not mean the old non-ZK debug mode.
`v2` rejects `--no-zk`. No rebuild is necessary when switching modes after
building the two executables below.

The Python APIs support the same selection:

```python
from BDAC import SchemeConfig
from BDAC.instantiations.capss_aurora import create_scheme
from BDAC.protocols.presentation import Presentation
from BDAC.proofs.aurora_backend import AuroraBackend

scheme = create_scheme(SchemeConfig(aurora_version="v2"))
# Or select a backend for an individual protocol or proof:
presentation = Presentation(aurora_version="v2")
backend = AuroraBackend(version="v2")
```

Working directories are separated: `aurora_workspace/show_zk_d4` and
`aurora_workspace/show_zk_v2_d4` (similarly for other disclosure counts).
The binary proof headers are `LIBIOP_BCS_BIN_V1` and `LIBIOP_BCS_BIN_V2`.
The verifier requires the explicitly selected mode to match the header;
there is no automatic fallback or downgrade. Ordinary V1 proofs remain readable.

## What v2 changes

- The public instance includes the field modulus, R1CS dimensions, ordered
  constraints and coefficients, public inputs, a protocol-profile label, and
  effective domain, FRI, LDT and proof-of-work parameters. Coefficients are
  canonical field representatives, encoded little-endian at fixed field width.
  Counts and indexes are unsigned 64-bit little-endian integers. Variable-size
  byte strings have a length prefix.
- A dedicated 256-bit hash of that instance initializes the transcript. This
  avoids hashing the complete matrices at every query. The proof argument must
  therefore account for collisions in this instance digest; it is not the
  literal unhashed-instance syntax of the theoretical construction.
- The transcript stores framed round numbers, 32-byte fresh random round
  salts, roots and explicit prover messages. Random draws hash that complete
  prefix with purpose/round/draw counters. Fields use rejection sampling below
  the modulus; query positions use a uniform 64-bit value masked into a
  power-of-two domain. Distinct purpose labels separate fields, query positions,
  proof-of-work challenges, proof-of-work checks, leaves and internal nodes.
- Every BCS prover Merkle tree uses independent 32-byte salts per leaf.
  Leaves hash the canonical field-vector encoding and salt directly, without
  the old unsalted inner leaf hash. Internal nodes remain unsalted. The existing
  coset packing and grouped authentication paths are retained.
- The proof serializes one salt per round before the existing binary transcript
  payload. Leaf salts use the existing authentication-proof representation.
  Version mismatches, inconsistent round counts and trailing bytes are rejected.

The CAPSS signatures, attribute Merkle tree, presentation relation, R1CS,
FFT and arithmetic IOP are unchanged. Proof of work is retained in its own
hash domain and is not credited toward IOP soundness.

## Build and tests

From `Implementation/capss-aggregation` under WSL:

```sh
cmake -S . -B build-openmp
cmake --build build-openmp --target aurora_prove_r1cs_256_zk_save_bin aurora_verify_r1cs_256_zk_bin test_bcs_v2 test_blake2b_absorption test_bcs_query_binding -j 4
```

Run the C++ test executables from a directory containing `r1cs-field.txt`.
From `Implementation`:

```sh
python -m unittest BDAC.tests.test_aurora_verdict BDAC.tests.test_aurora_version
python -m BDAC.tests.check_aurora_versions --iterations 30
python -m BDAC.benchmarks.paper_preview --aurora-version v2 --aurora-iters 30 --issuance-iters 30 --micro-iters 30 --out BDAC/benchmarks/paper_v2.json
```

`check_aurora_versions` uses the already exported normal d4 instance, copies
its files to a temporary directory, checks an old normal proof, then produces
and verifies proofs in both modes. It tests cross-mode rejection and mutations
of round salts, proof payload, public challenge, and trailing data. Its timing
comparison fixes the witness and excludes Sage preparation/export; it is not
the complete protocol benchmark. The full demo tests fresh issuance and SE use.

The standalone executables accept `proof.bin normal` or `proof.bin v2`.
Omitting the mode selects `normal` for compatibility. The v2 binary path is
currently limited to the existing nominal-128-bit, prime-field-256 ZK profile.

## Local comparison (2026-08-31)

Thirty measured executions per mode after one excluded warmup, under WSL
with eight OpenMP threads, on the same d4 R1CS and witness:

| Mode | Prover process (s) | Verifier process (s) | Serialized proof (KB) |
| --- | ---: | ---: | ---: |
| normal | 3.149 | 1.447 | 310.623 |
| v2 | 3.312 | 1.541 | 327.145 |

KB means 1,000 bytes. These are means of process wall times, including local
file loading and proof serialization, but excluding Sage R1CS preparation and
export. This is a sequential local comparison, not a cross-device benchmark.
Raw samples are in `../benchmarks/aurora_v2_comparison30.json`.
All generated proofs verified; the existing normal proof and the cross-mode
and mutation rejection checks also passed. A separate full v2 demo completed
fresh enrollment, issuance and presentation successfully.

## Security status

The [first implementation audit](AURORA_V2_AUDIT.md) records a corrected
oracle-index/Merkle-position mismatch in the shared verifier, passing
normal/v2 regression tests, and the remaining proof obligations. The
`test_bcs_query_binding` executable tests this invariant for plain and grouped
leaves. This correction changes neither proof format nor honest prover output;
the 30-run timing table above predates the additional verifier checks.

V2 is an experimental implementation alignment, not a standalone new theorem
or a certification of the stronger extraction property. Chiesa--Fenzi
(https://eprint.iacr.org/2024/724.pdf, Sections 7 and 9) is the reference for
salted commitments and round randomness. The paper's Aurora-CF correspondence
lemma describes instance hashing, separated query purposes, explicit prover
messages, coset packing/grouped openings, and sampling in field-valued rounds.
Tests validate the implementation invariants used by that mapping; they do not
by themselves establish simulation-extractability.

Keep the security bound symbolic: this implementation does not select an
adversarial query budget or establish a tight end-to-end 128-bit guarantee.
The heuristic FRI/LDT parameter analysis is unchanged. The verifier loader
uses only the constraint system and public inputs; the auxiliary witness is
not available to the verifier. This remains a research prototype rather than
a hardened untrusted-proof parser.

V2 measurements are kept separate from normal measurements. Existing paper
tables and the version-guarded LaTeX exporter are not silently overwritten.
Without `--out`, `paper_preview` writes `paper_preview_results.json` for normal
and `paper_preview_v2_results.json` for v2 in `BDAC/benchmarks`.
