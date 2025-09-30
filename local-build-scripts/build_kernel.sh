#!/bin/bash

source ./config.ini
source ./common.sh

# if PLATFORM is already exported from main_build.sh, keep it
if [ -n "${PLATFORM:-}" ] && [ -n "${PLAT:-}" ]; then
	PLATFORM="$PLAT"
fi

# Check Linux Kernel location
if [ -z "${KERNEL_DIR}" ]; then
	echo "There is no Linux Kernel source at ${KERNEL_DIR} or it does not set properly at config.ini file."
	echo "Please recheck your setup"
	exit 1
fi

# Default fallback
DEFCONFIG="renesas_defconfig"

# Per-platform mapping
declare -A KERN_DEFCONFIG=(
	["RZG2L-SBC"]="rzg2l-sbc_defconfig"
	["RZG2L-EVK"]="rzv2l_defconfig"
	["RZV2L-EVK"]="rzv2l_defconfig"
	["RZV2H-EVK"]="rzv2h_defconfig"
	["RZV2H-RDK"]="rzv2h_defconfig"
)

# Resolve DEFCONFIG
if [[ "${PLATFORM}" == "RZ-CMN" ]]; then
	DEFCONFIG="renesas_defconfig"
elif [[ -n "${KERN_DEFCONFIG[$PLATFORM]+x}" ]]; then
	DEFCONFIG="${KERN_DEFCONFIG[$PLATFORM]}"
fi

echo "Using DEFCONFIG=${DEFCONFIG}"

# Setup the build
kernel_setup() {
	CONFIG_LOCALVERSION='CONFIG_LOCALVERSION="-yocto-standard"'
	CONFIG_LOCALVERSION_AUTO='CONFIG_LOCALVERSION_AUTO=n'
	FILE="arch/arm64/configs/${DEFCONFIG}"

	# Remove '+' at the end of kernel version
	#touch .scmversion
	export LOCALVERSION=""

	# Update defconfig to compatible with rootfs
	if grep -q "$CONFIG_LOCALVERSION" "$FILE"; then
		echo "Already set $CONFIG_LOCALVERSION"
	else
		echo "$CONFIG_LOCALVERSION" >> "$FILE"
		echo "Appended $CONFIG_LOCALVERSION to $FILE"
	fi

	if grep -q "$CONFIG_LOCALVERSION_AUTO" "$FILE"; then
		echo "Already set $CONFIG_LOCALVERSION_AUTO"
	else
		echo "$CONFIG_LOCALVERSION_AUTO" >> "$FILE"
		echo "Appended $CONFIG_LOCALVERSION_AUTO to $FILE"
	fi
}

mk_image() {
	echo '|============================================|'
	echo '|          Build IMAGE Yocto-standard        |'
	echo '|============================================|'
	make -j"$(nproc)" Image
}

mk_dtbs() {
	echo '|============================================|'
	echo '|             Build device tree              |'
	echo '|============================================|'
	make -j"$(nproc)" dtbs
}

mk_full_image() {
	kernel_setup
	make ${DEFCONFIG}
	echo '|============================================|'
	echo '|          Build IMAGE Yocto-standard        |'
	echo '|============================================|'
	make -j"$(nproc)" Image
	echo '|============================================|'
	echo '|             Build device tree              |'
	echo '|============================================|'
	make -j"$(nproc)" dtbs
}

mk_clean() {
	make clean
}

mk_distclean() {
	make distclean
}

mk_defconfig() {
	kernel_setup
	make ${DEFCONFIG}
}

mk_menuconfig() {
	kernel_setup
	make menuconfig
}

mk_modules() {
	kernel_setup
	make ${DEFCONFIG}
	mk_full_image
	echo '|============================================|'
	echo '|               Build modules                |'
	echo '|============================================|'
	make -j"$(nproc)" modules
	echo "Build completed successfully"
}

# Main Linux Kernel build
echo "Starting the kernel build at ${KERNEL_DIR}"
cd "${KERNEL_DIR}" || exit 1

case ${1} in
	'clean')
		mk_clean
		;;
	'distclean')
		mk_distclean
		;;
	'defconfig')
		mk_defconfig
		;;
	'menuconfig')
		mk_menuconfig
		;;
	'image')
		mk_defconfig
		mk_image
		;;
	'dtbs')
		mk_defconfig
		mk_dtbs
		;;
	'all')
		mk_full_image
		;;
	'modules')
		mk_modules
		;;
	*)
		show_help
		;;
esac

exit 0
