#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.ini"
source "${SCRIPT_DIR}/common.sh"

# Overrides common.sh's show_help with one scoped to this script.
show_help() {
	cat <<USAGE
Usage: ./build_kernel.sh [sub_command]

Build the Linux kernel (${KERNEL_DIR}). Called directly or via
'./main_build.sh kernel <sub_command>'.

  <sub_command>:
    clean             make clean
    distclean         make distclean
    reset-src         Reset KERNEL_DIR to a clean checkout of its current commit, without
                      re-cloning (see clean_repo() in common.sh)
    defconfig         Write .config: ${DEFCONFIG}, plus kernel-config/<KERNEL_VARIANT>.config
                      if config.ini sets KERNEL_VARIANT
    menuconfig        make menuconfig on the current .config (defconfig first if
                      there is none); kept by the build targets below
    image             Build Image
    dtbs              Build device trees
    modules           Image + dtbs + build modules
    modules-install   modules, then install into KERNEL_MODULES_OUTPUT_DIR
    all               defconfig + Image + dtbs + modules + modules-install
                      (i.e. everything, same as modules-install)

  The build targets run defconfig only if there is no .config, or if DEFCONFIG,
  KERNEL_VARIANT or its fragment changed since the last defconfig. Otherwise they
  build the current .config, with the menuconfig changes.
USAGE
	exit 1
}

# Check Linux Kernel location
if [ -z "${KERNEL_DIR}" ]; then
	echo "KERNEL_DIR is not set properly at config.ini file."
	echo "Please recheck your setup"
	exit 1
fi

# KERNEL_SRCREV pins a commit; otherwise clone KERNEL_BRANCH once and build the tree as it is
ensure_kernel_src() {
	if [ -n "${KERNEL_SRCREV:-}" ]; then
		ensure_src_dir_at_rev "${KERNEL_DIR}" "${KERNEL_REPO:-}" "${KERNEL_SRCREV}" "Linux Kernel"
	else
		ensure_src_dir "${KERNEL_DIR}" "${KERNEL_REPO:-}" "${KERNEL_BRANCH:-}" "Linux Kernel"
	fi
}

# RZ/V2H RDK ver1 and ver101 both build from the one defconfig
DEFCONFIG="renesas_defconfig"
echo "Using DEFCONFIG=${DEFCONFIG}"

# Optional: KERNEL_VARIANT=<name> merges kernel-config/<name>.config on top of DEFCONFIG.
VARIANT_FRAGMENT=""
if [ -n "${KERNEL_VARIANT:-}" ]; then
	VARIANT_FRAGMENT="${SCRIPT_DIR}/kernel-config/${KERNEL_VARIANT}.config"
	if [ ! -f "${VARIANT_FRAGMENT}" ]; then
		echo "Error: unknown KERNEL_VARIANT '${KERNEL_VARIANT}'."
		echo "       No such fragment: ${VARIANT_FRAGMENT}"
		echo "Available variants:"
		for f in "${SCRIPT_DIR}"/kernel-config/*.config; do
			[ -e "$f" ] || { echo "  (none)"; break; }
			echo "  $(basename "$f" .config)"
		done
		exit 1
	fi
	echo "Using KERNEL_VARIANT=${KERNEL_VARIANT} (${VARIANT_FRAGMENT})"
fi

kernel_setup() {
	export LOCALVERSION=""
	# "Linux version ... (user@host)": fixed identity instead of whoever/wherever built it.
	export KBUILD_BUILD_USER="${KBUILD_BUILD_USER:-ubuntu}"
	export KBUILD_BUILD_HOST="${KBUILD_BUILD_HOST:-rzv2h-rdk}"
}

# Merge the KERNEL_VARIANT fragment into DEFCONFIG
mk_config_merged() {
	local defconfig_file="arch/arm64/configs/${DEFCONFIG}"

	if [ ! -f "${defconfig_file}" ]; then
		echo "Error: missing kernel config input: ${KERNEL_DIR}/${defconfig_file}"
		exit 1
	fi

	local merged
	merged="$(mktemp -t rzv2h-merged-config.XXXXXX)"
	cat "${defconfig_file}" > "${merged}"
	# The fragment goes last so it overrides the defconfig.
	cat "${VARIANT_FRAGMENT}" >> "${merged}"

	echo '|============================================|'
	echo '|      Configure kernel (alldefconfig)       |'
	echo '|============================================|'
	make KCONFIG_ALLCONFIG="${merged}" alldefconfig
	local rc=$?
	rm -f "${merged}"
	if [ ${rc} -ne 0 ]; then
		echo "Error: kernel configuration failed"
		exit ${rc}
	fi
}

# DEFCONFIG, merged with the KERNEL_VARIANT fragment if any
configure_kernel() {
	if [ -n "${VARIANT_FRAGMENT}" ]; then
		mk_config_merged
	else
		make ${DEFCONFIG} || exit 1
	fi
}

# What .config was generated from: DEFCONFIG, KERNEL_VARIANT and the fragment contents
CONFIG_STAMP=".config.rz-utils"

config_inputs() {
	echo "${DEFCONFIG} ${KERNEL_VARIANT:-}"
	cat "arch/arm64/configs/${DEFCONFIG}" ${VARIANT_FRAGMENT:+"${VARIANT_FRAGMENT}"} 2>/dev/null | sha256sum
}

# defconfig only if there is no .config or its inputs changed: keeps menuconfig changes
ensure_config() {
	kernel_setup
	if [ -f .config ] && [ "$(cat "${CONFIG_STAMP}" 2>/dev/null)" = "$(config_inputs)" ]; then
		echo "Using the current .config (run defconfig to regenerate it)"
		return 0
	fi
	mk_defconfig
}

mk_image() {
	echo '|============================================|'
	echo '|          Build IMAGE ARM64 RENESAS         |'
	echo '|============================================|'
	make -j"$(nproc)" Image || exit 1
}

mk_dtbs() {
	echo '|============================================|'
	echo '|             Build device tree              |'
	echo '|============================================|'
	make -j"$(nproc)" dtbs || exit 1
}

mk_full_image() {
	ensure_config
	mk_image
	mk_dtbs
}

mk_clean() {
	make clean || exit 1
}

mk_distclean() {
	make distclean || exit 1
	rm -f "${CONFIG_STAMP}"
}

# reset ${KERNEL_DIR}
mk_reset_src() {
	clean_repo "${KERNEL_DIR}" "Linux Kernel"
}

mk_defconfig() {
	kernel_setup
	configure_kernel
	config_inputs > "${CONFIG_STAMP}"
}

mk_menuconfig() {
	ensure_config
	make menuconfig || exit 1
}

mk_modules() {
	mk_full_image
	echo '|============================================|'
	echo '|               Build modules                |'
	echo '|============================================|'
	make -j"$(nproc)" modules || exit 1
	echo "Build completed successfully"
}

mk_modules_install() {
	if [ -z "${KERNEL_MODULES_OUTPUT_DIR:-}" ]; then
		echo "KERNEL_MODULES_OUTPUT_DIR is not set in config.ini."
		echo "Please recheck your setup"
		exit 1
	fi

	mk_modules
	echo '|============================================|'
	echo '|              Install modules               |'
	echo '|============================================|'
	mkdir -p "${KERNEL_MODULES_OUTPUT_DIR}"
	make INSTALL_MOD_PATH="${KERNEL_MODULES_OUTPUT_DIR}" modules_install || exit 1
	rm -f "${KERNEL_MODULES_OUTPUT_DIR}"/lib/modules/*/build
	echo "Installed kernel modules to ${KERNEL_MODULES_OUTPUT_DIR}"
}

# Main Linux Kernel build
case ${1} in
	'clean'|'distclean')
		# Nothing to clean without a tree: do not clone one
		if [ ! -d "${KERNEL_DIR}/.git" ]; then
			echo "No kernel source at ${KERNEL_DIR}, nothing to clean"
			exit 0
		fi
		;;
	'reset-src'|'defconfig'|'menuconfig'|'image'|'dtbs'|'all'|'modules'|'modules-install')
		ensure_kernel_src
		;;
	*)
		show_help
		;;
esac

echo "Starting the kernel build at ${KERNEL_DIR}"
cd "${KERNEL_DIR}" || exit 1

case ${1} in
	'clean')
		mk_clean
		;;
	'distclean')
		mk_distclean
		;;
	'reset-src')
		mk_reset_src
		;;
	'defconfig')
		mk_defconfig
		;;
	'menuconfig')
		mk_menuconfig
		;;
	'image')
		ensure_config
		mk_image
		;;
	'dtbs')
		ensure_config
		mk_dtbs
		;;
	'all')
		mk_modules_install
		;;
	'modules')
		mk_modules
		;;
	'modules-install')
		mk_modules_install
		;;
	*)
		show_help
		;;
esac

exit 0
