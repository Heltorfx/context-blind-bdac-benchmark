#include <chrono>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "algebra/convolution.h"
#include "algebra/fp.h"
#include "algebra/reed_solomon.h"
#include "arrays/dense.h"
#include "circuits/compiler/compiler.h"
#include "random/secure_random_engine.h"
#include "random/transcript.h"
#include "util/readbuffer.h"
#include "zk/zk_proof.h"
#include "zk/zk_prover.h"
#include "zk/zk_verifier.h"

namespace {
using Field = proofs::Fp<4>;
using Clock = std::chrono::steady_clock;

double seconds(Clock::time_point start) {
  return std::chrono::duration<double>(Clock::now() - start).count();
}

std::string token(std::istream& in) {
  std::string value;
  if (!(in >> value)) throw std::runtime_error("Unexpected end of R1CS input");
  return value;
}

size_t number(std::istream& in) { return std::stoull(token(in)); }

Field::Elt element(std::istream& in, const Field& field) {
  auto value = token(in);
  auto parsed = field.of_untrusted_string(value.c_str());
  if (!parsed) throw std::runtime_error("Invalid field element: " + value);
  return *parsed;
}

size_t linear_form(std::istream& in, proofs::QuadCircuit<Field>& q,
                   const std::vector<size_t>& wires, const Field& field) {
  size_t result = q.konst(field.zero());
  size_t count = number(in);
  for (size_t i = 0; i < count; ++i) {
    size_t index = number(in);
    if (index >= wires.size()) throw std::runtime_error("R1CS wire out of range");
    result = q.axpy(result, element(in, field), wires[index]);
  }
  return result;
}

std::vector<Field::Elt> read_witness(const std::string& path, size_t expected,
                                     const Field& field) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("Cannot read " + path);
  size_t batch = number(in), count = number(in);
  if (batch != 1 || count != expected) throw std::runtime_error("Witness dimensions mismatch");
  std::vector<Field::Elt> values(count);
  for (auto& value : values) value = element(in, field);
  return values;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc < 2 || argc > 5) {
      std::cerr << "Usage: bdac_r1cs_bench R1CS_DIR [block_enc|auto|scan] [runs=2] [queries=132]\n";
      return 2;
    }
    const std::string dir = argv[1];
    const std::string requested = argc >= 3 ? argv[2] : "auto";
    const size_t runs = argc >= 4 ? std::stoull(argv[3]) : 2;
    const size_t queries = argc >= 5 ? std::stoull(argv[4]) : 132;
    if (runs < 1 || runs > 3) throw std::runtime_error("runs must be 1..3");
    if (queries < 1 || queries > 256) throw std::runtime_error("queries must be 1..256");

    const Field field("21888242871839275222246405745257275088548364400416034343698204186575808495617");
    {
      std::ifstream field_file(dir + "/r1cs-field.txt");
      if (!field_file || number(field_file) != 254 ||
          token(field_file) != "21888242871839275222246405745257275088548364400416034343698204186575808495617") {
        throw std::runtime_error("Expected the exported BN254 scalar field");
      }
    }
    const auto omega = field.of_string("19103219067921713944291392827692070036145651957329286315305642004821462161904");
    const proofs::FFTConvolutionFactory<Field> fft(field, omega, 1ull << 28);
    const proofs::ReedSolomonFactory<Field, proofs::FFTConvolutionFactory<Field>> rsf(fft, field);

    auto started = Clock::now();
    std::ifstream constraints(dir + "/r1cs-constraints.txt");
    if (!constraints) throw std::runtime_error("Cannot read R1CS constraints");
    const size_t public_count = number(constraints);
    const size_t variable_count = number(constraints);
    const size_t constraint_count = number(constraints);

    proofs::QuadCircuit<Field> q(field);
    std::vector<size_t> wires(variable_count + 1);
    wires[0] = 0;
    for (size_t i = 1; i <= public_count; ++i) wires[i] = q.input_wire();
    q.private_input();
    for (size_t i = public_count + 1; i <= variable_count; ++i) wires[i] = q.input_wire();
    for (size_t i = 0; i < constraint_count; ++i) {
      size_t a = linear_form(constraints, q, wires, field);
      size_t b = linear_form(constraints, q, wires, field);
      size_t c = linear_form(constraints, q, wires, field);
      q.assert0(q.sub(q.mul(a, b), c));
    }
    auto circuit = q.mkcircuit(1);
    const double compile_s = seconds(started);
    if (circuit->npub_in != public_count + 1 || circuit->ninputs != variable_count + 1)
      throw std::runtime_error("Compiled circuit input dimensions mismatch");

    const auto public_values = read_witness(dir + "/r1cs-primary-inputs.txt", public_count, field);
    const auto private_values = read_witness(dir + "/r1cs-auxiliary-inputs.txt", variable_count - public_count, field);
    proofs::Dense<Field> witness(1, variable_count + 1);
    witness.v_[0] = field.one();
    for (size_t i = 0; i < public_count; ++i) witness.v_[i + 1] = public_values[i];
    for (size_t i = 0; i < private_values.size(); ++i) witness.v_[public_count + i + 1] = private_values[i];
    proofs::Dense<Field> pub(1, public_count + 1);
    for (size_t i = 0; i <= public_count; ++i) pub.v_[i] = witness.v_[i];

    constexpr size_t rate = 7;
    proofs::LigeroParam<Field> params(
        circuit->ninputs - circuit->npub_in + proofs::ZkCommon<Field>::pad_size(*circuit),
        circuit->nl, rate, queries);
    size_t block_enc = params.block_enc;
    if (requested == "scan") {
      size_t best_size = SIZE_MAX;
      for (size_t candidate = 100; candidate <= (1u << 17); ++candidate) {
        const size_t estimate = params.layout(candidate);
        if (estimate < best_size) {
          best_size = estimate;
          block_enc = candidate;
        }
      }
    } else if (requested != "auto") {
      block_enc = std::stoull(requested);
    }
    params.layout(block_enc);
    std::cout << "constraints=" << constraint_count << " variables=" << variable_count
              << " public=" << public_count << " wires=" << q.nwires_
              << " quads=" << q.nquad_terms_ << " layers=" << circuit->nl
              << " compile_s=" << compile_s << " queries=" << queries
              << " block_enc=" << block_enc
              << " predicted_ligero_bytes=" << params.layout(block_enc) << '\n';

    for (size_t run = 1; run <= runs; ++run) {
      proofs::ZkProof<Field> proof(*circuit, rate, queries, block_enc);
      proofs::Transcript transcript((uint8_t*)"bdac_longfellow", 16, 7);
      proofs::SecureRandomEngine rng;
      proofs::ZkProver<Field, decltype(rsf)> prover(*circuit, field, rsf);
      started = Clock::now();
      prover.commit(proof, witness, transcript, rng);
      const double commit_s = seconds(started);
      if (!prover.prove(proof, witness, transcript)) throw std::runtime_error("Prover rejected witness");
      const double prove_s = seconds(started);
      std::vector<uint8_t> bytes;
      proof.write(bytes, field);

      proofs::ZkProof<Field> parsed(*circuit, rate, queries, block_enc);
      proofs::ReadBuffer buffer(bytes);
      if (!parsed.read(buffer, field)) throw std::runtime_error("Proof deserialization failed");
      proofs::ZkVerifier<Field, decltype(rsf)> verifier(*circuit, rsf, rate, queries, block_enc, field);
      proofs::Transcript verifying((uint8_t*)"bdac_longfellow", 16, 7);
      started = Clock::now();
      verifier.recv_commitment(parsed, verifying);
      bool valid = verifier.verify(parsed, pub, verifying);
      const double verify_s = seconds(started);
      std::cout << "run=" << run << " commit_s=" << commit_s << " prove_s=" << prove_s
                << " verify_s=" << verify_s << " proof_bytes=" << bytes.size()
                << " valid=" << valid << '\n';
      if (!valid) return 1;
      if (run == 1) {
        pub.v_[1] = field.addf(pub.v_[1], field.one());
        proofs::Transcript tampered((uint8_t*)"bdac_longfellow", 16, 7);
        verifier.recv_commitment(parsed, tampered);
        bool accepted = verifier.verify(parsed, pub, tampered);
        std::cout << "modified_public_input_accepted=" << accepted << '\n';
        if (accepted) return 1;
        pub.v_[1] = field.subf(pub.v_[1], field.one());
      }
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
