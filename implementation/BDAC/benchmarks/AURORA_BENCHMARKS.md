# Aurora benchmark revision (2026-08-30)

The corrected backend uses 92 FRI queries at nominal security parameter 128,
without subtracting the proof-of-work contribution from the query-soundness
target. The backend's reported 130.2-bit estimate uses heuristic FRI and LDT
soundness settings; it is not an end-to-end reduction-tight security bound.

## Important correction

The local Blake2b hash chain previously passed the digest length instead of
the concatenated input length to Blake2b. Thus it hashed the old state without
the newly absorbed message. This is corrected in `blake2b.tcc`. The regression
test was observed to fail before the change and pass afterward. The Python
wrapper now also checks process exit codes and the exact `[OK] VALID` verdict;
`INVALID` must never be accepted through a substring match.

The older files `paper_benchmark_results_aurora130_30.json` and
`paper_benchmark_results_20260827.json` are historical measurements, NOT the
results to use in the paper. Honest runs on that backend do not establish
soundness. Rebuild both prover and verifier; old proofs are incompatible.

## Run (WSL, Sage environment)

From `Implementation`, with `conda activate sage`:

```sh
cmake -S capss-aggregation -B capss-aggregation/build-openmp
cmake --build capss-aggregation/build-openmp --target test_blake2b_absorption aurora_prove_r1cs_256_zk_save_bin aurora_verify_r1cs_256_zk_bin -j8
python -m unittest BDAC.tests.test_aurora_verdict
OMP_NUM_THREADS=8 python -u -m BDAC.benchmarks.paper_preview --aurora-iters 30 --issuance-iters 30 --micro-iters 30 --out BDAC/benchmarks/paper_benchmark_corrected_20260830.json
OMP_NUM_THREADS=8 python -m BDAC.tests.check_aurora_artifact
OMP_NUM_THREADS=8 python -m BDAC.benchmarks.aurora_verifier_only --iterations 30 --out BDAC/benchmarks/aurora_verifier_public_only.json
python -m BDAC.benchmarks.profile_aurora_artifact --out BDAC/benchmarks/aurora_corrected_profile.json
python -m BDAC.benchmarks.export_paper_values BDAC/benchmarks/paper_benchmark_corrected_20260830.json ../A-Modular-Implementation-of-Post-Quantum-Context-Blind-Device-Bound-Anonymous-Credentials/Section2/benchmark-values.tex --expected-version normal
```

Run the C++ absorption test from `aurora_workspace/show_zk_d4`, which supplies
`r1cs-field.txt`:

```sh
../../capss-aggregation/build-openmp/capss/test_blake2b_absorption
```

Each disclosure configuration has one untimed warm-up and 30 measured proofs
with fresh challenges and SE signatures; attributes, issuer credential, and
index set are held fixed within a configuration. Configurations run serially,
not concurrently. Raw samples are retained. Sizes are decimal KB in the paper
and integer bytes in individual samples. Merkle proof sizes may vary.

Issuance uses fixed pre-enrolled attributes and keys, rebuilding the tree and
signing freshly at every iteration. Stage sums omit small orchestration costs.
Prover and verifier process times include file loading and serialization.
The separate profile logs report inclusive nested blocks: do not sum parent
and child block times as disjoint costs.

The verifier has a dedicated public-input loader and does not read
`r1cs-auxiliary-inputs.txt`. The artifact regression test copies no auxiliary
witness and checks that the original proof is accepted while modified public
inputs and proof bytes are rejected. The verifier-only benchmark records this
public deployment path separately from the historical full-protocol samples.

The command above reproduces the historical corrected-normal benchmark.  The
paper now measures the Aurora-CF backend instead:

```sh
OMP_NUM_THREADS=8 python -u -m BDAC.benchmarks.paper_preview --aurora-version v2 --aurora-iters 30 --issuance-iters 30 --micro-iters 30 --out BDAC/benchmarks/paper_preview_v2_results.json
python -m BDAC.benchmarks.export_paper_values BDAC/benchmarks/paper_preview_v2_results.json ../A-Modular-Implementation-of-Post-Quantum-Context-Blind-Device-Bound-Anonymous-Credentials/Section2/benchmark-values.tex --expected-version v2
```

The paper's BCS admissibility theorem and Aurora-CF correspondence lemma state
the compiler-level conditions. The tests validate the relevant serialization,
salting and query-binding invariants, but are not themselves a proof of
simulation extractability. See the Aurora appendix.
