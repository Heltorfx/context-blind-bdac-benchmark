#include "wots_adapter.h"

#include <stdint.h>
#include <string.h>

#include "address.h"
#include "context.h"
#include "hash.h"
#include "params.h"
#include "thash.h"
#include "wots.h"
#include "wotsx1.h"

#if SPX_N != BDAC_WOTS_N
#error "The BDAC adapter expects the SPHINCS+-SHAKE-128f WOTS+ parameters"
#endif

#if SPX_WOTS_BYTES != BDAC_WOTS_SIGNATURE_BYTES
#error "Unexpected WOTS+ signature size"
#endif

static void initialize_context(spx_ctx *ctx,
                               const uint8_t *secret_key,
                               const uint8_t *public_seed) {
    memset(ctx, 0, sizeof(*ctx));
    memcpy(ctx->pub_seed, public_seed, SPX_N);
    if (secret_key != NULL) {
        memcpy(ctx->sk_seed, secret_key, SPX_N);
    }
    initialize_hash_function(ctx);
}

static void generate_public_root(uint8_t *root,
                                 uint8_t *signature,
                                 const uint8_t *digest,
                                 const spx_ctx *ctx) {
    struct leaf_info_x1 info = {0};
    unsigned int steps[SPX_WOTS_LEN] = {0};
    uint32_t address[8] = {0};

    if (digest != NULL) {
        chain_lengths(steps, digest);
        info.wots_sig = signature;
        info.wots_sign_leaf = 0;
    } else {
        info.wots_sig = NULL;
        info.wots_sign_leaf = (uint32_t)~0u;
    }
    info.wots_steps = steps;
    memcpy(info.leaf_addr, address, sizeof(address));
    memcpy(info.pk_addr, address, sizeof(address));
    set_type(info.pk_addr, SPX_ADDR_TYPE_WOTSPK);
    wots_gen_leafx1(root, ctx, 0, &info);
}

int bdac_wots_keypair_from_seed(uint8_t *public_key,
                                uint8_t *secret_key,
                                const uint8_t *seed,
                                size_t seed_len) {
    spx_ctx ctx;

    if (public_key == NULL || secret_key == NULL || seed == NULL ||
        seed_len != BDAC_WOTS_SECRET_KEY_BYTES) {
        return -1;
    }

    memcpy(secret_key, seed, BDAC_WOTS_SECRET_KEY_BYTES);
    initialize_context(&ctx, secret_key, secret_key + SPX_N);
    memcpy(public_key, ctx.pub_seed, SPX_N);
    generate_public_root(public_key + SPX_N, NULL, NULL, &ctx);
    return 0;
}

int bdac_wots_sign(uint8_t *signature,
                   const uint8_t *digest,
                   size_t digest_len,
                   const uint8_t *secret_key,
                   size_t secret_key_len) {
    spx_ctx ctx;
    uint8_t ignored_root[SPX_N];

    if (signature == NULL || digest == NULL || secret_key == NULL ||
        digest_len != SPX_N || secret_key_len != BDAC_WOTS_SECRET_KEY_BYTES) {
        return -1;
    }

    initialize_context(&ctx, secret_key, secret_key + SPX_N);
    generate_public_root(ignored_root, signature, digest, &ctx);
    return 0;
}

int bdac_wots_verify(const uint8_t *signature,
                     size_t signature_len,
                     const uint8_t *digest,
                     size_t digest_len,
                     const uint8_t *public_key,
                     size_t public_key_len) {
    spx_ctx ctx;
    uint8_t endpoints[SPX_WOTS_BYTES];
    uint8_t root[SPX_N];
    uint8_t difference = 0;
    uint32_t wots_address[8] = {0};
    uint32_t pk_address[8] = {0};
    size_t i;

    if (signature == NULL || digest == NULL || public_key == NULL ||
        signature_len != SPX_WOTS_BYTES || digest_len != SPX_N ||
        public_key_len != BDAC_WOTS_PUBLIC_KEY_BYTES) {
        return 0;
    }

    initialize_context(&ctx, NULL, public_key);
    set_type(wots_address, SPX_ADDR_TYPE_WOTS);
    wots_pk_from_sig(endpoints, signature, digest, &ctx, wots_address);
    set_type(pk_address, SPX_ADDR_TYPE_WOTSPK);
    thash(root, endpoints, SPX_WOTS_LEN, &ctx, pk_address);

    for (i = 0; i < SPX_N; i++) {
        difference |= (uint8_t)(root[i] ^ public_key[SPX_N + i]);
    }
    return difference == 0 ? 1 : 0;
}
