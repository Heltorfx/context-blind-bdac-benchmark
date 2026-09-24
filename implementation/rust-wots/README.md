# Rust WOTS+ Backend

This module exposes the WOTS+ component of the official SPHINCS+ reference
implementation to Python. It uses the SHAKE-128f WOTS+ parameters (`n = 16`,
`w = 16`) and a compressed 32-byte public key consisting of `PK.seed || root`.

The cryptographic implementation in `vendor/sphincsplus` is copied from the
official SPHINCS+ repository at commit
`7ec789ace6874d875f4bb84cb61b81155398167e`. The BDAC-specific code only
provides a fixed-address standalone adapter and Python bindings.

Build in the same environment as the rest of the prototype:

```bash
cd Implementation/rust-wots
python -m pip install maturin
maturin develop --release
```

WOTS+ keys are one-time keys. The Python protocol layer generates a fresh key
for every presentation and signs exactly one digest with it.
