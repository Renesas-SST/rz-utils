#!/bin/bash

source ./config.ini
source ./common.sh

# if PLATFORM is already exported from main_build.sh, keep it
if [ -n "${PLATFORM:-}" ] && [ -n "${PLAT:-}" ]; then
	PLATFORM="$PLAT"
fi

# Check U-Boot location
if [ -z "${UBOOT_DIR}" ]; then
	echo "There is no U-Boot source at ${UBOOT_DIR} or it does not set properly at config.ini file."
	echo "Please recheck your setup"
	exit 1
fi

# Setup the build
uboot_setup() {
	unset LD_LIBRARY_PATH
	unset LDFLAGS CFLAGS CPPFLAGS

	case ${PLATFORM} in
		'RZG2L-SBC')
			UBOOT_DEFCONFIG="rzpi_defconfig"
			;;
		'RZG2L-EVK')
			UBOOT_DEFCONFIG="smarc-rzg2l_defconfig"
			;;
		'RZV2L-EVK')
			UBOOT_DEFCONFIG="smarc-rzv2l_defconfig"
			;;
		'RZV2H-EVK')
			UBOOT_DEFCONFIG="rzv2h-evk-ver1_defconfig"
			;;
		'RZ-CMN')
			UBOOT_DEFCONFIG="rz-cmn_defconfig"
			;;
		*)
			echo "The platform does not support. Please recheck your setup" || exit 1
			;;
	esac
}

mk_image() {
	uboot_setup
	make -j"$(nproc)"
}

mk_full_image() {
	uboot_setup
	make "${UBOOT_DEFCONFIG}"
	make -j"$(nproc)"
}

mk_clean() {
	make clean
}

mk_distclean() {
	make distclean
}

mk_defconfig() {
	uboot_setup
	make "${UBOOT_DEFCONFIG}"
}

# Main U-Boot build
echo "Starting the U-Boot build ${1} at ${UBOOT_DIR}"
cd "${UBOOT_DIR}" || exit 1

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
	'image')
		mk_image
		;;
	'all')
		mk_full_image
		;;
	*)
		show_help
		;;
esac

exit 0