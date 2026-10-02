# RZ/V2H RDK IPL (ver1 / ver101)

Patches and tools to build the IPL (BL2, and a FIP with BL31 and U-Boot) for the two
RZ/V2H RDK boards from source.

| Board | RAM | Ethernet PHY reset | TF-A `BOARD` | U-Boot defconfig | Kernel DT loaded by U-Boot |
|---|---|---|---|---|---|
| RDK ver1 | 16GB LPDDR4X (same as RZ/V2H EVK) | none (RC power-on reset) | `rdk_1` | `rzv2h-rdk-ver1_defconfig` | `boot/rzv2h-rdk-ver1.dtb` |
| RDK ver101 | 8GB Foresee LPDDR4X (4GB per channel) | P47 | `rdk_101` | `rzv2h-rdk-ver101_defconfig` | `boot/rzv2h-rdk-ver101.dtb` |

## Contents

```
trusted-firmware-a/     TF-A patches + series (apply order)
u-boot/                 U-Boot patches + series (apply order)
kernel/                 kernel patch for RZ_CA55_CPU_CLOCKUP (CA55 OPPs for 1.8GHz)
flash-writer/           Flash_Writer_SCIF_RZV2H_DEV_INTERNAL_MEMORY.mot (prebuilt, runs from
                        internal RAM, works on both boards)
machine-features.conf   IPL options (used by build_ipl.sh)
build_ipl.sh            builds everything below in one go
uEnv.txt                sample boot/uEnv.txt (DT overlays, rootfs on SSD)
```

| Component | Repository | Commit |
|---|---|---|
| TF-A | https://github.com/renesas-rz/rzg_trusted-firmware-a.git | `3c83dd6f498574d7e8d029c4b1545f36c6d6e083` |
| U-Boot | https://github.com/renesas-rz/renesas-u-boot-cip.git | `8e0b7870026f1c7debdc503435fa51bfa3ae7006` |

## Options

The options and the modes below follow the RZ/V2H Multi-OS Package Quick Start Guide
(R01QS0077EJ0420). The default is `RZ_SRAM_REGION_ACCESS` and `RZ_REMOTEPROC`.

| Option | Default | TF-A make option | Effect on the IPL |
|---|---|---|---|
| `RZ_SRAM_REGION_ACCESS` | on | `ENABLE_SRAM_REGION_ACCESS_MCPU=1` | MCPU SRAM region set to unprivileged (accessible from Linux) |
| `RZ_REMOTEPROC` | on | – | No change to the IPL. Set `enable_overlay_remoteproc=1` in `boot/uEnv.txt` (see below) |
| `RZ_CM33_COLDBOOT` | off | `ENABLE_RZV2H_CM33_BOOT=1` | CM33 cold boot: CM33 boots first from xSPI, then starts CA55. BL2 and FIP move to other xSPI addresses (see Flash) |
| `RZ_CM33_FIRMWARE_LOAD` | off | `ENABLE_CM33_FIRMWARE_LOAD=1` | BL2 loads the CM33 firmware from xSPI and starts CM33 (xSPI boot only) |
| `RZ_CA55_CPU_CLOCKUP` | off | `ENABLE_CA55_CLOCKUP=1` | CA55 runs at 1.8GHz. Apply `kernel/0001-*-CA55-OPPs-for-1.8GHz-PLL.patch` to the kernel (see below) |

Supported combinations (build_ipl.sh rejects the others):

| Mode | Options | Boot |
|---|---|---|
| Remoteproc (default) | `RZ_SRAM_REGION_ACCESS RZ_REMOTEPROC` | xSPI or SD |
| CM33/CR8 started from U-Boot | `RZ_SRAM_REGION_ACCESS` | xSPI or SD |
| CA55 cold boot with CA55 at 1.8GHz | `RZ_CM33_FIRMWARE_LOAD RZ_CA55_CPU_CLOCKUP` | xSPI |
| CM33 cold boot | `RZ_CM33_COLDBOOT` | xSPI |

- `RZ_REMOTEPROC` cannot be combined with `RZ_CM33_COLDBOOT`, `RZ_CM33_FIRMWARE_LOAD` or
  `RZ_CA55_CPU_CLOCKUP`.
- `RZ_CM33_COLDBOOT` cannot be combined with `RZ_CM33_FIRMWARE_LOAD` or `RZ_CA55_CPU_CLOCKUP`.
- With `RZ_CM33_COLDBOOT` or `RZ_CM33_FIRMWARE_LOAD`, only the xSPI BL2 is built.

To select the options, either:
- edit `machine-features.conf` and (un)comment the `MACHINE_FEATURES:append` lines; or
- pass `-c <file>` to use another file; or
- pass `-f "<list>"` to override the file.

## Kernel patch for CA55 1.8GHz

With `RZ_CA55_CPU_CLOCKUP`, PLLCA55 runs at 1.8GHz instead of 1.7GHz, and the CA55 OPP table
of the kernel (`r9a09g057.dtsi`) must match: 1.8GHz, 900, 450 and 225MHz.
`kernel/0001-arm64-dts-renesas-r9a09g057-CA55-OPPs-for-1.8GHz-PLL.patch` does that. It is not in the kernel branch
because it is wrong in the other modes. A build with `RZ_CA55_CPU_CLOCKUP` copies it to the output
directory and notes it in `ipl-info.md`. Apply it and rebuild the device trees:

```sh
git -C <linux-rz> am <path>/0001-arm64-dts-renesas-r9a09g057-CA55-OPPs-for-1.8GHz-PLL.patch
```

## Build with the script

Host requirements:
- git, make, gcc and objcopy;
- OpenSSL headers (`libssl-dev`), needed by fiptool;
- an AArch64 cross toolchain, for example the Arm GNU Toolchain `aarch64-none-linux-gnu-` or
  Ubuntu `gcc-aarch64-linux-gnu`.

```sh
cd local-build-scripts/ipl_build
export CROSS_COMPILE=aarch64-linux-gnu-

./build_ipl.sh                                                # ver101 (default), machine-features.conf
./build_ipl.sh ver1 ver101                                   # both boards
./build_ipl.sh -c my-features.conf ver101                    # another options file
./build_ipl.sh -f "RZ_CM33_FIRMWARE_LOAD RZ_CA55_CPU_CLOCKUP" ver101
./build_ipl.sh -k                                            # rebuild work/ as is (local edits)
./build_ipl.sh -F                                            # discard local edits, re-patch
./build_ipl.sh -h                                            # help
```

The output goes to `out/rzv2h-rdk-<ver>/`, and the sources are kept in
`work/rzv2h-rdk-<ver>/{u-boot,trusted-firmware-a}`.

### Changing U-Boot or TF-A

Each run checks out the release commits again and applies the patches in `u-boot/` and
`trusted-firmware-a/` (in `series` order), then commits the result as
`build_ipl.sh: patches from series`. Everything after that commit (edits, new files, your own
commits) counts as a local change:
- Without `-k` or `-F`, the script stops if a tree has local changes, lists them and does
  not touch `out/`. Nothing is deleted.
- `-k` builds the trees in `work/` as they are. `ipl-info.md` then says so, because that
  build cannot be reproduced from the patches.
- To keep a change for every build, turn it into a patch:

  ```sh
  cd work/rzv2h-rdk-ver101/u-boot
  git add -A && git commit -m "<subject>"
  git format-patch <baseline>..HEAD -o ../../../u-boot/   # <baseline> is in the error message
  ```

  Add the new file names to `u-boot/series`, then run once with `-F`.
- `-F` discards the local changes and patches the trees again.

| File | Use |
|---|---|
| `bl2_bp_spi-rzv2h-rdk-<ver>.srec` / `.bin` | BL2 for xSPI flash boot |
| `bl2_bp_esd-rzv2h-rdk-<ver>.srec` / `.bin` | BL2 for SD boot (not built with `RZ_CM33_COLDBOOT` / `RZ_CM33_FIRMWARE_LOAD`) |
| `fip-rzv2h-rdk-<ver>.srec` / `.bin` | BL31 + U-Boot |
| `Flash_Writer_SCIF_RZV2H_DEV_INTERNAL_MEMORY.mot` | Flash Writer |
| `ipl-info.md` | board, options used, and the flash offsets for this build (Markdown) |

Optional environment variables:
- `WORK_DIR` and `OUT_DIR` set the source and output directories.
- `JOBS` sets the number of parallel make jobs.
- `TFA_GIT` and `UBOOT_GIT` point to a local git mirror instead of GitHub.
- `GIT_SHALLOW=0` clones TF-A and U-Boot with their full history; by default (`1`) only the
  pinned commits are fetched.

## Flash

### xSPI flash

Follow the [RDK Quick Setup Guide – Option 2: xSPI Boot Mode](https://renesas-rdk.github.io/rzv2h_rdk_documentation/latest/chapter-1/quick_setup_guide.html#option-2-xspi-boot-mode)
to boot the board in SCIF download mode and start
`Flash_Writer_SCIF_RZV2H_DEV_INTERNAL_MEMORY.mot`. Then write each file with `XLS2`
(Program Top Address / Qspi Save Address, in hex). The addresses depend on the mode:

| Mode | `bl2_bp_spi-rzv2h-rdk-<ver>.srec` | `fip-rzv2h-rdk-<ver>.srec` | CM33 firmware (S-record) |
|---|---|---|---|
| Remoteproc (default), CM33/CR8 from U-Boot | `8101E00` / `0` | `0` / `60000` | – |
| CA55 cold boot with 1.8GHz (`RZ_CM33_FIRMWARE_LOAD`) | `8101E00` / `0` | `0` / `60000` | `0` / `202000` |
| CM33 cold boot (`RZ_CM33_COLDBOOT`) | `8101E00` / `100000` | `0` / `280000` | built and written with the CM33 FSP project (Multi-OS guide, chapter 6.3) |

`ipl-info.md` lists the addresses for each build.

### SD card (eSD boot)

Only for the remoteproc and CM33/CR8-from-U-Boot modes. BL2 and the FIP go into the raw area
before the first partition:
- `bl2_bp_esd` from sector 0;
- the FIP at sector 768, i.e. 0x60000.

`bl2_bp_esd` holds redundant copies of the boot parameter in sectors 0–6. Skip sector 0
so the partition table is kept:

```sh
dd if=bl2_bp_esd-rzv2h-rdk-<ver>.bin of=/dev/sdX bs=512 skip=1 seek=1 conv=notrunc
dd if=fip-rzv2h-rdk-<ver>.bin        of=/dev/sdX bs=512 seek=768 conv=notrunc
```

The first partition must start after the IPL area, at 1MiB or later.

## Notes

- Use the IPL that matches the board. A ver101 IPL on a ver1 board (or the other way
  round) programs the wrong DDR configuration.
- U-Boot imports `boot/uEnv.txt` from mmc0 (microSD) partition 2 and applies the DT overlays
  enabled there. It then boots `boot/Image` with `boot/<board>.dtb` and `root=${rootdev}`.
  See `uEnv.txt`.
- The kernel remoteproc nodes (`cm33`, `cr8_0`, `cr8_1`) and their OpenAMP carveouts
  (`vdev0*` at 0x43000000–0x434fffff) are in the overlay `rzv2h-rdk-remoteproc.dtbo`, not in
  the base RDK DTs. Set `enable_overlay_remoteproc=1` in `boot/uEnv.txt` for the remoteproc
  mode only. In the other modes leave it unset: there the IPL, U-Boot or CM33 starts the
  remote cores, a remoteproc `stop`/`start` would reset them and wipe their memory, and
  without `RZ_SRAM_REGION_ACCESS` the MCPU SRAM accesses of the driver abort.
- U-Boot has no RZ/V2H PCIe/NVMe or USB3 (xHCI) driver. To use an SSD for the rootfs, keep
  the kernel on microSD and set `rootdev` in uEnv.txt.