#!/bin/bash
# Build and flash unified combo firmware for G2L/V2L and V2H to a single SD card.
#
# SD card layout (sector numbers, 512 bytes/sector):
#   Sector     1 : G2L Boot Parameter (512 B, 0x55AA at [510..511])
#   Sector   2-7 : V2H Boot Parameters x6 (0xAA55FFFF at [0x1FC], load=0x40000)
#   Sector     8 : G2L/V2L BL2 (PIE, dest=0x00012000 hardcoded in G2L BootROM)
#   Sector   512 : V2H BL2 (PIE, dest=0x08103000 from V2H BP load_offset=0x40000)
#   Sector  1024 : G2L SBC Board Package (BID@1024 + DTB@1028)
#   Sector  1088 : G2L EVK Board Package (BID@1088 + DTB@1092)
#   Sector  1152 : V2L EVK Board Package (BID@1152 + DTB@1156)
#   Sector  1216 : RS-G2L100 Board Package (BID@1216 + DTB@1220)
#   Sector  1280 : G2L/V2L FIP (BL31 + U-Boot, max 1MB -> ends <=3327)
#   Sector  3328 : V2H FIP (BL31 + U-Boot, max 1MB -> ends <=5375)
#   Sector  5376 : V2H SBC Board Package (BID@5376 + DTB@5380)
#   Sector  5888 : V2H EVK Board Package (BID@5888 + DTB@5892)
#   Sector  6400 : V2H RDK Board Package (BID@6400 + DTB@6404)
#
# Flash a WIC image first so the SD card has a valid partition table
# with FAT (partition 1) starting at sector >= 7168 to avoid overlap.
# Then run: sudo ./build_combo.sh --flash /dev/sdX
#
# Usage:
#   ./build_combo.sh --build                           # build ATF + U-Boot
#   ./build_combo.sh --flash /dev/sdX                  # flash bootloader only
#   ./build_combo.sh --build --flash /dev/sdX           # build + flash
#   ./build_combo.sh --package-image                   # .img.gz with rootfs+bootloader
#   WIC_DIR=/path ./build_combo.sh --package-image     # custom WIC path
#
# Env vars:
#   RZ_ATF_DIR     path to ATF source (default: ~/quoctrinh/workspace/rz-atf-sst)
#   RZ_UBOOT_DIR   path to U-Boot source (default: ~/quoctrinh/workspace/u-boot)
#   WIC_DIR        path to WIC images (default: ~/quoctrinh/workspace/yocto_rz-cmn/target/images)
#   POKY_SDK_DIR   path to Poky SDK sysroot (default: /opt/poky/5.1.4)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RZ_UTILS="$(cd "$SCRIPT_DIR/.." && pwd)"

# Env-var based paths with defaults
RZ_ATF_DIR="${RZ_ATF_DIR:-$HOME/quoctrinh/workspace/rz-atf-sst}"
RZ_UBOOT_DIR="${RZ_UBOOT_DIR:-$HOME/quoctrinh/workspace/u-boot}"
WIC_DIR="${WIC_DIR:-$HOME/quoctrinh/workspace/yocto_rz-cmn/target/images}"
POKY_SDK_DIR="${POKY_SDK_DIR:-/opt/poky/5.1.4}"

# Tools bundled in rz-utils
BPGEN="$RZ_UTILS/universal-scripts/host/tools/bin/linux/bpgen"
FIPTOOL="$RZ_UTILS/universal-scripts/host/tools/bin/linux/fiptool"
BIDTOOL="$RZ_ATF_DIR/tools/renesas/rz_board_id/gen_bid_blob.py"

OUT_DIR="$SCRIPT_DIR/target/images"
FLASH_DEV=""
DO_BUILD=0
DO_PACKAGE=0
G2L_ONLY=0

usage() {
    sed -n '2,18p' "$0"
    echo ""
    echo "Usage: $0 [--build] [--flash /dev/sdX] [--package-image] [--g2l-only]"
    echo ""
    echo "  --build            Build ATF (BL2+BL31) for G2L & V2H + U-Boot"
    echo "  --flash /dev/sdX   Flash bootloader to SD card (raw sectors)"
    echo "  --package-image    Create bootloader+9rootfs combo .img.gz"
    echo "  --g2l-only         Build/flash/package G2L/V2L only (skip V2H)"
    echo ""
    echo "Env vars:"
    echo "  RZ_ATF_DIR    (default: ~/quoctrinh/workspace/rz-atf-sst)"
    echo "  RZ_UBOOT_DIR  (default: ~/quoctrinh/workspace/u-boot)"
    echo "  WIC_DIR       (default: ~/quoctrinh/workspace/yocto_rz-cmn/target/images)"
    echo "  POKY_SDK_DIR  (default: /opt/poky/5.1.4)"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build) DO_BUILD=1; shift ;;
        --flash) FLASH_DEV="$2"; shift 2 ;;
        --package-image) DO_PACKAGE=1; shift ;;
        --g2l-only) G2L_ONLY=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown arg: $1"; usage; exit 1 ;;
    esac
done

if [[ "$DO_BUILD" == "1" ]]; then
    echo "=== Building ATF (Clean G2L & V2H) ==="
    cd "$RZ_ATF_DIR"

    POKY_CROSS="$POKY_SDK_DIR/sysroots/x86_64-pokysdk-linux/usr/bin/aarch64-poky-linux"
    export PATH="$POKY_CROSS:$PATH"
    unset CC CFLAGS LDFLAGS ASFLAGS CXXFLAGS CPPFLAGS 2>/dev/null || true

    rm -rf build/cmn build/g2l_out build/v2h_out

    echo "--- Building G2L/V2L ATF ---"
    make PLAT=cmn BOARD=rz_cmn RZ_SOC= DEBUG=0 PLAT_BL2_STORAGE=esd \
        CROSS_COMPILE=aarch64-poky-linux- \
        LD=aarch64-poky-linux-ld AS=aarch64-poky-linux-gcc bl2 bl31 dtbs

    mkdir -p build/g2l_out/fdts
    cp build/cmn/release/bl2.bin  build/g2l_out/bl2.bin
    cp build/cmn/release/bl31.bin build/g2l_out/bl31.bin
    cp build/cmn/release/fdts/*.dtb build/g2l_out/fdts/
    rm -rf build/cmn

    echo "--- Building V2H ATF ---"
    make PLAT=cmn BOARD=rz_cmn RZ_SOC=v2h DEBUG=0 \
        CROSS_COMPILE=aarch64-poky-linux- \
        LD=aarch64-poky-linux-ld AS=aarch64-poky-linux-gcc bl2 bl31 dtbs

    mkdir -p build/v2h_out/fdts
    cp build/cmn/release/bl2.bin  build/v2h_out/bl2-v2h.bin
    cp build/cmn/release/bl31.bin build/v2h_out/bl31-v2h.bin
    cp build/cmn/release/fdts/*.dtb build/v2h_out/fdts/

    echo "--- Building U-Boot ---"
    cd "$RZ_UBOOT_DIR"
    SYSROOT="$POKY_SDK_DIR/sysroots/cortexa55-poky-linux"
    make rz-cmn_defconfig ARCH=arm CROSS_COMPILE=aarch64-poky-linux-
    make -j"$(nproc)" ARCH=arm CROSS_COMPILE=aarch64-poky-linux- \
        KCFLAGS="--sysroot=${SYSROOT}" \
        KCPPFLAGS="--sysroot=${SYSROOT}" \
        LDFLAGS="--sysroot=${SYSROOT}"

    cd "$SCRIPT_DIR"
fi

G2L_BL2="$RZ_ATF_DIR/build/g2l_out/bl2.bin"
G2L_BL31="$RZ_ATF_DIR/build/g2l_out/bl31.bin"
V2H_BL2="$RZ_ATF_DIR/build/v2h_out/bl2-v2h.bin"
V2H_BL31="$RZ_ATF_DIR/build/v2h_out/bl31-v2h.bin"

G2L_SBC_DTB="$RZ_ATF_DIR/build/g2l_out/fdts/rzg2l-sbc.dtb"
G2L_EVK_DTB="$RZ_ATF_DIR/build/g2l_out/fdts/r9a07g044l2-smarc.dtb"
V2L_EVK_DTB="$RZ_ATF_DIR/build/g2l_out/fdts/r9a07g054l2-smarc.dtb"
RSG2L100_DTB="$RZ_ATF_DIR/build/g2l_out/fdts/rs-g2l100.dtb"
V2H_SBC_DTB="$RZ_ATF_DIR/build/v2h_out/fdts/imdt-v2h-sbc.dtb"
V2H_EVK_DTB="$RZ_ATF_DIR/build/v2h_out/fdts/rzv2h-evk-ver1.dtb"
V2H_RDK_DTB="$RZ_ATF_DIR/build/v2h_out/fdts/rzv2h-rdk-ver1.dtb"

UBOOT_BIN="$RZ_UBOOT_DIR/u-boot.bin"

for f in "$G2L_BL2" "$G2L_BL31" "$V2H_BL2" "$V2H_BL31" \
         "$G2L_SBC_DTB" "$G2L_EVK_DTB" "$V2L_EVK_DTB" "$RSG2L100_DTB" \
         "$V2H_SBC_DTB" "$V2H_EVK_DTB" "$V2H_RDK_DTB" \
         "$UBOOT_BIN" "$BPGEN"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: Missing file: $f" >&2
        exit 1
    fi
done

mkdir -p "$OUT_DIR"

echo "=== Generating Boot Parameters ==="
"$BPGEN" --soc g2l --image "$G2L_BL2" -o "$OUT_DIR/bp_g2l.bin"
python3 -c "
with open('$OUT_DIR/bp_g2l.bin', 'r+b') as f:
    f.seek(508)
    f.write(b'\x00\x00')
"

"$BPGEN" --soc v2h --image "$V2H_BL2" --mode esd --dest 0x08103000 --copies 6 -o "$OUT_DIR/bp_v2h.bin"
python3 -c "
import struct
with open('$OUT_DIR/bp_v2h.bin', 'r+b') as f:
    for i in range(6):
        f.seek(i * 512 + 16)
        f.write(struct.pack('<I', 0x40000))
"

echo "=== Generating Board ID Blobs ==="
python3 "$BIDTOOL" 0x11 "$OUT_DIR/bid_g2l_sbc.bin"
python3 "$BIDTOOL" 0x10 "$OUT_DIR/bid_g2l_evk.bin"
python3 "$BIDTOOL" 0x20 "$OUT_DIR/bid_v2l_evk.bin"
python3 "$BIDTOOL" 0x12 "$OUT_DIR/bid_rsg2l100.bin"
python3 "$BIDTOOL" 0x32 "$OUT_DIR/bid_v2h_sbc.bin"
python3 "$BIDTOOL" 0x30 "$OUT_DIR/bid_v2h_evk.bin"
python3 "$BIDTOOL" 0x31 "$OUT_DIR/bid_v2h_rdk.bin"

echo "=== Generating FIPs ==="
"$FIPTOOL" create --align 16 --soc-fw "$G2L_BL31" --nt-fw "$UBOOT_BIN" "$OUT_DIR/fip_g2l_combo.bin"
"$FIPTOOL" create --align 16 --soc-fw "$V2H_BL31" --nt-fw "$UBOOT_BIN" "$OUT_DIR/fip_v2h_combo.bin"

G2L_FIP_SECTORS=$(( ($(wc -c < "$OUT_DIR/fip_g2l_combo.bin") + 511) / 512 ))
V2H_FIP_SECTORS=$(( ($(wc -c < "$OUT_DIR/fip_v2h_combo.bin") + 511) / 512 ))
if (( 1280 + G2L_FIP_SECTORS > 3328 )); then
    echo "ERROR: G2L FIP too large: ends at sector $((1280 + G2L_FIP_SECTORS)), overlaps V2H FIP at 3328" >&2
    exit 1
fi
if (( 3328 + V2H_FIP_SECTORS > 5376 )); then
    echo "ERROR: V2H FIP too large: ends at sector $((3328 + V2H_FIP_SECTORS)), overlaps V2H SBC at 5376" >&2
    exit 1
fi
echo "FIP sizes OK: G2L=${G2L_FIP_SECTORS} sectors, V2H=${V2H_FIP_SECTORS} sectors"

package_combo_image() {
    echo "=== Launching Host-Side Virtual Packaging ==="
    local IMG_PATH="$OUT_DIR/renesas-multi-os-combo.img"
    local IMG_SIZE="28G"
    local START_TIME
    START_TIME=$(date +%s)

    echo "==> Validating bootloader source artifacts..."
    local missing_artifacts=0
    declare -a REQUIRED_BINARIES=(
        "$OUT_DIR/bp_g2l.bin"
        "$OUT_DIR/bp_v2h.bin"
        "$OUT_DIR/bid_g2l_sbc.bin"
        "$OUT_DIR/bid_g2l_evk.bin"
        "$OUT_DIR/bid_v2l_evk.bin"
        "$OUT_DIR/bid_rsg2l100.bin"
        "$OUT_DIR/bid_v2h_sbc.bin"
        "$OUT_DIR/bid_v2h_evk.bin"
        "$OUT_DIR/bid_v2h_rdk.bin"
        "$G2L_BL2"
        "$V2H_BL2"
        "$G2L_BL31"
        "$V2H_BL31"
        "$G2L_SBC_DTB"
        "$G2L_EVK_DTB"
        "$V2L_EVK_DTB"
        "$RSG2L100_DTB"
        "$V2H_SBC_DTB"
        "$V2H_EVK_DTB"
        "$V2H_RDK_DTB"
    )

    for binary in "${REQUIRED_BINARIES[@]}"; do
        if [ ! -f "$binary" ]; then
            echo "[-] ERROR: Required bootloader artifact is missing: $binary"
            missing_artifacts=1
        fi
    done

    if [ "$missing_artifacts" -eq 1 ]; then
        echo "[!] Run with --build first to generate missing source files!"
        exit 1
    fi
    echo "    All artifacts present."

    echo "==> Creating blank virtual disk ($IMG_SIZE)..."
    truncate -s "$IMG_SIZE" "$IMG_PATH"

    echo "==> Mapping image to virtual loop block..."
    local LOOP_DEV
    LOOP_DEV=$(sudo losetup -f --show "$IMG_PATH")
    echo "    Loop device: $LOOP_DEV"

    echo "==> Deploying partition table and rootfs..."
    local SETUP_SCRIPT="$SCRIPT_DIR/setup_multiroot.sh"
    if [[ ! -f "$SETUP_SCRIPT" ]]; then
        echo "ERROR: $SETUP_SCRIPT not found" >&2
        sudo losetup -d "$LOOP_DEV"
        exit 1
    fi
    sudo CUSTOM_WICS="${CUSTOM_WICS:-}" WIC_DIR="$WIC_DIR" bash "$SETUP_SCRIPT" "$LOOP_DEV" "p"

    echo "==> Flashing bootloader..."
    sudo dd if="$OUT_DIR/bp_g2l.bin" of="$LOOP_DEV" seek=1 bs=512 count=1 conv=fsync status=none
    if [[ "$G2L_ONLY" == "0" ]]; then
        sudo dd if="$OUT_DIR/bp_v2h.bin" of="$LOOP_DEV" seek=2 bs=512 count=6 conv=fsync status=none
    fi
    sudo dd if="$G2L_BL2" of="$LOOP_DEV" seek=8 bs=512 conv=fsync status=none
    if [[ "$G2L_ONLY" == "0" ]]; then
        sudo dd if="$V2H_BL2" of="$LOOP_DEV" seek=512 bs=512 conv=fsync status=none
    fi
    for seek in 1024 1028 1088 1092 1152 1156 1216 1220; do
        case $seek in
            1024) f="$OUT_DIR/bid_g2l_sbc.bin";; 1028) f="$G2L_SBC_DTB";;
            1088) f="$OUT_DIR/bid_g2l_evk.bin";; 1092) f="$G2L_EVK_DTB";;
            1152) f="$OUT_DIR/bid_v2l_evk.bin";; 1156) f="$V2L_EVK_DTB";;
            1216) f="$OUT_DIR/bid_rsg2l100.bin";; 1220) f="$RSG2L100_DTB";;
        esac
        sudo dd if="$f" of="$LOOP_DEV" seek=$seek bs=512 conv=fsync status=none
    done
    sudo dd if="$OUT_DIR/fip_g2l_combo.bin" of="$LOOP_DEV" seek=1280 bs=512 conv=fsync status=none
    if [[ "$G2L_ONLY" == "0" ]]; then
        sudo dd if="$OUT_DIR/fip_v2h_combo.bin" of="$LOOP_DEV" seek=3328 bs=512 conv=fsync status=none
    fi
    if [[ "$G2L_ONLY" == "0" ]]; then
        for seek in 5376 5380 5888 5892 6400 6404; do
            case $seek in
                5376) f="$OUT_DIR/bid_v2h_sbc.bin";; 5380) f="$V2H_SBC_DTB";;
                5888) f="$OUT_DIR/bid_v2h_evk.bin";; 5892) f="$V2H_EVK_DTB";;
                6400) f="$OUT_DIR/bid_v2h_rdk.bin";; 6404) f="$V2H_RDK_DTB";;
            esac
            sudo dd if="$f" of="$LOOP_DEV" seek=$seek bs=512 conv=fsync status=none
        done
    fi
    sync

    echo "==> Finalizing image and releasing virtual devices..."
    sync
    sudo losetup -d "$LOOP_DEV"

    local END_TIME
    END_TIME=$(date +%s)
    local DURATION=$((END_TIME - START_TIME))
    echo ""
    echo "=== SUCCESS: Packaged virtual image generated ==="
    echo "  Image:  $IMG_PATH ($(du -h "$IMG_PATH" | cut -f1))"
    echo "  Time:   $((DURATION / 60))m $((DURATION % 60))s"
    echo "  Size:   $IMG_SIZE"
    echo ""
    echo "Compressing..."
    gzip -f "$IMG_PATH"
    echo "  Compressed: ${IMG_PATH}.gz ($(du -h "${IMG_PATH}.gz" | cut -f1))"
}

if [[ -n "$FLASH_DEV" ]]; then
    echo "=== Flashing to $FLASH_DEV ==="
    sudo umount "${FLASH_DEV}"* 2>/dev/null || true

    sudo dd if="$OUT_DIR/bp_g2l.bin" of="$FLASH_DEV" seek=1 bs=512 count=1 conv=fsync
    if [[ "$G2L_ONLY" == "0" ]]; then
        sudo dd if="$OUT_DIR/bp_v2h.bin" of="$FLASH_DEV" seek=2 bs=512 count=6 conv=fsync
    fi
    sudo dd if="$G2L_BL2" of="$FLASH_DEV" seek=8   bs=512 conv=fsync
    if [[ "$G2L_ONLY" == "0" ]]; then
        sudo dd if="$V2H_BL2" of="$FLASH_DEV" seek=512 bs=512 conv=fsync
    fi
    sudo dd if="$OUT_DIR/bid_g2l_sbc.bin"  of="$FLASH_DEV" seek=1024 bs=512 conv=fsync
    sudo dd if="$G2L_SBC_DTB"              of="$FLASH_DEV" seek=1028 bs=512 conv=fsync
    sudo dd if="$OUT_DIR/bid_g2l_evk.bin"  of="$FLASH_DEV" seek=1088 bs=512 conv=fsync
    sudo dd if="$G2L_EVK_DTB"              of="$FLASH_DEV" seek=1092 bs=512 conv=fsync
    sudo dd if="$OUT_DIR/bid_v2l_evk.bin"  of="$FLASH_DEV" seek=1152 bs=512 conv=fsync
    sudo dd if="$V2L_EVK_DTB"              of="$FLASH_DEV" seek=1156 bs=512 conv=fsync
    sudo dd if="$OUT_DIR/bid_rsg2l100.bin" of="$FLASH_DEV" seek=1216 bs=512 conv=fsync
    sudo dd if="$RSG2L100_DTB"             of="$FLASH_DEV" seek=1220 bs=512 conv=fsync
    sudo dd if="$OUT_DIR/fip_g2l_combo.bin" of="$FLASH_DEV" seek=1280 bs=512 conv=fsync
    if [[ "$G2L_ONLY" == "0" ]]; then
        sudo dd if="$OUT_DIR/fip_v2h_combo.bin" of="$FLASH_DEV" seek=3328 bs=512 conv=fsync
    fi
    if [[ "$G2L_ONLY" == "0" ]]; then
        sudo dd if="$OUT_DIR/bid_v2h_sbc.bin"  of="$FLASH_DEV" seek=5376 bs=512 conv=fsync
        sudo dd if="$V2H_SBC_DTB"              of="$FLASH_DEV" seek=5380 bs=512 conv=fsync
        sudo dd if="$OUT_DIR/bid_v2h_evk.bin"  of="$FLASH_DEV" seek=5888 bs=512 conv=fsync
        sudo dd if="$V2H_EVK_DTB"              of="$FLASH_DEV" seek=5892 bs=512 conv=fsync
        sudo dd if="$OUT_DIR/bid_v2h_rdk.bin"  of="$FLASH_DEV" seek=6400 bs=512 conv=fsync
        sudo dd if="$V2H_RDK_DTB"              of="$FLASH_DEV" seek=6404 bs=512 conv=fsync
    fi
    sync
    echo "=== Flash Complete! ==="
    if [[ "$G2L_ONLY" == "1" ]]; then
        echo "This SD card is formatted for G2L/V2L boards only (V2H components skipped)."
    else
        echo "This SD card can boot: G2L-SBC, G2L-EVK, V2L-EVK, RS-G2L100, V2H-SBC, V2H-EVK, V2H-RDK"
    fi
elif [[ "$DO_PACKAGE" == "1" ]]; then
    package_combo_image
else
    echo "=== Build Complete! ==="
    echo "All outputs located in: $OUT_DIR"
    echo ""
    echo "Next steps:"
    echo "  sudo ./build_combo.sh --flash /dev/sdX"
    echo "  sudo ./build_combo.sh --package-image"
fi
