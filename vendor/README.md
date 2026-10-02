# vendor/

Proprietary packages needed by the build scripts. They are **not** part of this
repository (ignored by `.gitignore`); download them yourself and put them here.

| File | Used by | sha256 |
|---|---|---|
| `uvcs_kernel_package_v4.3.4.0.tar.bz2` | `local-build-scripts/kernel-modules/build_uvcs_drv.sh` | `a719268bbab3ce13f078158d3ee9b3e7ad1d86c7c04ab8e8ff776e540ecb0738` |
| `mali-g31_km_v1.3.0.tar.gz` | `local-build-scripts/kernel-modules/build_mali_kbase.sh` | `30d9625e33ab4a52ab9c995bf0e218d65cc909c320bf85c0e60f3572962fb389` |

## Where to get them

### From the RZ/V2H AI SDK v8.00

1. Log in to renesas.com and download the RZ/V2H AI SDK v8.00 source package:
   <https://www.renesas.com/en/document/sws/rzv2h-ai-sdk-v800?r=25470141>
2. Extract it. The files are inside the `meta-rz-features` Yocto layer:

   ```
   meta-rz-features/meta-rz-codecs/recipes-kernel/kernel-module-uvcs-drv/files/uvcs_kernel_package_v4.3.4.0.tar.bz2
   meta-rz-features/meta-rz-graphics/recipes-kernel/kernel-module-mali/files/mali-g31_km_v1.3.0.tar.gz
   ```

3. Copy both into this directory:

   ```bash
   cp <sdk>/meta-rz-features/meta-rz-codecs/recipes-kernel/kernel-module-uvcs-drv/files/uvcs_kernel_package_v4.3.4.0.tar.bz2 vendor/
   cp <sdk>/meta-rz-features/meta-rz-graphics/recipes-kernel/kernel-module-mali/files/mali-g31_km_v1.3.0.tar.gz vendor/
   ```

## Check

```bash
cd vendor && sha256sum -c <<'SUMS'
a719268bbab3ce13f078158d3ee9b3e7ad1d86c7c04ab8e8ff776e540ecb0738  uvcs_kernel_package_v4.3.4.0.tar.bz2
30d9625e33ab4a52ab9c995bf0e218d65cc909c320bf85c0e60f3572962fb389  mali-g31_km_v1.3.0.tar.gz
SUMS
```

Each script also accepts an explicit path instead: `UVCS_TAR=...`, `MALI_DDK_TAR=...`
