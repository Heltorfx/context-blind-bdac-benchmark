# Aggregation of CAPSS Signatures

The wrapper aims to prove knowledge of a Rank-1 constraint system (R1CS) encoding in some files using the Aurora SNARK. The R1CS files are:
  * `r1cs-field.txt` that contains the information about the R1CS field;
  * `r1cs-constraints.txt` that encodes the R1CS constraints (part of the proved statement);
  * `r1cs-primary-inputs.txt` that contains the assignment of the public R1CS variables (part of the proved statement);
  * `r1cs-auxiliary-inputs.txt` that contains the assigment of the auxiliary R1CS variables (part of the witness).
Those files can be generated using the Python implementation of the CAPSS framework.

📄 The accompanying paper introducing CAPSS is available on the IACR ePrint archive: [https://eprint.iacr.org/2025/061](https://eprint.iacr.org/2025/061).

This wrapper has been used to produce the aggregation performance numbers in Table 6 of the CAPSS article:

| #Sigs                | 1      | 4      | 16     | 64     | 256    | 1024   |
|----------------------|--------|--------|--------|--------|--------|--------|
| #R1CS                | ≤ 2^15 | ≤ 2^17 | ≤ 2^19 | ≤ 2^21 | ≤ 2^23 | ≤ 2^25 |
| t_aggr (s)           | 2.6    | 12     | 49     | 208    | 906    | 3872   |
| t_verif (s)          | 0.5    | 1.9    | 7.8    | 31     | 127    | 513    |
| \|proof\| (KB)       | 128    | 153    | 181    | 209    | 241    | 271    |
| \|proof\|/#Sigs (KB) | 128    | 38     | 11     | 3.3    | 0.94   | 0.26   |


## Instructions

To get the library *libiop*:
```bash
make install-libiop
```

To build the library *libiop*, together with the wrapper:
```bash
make build
```

The compiled executables are then available in the folder `build/capss`. You can execute them, while having the R1CS files in the working directory. The executable suffix refers to the size of the R1CS field. Executables with `zk` in the file name produce *zero-knowledge* proofs.

## Signature Aggregation with Python-SmallWood

To build the R1CS constraints of the verification algorithm of a CAPSS-based signature scheme, using the [Python library of the SmallWood proof system](https://github.com/CryptoExperts/smallwood-python), you can run the script `capss-build-r1cs.py`:

```bash
sage --python3 scripts/capss-build-r1cs.py G256-5.default 1
```
`G256-3.default` is the label of the desired signature scheme, while the second parameter `1` is the size of the message (in field elements). It will produce two files:
 * `r1cs-field.txt` that contains the information about the signature field;
 * `r1cs-constraints.txt` that encodes the R1CS constraints that checks that one knows a signature that correspond to a given public key and message.

To produce a signature, together with a public key and a message. You can use the following script:
```bash
sage --python3 scripts/capss-sign.py G256-5.default 1 sig.json
```
The two first parameters are the same than the previous script, while the third argument is the file name where the public key, the message and the signature.

To convert `n` signatures into R1CS variable assigments for the corresponding R1CS constraints, you can run the following script:
```bash
sage --python3 scripts/capss-build-witness.py sig1.json sig2.json sig3.json ...
```
where `sig1.json sig2.json ...` is the list of the `n` files that contain the signatures. It will produce two files:
  * `r1cs-primary-inputs.txt` that contains the `n` variable assignments for the public R1CS variables that correspond to the `n` public keys and the `n` messages.
  * `r1cs-auxiliary-inputs.txt` that contains the `n` variable assignments for the auxiliary R1CS variables that correspond to the `n` signatures.

Finally, to aggregate `n` signatures encoded in the above text files, you can run the executable
```bash
./build/capss/aurora_prove_r1cs_256
```
where `256` is a upper bound of the field size (in bits).

