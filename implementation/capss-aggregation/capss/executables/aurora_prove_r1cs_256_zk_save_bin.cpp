#include "capss/relations/r1cs_field.hpp"
#include "capss/snarks/aurora_prove_r1cs_save_bin.tcc"

int main(int argc, char** argv) {
    capss::init_field256("r1cs-field.txt");
    typedef capss::field256 FieldT;

    const std::string out_path = argc > 1 ? argv[1] : "proof.bin";
    try {
        aurora_prove_r1cs_save_bin<FieldT>(128, true, out_path, capss::aurora_v2_mode(argc, argv));
    } catch (const std::exception &error) {
        std::cerr << error.what() << std::endl;
        return 1;
    }
    return 0;
}
