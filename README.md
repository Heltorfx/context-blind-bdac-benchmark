# Context-Blind BDAC Benchmark Artifact

This repository contains the context-blind device-bound anonymous credential
prototype together with entry points for running the protocol and reproducing
its benchmarks. The implementation is included under `implementation/`.

## Code provenance

The prototype builds on the CAPSS implementation released with *CAPSS: A
Framework for SNARK-Friendly Post-Quantum Signatures* by Feneuil and Rivain.
In particular, the included CAPSS, SmallWood, and Aurora/libiop components are
derived from that artifact. This repository adds the context-blind BDAC
protocol layer, its augmented presentation relation, optimized backends,
integration code, tests, executable demonstrations, and benchmark tooling.
The original licenses and attribution files are retained in the corresponding
source directories.

## Run a presentation with Longfellow

Build the native components once:

```bash
bash ./setup-longfellow.sh
```

Run issuance alone, or the full enrollment, issuance, presentation, and
verification flow:

```bash
./demo.sh issuance
./demo.sh presentation longfellow
```

On Windows, run these commands from the repository directory:

```powershell
wsl bash ./setup-longfellow.sh
.\demo.ps1 issuance
.\demo.ps1 presentation longfellow
```

The demo executes all protocol roles locally. The presentation command prints
the disclosed attribute indexes, verification result, proof size, and timings.
The setup script builds the Rust components, checks out a pinned revision of
Google's Longfellow source into the ignored `longfellow-zk/` directory, and
builds the BDAC R1CS adapter from `longfellow/`. The Longfellow profile uses
160 openings and a block encoding length of 15677. It targets 128-bit
security, but this BN254-field parameter profile remains experimental; the
source project's analysis for other fields does not directly validate it.

## Aurora backend

Build, test, and run one Aurora benchmark trial:

```bash
./run.sh smoke
```

Then run the same presentation relation with Aurora:

```bash
./demo.sh presentation aurora
```

On Windows, use `.\run.ps1 -Mode smoke` and
`.\demo.ps1 presentation aurora`. Issuance and the presentation R1CS are
shared between both backends; only proof generation and verification change.

## What the artifact measures

The benchmark records:

- CAPSS key generation, signing, and verification;
- complete credential issuance and communication;
- Show-witness construction and R1CS export;
- Aurora proving and verification in `run.sh`, or Longfellow proving and
  verification in the presentation demo;
- proof and complete-presentation sizes; and
- R1CS constraints, variables, and public inputs.

Every presentation configuration has one untimed warm-up. The `paper` mode
then performs 30 measured issuance, CAPSS, and presentation trials and retains
all individual presentation samples. Runs are serial; OpenMP and Rayon are
configured with the same explicit thread count.

## Requirements

The current artifact targets Linux or WSL and expects:

- a Sage-enabled Python environment containing the dependencies used by CAPSS;
- CMake and a C++ compiler;
- Rust and Cargo; and
- Git for fetching the pinned Longfellow source; and
- the system libraries required by CAPSS/libiop, including `libsodium-dev`
  when building Aurora.

Run the artifact from a Sage-enabled environment. The scripts fail early when
Sage, Cargo, CMake, or a required source tree is missing. Common Conda/Mamba
installations containing an environment named `sage` are detected
automatically. For another layout, set
`BENCHMARK_PYTHON=/absolute/path/to/python`.

## Aurora benchmark execution

Quick validation:

```bash
./run.sh smoke
```

Full benchmark:

```bash
./run.sh paper --threads 8
```

On Windows, the PowerShell launcher delegates to WSL:

```powershell
.\run.ps1 -Mode smoke
.\run.ps1 -Mode paper -Threads 8
```

Use `--skip-build` after the native components have already been built. Use
`--skip-tests` only for local timing iterations. `./run.sh --help` lists all
options, including an alternate implementation path and the experimental
Aurora `v2` backend.

## Results

Each execution creates a timestamped directory under `results/` containing:

- `benchmark.json`: complete machine-readable results and raw samples;
- `environment.json`: CPU, platform, tool versions, thread settings, and Git
  revisions when available;
- `REPORT.md`: compact result table;
- `summary.csv`: aggregate values;
- `presentation-samples.csv`: every measured presentation;
- `logs/`: build, test, and benchmark logs; and
- `SHA256SUMS.txt`: integrity hashes for the generated files.

Sizes in the report are decimal kilobytes. The JSON files retain byte counts
and unrounded timings.

## Reproducing the Aurora measurements

The full `paper` benchmark currently measures the non-interactive Aurora
backend only. Its command is:

```bash
./run.sh paper --aurora-version normal --threads 8
```

Machine-dependent timings should be compared only between runs performed on
the same host and under the same power and thread settings. Proof sizes and
circuit dimensions are machine independent.
The Longfellow demo above runs one complete presentation; it is not the
repeated-trial `paper` benchmark.
