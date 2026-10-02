#!/bin/bash
# Build uvcs_drv.ko, the UVCS (Codec) out-of-tree kernel module.
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../config.ini"
source "${SCRIPT_DIR}/../common.sh"
source "${SCRIPT_DIR}/common_modules.sh"

if [ -z "${KERNEL_DIR:-}" ]; then
	echo "There is no Linux Kernel source at ${KERNEL_DIR:-} or it does not set properly at config.ini file."
	echo "Please recheck your setup"
	exit 1
fi

NAME="uvcs_drv"
UVCS_TAR="${UVCS_TAR:-${SCRIPT_DIR}/../../vendor/uvcs_kernel_package_v4.3.4.0.tar.bz2}"
URL="${UVCS_URL:-file://${UVCS_TAR}}"
SHA256="${UVCS_SHA256:-a719268bbab3ce13f078158d3ee9b3e7ad1d86c7c04ab8e8ff776e540ecb0738}"
SRC_DIR="${EXT_MODULES_SRC_DIR}/${NAME}"
PKG_DIR="${SRC_DIR}/uvcs_kernel_package"
BUILD_SUBDIR="${PKG_DIR}/src/makefile"

# Export the source and include directories for uvcs_drv and vcp4_drv modules
export UVCS_SRC="${PKG_DIR}/src"
export UVCS_INC="${PKG_DIR}"
export VCP4_SRC="${PKG_DIR}/src"
export KERNELDIR="${KERNEL_DIR}"

mk_fetch() {
	ensure_tar_src "${NAME}" "${URL}" "${SHA256}" "${PKG_DIR}" 1
}

mk_build() {
	kernel_is_built
	mk_fetch
	echo "--- building ${NAME}"
	( unset CFLAGS CPPFLAGS CXXFLAGS
	  cd "${BUILD_SUBDIR}" && make ) || exit 1
}

mk_install() {
	mk_build
	echo '|============================================|'
	echo '|       Install out-of-tree modules          |'
	echo '|============================================|'
	install_module_ko "${NAME}" "${BUILD_SUBDIR}" "extra"
}

mk_reset_src() {
	rm -f "${SRC_DIR}/.srcrev"
	mk_fetch
}

mk_clean() {
	[ -d "${BUILD_SUBDIR}" ] || return 0
	( cd "${BUILD_SUBDIR}" && make clean ) || true
}

# ---- Main ----
cmd="${1:-all}"
echo "Starting the ${NAME} module build '${cmd}'"
echo "Source under ${SRC_DIR}"

case "${cmd}" in
	fetch)   mk_fetch ;;
	reset-src) mk_reset_src ;;
	all)     mk_build ;;
	install) mk_install ;;
	clean)   mk_clean ;;
	*)       show_help ;;
esac

exit 0
