#!/bin/bash

source ./config.ini
source ./common.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Extra hardening flags/tools on top of common.sh's ARCH/CROSS_COMPILE.
export KERNEL_CROSS_COMPILE=${CROSS_COMPILE}
export OECORE_TUNE_CCARGS=" -mcpu=cortex-a55+crypto -mbranch-protection=standard"
export CC="aarch64-linux-gnu-gcc  -mcpu=cortex-a55+crypto -mbranch-protection=standard -fstack-protector-strong  -O2 -D_FORTIFY_SOURCE=2 -Wformat -Wformat-security -Werror=format-security"
export CXX="aarch64-linux-gnu-g++  -mcpu=cortex-a55+crypto -mbranch-protection=standard -fstack-protector-strong  -O2 -D_FORTIFY_SOURCE=2 -Wformat -Wformat-security -Werror=format-security"
export CPP="aarch64-linux-gnu-gcc -E  -mcpu=cortex-a55+crypto -mbranch-protection=standard -fstack-protector-strong  -O2 -D_FORTIFY_SOURCE=2 -Wformat -Wformat-security -Werror=format-security"
export LD="aarch64-linux-gnu-ld"
export AS="aarch64-linux-gnu-as"

# The IPL and kernel-modules scripts are standalone (that is how they are tested): run
# them without the CC/CXX/... above, which would leak into TF-A/U-Boot host tools.
run_standalone() {
	env -u CC -u CXX -u CPP -u LD -u AS -u OECORE_TUNE_CCARGS "$@"
}

# ipl <sub_command>: ipl_build/build_ipl.sh with the IPL_* settings of config.ini
run_ipl() {
	local sub="${1:-all}" opts=()

	[ -n "${IPL_FEATURES_FILE:-}" ] && opts+=(-c "${IPL_FEATURES_FILE}")
	[ -n "${IPL_FEATURES:-}" ] && opts+=(-f "${IPL_FEATURES}")
	case "${sub}" in
		'all')   ;;
		'keep')  opts+=(-k) ;;
		'force') opts+=(-F) ;;
		'clean')
			echo "Removing IPL output ${IPL_OUT_DIR} (sources in ${IPL_WORK_DIR} are kept)"
			rm -rf "${IPL_OUT_DIR}"
			return 0
			;;
		*) show_help ;;
	esac

	# shellcheck disable=SC2086
	WORK_DIR="${IPL_WORK_DIR}" OUT_DIR="${IPL_OUT_DIR}" \
		run_standalone "${SCRIPT_DIR}/ipl_build/build_ipl.sh" "${opts[@]}" ${IPL_BOARDS}
}

# kernel-modules <sub_command> [module]: all modules (kernel_modules_all.sh) or one
run_kernel_modules() {
	local sub="$1" module="${2:-}"

	case "${sub}" in
		'fetch'|'reset-src'|'all'|'install'|'clean') ;;
		*) show_help ;;
	esac
	if [ -n "${module}" ]; then
		[ -x "${SCRIPT_DIR}/kernel-modules/build_${module}.sh" ] || {
			echo "Error: unknown kernel module '${module}' (no kernel-modules/build_${module}.sh)" >&2
			exit 1
		}
		run_standalone "${SCRIPT_DIR}/kernel-modules/build_${module}.sh" "${sub}"
	else
		run_standalone "${SCRIPT_DIR}/kernel-modules/kernel_modules_all.sh" "${sub}"
	fi
}

# Main process
echo "Starting the build script at $(pwd)"
echo "Target board: RZ/V2H RDK (IPL: ${IPL_BOARDS})"
echo "Using cross toolchain prefix: ${CROSS_COMPILE}"
if [ -z "${1:-}" ] ; then
	show_help
fi

case ${1} in
	"all")
		[ -z "${2:-}" ] || show_help
		./build_kernel.sh "all" || exit 1
		run_kernel_modules "install" || exit 1
		run_ipl "all" || exit 1
		;;
	"clean-all")
		[ -z "${2:-}" ] || show_help
		./build_kernel.sh "distclean"
		run_kernel_modules "clean"
		run_ipl "clean"
		;;
	"kernel")
		[ -n "${2:-}" ] || show_help
		./build_kernel.sh "${2}" || exit 1
		;;
	"kernel-modules")
		[ -n "${2:-}" ] || show_help
		run_kernel_modules "${2}" "${3:-}" || exit 1
		;;
	"ipl")
		run_ipl "${2:-all}" || exit 1
		;;
	*)
		show_help
		;;
esac

exit 0
