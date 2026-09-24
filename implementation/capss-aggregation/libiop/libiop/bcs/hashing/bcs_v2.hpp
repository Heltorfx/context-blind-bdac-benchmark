#pragma once

#include <cstdint>
#include <limits>
#include <stdexcept>
#include <sodium/crypto_generichash_blake2b.h>
#include "libiop/bcs/hashing/hashing.hpp"

namespace libiop { namespace bcs_v2 {

inline void u64(std::string &out, uint64_t value) {
    for (size_t i = 0; i < 8; ++i) out.push_back(static_cast<char>(value >> (8*i)));
}
inline void bytes(std::string &out, const std::string &value) {
    u64(out, value.size());
    out += value;
}
inline std::string hash(const std::string &domain, const std::string &input) {
    std::string framed = "BDAC-AURORA-V2";
    bytes(framed, domain);
    bytes(framed, input);
    std::string digest(32, '\0');
    if (crypto_generichash_blake2b(reinterpret_cast<unsigned char*>(&digest[0]), 32,
        reinterpret_cast<const unsigned char*>(framed.data()), framed.size(), nullptr, 0) != 0)
        throw std::runtime_error("BCS v2 hash failed");
    return digest;
}
template<typename Bigint>
void integer(std::string &out, const Bigint &value, size_t width) {
    const size_t limb_bytes = sizeof(value.data[0]);
    for (size_t i = 0; i < width; ++i)
        out.push_back(static_cast<char>(value.data[i/limb_bytes] >> (8*(i%limb_bytes))));
}
template<typename FieldT>
void field(std::string &out, const FieldT &value) {
    integer(out, value.as_bigint(), (FieldT::mod.num_bits()+7)/8);
}
template<typename FieldT>
std::string fields(const std::vector<FieldT> &values) {
    std::string out;
    u64(out, values.size());
    for (const auto &value : values) field(out, value);
    return out;
}

// A prefix transcript: each draw hashes the complete framed prefix, not raw C++ memory.
template<typename FieldT>
class transcript : public hashchain<FieldT, binary_hash_digest> {
    std::string context_, prefix_;
    size_t draw_ = 0;
    size_t round_ = 0;
    bool in_round_ = false;
    std::string draw_input(size_t index, size_t count, size_t retry) const {
        std::string input = prefix_;
        u64(input, round_); u64(input, draw_); u64(input, index);
        u64(input, count); u64(input, retry);
        return input;
    }
    FieldT sample_field(size_t index, size_t count) const {
        const size_t bits = FieldT::mod.num_bits();
        if (bits > 256) throw std::invalid_argument("BCS v2 supports prime fields up to 256 bits");
        for (size_t retry = 0; ; ++retry) {
            auto digest = hash("challenge-field", draw_input(index, count, retry));
            auto value = FieldT::zero().as_bigint();
            for (size_t i = 0; i < sizeof(value.data)/sizeof(value.data[0]); ++i) value.data[i] = 0;
            for (size_t i = 0; i < (bits+7)/8; ++i) {
                unsigned char byte = static_cast<unsigned char>(digest[i]);
                if (i == bits/8 && bits%8) byte &= (1u << (bits%8))-1;
                value.data[i/sizeof(mp_limb_t)] |= static_cast<mp_limb_t>(byte) << (8*(i%sizeof(mp_limb_t)));
            }
            if (mpn_cmp(value.data, FieldT::mod.data, sizeof(value.data)/sizeof(value.data[0])) < 0)
                return FieldT(value);
        }
    }
public:
    explicit transcript(const std::string &context) : context_(context) { bytes(prefix_, context); }
    std::shared_ptr<hashchain<FieldT, binary_hash_digest>> new_hashchain() override {
        return std::make_shared<transcript<FieldT>>(context_);
    }
    void begin_round(size_t round, const std::string &salt) override {
        if (salt.size() != 32 || round != (in_round_ ? round_+1 : 0))
            throw std::invalid_argument("invalid BCS v2 round or salt");
        round_ = round; in_round_ = true;
        bytes(prefix_, "round"); u64(prefix_, round); bytes(prefix_, salt);
    }
    void absorb(const binary_hash_digest root) override {
        if (root.size() != 32) throw std::invalid_argument("invalid BCS v2 root");
        bytes(prefix_, "root"); bytes(prefix_, root);
    }
    void absorb(const std::vector<FieldT> &message) override {
        bytes(prefix_, "message"); bytes(prefix_, fields(message));
    }
    std::vector<FieldT> squeeze(size_t count) override {
        if (!in_round_) throw std::logic_error("BCS v2 draw before first round");
        ++draw_;
        std::vector<FieldT> result;
        for (size_t i = 0; i < count; ++i) result.emplace_back(sample_field(i, count));
        return result;
    }
    std::vector<size_t> squeeze_query_positions(size_t count, size_t range) override {
        if (!range || (range & (range-1))) throw std::invalid_argument("BCS v2 query range must be power of two");
        std::vector<size_t> result;
        for (size_t i = 0; i < count; ++i) {
            ++draw_;
            auto digest = hash("query-position", draw_input(0, range, 0));
            uint64_t value = 0;
            for (size_t j = 0; j < 8; ++j) value |= uint64_t(static_cast<unsigned char>(digest[j])) << (8*j);
            result.push_back(value & (range-1));
        }
        return result;
    }
    binary_hash_digest squeeze_root_type() override {
        ++draw_;
        return hash("pow-challenge", draw_input(0, 1, 0));
    }
};

template<typename FieldT>
class leafhash_v2 : public leafhash<FieldT, binary_hash_digest> {
public:
    binary_hash_digest hash(const std::vector<FieldT> &) override {
        throw std::logic_error("BCS v2 requires salted leaves");
    }
    binary_hash_digest zk_hash(const std::vector<FieldT> &leaf, const zk_salt_type &salt) override {
        if (salt.size() != 32) throw std::invalid_argument("invalid BCS v2 leaf salt");
        auto input = fields(leaf); bytes(input, salt);
        return bcs_v2::hash("merkle-leaf", input);
    }
};
inline binary_hash_digest node(const binary_hash_digest &left, const binary_hash_digest &right, size_t width) {
    if (width != 32 || left.size() != 32 || right.size() != 32)
        throw std::invalid_argument("invalid BCS v2 node");
    return hash("merkle-node", left + right);
}

} }
