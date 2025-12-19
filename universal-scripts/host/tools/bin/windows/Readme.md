# `bin/windows/` – Windows Host Tools

This directory contains Windows-compatible versions of the firmware utilities used in the RZ software build flow.
They are invoked automatically when the build system detects a Windows host.

## Contents

| Tool               | Platform Use Case                | Purpose |
|--------------------|----------------------------------|---------|
| `bpgen.exe`        | RZ/G2L, RZ/V2L, RZ/V2H           | Generates the boot parameter binary (`bl2_bp_<board>.bin`) used by Boot ROM to load BL2|
| `fiptool.exe`      | All                              | Creates and manipulates Firmware Image Packages (FIP) for ARM Trusted Firmware (TF-A). Requires bundled OpenSSL DLL. |
| `objcopy.exe`      | All                              | Converts binary files to SREC format with VMA addressing (from GNU binutils). Requires libwinpthread-1.dll. |

### Directory Structure

```
windows/
├── bpgen.exe                      # Boot parameter generator (statically linked)
├── fiptool.exe                    # FIP tool (requires libcrypto-3-x64.dll)
├── objcopy.exe                    # Binary to SREC converter (GNU Binutils, requires libwinpthread-1.dll)
├── libcrypto-3-x64.dll            # OpenSSL 3.x crypto library (required by fiptool only)
├── libwinpthread-1.dll            # MinGW-w64 pthread library (required by objcopy only)
├── GNU_BINUTILS_LICENSE.txt       # GNU Binutils license (GPL v3)
├── LIBWINPTHREAD_LICENSE.txt      # libwinpthread license (MIT/BSD 3-Clause)
├── OPENSSL_LICENSE.txt            # OpenSSL license (Apache 2.0)
└── Readme.md
```

**Note**: `fiptool.exe` requires the bundled `libcrypto-3-x64.dll`, and `objcopy.exe` requires `libwinpthread-1.dll`. Only `bpgen.exe` is fully statically linked with no runtime DLL dependencies. Windows automatically loads DLLs from the same directory. No separate installation or PATH configuration needed.

**License Information**:
- `objcopy.exe` is from GNU Binutils 2.45.1-1 (MSYS2/MinGW-w64 build) and is licensed under GPL v3. See `GNU_BINUTILS_LICENSE.txt` for full license text and source code availability.
- `libwinpthread-1.dll` is part of MinGW-w64 winpthreads, licensed under MIT License with portions derived from Lockless Inc under BSD 3-Clause. See `LIBWINPTHREAD_LICENSE.txt`.
- OpenSSL library (`libcrypto-3-x64.dll`) is licensed under Apache License 2.0. See `OPENSSL_LICENSE.txt`.

## Building from Source

> **Note for End Users:** You do **NOT** need to install MinGW-w64, MSYS2, or OpenSSL. All required binaries and DLLs are already bundled in this directory and will work out-of-the-box on Windows.

The prebuilt binaries are already prepared in this directory. The instructions below are **only for developers** who want to rebuild the tools from source.

### Prerequisites (for rebuilding from source only)
- MinGW-w64 or MSVC
- MinGW-w64 OpenSSL: https://packages.msys2.org/packages/mingw-w64-x86_64-openssl

### Source Repositories
- `bpgen`: https://github.com/Renesas-SST/rz-utils/tree/styhead/rz-cmn/tools/bpgen
- `fiptool`: https://github.com/Renesas-SST/rz-atf/blob/styhead/rz-cmn/tools/fiptool

### Build Steps (for developers only - Windows with MinGW)

> **Important:** These steps are **only for developers rebuilding from source**. End users do not need to follow these steps.

1. Clone repositories:

```powershell
cd ~/workspace
git clone https://github.com/Renesas-SST/rz-atf.git -b styhead/rz-cmn
git clone https://github.com/Renesas-SST/rz-utils.git -b styhead/rz-cmn
```

2. Build bpgen:

```powershell
cd ~/workspace/rz-utils/tools/bpgen
gcc -o bpgen bpgen.c
```

3. Build Fiptool

- Install MinGW-w64 OpenSSL
 - Download the package: https://packages.msys2.org/packages/mingw-w64-x86_64-openssl
 - Extract it into C:/mingw64.

- Navigate to the fiptool folder:

```powershell
cd ~/workspace/rz-atf/tools/fiptool
```

- Compile using mingw make

```powershell
mingw32-make   OPENSSL_DIR=/c/mingw64   CFLAGS+=" -I/c/mingw64/include"   LDFLAGS+=" -L/c/mingw64/lib"
```

## Usage Examples (PowerShell)

```powershell
# Boot parameter
.\bpgen.exe --soc v2h --image bl2.bin --mode {xspi|mmc|scif|esd} --dest 0xADDR -o bl2_bp.bin [--copies N]

# Create an FIP package
.\fiptool.exe create --soc-fw bl31.bin --nt-fw u-boot.bin fip.bin
```