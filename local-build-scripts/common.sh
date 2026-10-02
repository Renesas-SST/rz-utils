#!/bin/bash

# Default cross-compile vars so build_<target>.sh also works standalone.
export ARCH="${ARCH:-arm64}"
export CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}"

# Clone <repo>@<branch> into <dir> if missing; no-op if already a git repo (never pulls/resets).
ensure_src_dir() {
	local dir="$1" repo="$2" branch="$3" label="$4"

	if [ -d "${dir}/.git" ]; then
		return 0
	fi

	if [ -e "${dir}" ]; then
		echo "Error: ${dir} exists but is not a git repository (no .git found)." >&2
		echo "Refusing to auto-clone ${label} into it -- please check/remove this directory manually." >&2
		exit 1
	fi

	if [ -z "${repo}" ] || [ -z "${branch}" ]; then
		echo "There is no ${label} source at ${dir}, and no repo/branch configured in config.ini to clone it automatically." >&2
		echo "Please clone it manually, or set the matching *_REPO/*_BRANCH variables in config.ini." >&2
		exit 1
	fi

	echo "${label} source not found at ${dir}, cloning ${repo} (branch ${branch})..."
	git clone --branch "${branch}" "${repo}" "${dir}"
}

# Like ensure_src_dir() but pins to a commit (checked out with -f).
ensure_src_dir_at_rev() {
	local dir="$1" repo="$2" rev="$3" label="$4"
	local have

	if [ -z "${repo}" ] || [ -z "${rev}" ]; then
		echo "There is no ${label} source at ${dir}, and no repo/rev configured in config.ini to clone it automatically." >&2
		echo "Please clone it manually, or set the matching *_REPO/*_SRCREV variables in config.ini." >&2
		exit 1
	fi

	if [ ! -d "${dir}/.git" ]; then
		if [ -e "${dir}" ]; then
			echo "Error: ${dir} exists but is not a git repository (no .git found)." >&2
			echo "Refusing to auto-clone ${label} into it -- please check/remove this directory manually." >&2
			exit 1
		fi
		echo "${label} source not found at ${dir}, cloning ${repo}..."
		git clone -q "${repo}" "${dir}"
	fi

	# Repo URL changed since last clone (e.g. fork move) -- repoint origin instead of erroring.
	local origin_url
	origin_url="$(git -C "${dir}" remote get-url origin 2>/dev/null)"
	if [ -n "${origin_url}" ] && [ "${origin_url}" != "${repo}" ]; then
		echo "${label}: origin was ${origin_url}, repointing to ${repo}"
		git -C "${dir}" remote set-url origin "${repo}"
		git -C "${dir}" fetch -q origin
	fi

	have="$(git -C "${dir}" rev-parse HEAD 2>/dev/null)"
	if [ "${have}" = "${rev}" ]; then
		echo "${label}: already at ${rev}"
		return 0
	fi

	if ! git -C "${dir}" cat-file -e "${rev}^{commit}" 2>/dev/null; then
		git -C "${dir}" fetch -q --all --tags
	fi
	echo "${label}: checking out ${rev}"
	git -C "${dir}" checkout -q -f "${rev}"
}

# Reset <dir> to a pristine checkout of its current commit (no re-clone).
clean_repo() {
	local dir="$1" label="$2"

	if [ ! -d "${dir}/.git" ]; then
		echo "Error: ${dir} is not a git repository (no .git found) -- nothing to clean." >&2
		exit 1
	fi

	echo "${label}: resetting to a clean checkout of $(git -C "${dir}" rev-parse --short HEAD)"
	git -C "${dir}" reset -q
	git -C "${dir}" checkout -q .
	git -C "${dir}" clean -q -fdx
}

_usage="
Usage:

$ ./main_build.sh <target_build> [<sub_command>] [<module>]

Builds the software for the RZ/V2H RDK (ver1 and ver101), the only supported board.

Option:
    <target_build>:
        1. kernel
            Build the Linux kernel (KERNEL_DIR, KERNEL_BRANCH or KERNEL_SRCREV;
            optional KERNEL_VARIANT=<name> merges kernel-config/<name>.config, e.g. preempt-rt)
            <sub_command>:
                - clean
                - distclean
                - reset-src
                - defconfig
                - menuconfig
                - image
                - dtbs
                - modules
                - modules-install
                - all

        2. kernel-modules
            Out-of-tree kernel modules (mmngr, mmngrbuf, vspm, vspm_if, mali_kbase,
            uvcs_drv), the extra/ set of the kernel .deb. Needs the kernel built first
            (kernel modules-install). Without <module>, all of them in dependency order
            (kernel-modules/kernel_modules_all.sh); see kernel-modules/README.md.
            <sub_command>:
                - fetch
                - reset-src
                - all
                - install (into KERNEL_MODULES_OUTPUT_DIR)
                - clean
            <module>: optional, one of the above names (kernel-modules/build_<module>.sh)

        3. ipl
            IPL (BL2 + FIP with BL31/U-Boot) for the RZ/V2H RDK boards in IPL_BOARDS
            (ipl_build/build_ipl.sh; sources in IPL_WORK_DIR, output in IPL_OUT_DIR).
            Multi-OS options: IPL_FEATURES_FILE / IPL_FEATURES, see ipl_build/README.md.
            <sub_command>:
                - all (default): check out, patch and build; stops if IPL_WORK_DIR has
                  local changes
                - keep: rebuild IPL_WORK_DIR as it is, with local changes
                - force: discard local changes in IPL_WORK_DIR, patch and build again
                - clean: remove IPL_OUT_DIR (sources are kept)

        4. all
            kernel all, kernel-modules install, ipl all
            <sub_command>: None

        5. clean-all
            kernel distclean, kernel-modules clean, ipl clean
            <sub_command>: None

For example:
    Build the kernel (Image, device trees, modules) and install the modules:
        $ ./main_build.sh kernel all

    Build and install all out-of-tree modules, or only one:
        $ ./main_build.sh kernel-modules install
        $ ./main_build.sh kernel-modules all vspm

    Build the IPL for RDK ver1 and ver101 in CM33 cold boot mode:
        $ IPL_BOARDS=\"ver1 ver101\" IPL_FEATURES=RZ_CM33_COLDBOOT ./main_build.sh ipl

Note: Before executing the build, please make sure that you have updated the configuration file: config.ini at the top of the build scripts folder.
      Kernel modules install output path is configured by KERNEL_MODULES_OUTPUT_DIR in config.ini.
      In the remoteproc IPL mode (default), set enable_overlay_remoteproc=1 in boot/uEnv.txt
      (see ipl_build/uEnv.txt); leave it unset in the other modes.
"
# Help message
show_help() {
	echo 'Error: Invalid Syntax!'
	echo "${_usage}"
	exit 1
}
