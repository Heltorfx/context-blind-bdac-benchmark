# Context-Blind BDAC Benchmark Artifact

This directory provides a single entry point for building, testing, and
benchmarking the context-blind device-bound anonymous credential prototype.
It does not duplicate the implementation: by default it uses the adjacent
`Implementation/` directory.

## What the artifact measures

The paper-facing run records:

- CAPSS key generation, signing, and verification;
- complete credential issuance and communication;
- Show-witness construction and R1CS export;
- Aurora proving and verification;
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
- the CAPSS/libiop dependencies already present under `Implementation/`.

Run the artifact from the same Sage environment used for the implementation.
The scripts fail early when Sage, Cargo, CMake, or the implementation tree is
missing. Common Conda/Mamba installations containing an environment named
`sage` are detected automatically. For another layout, set
`BENCHMARK_PYTHON=/absolute/path/to/python`.

## One-command execution

Quick validation:

```bash
./run.sh smoke
```

Paper-facing benchmark:

```bash
./run.sh paper --threads 8
```

On Windows, the PowerShell launcher delegates to WSL:

```powershell
.\run.ps1 -Mode smoke
.\run.ps1 -Mode paper -Threads 8
```

Use `--skip-build` after the native components have already been built. Use
`--skip-tests` only for local timing iterations, not for an artifact-evaluation
run. `./run.sh --help` lists all options, including an alternate implementation
path and the experimental Aurora `v2` backend.

## Results

Each execution creates a timestamped directory under `results/` containing:

- `benchmark.json`: complete machine-readable results and raw samples;
- `environment.json`: CPU, platform, tool versions, thread settings, and Git
  revisions when available;
- `REPORT.md`: compact reviewer-readable result table;
- `summary.csv`: aggregate values;
- `presentation-samples.csv`: every measured presentation;
- `logs/`: build, test, and benchmark logs; and
- `SHA256SUMS.txt`: integrity hashes for the generated files.

Sizes in the report are decimal kilobytes. The JSON files retain byte counts
and unrounded timings.

## Reproducing the paper values

The default backend is the non-interactive Aurora implementation used by the
paper. The command corresponding to the reported methodology is:

```bash
./run.sh paper --aurora-version normal --threads 8
```

Machine-dependent timings should be compared only between runs performed on
the same host and under the same power and thread settings. Proof sizes and
circuit dimensions are machine independent.
