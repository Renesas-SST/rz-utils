#!/bin/bash

source ./config.ini
source ./common.sh

# if PLATFORM is already exported from main_build.sh, keep it
if [ -n "${PLATFORM:-}" ] && [ -n "${PLAT:-}" ]; then
	PLATFORM="$PLAT"
fi

# Check Flash-Writer location
if [ -z "${FLASH_WRITER_DIR}" ]; then
	echo "There is no Flash-writer source at ${FLASH_WRITER_DIR} or it does not set properly at config.ini file."
	echo "Please recheck your setup"
	exit 1
fi

# Map PLATFORM -> "PLAT BOARD"
declare -A FW_P2B=(
	["RZG2L-SBC"]="RZG2L_SBC"
	["RZG2L-EVK"]="RZG2L_SMARC_PMIC"
	["RZV2L-EVK"]="RZV2L_SMARC_PMIC"
	["RZV2H-EVK"]="RZV2H_DEV"
)

sanitize_env() {
	unset CFLAGS LDFLAGS;
}

resolve_fw_board() {
	local platform="$1"
	if [[ -z "${FW_P2B[$platform]+set}" ]]; then
		echo "The platform '$platform' is not supported by Flash Writer yet."
		exit 1
	fi
	BOARD="${FW_P2B[$platform]}"
	export BOARD
}

mk_image_one() {
	local platform="$1"
	sanitize_env
	resolve_fw_board "${platform}"
	make -C "${FLASH_WRITER_DIR}" -j"${JOBS}" BOARD="${BOARD}"
}

mk_clean_one() {
	local platform="$1"
	# Clean doesn’t need BOARD in upstream trees, but keep it consistent
	if [[ -n "${FW_P2B[$platform]+set}" ]]; then
		BOARD="${FW_P2B[$platform]}"
		sanitize_env
		make -C "${FLASH_WRITER_DIR}" clean || true
	fi
}

mk_image() {
	local build_dir="build"
	rm -rf "${FLASH_WRITER_DIR}/${build_dir}"
	if [ "${PLATFORM}" = "RZ-CMN" ]; then
		for pf in "${COMMON_PLATFORMS[@]}"; do
			local pf_build_dir="${build_dir}/${pf}"
			mkdir -p "${FLASH_WRITER_DIR}/${pf_build_dir}"
			echo "==> Building Flash Writer for ${pf}"
			mk_image_one "${pf}"
			echo "==> Copying output to ${pf_build_dir}"
			cp ${FLASH_WRITER_DIR}/AArch64_output/* "${FLASH_WRITER_DIR}/${pf_build_dir}/"
			mk_clean_one "${pf}"
		done
	else
		local pf="${PLATFORM}"
		local pf_build_dir="${build_dir}/${pf}"
		mkdir -p "${pf_build_dir}"
		echo "==> Building Flash Writer for ${pf}"
		mk_image_one "${pf}"
		echo "==> Copying output to ${pf_build_dir}"
		find "${FLASH_WRITER_DIR}" -maxdepth 1 -name '*.mot' -exec cp {} "${pf_build_dir}/" \;
	fi
}

mk_clean() {
	rm -rf "${FLASH_WRITER_DIR}/build"
	if [ "${PLATFORM}" = "RZ-CMN" ]; then
		for pf in "${COMMON_PLATFORMS[@]}"; do mk_clean_one "${pf}"; done
	else
		mk_clean_one "${PLATFORM}"
	fi
}

# ---- Main ----
cmd="${1:-all}"
echo "Starting the Flash-Writer build '${cmd}' (PLATFORM=${PLATFORM}) at ${FLASH_WRITER_DIR}"

case "${cmd}" in
	clean) mk_clean ;;
	all)   mk_image ;;
	*)     show_help ;;
esac

exit 0