# local-build-scripts

Build scripts for the RZ/V2H RDK (ver1 16GB and ver101 8GB), the only supported board: the
Linux kernel, the out-of-tree kernel modules and the IPL (BL2 + FIP with BL31/U-Boot).

## Hierarchy

```
.
├── main_build.sh        # entry point: kernel, kernel-modules, ipl, all, clean-all
├── build_kernel.sh      # Linux kernel (KERNEL_DIR)
├── common.sh            # shared helpers and the main_build.sh usage text
├── config.ini           # build settings, read by every script
├── kernel-config/       # optional kernel config fragments (KERNEL_VARIANT=<name>)
│   └── preempt-rt.config
├── kernel-modules/      # out-of-tree modules: mmngr, mmngrbuf, vspm, vspm_if, mali_kbase,
│                        # uvcs_drv (see kernel-modules/README.md)
└── ipl_build/           # IPL for RDK ver1/ver101 with the Multi-OS options
                         # (see ipl_build/README.md)
```

## Prerequisites

Ubuntu 24.04 host machine or Docker container with Ubuntu 24.04 image.

```bash
sudo apt update
sudo apt install \
    build-essential \
    gcc-aarch64-linux-gnu \
    bc \
    bison \
    flex \
    libssl-dev \
    device-tree-compiler \
    libgnutls28-dev
```

`mali_kbase` and `uvcs_drv` also need proprietary tarballs in `rz-utils/vendor/`, see
[`vendor/README.md`](../vendor/README.md).

## Usage

Run the scripts from this directory.

```
$ ./main_build.sh <target_build> [<sub_command>] [<module>]

    kernel <sub_command>
        clean | distclean | reset-src | defconfig | menuconfig | image | dtbs |
        modules | modules-install | all

    kernel-modules <sub_command> [<module>]
        fetch | reset-src | all | install | clean
        Needs the kernel built first. Without <module>, all modules in dependency
        order; <module> is one of mmngr, mmngrbuf, vspm, vspm_if, mali_kbase, uvcs_drv.

    ipl [<sub_command>]
        all (default) | keep | force | clean
        all:   check out TF-A/U-Boot, apply the ipl_build patches and build; stops if
               IPL_WORK_DIR has local changes
        keep:  rebuild IPL_WORK_DIR as it is, with local changes
        force: discard local changes in IPL_WORK_DIR, patch and build again
        clean: remove IPL_OUT_DIR (sources are kept)

    all         kernel all, kernel-modules install, ipl all
    clean-all   kernel distclean, kernel-modules clean, ipl clean
```

Examples:

```bash
./main_build.sh kernel all                    # Image, DTBs/overlays, modules + modules-install
./main_build.sh kernel-modules install        # all out-of-tree modules
./main_build.sh kernel-modules all vspm       # one module
./main_build.sh ipl                           # IPL for IPL_BOARDS (default ver101)
IPL_BOARDS="ver1 ver101" IPL_FEATURES=RZ_CM33_COLDBOOT ./main_build.sh ipl
KERNEL_VARIANT=preempt-rt ./main_build.sh kernel all
```

`./main_build.sh` without arguments prints the full help. Each script also runs on its own:
`./build_kernel.sh <sub_command>`, `kernel-modules/build_<module>.sh <sub_command>`,
`ipl_build/build_ipl.sh [ver1|ver101]`.

The IPL default mode is remoteproc: set `enable_overlay_remoteproc=1` in `boot/uEnv.txt`
(see `ipl_build/uEnv.txt`), and leave it unset in the other Multi-OS modes.

## config.ini

Review it before a build. Every setting can also be overridden from the environment.

| Setting | Use |
|---|---|
| `WORKDIR` | base directory of the sources and outputs below (default `/workspace/workspace`) |
| `KERNEL_DIR` | Linux kernel source, cloned from `KERNEL_REPO` / `KERNEL_BRANCH` if missing (never pulled or reset afterwards) |
| `KERNEL_SRCREV` | optional: pin the kernel to a commit (checked out with `-f`, local changes are lost) |
| `KERNEL_VARIANT` | optional: merge `kernel-config/<name>.config` on top of `renesas_defconfig`, e.g. `preempt-rt` |
| `EXT_MODULES_SRC_DIR` | sources of the out-of-tree modules |
| `KERNEL_MODULES_OUTPUT_DIR` | install directory of the in-tree and out-of-tree modules |
| `IPL_BOARDS` | IPL boards: `ver1` and/or `ver101` (default `ver101`) |
| `IPL_WORK_DIR` / `IPL_OUT_DIR` | TF-A/U-Boot sources and IPL output |
| `IPL_FEATURES_FILE` / `IPL_FEATURES` | Multi-OS options file, or the options themselves (default `ipl_build/machine-features.conf`) |