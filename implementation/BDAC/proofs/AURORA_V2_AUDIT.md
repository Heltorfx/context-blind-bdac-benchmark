# Aurora v2: first implementation and proof-correspondence audit

Date: 2026-08-31. Scope: the local normal/v2 ZK backends, not the LaTeX paper.
This is an internal audit, not a simulation-extractability theorem or a complete
security review. No adversarial random-oracle query budget is fixed here.

## Outcome

1. A concrete mismatch between authenticated Merkle positions and logical IOP
   query positions was reproduced and fixed in the shared verifier.
2. Honest proofs still verify in both modes, including an existing normal proof.
3. V2 implements the transcript, commitment and query-handling ingredients
   used by the paper's Aurora-CF correspondence lemma. The simulator and
   extractor remain theoretical objects and are not production code.
4. The current FRI/LDT profile uses heuristic error estimates. Its printed
   security level must not be substituted for a proved knowledge-error bound.

## References and what they provide

- [Chiesa--Fenzi, 2024/724](https://eprint.iacr.org/2024/724.pdf), Sections 7 and 9:
  salted Merkle commitments and a BCS analysis with simulation and extraction.
  Construction 9.10 and Lemma 9.9 concern simulation; Construction 9.13 and
  Lemma 9.12 concern extraction. Remark 7.13 matters for the extraction trace:
  completing a simulated commitment must query the programmed points again.
  Their two-stage simulation interface is not automatically identical to our
  witnessless oracle. A correspondence argument must handle that difference.
- [BCS, 2016/116](https://eprint.iacr.org/2016/116.pdf), Remark 5.2 and Lemma 5.3:
  the state-restoration reduction has a combinatorial loss, with a
  proof-of-knowledge extension. Applying it requires matching the rounds and
  moves of the actual IOP to those in the experiment.
- [Aurora, full version](https://eprint.iacr.org/2018/828.pdf), Sections 7--9:
  zero knowledge of the encoded protocol and knowledge extraction through
  decoding the oracle strings. Section 10.2 discusses column hashing and
  pruned paths. The [conference version](https://www.iacr.org/archive/eurocrypt2019/114760150/114760150.pdf),
  Section 3, also discusses multiplicative cosets. Using a prime field is not
  itself evidence that Aurora is unsupported; the precise variant and bounds
  still need to be matched.

## Confirmed verifier defect and correction

The transcript separately stores `query_positions_` and `MT_leaf_positions_`.
Previously, Merkle verification authenticated the latter, while the IOP consumed
the former. The verifier did not establish their correspondence.

A small BCS test produced an honest opening of leaf 0, retained its root,
authentication path and value, and shifted the claimed logical positions by 1.
Before the correction, the verifier accepted and returned the authenticated
value of position 0 as the value at position 1. This was reproduced in v2 for
plain leaves and two-element cosets.

This demonstrates a broken authentication invariant at the BCS interface. It
does **not** demonstrate an end-to-end forged credential or presentation.

The correction in `libiop/libiop/bcs/bcs_verifier.tcc` now checks:

- response counts and the number of oracle values in each response;
- sorted, unique, in-domain logical query positions;
- complete cosets under the registered packing map;
- exact equality between the resulting leaf positions and the authenticated
  leaf-position list.

The grouped-response helper now also uses the processed tree index rather
than the round index, which matters if a round has multiple trees. Empty
query lists no longer enter the nonempty coset serializer.

Both modes use these checks. The prover, proof format and hash encodings were
not changed by this correction. A dedicated multi-domain regression now covers
two trees in one round. Preprocessing/holographic BCS remains outside this
suite and is not used by the Aurora backend measured here.

## Implementation-to-proof checklist

Paths below are relative to `Implementation/capss-aggregation`.

| Item | Local evidence | Status / remaining obligation |
| --- | --- | --- |
| Instance binding | `capss/snarks/aurora_v2.hpp` includes matrices, public inputs, field and effective parameters in a dedicated instance digest. | Account for digest collisions when transferring statement freshness. The encoding review is scoped to the current fixed-field profile, not arbitrary cross-field reuse. |
| Round randomness | `libiop/libiop/bcs/hashing/bcs_v2.hpp` frames full prefixes, roots, messages, fresh salts and counters. | Match each draw to the public-coin experiment; the implementation is not literally the paper's bit-string syntax. |
| Challenge distribution | Fields use rejection sampling; query positions use masking for power-of-two domains. | Include retry queries in the trace/budget and handle the variable running time of sampling. Do not count a field draw as exactly one raw RO query. |
| Merkle leaf hiding | V2 hashes canonical leaf vectors directly with independent salts. | Specify the simulator and extracted oracle strings for the packed alphabet. Salted hashing alone is not the complete extraction argument. |
| Authentication | The new shared checks tie IOP positions to complete authenticated cosets. | Regression verified for coset sizes 1, 2 and 4 in each mode and for two domains in one round. |
| Prover messages | Explicit field messages are absorbed into the transcript. | Include them in the abstract IOP/transcript correspondence, not only the Merkle roots. |
| Final queries and PoW | Query and PoW draws have separate purposes. | Map the final query stage to the theorem's round convention. PoW is not credited toward soundness. |
| Oracle decoding | Aurora's arithmetic IOP is unchanged by v2. | Specify how its knowledge extractor consumes the oracle strings recovered from the BCS trace. |
| Simulation and trace | No production simulator or ROM trace recorder is implemented. | Give the theoretical simulator and the reduction-visible trace argument. These need not run during an ordinary presentation. |
| Error parameters | Prover selects optimistic LDT and heuristic FRI analysis. | Keep the knowledge error symbolic; the logged estimate is not a proved SE bound. |

### Zero-knowledge query budget

For the inspected d4 profile, the first FRI localization parameter is 1 and
there are 92 query repetitions. `FRI_protocol_parameters::queries_to_input_oracles`
returns `92 * 2^1 = 184`; Aurora sets its masking query bound to 185 after its
parameter iteration. This is the code's intended accounting, not a completed
zero-knowledge proof for the full serialized transcript.

The next check must track distinct revealed evaluations of each masked oracle,
including complete packed cosets and derived queries. It must not confuse the
number of leaf positions with the number of scalar evaluations, or count every
oracle column as an extra position of one polynomial. Any future repetition
change must recompute this bound and the resulting degree/domain parameters.

### Heuristic profile versus a proved bound

`capss/snarks/aurora_prove_r1cs_save_bin.tcc` uses
`RS_extra_dimensions = 1` in ZK mode, `optimistic_heuristic` for the LDT reducer,
and `heuristic` for FRI. The verifier uses the corresponding profile.

Switching the FRI enum alone is not a valid fix: the current implementation's
proved branch uses the term

```
(1 - 3 * rate - localization_coset_size / sqrt(codeword_domain_size)) / 4
```

which is negative when the configured rate is 1/2. A useful bound from that
branch requires a different rate and a complete parameter recomputation, or
a different applicable theorem. This does not show an attack against the
current heuristic profile. It shows why more repetitions alone do not settle
the theorem-to-implementation question.

No parameter profile was changed during this audit. In particular, the
previous 30-run normal/v2 comparison is not a benchmark of a newly proved
parameter set.

## Verification performed after the correction

- Built `test_bcs_query_binding` and both ZK prover/verifier executables.
- The query-binding regression accepts honest openings and rejects relabelling
  in both modes for coset sizes 1, 2 and 4. It also accepts a round containing
  two distinct evaluation domains after correcting the prover's tree index.
- The v2 transcript test includes a fixed independently computed Blake2b test
  vector in addition to its framing, domain-separation and Merkle checks.
- `BDAC.tests.check_aurora_versions --iterations 1` passed: existing normal
  proof, fresh proofs in both modes, cross-mode rejection, and mutations of
  a round salt, proof payload, public challenge and trailing data.
- Each mode had one excluded warmup and one measured smoke-test execution.
  These measurements are not statistically meaningful benchmark updates.
- The six Python tests in `BDAC.tests.test_aurora_verdict` and
  `BDAC.tests.test_aurora_version` passed.

Results: `../benchmarks/aurora_v2_audit_smoke.json`, with separate prover and
verifier logs. The checks concern a fixed exported presentation R1CS and do
not rerun fresh issuance.

The legacy proof loader and Merkle path parser are still research-prototype
code. This audit does not certify robustness against arbitrary malformed
lengths, truncated authentication paths or resource-exhaustion inputs.

## Remaining scope

The paper now states the exact compiler correspondence, the witnessless BCS
simulation/extraction argument, and the connection to Aurora's decoding
extractor. The masking budget is checked for the measured four-disclosure
profile and the state-restoration loss remains symbolic, as requested.

What remains deliberately outside the claim is a reduction-tight concrete
security calibration for a fixed random-oracle query budget. The measured
profile still relies on the backend's heuristic FRI/LDT estimators. A future
deployment audit should also harden parsing and exercise preprocessing BCS if
that unused mode is ever enabled.
