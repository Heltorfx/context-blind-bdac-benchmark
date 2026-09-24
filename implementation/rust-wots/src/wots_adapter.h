#ifndef BDAC_WOTS_ADAPTER_H
#define BDAC_WOTS_ADAPTER_H

#include <stddef.h>
#include <stdint.h>

#define BDAC_WOTS_N 16
#define BDAC_WOTS_SECRET_KEY_BYTES 32
#define BDAC_WOTS_PUBLIC_KEY_BYTES 32
#define BDAC_WOTS_SIGNATURE_BYTES 560

int bdac_wots_keypair_from_seed(uint8_t *public_key,
                                uint8_t *secret_key,
                                const uint8_t *seed,
                                size_t seed_len);
int bdac_wots_sign(uint8_t *signature,
                   const uint8_t *digest,
                   size_t digest_len,
                   const uint8_t *secret_key,
                   size_t secret_key_len);
int bdac_wots_verify(const uint8_t *signature,
                     size_t signature_len,
                     const uint8_t *digest,
                     size_t digest_len,
                     const uint8_t *public_key,
                     size_t public_key_len);

#endif
