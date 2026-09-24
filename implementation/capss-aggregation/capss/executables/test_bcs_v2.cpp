#include <iostream>
#include <iomanip>
#include <sstream>
#include "capss/relations/r1cs_field.hpp"
#include "libiop/bcs/hashing/bcs_v2.hpp"
#include "libiop/bcs/merkle_tree.hpp"

using Field = capss::field256;
using Transcript = libiop::bcs_v2::transcript<Field>;
void require(bool value, const char *message) { if (!value) throw std::runtime_error(message); }

std::string hex(const std::string &value) {
    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (const unsigned char byte : value) out << std::setw(2) << static_cast<unsigned int>(byte);
    return out.str();
}

int main() {
    capss::init_field256("r1cs-field.txt");
    const std::string salt(32, 's'), root(32, 'r');
    auto sample = [&](const std::string &ctx, const std::string &s, const std::string &r) {
        Transcript t(ctx); t.begin_round(0, s); t.absorb(r);
        return t.squeeze(3);
    };
    auto baseline = sample("statement", salt, root);
    require(baseline == sample("statement", salt, root), "nondeterministic transcript");
    require(baseline != sample("different", salt, root), "statement ignored");
    require(baseline != sample("statement", std::string(32, 't'), root), "salt ignored");
    require(baseline != sample("statement", salt, std::string(32, 'q')), "root ignored");
    Transcript a("x"), b("x"), c("x"), d("x");
    for (auto *t : {&a, &b, &c, &d}) t->begin_round(0, salt);
    a.absorb(root); a.absorb(std::string(32, 'q'));
    b.absorb(std::string(32, 'q')); b.absorb(root);
    require(a.squeeze(2) != b.squeeze(2), "message order ignored");
    c.absorb(std::vector<Field>{Field::one(), Field::zero()});
    d.absorb(std::vector<Field>{Field::one()}); d.absorb(std::vector<Field>{Field::zero()});
    require(c.squeeze(2) != d.squeeze(2), "message framing ambiguous");
    std::string zero, one;
    libiop::bcs_v2::field(zero, Field::zero());
    libiop::bcs_v2::field(one, Field::one());
    require(zero == std::string(32, '\0'), "bad zero encoding");
    require(one == std::string(1, '\1') + std::string(31, '\0'), "noncanonical field encoding");
    require(hex(libiop::bcs_v2::hash("a", "x")) ==
        "a4a9261429f618426edb5293f3c469d1e6a77dbd30d74489c04f6e8fedc2a80f",
        "BCS v2 known-answer hash changed");
    require(libiop::bcs_v2::hash("a", "x") != libiop::bcs_v2::hash("b", "x"), "domains overlap");
    auto hasher = std::make_shared<libiop::bcs_v2::leafhash_v2<Field>>();
    libiop::merkle_tree<Field, std::string> tree(4, hasher, libiop::bcs_v2::node, 32, true, 128);
    tree.construct(std::vector<std::vector<Field>>{{Field(1), Field(2), Field(3), Field(4)}});
    auto proof = tree.get_set_membership_proof({0, 2});
    require(proof.randomness_hashes.size() == 2, "missing leaf salts");
    require(tree.validate_set_membership_proof(tree.get_root(), {0, 2}, {{Field(1)}, {Field(3)}}, proof), "valid Merkle opening rejected");
    proof.randomness_hashes[0][0] ^= 1;
    require(!tree.validate_set_membership_proof(tree.get_root(), {0, 2}, {{Field(1)}, {Field(3)}}, proof), "modified leaf salt accepted");
    Transcript positions("x"); positions.begin_round(0, salt);
    for (auto pos : positions.squeeze_query_positions(100, 64)) require(pos < 64, "bad query position");
    bool rejected = false;
    try { positions.begin_round(2, salt); } catch (const std::invalid_argument &) { rejected = true; }
    require(rejected, "out-of-order round accepted");
    std::cout << "PASS: known vector, context, salts, roots, order, framing, canonical fields, Merkle openings, query positions\n";
}
