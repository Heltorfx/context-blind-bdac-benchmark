# CAPSS upstream comparison (2026-09-12)

This note records exploratory measurements made before updating the paper
benchmarks. Sizes use decimal KB (1000 bytes).

## Machine

- CPU: Intel Core Ultra 7 165U
- WSL-visible topology: 7 cores, 14 logical processors
- OS environment: WSL2
- Local compiler: GCC 13.3, with `-O3 -flto=auto -march=native`

## Artifacts inspected

- Optimized C CAPSS: `CryptoExperts/smallwood`, commit `6d0a801`
- Python SmallWood and R1CS exporter: `CryptoExperts/smallwood-python`,
  commit `28c269c`
- Aurora wrapper: `CryptoExperts/capss-aggregation`, commit `d238d58`

The public repositories do not contain a 2026 commit. The September 2026
paper revision adds analysis and anonymous-credential measurements, but its
public Python and Aurora artifacts are still the 2025 versions above.

## Signature microbenchmarks

Each primary result is an average over 30 successful sign/verify executions.
Our Python/Rust benchmark excludes one warm-up execution. The upstream C
benchmark was run once before the measured 30-execution process to warm the
build and runtime environment.

| Implementation | Field / permutation | Threads | Signature | KeyGen | Sign | Verify |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| BDAC current | BN254 / Griffin-5 fast extended | 14 | 16.160 KB | not remeasured | 479 ms | 166 ms |
| BDAC fixed-width | BN254 / Griffin-5 fast extended | 14 | 16.160 KB | not remeasured | 240 ms | 93 ms |
| Upstream Python | BN254 / Griffin-5 fast extended | 1 | 16.160 KB | not remeasured | 7.692 s | 536 ms |
| Upstream C | BN254 / Anemoi-5 fast | 1 | 12.539 KB | 0.249 ms | 863 ms | 52.0 ms |
| Upstream C | Goldilocks / Anemoi-7 fast | 1 | 10.720 KB | 0.009 ms | 42.8 ms | 2.36 ms |

The two Griffin rows use the same parameters and produce the same 505 field
elements. Relative to the official Python implementation, the fixed-width
backend is about 32 times faster for signing and 5.8 times faster for
verification. The upstream C rows are implementation alternatives rather than
language-only comparisons because their permutation and CAPSS instance differ.
The Goldilocks row cannot directly replace the current BN254 signature inside
the Aurora presentation relation without a cross-field arithmetization or a
change of proof field.

The original `BDAC current` row records the pre-change `BigUint` backend. The
new backend keeps Python/Sage orchestration but performs Griffin arithmetic in
the fixed-width Montgomery representation from `ark_bn254::Fr`. Across 30
executions this halves signing time and reduces verification time by roughly
44 percent, without changing parameters, signatures, or protocol messages.

## Scaling of the current Griffin backend

The 1-thread and 14-thread rows use 30 executions. Intermediate rows are
three-execution exploratory measurements.

| Rayon threads | Mean signing time |
| ---: | ---: |
| 1 | 1.564 s |
| 2 | 1.132 s |
| 4 | 744 ms |
| 8 | 588 ms |
| 14 | 479 ms |

The current implementation already benefits substantially from parallel leaf
hashing and parallel Merkle levels. Scaling begins to flatten after eight
threads, but using all available logical processors remains beneficial on this
machine.

## Internal profiles

### Upstream BN254 / Anemoi-5 fast

Instrumentation increases the total runtime, so these figures are useful as a
breakdown and must not replace the non-instrumented timing above.

| Block | Mean time |
| --- | ---: |
| CAPSS signing, instrumented | 1.062 s |
| DECS compute leaves | 271.5 ms |
| DECS hash leaves | 548.5 ms |
| DECS Merkle tree | 64.7 ms |
| LVCS opening challenge | 144.2 ms |

DECS commitment work accounts for most of the signing cost. The result agrees
with the cost distribution reported in the revised CAPSS paper.

### BDAC current BN254 / Griffin-5 fast extended

A one-execution Python profile measured 516 ms for signing:

| Block | Inclusive time |
| --- | ---: |
| SmallWood proof | 511 ms |
| LVCS commit | 399 ms |
| DECS commit | 384 ms |
| Fused Rust leaf hashing and Merkle tree | 243 ms |
| Other Rust sponge calls (65 calls) | 97 ms |
| Verification | 152 ms |

The profile includes nested calls, so rows must not be summed.

## Upstream anonymous-credential reproduction

The official `A256-3.default` Python generator produced:

- claimed security: 129.6 bits;
- compressed CAPSS signature: 12.640 KB;
- R1CS variables: 23,983;
- R1CS constraints: 23,484;
- R1CS construction, witness resolution, and export: 3 min 24 s;
- maximum resident memory: 2.36 GB;
- exported constraint file: 893 MB.

The public artifact does not reproduce the Aurora experiment as-is. The
official Anemoi-3 instance uses the BN254 base-field modulus, whose 2-adicity is
one, while the public Aurora wrapper selects a multiplicative-coset FFT domain.
The prover consequently aborts with `libfqfft::DomainSizeException` at a
32,768-element domain. The paper experiment may have used an unpublished
Aurora-compatible field configuration. This should be clarified before using
a locally reproduced Table 8 value.

## Optimization conclusions

1. The `BigUint` backend has been replaced by the fixed-width Montgomery
   representation from `ark_bn254::Fr`. This follows the main low-level design
   choice in the upstream Anemoi backend while retaining the Python/Sage
   protocol implementation.
2. A possible future optimization is to fuse the remaining per-call sponge operations or the complete verifier
   recomputation into fewer Rust calls. The current profile still spends about
   79 ms across the generic Rust sponge calls in two sign/verify executions.
   At this point Sage polynomial work is also material, so moving the complete
   verifier is no longer an obviously proportionate engineering trade-off.
3. Keep the existing fused leaf-hash/Merkle API and Rayon parallelism. The
   scaling measurements show that these optimizations are effective.
4. Do not replace Griffin with upstream Anemoi only for native signing speed.
   Such a change also requires a new R1CS gadget, serialization agreement,
   witness adapter, and fresh end-to-end Aurora measurements.
5. Treat Goldilocks as a separate future instantiation rather than a drop-in
   optimization of the current BN254 construction.
