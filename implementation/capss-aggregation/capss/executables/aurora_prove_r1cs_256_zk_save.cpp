#include "capss/relations/r1cs_field.hpp"
#include "capss/snarks/aurora_prove_r1cs_save.tcc"

int main(int argc, char** argv) {
    capss::init_field256("r1cs-field.txt");
    typedef capss::field256 FieldT;

    const std::string out_path = argc > 1 ? argv[1] : "proof.bin";
    aurora_prove_r1cs_save<FieldT>(128, true, out_path);
    return 0;
}
