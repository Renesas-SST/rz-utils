# kernel-modules

Out-of-tree kernel modules for the RZ/V2H RDK Ubuntu image, matching the `extra/` module set
Renesas ships in the prebuilt kernel `.deb` (`mali_kbase`, `mmngr`, `mmngrbuf`, `uvcs_drv`,
`vspm`, `vspm_if`). These are **not** built as part of the kernel tree itself — `rz-utils`'
`build_kernel.sh modules`/`modules-install` only covers `CONFIG_X=m` in-tree modules.

One self-contained script per module, no shared table to keep in sync:

```
kernel-modules/
├── common_modules.sh    # shared fetch/patch/build/install helpers, sourced by every script
├── kernel_modules_all.sh # runs all 6 build_*.sh scripts in dependency order, prints a summary
├── build_mmngr.sh
├── build_mmngrbuf.sh
├── build_vspm.sh
├── build_vspm_if.sh     # depends on vspm being built first
├── build_mali_kbase.sh  # needs a local copy of the proprietary Mali DDK tarball (see below)
├── build_uvcs_drv.sh    # Codec, needs a local copy of the proprietary UVCS tarball (see below)
└── patches/<name>/      # per-module patch series (series file + .patch files)
```

## Usage

Each script takes the same subcommands (also reachable as `./main_build.sh kernel-modules <sub_command> [<module>]`):

```bash
cd local-build-scripts/kernel-modules
./build_mmngr.sh fetch      # clone/extract source + apply patches
./build_mmngr.sh reset-src  # discard local edits in the source and re-apply the patches
./build_mmngr.sh all        # fetch + build (default if no argument given)
./build_mmngr.sh install    # build + install into KERNEL_MODULES_OUTPUT_DIR, refresh depmod
./build_mmngr.sh clean      # make clean in the module's build dir
```

Prerequisite: the kernel pointed at by `config.ini`'s `KERNEL_DIR` must already be built
(`Module.symvers` present) — external modules link against it:

```bash
cd local-build-scripts
./main_build.sh kernel modules-install
```

`vspm_if` additionally needs `vspm` built first (it links against `vspm`'s `Module.symvers`,
staged as `$KERNEL_DIR/include/vspm.symvers`):

```bash
./build_vspm.sh all
./build_vspm_if.sh all
```

`kernel_modules_all.sh` runs all 6 scripts in that dependency order for you (`fetch`/`reset-src`/
`all`/`install`/`clean`, same subcommands), then prints an OK/FAILED summary per module:

```bash
./kernel_modules_all.sh install
```

`mali_kbase` and `uvcs_drv` need proprietary tarballs that are not committed to this repo.
Download them from the RZ/V2H AI SDK v8.00 and put them in `rz-utils/vendor/`; see
[`vendor/README.md`](../../vendor/README.md) for the exact files, SDK paths and checksums.

- `mali_kbase`: `vendor/mali-g31_km_v1.3.0.tar.gz` (override with `MALI_DDK_TAR=...`)
- `uvcs_drv`: `vendor/uvcs_kernel_package_v4.3.4.0.tar.bz2` (override with `UVCS_TAR=...`)