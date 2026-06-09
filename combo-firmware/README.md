# Combo Firmware — Multi-SoC Unified Bootloader + Multi-Root SD

## Overview

Build and deploy a single SD card that boots **7 Renesas RZ boards** across 2 SoC families (G2L/V2L + V2H) with **9 root filesystem options**.

## Directory Structure

```
combo-firmware/
├── combo.py                     # Python CLI tool — interactive menu
├── build_combo.sh               # Main script: build ATF + U-Boot, flash, package
├── setup_multiroot.sh           # Partition + 9 rootfs + DATA deployment
├── config/
│   └── combo_layout.toml       # Sector layout definition
├── target/
│   └── images/                 # Output: bp_*.bin, bid_*.bin, fip_*.bin, combo.img.gz
├── SOC_BOARD_ADDITION_GUIDE.md # Adding new SoCs/boards
├── MULTIROOT_GUIDE.md          # Multi-root SD usage guide
└── README.md                   # This file
```

## Quick Start

```bash
# Interactive menu
./combo.py

# Build ATF + U-Boot, then package full image
./combo.py --build --package

# Flash bootloader to SD card
sudo ./combo.py --flash /dev/sdX

# Deploy full combo image (bootloader + 9 rootfs)
sudo ./combo.py --deploy /dev/sdX
```

## Usage

### Interactive Mode

Run without arguments for the interactive menu:

```bash
./combo.py
```

```
=======================================================================
  COMBO FIRMWARE MANAGER
=======================================================================
  ATF dir:    ~/quoctrinh/workspace/rz-atf-sst
  U-Boot dir: ~/quoctrinh/workspace/u-boot
  WIC dir:    ~/quoctrinh/workspace/yocto_rz-cmn/target/images
=======================================================================
  1. Build ATF + U-Boot
  2. Generate bootloader artifacts (bp/bid/fip)
  3. Package combo .img.gz (includes 9 rootfs)
  4. Flash bootloader to SD card
  5. Deploy full combo .img.gz to SD card
  6. Configure paths
  0. Exit
=======================================================================
Select:
```

### CLI Mode

| Command | Description |
|---------|-------------|
| `./combo.py --build` | Build ATF + U-Boot |
| `./combo.py --build --package` | Build + package in one step |
| `sudo ./combo.py --flash /dev/sdX` | Flash bootloader to SD card |
| `sudo ./combo.py --deploy /dev/sdX` | Deploy full combo image |
| `./combo.py --build --g2l-only` | G2L/V2L only (skip V2H) |

### Custom Paths

```bash
./combo.py --atf-dir /path/to/atf --uboot-dir /path/to/u-boot
sudo ./combo.py --deploy /dev/sdc --image /path/to/custom/combo.img.gz
```

Environment variables `RZ_ATF_DIR`, `RZ_UBOOT_DIR`, `WIC_DIR` also work.

## Prerequisites

- Poky SDK at `/opt/poky/5.1.4/` (or set `POKY_SDK_DIR`)
- ATF source at `$RZ_ATF_DIR` (default: `~/quoctrinh/workspace/rz-atf-sst`)
- U-Boot source at `$RZ_UBOOT_DIR` (default: `~/quoctrinh/workspace/u-boot`)
- WIC images at `$WIC_DIR` (default: `~/quoctrinh/workspace/yocto_rz-cmn/target/images`)
- bpgen/fiptool from `rz-utils/universal-scripts/host/tools/bin/linux/`

## Usage

### Build bootloader artifacts only

```bash
./build_combo.sh --build
```

Output: `target/images/{bp,bid,fip}_*.bin`

### Flash bootloader to SD card

```bash
sudo ./build_combo.sh --flash /dev/sdX
```

The SD card must already have a partition table with FAT starting at sector >= 7168.

### Build + flash in one step

```bash
sudo ./build_combo.sh --build --flash /dev/sdX
```

### Package full SD image (bootloader + 9 rootfs + DATA)

```bash
sudo ./build_combo.sh --package-image
```

Output: `target/images/renesas-multi-os-combo.img.gz` (deploy with `gunzip -c | sudo dd of=/dev/sdX`)

### G2L-only mode (skip V2H)

```bash
./build_combo.sh --build --g2l-only
```

### Custom paths

```bash
RZ_ATF_DIR=/path/to/atf \
RZ_UBOOT_DIR=/path/to/u-boot \
WIC_DIR=/path/to/wics \
sudo -E ./build_combo.sh --package-image
```

## SD Card Layout

| Sector | Content | SoC |
|--------|---------|-----|
| 1 | G2L Boot Parameter | G2L |
| 2-7 | V2H Boot Parameters (x6) | V2H |
| 8 | G2L BL2 | G2L |
| 512 | V2H BL2 | V2H |
| 1024-1220 | Board Packages (G2L: SBC, EVK, V2L-EVK, RS-G2L100) | G2L |
| 1280 | G2L FIP (BL31 + U-Boot) | G2L |
| 3328 | V2H FIP (BL31 + U-Boot) | V2H |
| 5376-6404 | Board Packages (V2H: SBC, EVK, RDK) | V2H |
| >= 7168 | FAT partition + 9 rootfs + DATA | Both |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RZ_ATF_DIR` | `~/quoctrinh/workspace/rz-atf-sst` | ATF source directory |
| `RZ_UBOOT_DIR` | `~/quoctrinh/workspace/u-boot` | U-Boot source directory |
| `WIC_DIR` | `~/quoctrinh/workspace/yocto_rz-cmn/target/images` | WIC images directory |
| `POKY_SDK_DIR` | `/opt/poky/5.1.4` | Poky SDK installation path |

## Root Filesystem Selection

### By label

In U-Boot console:

```bash
run core-image-weston
run core-image-minimal
run ubuntu-core-image
```

All labels:

| `run <label>` | Partition |
|---------------|-----------|
| `run core-image-minimal` | 5 |
| `run core-image-bsp` | 6 |
| `run core-image-weston` | 7 |
| `run renesas-core-image-cli` | 8 |
| `run renesas-core-image-weston` | 9 |
| `run renesas-quickboot-cli` | 10 |
| `run renesas-quickboot-wayland` | 11 |
| `run ubuntu-core-image` | 12 |
| `run ubuntu-lxde-image` | 13 |

### By partition number

```bash
setenv root_part 9; boot
```

## Quick Test (1 WIC + Bootloader)

Test nhanh 1 rootfs với bootloader combo, không cần build full .img.gz:

```bash
# CLI
sudo ./unified-bootloader-tool.py --quick-test core-image-minimal.wic /dev/sdc

# Interactive: menu option 8
```

Cơ chế: đọc partition layout từ WIC, copy từng partition ra SD với offset né vùng bootloader (sector 8192+), tạo MBR mới, flash bootloader. Không shrink, không format, không overlay-data.service.

Thời gian: ~2-6 phút tùy WIC size + tốc độ SD.

| root_part | Rootfs |
|-----------|--------|
| 5 | minimal |
| 6 | bsp |
| 7 | weston |
| 8 | cli |
| 9 | renesas-core-image-weston |
| 10 | quickboot-cli |
| 11 | quickboot-wayland |
| 12 | ubuntu-core-image |
| 13 | ubuntu-lxde-image |

## Integration Notes

- This module is **self-contained** in `combo-firmware/`. It does not modify existing `rz-utils` tools.
- It calls `bpgen` and `fiptool` from `rz-utils/universal-scripts/host/tools/bin/linux/` via relative path.
- Output images go to `target/images/` inside this directory (separate from `universal-scripts/target/images/`).
- For integration with `universal_flash.py`, see `SOC_BOARD_ADDITION_GUIDE.md`.
