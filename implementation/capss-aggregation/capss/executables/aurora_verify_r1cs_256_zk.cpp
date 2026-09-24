#include "capss/relations/r1cs_field.hpp"
#include "capss/snarks/aurora_verify_r1cs.tcc"

int main(int argc, char** argv) {
    capss::init_field256("r1cs-field.txt");
    const std::string in_path = argc > 1 ? argv[1] : "proof.bin";
    return aurora_verify_r1cs<capss::field256>(128, true, in_path) ? 0 : 1;
}
