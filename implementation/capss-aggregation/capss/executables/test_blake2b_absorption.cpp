#include <iostream>
#include <stdexcept>
#include "capss/relations/r1cs_field.hpp"
#include "libiop/bcs/hashing/blake2b.hpp"

using FieldT = capss::field256;
using Chain = libiop::blake2b_hashchain<FieldT, libiop::binary_hash_digest>;

class ObservableChain : public Chain {
public:
    ObservableChain() : Chain(128) {}
    const libiop::binary_hash_digest& state() const { return internal_state_; }
};

int main() {
    capss::init_field256("r1cs-field.txt");
    const std::string a(32, 'a'), b(32, 'b');
    ObservableChain left, right, same;
    left.absorb(a);
    right.absorb(b);
    same.absorb(a);
    if (left.state() == right.state())
        throw std::runtime_error("different roots have identical transcript states");
    if (left.state() != same.state())
        throw std::runtime_error("absorption is not deterministic");
    const std::string input = std::string(32, ' ') + a;
    std::string expected(32, '\0');
    if (crypto_generichash_blake2b(
            reinterpret_cast<unsigned char*>(&expected[0]), expected.size(),
            reinterpret_cast<const unsigned char*>(input.data()), input.size(),
            nullptr, 0) != 0 || expected != left.state())
        throw std::runtime_error("absorption does not hash state || full input");
    left.absorb(b);
    right.absorb(a);
    if (left.state() == right.state())
        throw std::runtime_error("transcript ignores message order");
    ObservableChain x, y, empty;
    x.absorb(std::vector<FieldT>{FieldT::zero()});
    y.absorb(std::vector<FieldT>{FieldT::one()});
    empty.absorb(std::vector<FieldT>{});
    if (x.state() == y.state() || x.squeeze(4) == y.squeeze(4))
        throw std::runtime_error("field messages do not affect challenges");
    std::cout << "PASS: roots, order, field inputs, challenges, empty input\n";
}
