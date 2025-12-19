# `bin/linux/` – Linux Host Tools

This folder contains the Linux-compatible versions of firmware build utilities.
They are used automatically when the build system detects a Linux host.

## Contents

| Tool               | Platform Use Case                | Purpose |
|--------------------|----------------------------------|---------|
| `bpgen`            | RZ/G2L, RZ/V2L, RZ/V2H           | Generates a boot parameter binary (`bl2_bp_<board>.bin`) used by Boot ROM to load BL2|
| `fiptool`          | All                              | Creates and manipulates Firmware Image Packages (FIP) for ARM Trusted Firmware. Uses embedded RPATH (`$ORIGIN`) to automatically find bundled OpenSSL library. |

**Note**: `$ORIGIN` is a special linker variable that represents the directory containing the executable. When `fiptool` is run, it looks for `libcrypto.so.1.1` in the same directory where the `fiptool` binary is located.

### Directory Structure

```
linux/
├── bpgen                    # Boot parameter generator (static binary)
├── fiptool                  # FIP tool binary (with RPATH=$ORIGIN)
├── libcrypto.so.1.1         # OpenSSL 1.1 crypto library (bundled)
├── OPENSSL_LICENSE.txt      # OpenSSL license
└── Readme.md
```

**Note**: The `fiptool` binary has embedded RPATH (`$ORIGIN`) which automatically loads the bundled `libcrypto.so.1.1` from the same directory. No system OpenSSL installation or environment variables required.

## Building from Source

The prebuilt binaries are already prepared in this directory; however, they can also be compiled from source if needed.

### Prerequisites

**Note**: These are only required if you want to rebuild the tools from source. The bundled prebuilt binaries work out-of-the-box without any additional dependencies.

- GNU toolchain (gcc, make)
- patchelf - for setting RPATH on fiptool binary

```bash
sudo apt-get install build-essential patchelf
```

### Source Repositories
- `bpgen`: https://github.com/Renesas-SST/rz-utils/tree/styhead/rz-cmn/tools/bpgen
- `fiptool`: https://github.com/Renesas-SST/rz-atf/blob/styhead/rz-cmn/tools/fiptool

### Build Steps (GNU)

1. Clone the repositories just in case:

```shell
cd ~/workspace
git clone https://github.com/Renesas-SST/rz-atf.git -b styhead/rz-cmn
git clone https://github.com/Renesas-SST/rz-utils.git -b styhead/rz-cmn
```

2. Build Bootparameter

```shell
cd ~/workspace/rz-utils/tools/bpgen
gcc -o bpgen bpgen.c
```

3. Build Fiptool

Navigate to the fiptool folder:

```bash
cd ~/workspace/rz-atf/tools/fiptool
```

Build and set RPATH:

```bash
make clean
make
patchelf --set-rpath '$ORIGIN' fiptool
```

Verify RPATH:

```bash
readelf -d fiptool | grep RUNPATH
# Expected output: Library runpath: [$ORIGIN]
```

## Usage Examples

```shell
# Boot parameter
.\bpgen --soc v2h --image bl2.bin --mode {spi|mmc|scif|esd} --dest 0xADDR -o bl2_bp.bin [--copies N]

# Create an FIP package
.\fiptool create --soc-fw bl31.bin --nt-fw u-boot.bin fip.bin
```