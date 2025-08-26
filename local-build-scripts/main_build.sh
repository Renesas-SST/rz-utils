#!/bin/bash

source ./config.ini
source ./common.sh

# POKY setup
if [ ! -d "${SDK_LOCATION}" ];then
	echo "There is no installed SDK at ${SDK_LOCATION} or it does not set properly at config.ini file."
	echo "Please recheck your setup"
	exit 1
fi

TOOLCHAIN=${SDK_LOCATION}/sysroots/x86_64-pokysdk-linux/usr/bin/aarch64-poky-linux
export SDKTARGETSYSROOT=${SDK_LOCATION}/sysroots/cortexa55-poky-linux
export PATH=${TOOLCHAIN}:${PATH}
export ARCH=arm64
export CROSS_COMPILE=aarch64-poky-linux-
export KERNEL_CROSS_COMPILE=${CROSS_COMPILE}
export KCFLAGS="--sysroot=$SDKTARGETSYSROOT"
export OECORE_TUNE_CCARGS=" -mcpu=cortex-a55+crypto -mbranch-protection=standard"
export CC="aarch64-poky-linux-gcc  -mcpu=cortex-a55+crypto -mbranch-protection=standard -fstack-protector-strong  -O2 -D_FORTIFY_SOURCE=2 -Wformat -Wformat-security -Werror=format-security --sysroot=$SDKTARGETSYSROOT"
export CXX="aarch64-poky-linux-g++  -mcpu=cortex-a55+crypto -mbranch-protection=standard -fstack-protector-strong  -O2 -D_FORTIFY_SOURCE=2 -Wformat -Wformat-security -Werror=format-security --sysroot=$SDKTARGETSYSROOT"
export CPP="aarch64-poky-linux-gcc -E  -mcpu=cortex-a55+crypto -mbranch-protection=standard -fstack-protector-strong  -O2 -D_FORTIFY_SOURCE=2 -Wformat -Wformat-security -Werror=format-security --sysroot=$SDKTARGETSYSROOT"
export LD="aarch64-poky-linux-ld  --sysroot=$SDKTARGETSYSROOT"
export AS="aarch64-poky-linux-as "
#source ${SDK_LOCATION}/environment-setup-cortexa55-poky-linux

# Allow PLATFORM override via positional arg
if [ -n "${PLAT:-}" ]; then
	PLATFORM="$PLAT"
	export PLATFORM
fi

# Main process
echo "Starting the build script at $(pwd)"
echo "Target platform ${PLATFORM}"
if [ -z "${1}" ] ; then
	show_help
else
	if [ -z "${2-}" ]; then
		if [ "${1}" = "build-all" ] || [ "${1}" = "clean-all" ]; then
			case ${1} in
				"build-all")
					./build_kernel.sh "all"
					./build_uboot.sh "all"
					./build_atf.sh "all"
					./build_flash_writer.sh "all"
					;;
				"clean-all")
					./build_kernel.sh "distclean"
					./build_uboot.sh "distclean"
					./build_atf.sh "distclean"
					./build_flash_writer.sh "clean"
					;;
				*)
					show_help
					;;
			esac
		else
			show_help
		fi
	else
		if [ "${1}" = "kernel" ] || [ "${1}" = "uboot" ] || [ "${1}" = "atf" ] || [ "${1}" = "flash-writer" ]; then
			case ${1} in
				"kernel")
					./build_kernel.sh "${2}"
					;;
				"uboot")
					./build_uboot.sh "${2}"
					;;
				"atf")
					./build_atf.sh "${2}"
					;;
				"flash-writer")
					./build_flash_writer.sh "${2}"
					;;
				*)
					show_help
					;;
			esac
		else
			show_help
		fi
	fi
fi

exit 0
