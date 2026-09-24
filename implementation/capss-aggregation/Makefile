

install-libiop:
	echo "[+] Fetching libiop and its dependencies"
	git clone https://github.com/scipr-lab/libiop
	cd libiop; git submodule init && git submodule update
	@FP=libiop/depends/libff/libff/algebra/fields/prime_base/fp.hpp; \
	 sed 's/private:/public:/g' $$FP > $$FP.tmp && mv $$FP.tmp $$FP
	@UTILS=libiop/libiop/algebra/utils.hpp; \
	 sed 's/#include <cstdint>/#include <cstddef>/g' $$UTILS > $$UTILS.tmp && mv $$UTILS.tmp $$UTILS
	@echo "[+] Applying cross-platform patches"
	#cd libiop && patch -p1 < ../patches/libiop-no-ate-pairing.patch
	cd libiop && patch -p1 < ../patches/libiop-apple-clang-template-fixes.patch
	#echo "[+] Compiling libiop"
	#cd libiop; mkdir build; cd build; cmake ..; make

build:
	mkdir build; cd build; cmake ..; make

clean:
	rm -rf build

clean-all:
	rm -rf libiop
	rm -rf build
