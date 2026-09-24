fn main() {
    let sources = [
        "vendor/sphincsplus/ref/address.c",
        "vendor/sphincsplus/ref/fips202.c",
        "vendor/sphincsplus/ref/hash_shake.c",
        "vendor/sphincsplus/ref/thash_shake_simple.c",
        "vendor/sphincsplus/ref/utils.c",
        "vendor/sphincsplus/ref/wots.c",
        "vendor/sphincsplus/ref/wotsx1.c",
        "src/wots_adapter.c",
    ];

    let mut build = cc::Build::new();
    build
        .include("vendor/sphincsplus/ref")
        .include("vendor/sphincsplus/ref/params")
        .define("PARAMS", "sphincs-shake-128f")
        .warnings(true)
        .flag_if_supported("-std=c99");
    for source in sources {
        build.file(source);
        println!("cargo:rerun-if-changed={source}");
    }
    build.compile("bdac_wots");
    println!("cargo:rerun-if-changed=src/wots_adapter.h");
}
