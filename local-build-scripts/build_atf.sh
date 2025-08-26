#!/bin/bash
set -euo pipefail

source ./config.ini
source ./common.sh

# if PLATFORM is already exported from main_build.sh, keep it
if [ -n "${PLATFORM:-}" ] && [ -n "${PLAT:-}" ]; then
	PLATFORM="$PLAT"
fi

# Check ATF location
if [ -z "${ATF_DIR}" ]; then
	echo "There is no TF-A source at ${ATF_DIR} or it does not set properly at config.ini file."
	echo "Please recheck your setup"
	exit 1
fi

# ---- Config ----
JOBS="${JOBS:-$(nproc)}"

# Map PLATFORM -> "PLAT BOARD"
declare -A P2B=(
	["RZG2L-SBC"]="g2l sbc_1"
	["RZG2L-EVK"]="g2l smarc_pmic_2"
	["RZV2L-EVK"]="v2l smarc_rzv2l"
	["RZV2H-EVK"]="v2h v2h_evk_1"
)

# Resolve PLAT/BOARD for a single PLATFORM
resolve_board() {
	local platform="$1"
	if [[ -z "${P2B[$platform]+set}" ]]; then
		echo "The platform '$platform' is not supported. Please recheck your setup."
		exit 1
	fi
	read -r PLAT BOARD <<<"${P2B[$platform]}"
	export PLAT BOARD
}

mk_image_one() {
	local platform="$1"
	local image="$2"
	resolve_board "${platform}"

	if [ "${ATF_MODE:-RELEASE}" = "DEBUG" ]; then
		make -C "${ATF_DIR}" -j"${JOBS}" PLAT="${PLAT}" BOARD="${BOARD}" DEBUG=1 "${image}"
	else
		make -C "${ATF_DIR}" -j"${JOBS}" PLAT="${PLAT}" BOARD="${BOARD}" "${image}"
	fi
}

mk_clean_one() {
	local platform="$1"
	resolve_board "${platform}"
	make -C "${ATF_DIR}" clean || true
}

mk_distclean_one() {
	local platform="$1"
	resolve_board "${platform}"
	make -C "${ATF_DIR}" distclean || true
}

mk_image() {
	local image="$1"
	if [ "${PLATFORM}" = "RZ-CMN" ]; then
		for pf in "${COMMON_PLATFORMS[@]}"; do
			echo "==> Building ${image} for ${pf}"
			mk_image_one "${pf}" "${image}"
		done
	else
		mk_image_one "${PLATFORM}" "${image}"
	fi
}

mk_clean() {
	if [ "${PLATFORM}" = "RZ-CMN" ]; then
		for pf in "${COMMON_PLATFORMS[@]}"; do mk_clean_one "${pf}"; done
	else
		mk_clean_one "${PLATFORM}"
	fi
}

mk_distclean() {
	if [ "${PLATFORM}" = "RZ-CMN" ]; then
		for pf in "${COMMON_PLATFORMS[@]}"; do mk_distclean_one "${pf}"; done
	else
		mk_distclean_one "${PLATFORM}"
	fi
}

sanitize_env() {
	unset CFLAGS LDFLAGS;
}

# ---- Main ----
cmd="${1:-all}"
echo "Starting the ATF build '${cmd}' (PLATFORM=${PLATFORM}) in ${ATF_DIR}"
sanitize_env

case "${cmd}" in
  clean)      mk_clean ;;
  distclean)  mk_distclean ;;
  bl2|bl31|all)
			  mk_image "${cmd}" ;;
  *)
			  show_help ;;
esac

exit 0
