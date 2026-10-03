#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEVKITPRO="${DEVKITPRO:-/opt/devkitpro}"
DEVKITARM="${DEVKITARM:-${DEVKITPRO}/devkitARM}"
PREFIX="${UPDATE_DEPS_ROOT:-${ROOT}/build-3ds/update-prefix}"
SOURCES="${ROOT}/build-3ds/update-deps"
DOWNLOADS="${ROOT}/build-3ds/downloads"
JOBS="${JOBS:-2}"
export DEVKITPRO DEVKITARM
export PATH="${DEVKITARM}/bin:${DEVKITPRO}/tools/bin:${PATH}"

python3 "${ROOT}/tools/3ds/fetch_build_inputs.py" --libraries-only
mkdir -p "${SOURCES}" "${PREFIX}"
# Use fresh, hash-verified source trees so repeated builds never reapply patches.
rm -rf "${SOURCES}/mbedtls-2.28.8" "${SOURCES}/curl-8.4.0" "${SOURCES}/jansson-2.14"
tar -xzf "${DOWNLOADS}/mbedtls.tar.gz" -C "${SOURCES}"
tar -xJf "${DOWNLOADS}/curl.tar.xz" -C "${SOURCES}"
tar -xzf "${DOWNLOADS}/jansson.tar.gz" -C "${SOURCES}"
patch -d "${SOURCES}/mbedtls-2.28.8" -p1 < "${ROOT}/platform/3ds/update-dependencies/mbedtls.patch"
patch -d "${SOURCES}/curl-8.4.0" -p1 < "${ROOT}/platform/3ds/update-dependencies/curl.patch"

MBED="${SOURCES}/mbedtls-2.28.8"
perl "${MBED}/scripts/config.pl" -f "${MBED}/include/mbedtls/config.h" set MBEDTLS_ENTROPY_HARDWARE_ALT
perl "${MBED}/scripts/config.pl" -f "${MBED}/include/mbedtls/config.h" set MBEDTLS_NO_PLATFORM_ENTROPY
perl "${MBED}/scripts/config.pl" -f "${MBED}/include/mbedtls/config.h" set MBEDTLS_CMAC_C
perl "${MBED}/scripts/config.pl" -f "${MBED}/include/mbedtls/config.h" unset MBEDTLS_SELF_TEST
perl "${MBED}/scripts/config.pl" -f "${MBED}/include/mbedtls/config.h" unset MBEDTLS_TIMING_C
cmake -S "${MBED}" -B "${MBED}/build-3ds" \
  -DCMAKE_TOOLCHAIN_FILE="${DEVKITPRO}/cmake/3DS.cmake" \
  -DCMAKE_INSTALL_PREFIX="${PREFIX}" -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_TESTING=OFF -DENABLE_PROGRAMS=OFF -DENABLE_ZLIB_SUPPORT=OFF \
  -DUSE_SHARED_MBEDTLS_LIBRARY=OFF -DUSE_STATIC_MBEDTLS_LIBRARY=ON \
  -DMBEDTLS_FATAL_WARNINGS=OFF
cmake --build "${MBED}/build-3ds" --parallel "${JOBS}"
cmake --install "${MBED}/build-3ds"

export CC=arm-none-eabi-gcc AR=arm-none-eabi-ar RANLIB=arm-none-eabi-ranlib
export CFLAGS="-O2 -march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft -ffunction-sections -fdata-sections -D__3DS__"
export CPPFLAGS="-I${DEVKITPRO}/libctru/include -I${PREFIX}/include"
export LDFLAGS="-L${PREFIX}/lib -L${DEVKITPRO}/libctru/lib -specs=3dsx.specs"
(
  cd "${SOURCES}/curl-8.4.0"
  ./configure --prefix="${PREFIX}" --host=arm-none-eabi \
    --disable-shared --enable-static --disable-ipv6 --disable-unix-sockets \
    --disable-threaded-resolver --disable-manual --disable-pthreads \
    --disable-socketpair --disable-ntlm-wb --disable-ldap --disable-ldaps \
    --with-mbedtls="${PREFIX}" --with-ca-bundle='romfs:/update-ca.pem' \
    --without-openssl --without-zlib --without-brotli --without-zstd \
    --without-libidn2 --without-libpsl --without-nghttp2 --without-nghttp3 \
    --without-ngtcp2 --without-libssh2 --without-libssh --without-librtmp \
    --without-gssapi LIBS='-lctru -lm'
  make -C lib -j "${JOBS}"
  make -C lib install
  make -C include install
  make install-pkgconfigDATA
)
# Clear autotools flags before CMake supplies its own 3DS toolchain settings.
unset CC AR RANLIB CFLAGS CPPFLAGS LDFLAGS
cmake -S "${SOURCES}/jansson-2.14" -B "${SOURCES}/jansson-2.14/build-3ds" \
  -DCMAKE_TOOLCHAIN_FILE="${DEVKITPRO}/cmake/3DS.cmake" \
  -DCMAKE_INSTALL_PREFIX="${PREFIX}" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DJANSSON_EXAMPLES=OFF \
  -DJANSSON_WITHOUT_TESTS=ON -DJANSSON_BUILD_DOCS=OFF -DJANSSON_BUILD_SHARED_LIBS=OFF \
  -DUSE_URANDOM=OFF -DUSE_WINDOWS_CRYPTOAPI=OFF
cmake --build "${SOURCES}/jansson-2.14/build-3ds" --parallel "${JOBS}"
cmake --install "${SOURCES}/jansson-2.14/build-3ds"
