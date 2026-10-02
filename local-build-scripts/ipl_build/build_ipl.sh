#!/bin/bash
#
# Build the IPL (BL2 + FIP with BL31/U-Boot) for the RZ/V2H RDK ver1/ver101
# from source.
# The RDK has no eMMC: BL2 is built for xSPI flash boot and SD (eSD) boot.
#
# Usage: ./build_ipl.sh [-c <features.conf>] [-f "<FEATURE ...>"] [-k | -F] [ver1|ver101 ...]
#
#   board     ver1 and/or ver101 (default: ver101)
#   -c FILE   options file
#             (default: machine-features.conf next to this script)
#   -f LIST   space-separated options, overrides the file, e.g.
#             -f "RZ_CM33_FIRMWARE_LOAD RZ_CA55_CPU_CLOCKUP"
#   -k        keep the sources in WORK_DIR as they are (with your local
#             changes) and only rebuild; no checkout, no patching
#   -F        discard local changes in WORK_DIR and check out and patch
#             the sources again
#   -h        help
#
# Without -k, each run checks out U-Boot and TF-A and applies the patches
# in u-boot/ and trusted-firmware-a/. If a tree in WORK_DIR has changes
# made after it was patched, the script stops instead of deleting them:
# turn them into a patch (see the message), rebuild with -k, or pass -F.
#
# Options (default: RZ_SRAM_REGION_ACCESS RZ_REMOTEPROC):
#   RZ_SRAM_REGION_ACCESS  TF-A ENABLE_SRAM_REGION_ACCESS_MCPU=1
#   RZ_REMOTEPROC          no effect on the IPL; set enable_overlay_remoteproc=1 in
#                          boot/uEnv.txt (kernel rzv2h-rdk-remoteproc.dtbo)
#   RZ_CM33_COLDBOOT       TF-A ENABLE_RZV2H_CM33_BOOT=1 (xSPI: BL2 0x100000, FIP 0x280000)
#   RZ_CM33_FIRMWARE_LOAD  TF-A ENABLE_CM33_FIRMWARE_LOAD=1 (xSPI: CM33 FW 0x202000)
#   RZ_CA55_CPU_CLOCKUP    TF-A ENABLE_CA55_CLOCKUP=1; the kernel needs
#                          kernel/0001-*-CA55-OPPs-for-1.8GHz-PLL.patch
#
# Supported combinations (RZ/V2H Multi-OS Package Quick Start Guide):
#   remoteproc (default)          RZ_SRAM_REGION_ACCESS RZ_REMOTEPROC
#   CM33/CR8 from U-Boot          RZ_SRAM_REGION_ACCESS
#   CA55 cold boot, CA55 1.8GHz   RZ_CM33_FIRMWARE_LOAD RZ_CA55_CPU_CLOCKUP
#   CM33 cold boot                RZ_CM33_COLDBOOT
#
# Environment (optional):
#   CROSS_COMPILE  AArch64 cross compiler prefix (default: aarch64-linux-gnu-)
#   WORK_DIR       where sources are cloned and built (default: work/ next to this script)
#   OUT_DIR        where the IPL files are written (default: out/ next to this script)
#   TFA_GIT        TF-A git URL or local mirror
#   UBOOT_GIT      U-Boot git URL or local mirror
#   GIT_SHALLOW    1 (default): fetch only the pinned commits; 0: full history
#   JOBS           parallel make jobs (default: nproc)
#
# Host requirements: git, make, gcc, objcopy, OpenSSL headers (libssl-dev,
# for fiptool), and an AArch64 cross toolchain.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

CROSS_COMPILE=${CROSS_COMPILE:-aarch64-linux-gnu-}
WORK_DIR=$(realpath -m "${WORK_DIR:-${SCRIPT_DIR}/work}")
OUT_DIR=$(realpath -m "${OUT_DIR:-${SCRIPT_DIR}/out}")
JOBS=${JOBS:-$(nproc)}
GIT_SHALLOW=${GIT_SHALLOW:-1}

TFA_GIT=${TFA_GIT:-https://github.com/renesas-rz/rzg_trusted-firmware-a.git}
TFA_REV=3c83dd6f498574d7e8d029c4b1545f36c6d6e083
UBOOT_GIT=${UBOOT_GIT:-https://github.com/renesas-rz/renesas-u-boot-cip.git}
UBOOT_REV=8e0b7870026f1c7debdc503435fa51bfa3ae7006

# BL2 load address and S-record base addresses
BL2_BASE_ADDR=0x08103000
BL2_ADJUST_VMA=0x08101E00
FIP_ADJUST_VMA=0x0
# No eMMC on the RDK
BL2_BOOT_TARGET="spi esd"

FEATURES_FILE=${SCRIPT_DIR}/machine-features.conf
FEATURES_ARG=
FLASH_WRITER=${SCRIPT_DIR}/flash-writer/Flash_Writer_SCIF_RZV2H_DEV_INTERNAL_MEMORY.mot
# Kernel patch needed with RZ_CA55_CPU_CLOCKUP (CA55 OPPs for 1.8GHz)
CLOCKUP_KERNEL_PATCH=${SCRIPT_DIR}/kernel/0001-arm64-dts-renesas-r9a09g057-CA55-OPPs-for-1.8GHz-PLL.patch

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo; echo "==> $*"; }
usage() { sed -n '2,/^$/s/^# \{0,1\}//p' "$0"; exit "${1:-0}"; }

# Read the options from a file:
#   MACHINE_FEATURES:append = " RZ_xxx"   (lines starting with '#' are ignored)
read_features_file() {
	sed -n 's/^[[:space:]]*MACHINE_FEATURES:append[[:space:]]*=[[:space:]]*"\(.*\)".*/\1/p' "$1" | xargs
}

# Map the options to TF-A make options
tfa_options() {
	local f opts=
	for f in ${FEATURES}; do
		case "${f}" in
		RZ_SRAM_REGION_ACCESS) opts+=" ENABLE_SRAM_REGION_ACCESS_MCPU=1" ;;
		RZ_CM33_COLDBOOT)      opts+=" ENABLE_RZV2H_CM33_BOOT=1" ;;
		RZ_CM33_FIRMWARE_LOAD) opts+=" ENABLE_CM33_FIRMWARE_LOAD=1" ;;
		RZ_CA55_CPU_CLOCKUP)   opts+=" ENABLE_CA55_CLOCKUP=1" ;;
		RZ_REMOTEPROC)         ;; # kernel only
		*) die "unknown option '${f}'" ;;
		esac
	done
	echo "${opts# }"
}

has_feature() { [[ " ${FEATURES} " == *" $1 "* ]]; }

# Reject the combinations the Multi-OS Package does not support
check_features() {
	local f
	if has_feature RZ_REMOTEPROC; then
		for f in RZ_CM33_COLDBOOT RZ_CM33_FIRMWARE_LOAD RZ_CA55_CPU_CLOCKUP; do
			has_feature "${f}" && die "RZ_REMOTEPROC cannot be used with ${f}"
		done
	fi
	if has_feature RZ_CM33_COLDBOOT; then
		for f in RZ_CM33_FIRMWARE_LOAD RZ_CA55_CPU_CLOCKUP; do
			has_feature "${f}" && die "RZ_CM33_COLDBOOT cannot be used with ${f}"
		done
	fi
	if has_feature RZ_CA55_CPU_CLOCKUP && [ ! -f "${CLOCKUP_KERNEL_PATCH}" ]; then
		die "RZ_CA55_CPU_CLOCKUP: kernel patch ${CLOCKUP_KERNEL_PATCH} not found"
	fi
	if has_feature RZ_CA55_CPU_CLOCKUP && ! has_feature RZ_CM33_FIRMWARE_LOAD; then
		echo "WARNING: RZ_CA55_CPU_CLOCKUP is normally used with RZ_CM33_FIRMWARE_LOAD" >&2
	fi
	# CM33 cold boot and CM33 firmware load work from xSPI only
	if has_feature RZ_CM33_COLDBOOT || has_feature RZ_CM33_FIRMWARE_LOAD; then
		BL2_BOOT_TARGET="spi"
	fi
	return 0
}

# Clone (once) and check out a clean tree at the given revision.
# GIT_SHALLOW=1: only that commit is fetched; 0: full history.
checkout() {
	local url=$1 rev=$2 dir=$3
	if [ ! -d "${dir}/.git" ]; then
		if [ "${GIT_SHALLOW}" = 1 ]; then
			git init -q "${dir}"
			git -C "${dir}" remote add origin "${url}"
		else
			git clone --no-checkout "${url}" "${dir}"
		fi
	elif [ "${GIT_SHALLOW}" != 1 ] && \
	     [ "$(git -C "${dir}" rev-parse --is-shallow-repository)" = true ]; then
		git -C "${dir}" fetch --unshallow origin
	fi
	if ! git -C "${dir}" cat-file -e "${rev}^{commit}" 2>/dev/null; then
		if [ "${GIT_SHALLOW}" = 1 ]; then
			git -C "${dir}" fetch --depth 1 origin "${rev}"
		else
			git -C "${dir}" fetch origin "${rev}" || git -C "${dir}" fetch origin
		fi
	fi
	git -C "${dir}" checkout -q -f "${rev}"
	git -C "${dir}" clean -q -fdx
}

# Commit made on top of the patched tree; changes after it are local edits
BASELINE_MSG="build_ipl.sh: patches from series"

baseline() {
	git -C "$1" rev-list -1 --fixed-strings --grep="${BASELINE_MSG}" HEAD 2>/dev/null
}

# Stop if the tree has changes the next checkout would delete
check_local_changes() {
	local comp=$1 dir=$2 base changes
	[ -d "${dir}/.git" ] && git -C "${dir}" rev-parse -q --verify HEAD >/dev/null || return 0
	changes=$(git -C "${dir}" status --porcelain)
	base=$(baseline "${dir}")
	if [ -z "${base}" ]; then
		changes="(patched by an older build_ipl.sh: the series patches and local changes"$'\n'"cannot be told apart)"$'\n'"${changes}"
	elif [ "${base}" != "$(git -C "${dir}" rev-parse HEAD)" ]; then
		changes="$(git -C "${dir}" log --format='commit %h %s' "${base}..HEAD")"$'\n'"${changes}"
	fi
	changes=$(echo "${changes}" | sed '/^$/d')
	[ -n "${changes}" ] || return 0
	if [ "${FORCE}" = 1 ]; then
		echo "WARNING: ${dir}: discarding local changes (-F)" >&2
		return 0
	fi
	cat >&2 <<-EOM
	ERROR: ${dir} has local changes, a new checkout would delete them:
	$(echo "${changes}" | head -20 | sed 's/^/  /')

	Choose one:
	  - rebuild with them as they are:  $0 -k ...
	  - keep them as a patch, applied on every build:
	      git -C ${dir} add -A
	      git -C ${dir} commit -m "<subject>"
	      git -C ${dir} format-patch $(baseline "${dir}" | cut -c1-12)..HEAD -o ${SCRIPT_DIR}/${comp}/
	    add the file names to ${SCRIPT_DIR}/${comp}/series, then run with -F
	  - discard them:                   $0 -F ...
	EOM
	exit 1
}

src_step() {
	if [ "${KEEP}" = 1 ]; then echo "keep local sources (-k)"; else echo "checkout ${1:0:12} and patch"; fi
}

# Check out and patch a tree, or with -k, use it as it is
prepare_tree() {
	local comp=$1 url=$2 rev=$3 dir=$4
	if [ "${KEEP}" = 1 ]; then
		local base
		base=$(baseline "${dir}")
		[ -n "${base}" ] || die "${dir}: no tree patched by build_ipl.sh, run once without -k"
		echo "  keep ${dir} ($(git -C "${dir}" rev-list --count "${base}..HEAD") commits," \
			"$(git -C "${dir}" status --porcelain | wc -l) changed files since the patches)"
		return 0
	fi
	check_local_changes "${comp}" "${dir}"
	checkout "${url}" "${rev}" "${dir}"
	apply_series "${comp}" "${dir}"
	git -C "${dir}" add -A
	git -C "${dir}" -c user.name=build_ipl -c user.email=build_ipl@localhost \
		-c commit.gpgsign=false commit -q --allow-empty -m "${BASELINE_MSG}"
}

# Apply the patches listed in <component>/series, in order
apply_series() {
	local comp=$1 dir=$2 p
	while read -r p; do
		case "${p}" in ''|'#'*) continue ;; esac
		echo "  apply ${comp}/${p}"
		git -C "${dir}" apply --whitespace=nowarn "${SCRIPT_DIR}/${comp}/${p}"
	done < "${SCRIPT_DIR}/${comp}/series"
}

# Print a space-separated list as Markdown code spans, or "none"
md_list() {
	local w r=
	for w in $1; do r+="${r:+, }\`${w}\`"; done
	echo "${r:-none}"
}

# Write the build configuration and flash layout next to the IPL files
# (Markdown)
write_info() {
	local out=$1 machine=$2 tfa_board=$3 tfa_opts=$4
	local spi_bl2=0 spi_fip=60000 t
	if has_feature RZ_CM33_COLDBOOT; then
		spi_bl2=100000
		spi_fip=280000
	fi
	{
		echo "# IPL for ${machine}"
		echo
		echo "| Item | Value |"
		echo "|---|---|"
		echo "| Board | \`${machine}\` |"
		echo "| TF-A \`BOARD\` | \`${tfa_board}\` |"
		echo "| Options | $(md_list "${FEATURES}") |"
		echo "| TF-A options | $(md_list "${tfa_opts}") |"
		echo "| TF-A | \`${TFA_REV}\` |"
		echo "| U-Boot | \`${UBOOT_REV}\` (\`${machine}_defconfig\`) |"
		if [ "${KEEP}" = 1 ]; then
			echo "| Sources | **\`-k\`: work tree as is, may differ from the patches** |"
		else
			echo "| Sources | release commits + \`series\` patches |"
		fi
		echo "| Built | $(date '+%Y-%m-%d %H:%M') |"
		echo
		echo "## xSPI flash boot"
		echo
		echo "Flash Writer \`XLS2\`, addresses in hex:"
		echo
		echo "| File | Program Top Address | Qspi Save Address |"
		echo "|---|---|---|"
		echo "| \`bl2_bp_spi-${machine}.srec\` | \`8101E00\` | \`${spi_bl2}\` |"
		echo "| \`fip-${machine}.srec\` | \`0\` | \`${spi_fip}\` |"
		if has_feature RZ_CM33_FIRMWARE_LOAD; then
			echo "| CM33 firmware (S-record) | \`0\` | \`202000\` |"
		fi
		if has_feature RZ_CM33_COLDBOOT; then
			echo
			echo "CM33 firmware: build and write it with the CM33 FSP project"
			echo "(Multi-OS Package Quick Start Guide, chapter 6.3)."
		fi
		if [[ " ${BL2_BOOT_TARGET} " == *" esd "* ]]; then
			echo
			echo "## SD boot"
			echo
			echo "Raw writes; keep the partition table in sector 0:"
			echo
			echo "\`\`\`sh"
			echo "dd if=bl2_bp_esd-${machine}.bin of=/dev/sdX bs=512 skip=1 seek=1 conv=notrunc"
			echo "dd if=fip-${machine}.bin        of=/dev/sdX bs=512 seek=768 conv=notrunc"
			echo "\`\`\`"
		fi
		echo
		echo "## boot/uEnv.txt"
		echo
		if has_feature RZ_REMOTEPROC; then
			echo "Set \`enable_overlay_remoteproc=1\` (remoteproc DT overlay)."
		else
			echo "Do **not** set \`enable_overlay_remoteproc\` (remoteproc DT overlay)."
		fi
		if has_feature RZ_CA55_CPU_CLOCKUP; then
			echo
			echo "## Kernel"
			echo
			echo "**Required:** CA55 runs at 1.8GHz. Apply \`$(basename "${CLOCKUP_KERNEL_PATCH}")\`"
			echo "(in this directory) to the kernel and rebuild the device trees, or cpufreq"
			echo "uses the OPPs of 1.7GHz:"
			echo
			echo "\`\`\`sh"
			echo "git -C <linux-rz> am $(basename "${CLOCKUP_KERNEL_PATCH}")"
			echo "\`\`\`"
		fi
		echo
		echo "## Files"
		echo
		echo "| File | Use |"
		echo "|---|---|"
		for t in ${BL2_BOOT_TARGET}; do
			echo "| \`bl2_bp_${t}-${machine}.srec\` / \`.bin\` | BL2, $([ "${t}" = spi ] && echo "xSPI flash boot" || echo "SD boot") |"
		done
		echo "| \`fip-${machine}.srec\` / \`.bin\` | BL31 + U-Boot |"
		[ -f "${FLASH_WRITER}" ] && echo "| \`$(basename "${FLASH_WRITER}")\` | Flash Writer |"
		has_feature RZ_CA55_CPU_CLOCKUP && \
			echo "| \`$(basename "${CLOCKUP_KERNEL_PATCH}")\` | kernel patch, CA55 OPPs for 1.8GHz |"
		return 0
	} > "${out}/ipl-info.md"
}

build_board() {
	local ver=$1 tfa_board machine tfa_opts
	case "${ver}" in
	ver1)   tfa_board=rdk_1 ;;
	ver101) tfa_board=rdk_101 ;;
	*) die "unknown board '${ver}' (use ver1 or ver101)" ;;
	esac
	machine=rzv2h-rdk-${ver}
	tfa_opts=$(tfa_options)

	local src=${WORK_DIR}/${machine}
	local tfa=${src}/trusted-firmware-a uboot=${src}/u-boot
	local out=${OUT_DIR}/${machine}
	mkdir -p "${src}"

	log "[${machine}] Options: ${FEATURES}"
	echo "  TF-A options: ${tfa_opts:-none}"

	log "[${machine}] U-Boot: $(src_step "${UBOOT_REV}")"
	prepare_tree u-boot "${UBOOT_GIT}" "${UBOOT_REV}" "${uboot}"

	log "[${machine}] TF-A: $(src_step "${TFA_REV}")"
	prepare_tree trusted-firmware-a "${TFA_GIT}" "${TFA_REV}" "${tfa}"

	# Only now that the sources are ready: replace the previous output
	rm -rf "${out}" && mkdir -p "${out}"

	log "[${machine}] U-Boot: build ${machine}_defconfig"
	make -C "${uboot}" CROSS_COMPILE="${CROSS_COMPILE}" O=build "${machine}_defconfig"
	make -C "${uboot}" CROSS_COMPILE="${CROSS_COMPILE}" O=build -j"${JOBS}" u-boot.bin

	# TF-A does not rebuild when only the make options change
	rm -rf "${tfa}/build"

	log "[${machine}] TF-A: build BOARD=${tfa_board} (bl2, fip)"
	# shellcheck disable=SC2086
	make -C "${tfa}" CROSS_COMPILE="${CROSS_COMPILE}" HOSTCC=gcc E=0 -j"${JOBS}" \
		PLAT=v2h BOARD="${tfa_board}" ${tfa_opts} \
		BL33="${uboot}/build/u-boot.bin" bl2 fip

	log "[${machine}] bptool"
	make -C "${tfa}/tools/renesas/rz_boot_param" HOSTCC=gcc

	log "[${machine}] Pack IPL"
	local rel=${tfa}/build/v2h/release t
	for t in ${BL2_BOOT_TARGET}; do
		"${tfa}/tools/renesas/bptool" "${rel}/bl2.bin" "${out}/bp_${t}.bin" "${BL2_BASE_ADDR}" "${t}"
		cat "${out}/bp_${t}.bin" "${rel}/bl2.bin" > "${out}/bl2_bp_${t}-${machine}.bin"
		rm -f "${out}/bp_${t}.bin"
		objcopy -I binary -O srec --adjust-vma="${BL2_ADJUST_VMA}" --srec-forceS3 \
			"${out}/bl2_bp_${t}-${machine}.bin" "${out}/bl2_bp_${t}-${machine}.srec"
	done
	cp "${rel}/fip.bin" "${out}/fip-${machine}.bin"
	objcopy -I binary -O srec --adjust-vma="${FIP_ADJUST_VMA}" --srec-forceS3 \
		"${out}/fip-${machine}.bin" "${out}/fip-${machine}.srec"

	[ -f "${FLASH_WRITER}" ] && cp "${FLASH_WRITER}" "${out}/"
	has_feature RZ_CA55_CPU_CLOCKUP && cp "${CLOCKUP_KERNEL_PATCH}" "${out}/"
	write_info "${out}" "${machine}" "${tfa_board}" "${tfa_opts}"

	log "[${machine}] Done: ${out}"
	ls -l "${out}"
	echo; cat "${out}/ipl-info.md"
	if has_feature RZ_CA55_CPU_CLOCKUP; then
		echo
		echo "WARNING: RZ_CA55_CPU_CLOCKUP: apply $(basename "${CLOCKUP_KERNEL_PATCH}")" >&2
		echo "         (in ${out}) to the kernel, CA55 runs at 1.8GHz" >&2
	fi
}

KEEP=0
FORCE=0
while getopts "c:f:kFh" opt; do
	case "${opt}" in
	c) FEATURES_FILE=${OPTARG} ;;
	f) FEATURES_ARG=${OPTARG} ;;
	k) KEEP=1 ;;
	F) FORCE=1 ;;
	h) usage 0 ;;
	*) usage 1 ;;
	esac
done
shift $((OPTIND - 1))
[ "${KEEP}${FORCE}" != 11 ] || die "-k and -F cannot be used together"

[ $# -ge 1 ] || set -- ver101
command -v "${CROSS_COMPILE}gcc" >/dev/null || die "${CROSS_COMPILE}gcc not found (set CROSS_COMPILE)"

if [ -n "${FEATURES_ARG}" ]; then
	FEATURES=$(echo "${FEATURES_ARG}" | xargs)
else
	[ -f "${FEATURES_FILE}" ] || die "features file '${FEATURES_FILE}' not found"
	FEATURES=$(read_features_file "${FEATURES_FILE}")
fi
tfa_options >/dev/null   # validate the option names early
check_features

for b in "$@"; do
	build_board "${b}"
done
