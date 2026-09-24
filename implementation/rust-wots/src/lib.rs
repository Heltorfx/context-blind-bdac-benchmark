use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

const SECRET_KEY_BYTES: usize = 32;
const PUBLIC_KEY_BYTES: usize = 32;
const DIGEST_BYTES: usize = 16;
const SIGNATURE_BYTES: usize = 560;

unsafe extern "C" {
    fn bdac_wots_keypair_from_seed(
        public_key: *mut u8,
        secret_key: *mut u8,
        seed: *const u8,
        seed_len: usize,
    ) -> i32;
    fn bdac_wots_sign(
        signature: *mut u8,
        digest: *const u8,
        digest_len: usize,
        secret_key: *const u8,
        secret_key_len: usize,
    ) -> i32;
    fn bdac_wots_verify(
        signature: *const u8,
        signature_len: usize,
        digest: *const u8,
        digest_len: usize,
        public_key: *const u8,
        public_key_len: usize,
    ) -> i32;
}

fn require_len(name: &str, value: &[u8], expected: usize) -> PyResult<()> {
    if value.len() != expected {
        return Err(PyValueError::new_err(format!(
            "{name} has length {}, expected {expected}",
            value.len()
        )));
    }
    Ok(())
}

#[pyfunction]
fn keypair_from_seed(seed: Vec<u8>) -> PyResult<(Vec<u8>, Vec<u8>)> {
    require_len("seed", &seed, SECRET_KEY_BYTES)?;
    let mut public_key = vec![0u8; PUBLIC_KEY_BYTES];
    let mut secret_key = vec![0u8; SECRET_KEY_BYTES];
    let status = unsafe {
        bdac_wots_keypair_from_seed(
            public_key.as_mut_ptr(),
            secret_key.as_mut_ptr(),
            seed.as_ptr(),
            seed.len(),
        )
    };
    if status != 0 {
        return Err(PyValueError::new_err("WOTS+ key generation failed"));
    }
    Ok((public_key, secret_key))
}

#[pyfunction]
fn sign(secret_key: Vec<u8>, digest: Vec<u8>) -> PyResult<Vec<u8>> {
    require_len("secret key", &secret_key, SECRET_KEY_BYTES)?;
    require_len("digest", &digest, DIGEST_BYTES)?;
    let mut signature = vec![0u8; SIGNATURE_BYTES];
    let status = unsafe {
        bdac_wots_sign(
            signature.as_mut_ptr(),
            digest.as_ptr(),
            digest.len(),
            secret_key.as_ptr(),
            secret_key.len(),
        )
    };
    if status != 0 {
        return Err(PyValueError::new_err("WOTS+ signing failed"));
    }
    Ok(signature)
}

#[pyfunction]
fn verify(public_key: Vec<u8>, digest: Vec<u8>, signature: Vec<u8>) -> PyResult<bool> {
    require_len("public key", &public_key, PUBLIC_KEY_BYTES)?;
    require_len("digest", &digest, DIGEST_BYTES)?;
    require_len("signature", &signature, SIGNATURE_BYTES)?;
    Ok(unsafe {
        bdac_wots_verify(
            signature.as_ptr(),
            signature.len(),
            digest.as_ptr(),
            digest.len(),
            public_key.as_ptr(),
            public_key.len(),
        ) == 1
    })
}

#[pymodule]
fn rust_wots(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("PUBLIC_KEY_BYTES", PUBLIC_KEY_BYTES)?;
    m.add("SECRET_KEY_BYTES", SECRET_KEY_BYTES)?;
    m.add("DIGEST_BYTES", DIGEST_BYTES)?;
    m.add("SIGNATURE_BYTES", SIGNATURE_BYTES)?;
    m.add_function(wrap_pyfunction!(keypair_from_seed, m)?)?;
    m.add_function(wrap_pyfunction!(sign, m)?)?;
    m.add_function(wrap_pyfunction!(verify, m)?)?;
    Ok(())
}
