#!/usr/bin/env bash
# setup_multiroot.sh — 9 rootfs (rw) + 1 DATA trên 1 thẻ SD
# Usage: sudo WIC_DIR=/path/to/wics bash setup_multiroot.sh /dev/sdX [p]
#   [p] = partition prefix: "p" cho loop0p1, "" cho sdb1 (auto-detect nếu bỏ)
set -euo pipefail

SD=${1:?Usage: $0 /dev/sdX}
PPFX() { [[ "$1" =~ [0-9]$ ]] && echo p || true; }
P=${2:-$(PPFX "$SD")}
WIC_DIR="${WIC_DIR:-$HOME/quoctrinh/workspace/yocto_rz-cmn/target/images}"

declare -a WICS
if [[ -n "${CUSTOM_WICS:-}" ]]; then
  read -ra WICS <<< "$CUSTOM_WICS"
else
  WICS=(
    core-image-minimal.wic
    core-image-bsp.wic
    core-image-weston.wic
    renesas-core-image-cli.wic
    renesas-core-image-weston.wic
    renesas-quickboot-cli.wic
    renesas-quickboot-wayland.wic
    ubuntu-core-image.wic
    ubuntu-lxde-image.wic
  )
fi

wic_part_info() {
  local wic=$1 part=$2 field=$3
  local line
  line=$(sfdisk -l "$wic" 2>/dev/null | grep "${part} " | head -1)
  if echo "$line" | grep -q '\*'; then
    [ "$field" = start ] && echo "$line" | awk '{print $3}' || echo "$line" | awk '{print $5}'
  else
    [ "$field" = start ] && echo "$line" | awk '{print $2}' || echo "$line" | awk '{print $4}'
  fi
}

echo "=== 1/6 Unmount $SD ==="
sudo umount ${SD}* 2>/dev/null || true

echo "=== 2/6 Measure real rootfs size from WICs ==="
declare -a ROOT_SECTORS LABELS BOOT_NAMES
TOTAL_ROOT_SECTORS=0
for wic in "${WICS[@]}"; do
  base="${wic%.wic}"
  BOOT_NAMES+=("$base")
  label=$(echo "$base" | sed 's/renesas-core-image-//; s/core-image-//; s/renesas-//')
  LABELS+=("$label")
  p2_start=$(wic_part_info "$WIC_DIR/$wic" wic2 start)
  p2_sectors=$(wic_part_info "$WIC_DIR/$wic" wic2 size)
  TMP=$(mktemp -d)
  sudo mount -o loop,offset=$((p2_start * 512)),sizelimit=$((p2_sectors * 512)) \
      "$WIC_DIR/$wic" "$TMP" 2>/dev/null
  REAL_BYTES=$(sudo du -sb "$TMP" | cut -f1)
  NEW_MB=$(( (REAL_BYTES * 12 / 10 + 1048575) / 1048576 ))
  sudo umount "$TMP"
  rmdir "$TMP"
  NEW_SECTORS=$(( (NEW_MB * 1024 * 1024 + 511) / 512 ))
  ROOT_SECTORS+=("$NEW_SECTORS")
  TOTAL_ROOT_SECTORS=$((TOTAL_ROOT_SECTORS + NEW_SECTORS))
  printf "  %-25s %5d MB  (%d sectors)\n" "$label" "$NEW_MB" "$NEW_SECTORS"
done

TOTAL_SECTORS=$(( $(blockdev --getsz "$SD") ))
BOOT_SECTORS=$((200 * 1024 * 1024 / 512))
GAP=16384

USED=$((BOOT_SECTORS + TOTAL_ROOT_SECTORS + GAP * (${#WICS[@]} + 3)))
DATA_SECTORS=$((TOTAL_SECTORS - USED))
DATA_SECTORS=$(( DATA_SECTORS > 0 ? DATA_SECTORS : 0 ))

echo ""
echo "  BOOT:      $((BOOT_SECTORS * 512 / 1024 / 1024)) MB"
echo "  Rootfs:    $((TOTAL_ROOT_SECTORS * 512 / 1024 / 1024)) MB"
echo "  DATA:      $((DATA_SECTORS * 512 / 1024 / 1024)) MB"
echo "  SD total:  $((TOTAL_SECTORS * 512 / 1024 / 1024)) MB"

echo ""
echo "=== 3/6 Create partition table ==="
S=$GAP
BOOT_START=$S; BOOT_END=$((BOOT_START + BOOT_SECTORS - 1))
S=$((BOOT_END + 1 + GAP))
EXT_START=$S; LOG_START=$((EXT_START + GAP))

declare -a LOGICAL_STARTS
for sz in "${ROOT_SECTORS[@]}"; do
  LOGICAL_STARTS+=("$LOG_START")
  LOG_START=$((LOG_START + sz + GAP))
done
DATA_START=$LOG_START
DATA_END=$((DATA_START + DATA_SECTORS - 1))
EXT_END=$DATA_END

PART_BOOT=1
FIRST_ROOT=5
PART_DATA=$((FIRST_ROOT + ${#WICS[@]}))

sudo wipefs -a "$SD" 2>/dev/null || true
sleep 1

parted -s "$SD" mklabel msdos
parted -s "$SD" mkpart primary fat32 ${BOOT_START}s ${BOOT_END}s
parted -s "$SD" set 1 boot on
parted -s "$SD" mkpart extended ${EXT_START}s ${EXT_END}s

OFFSET=$((EXT_START + GAP))
for sz in "${ROOT_SECTORS[@]}"; do
  END=$((OFFSET + sz - 1))
  parted -s "$SD" mkpart logical ${OFFSET}s ${END}s
  OFFSET=$((END + 1 + GAP))
done
END=$((DATA_START + DATA_SECTORS - 1))
parted -s "$SD" mkpart logical ${DATA_START}s ${END}s

sleep 1
sudo partx -a "$SD" 2>/dev/null || true
sudo partprobe "$SD" 2>/dev/null || true
sleep 1
echo "  BOOT=$SD$PART_BOOT  DATA=$SD$PART_DATA  rootfs=$SD{5..13}"

echo ""
echo "=== 4/6 Format ==="
echo -n "  BOOT... "; sudo mkfs.vfat -F 32 -n BOOT "${SD}${P}${PART_BOOT}" >/dev/null 2>&1; echo "done"
for i in "${!LABELS[@]}"; do
  PART=$((FIRST_ROOT + i))
  echo -n "  ${LABELS[$i]} ($SD$PART)... "
  sudo mkfs.ext4 -F -L "${LABELS[$i]}" "${SD}${P}${PART}" >/dev/null 2>&1
  echo "done"
done
echo -n "  DATA... "; sudo mkfs.ext4 -F -L DATA "${SD}${P}${PART_DATA}" >/dev/null 2>&1; echo "done"

echo ""
echo "=== 5/6 Copy data ==="
WIC0="${WICS[0]}"
p1_start=$(wic_part_info "$WIC_DIR/$WIC0" wic1 start)
p1_size=$(wic_part_info "$WIC_DIR/$WIC0" wic1 size)
echo -n "  BOOT... "
sudo dd if="$WIC_DIR/$WIC0" of="${SD}${P}${PART_BOOT}" bs=512 \
    skip="$p1_start" count="$p1_size" conv=notrunc status=none 2>/dev/null
echo "done"

SROOT=$(mktemp -d)
DROOT=$(mktemp -d)
for i in "${!WICS[@]}"; do
  wic="${WICS[$i]}"
  PART=$((FIRST_ROOT + i))
  p2_start=$(wic_part_info "$WIC_DIR/$wic" wic2 start)
  p2_size=$(wic_part_info "$WIC_DIR/$wic" wic2 size)
  echo -n "  ${LABELS[$i]}... "
  sudo mount -o loop,offset=$((p2_start * 512)),sizelimit=$((p2_size * 512)) \
      "$WIC_DIR/$wic" "$SROOT"
  sudo mount "${SD}${P}${PART}" "$DROOT"
  sudo cp -a "$SROOT/." "$DROOT/"
  sudo umount "$DROOT"
  sudo umount "$SROOT"
  # fsck to clear needs_recovery flag (prevents ro mount on next boot)
  sudo fsck -f "${SD}${P}${PART}" 2>/dev/null || true
  echo "done"
done
rm -rf "$SROOT" "$DROOT"

echo ""
echo "=== 6/6 Setup uEnv.txt + fstab ==="

BROOT=$(mktemp -d)
sudo mount "${SD}${P}${PART_BOOT}" "$BROOT"

# Build boot-by-name variables (dynamic from WICS/LABELS array)
BOOT_VARS=""
ROOT_MAP_COMMENT="# root_part map:"
for i in "${!BOOT_NAMES[@]}"; do
  PART=$((FIRST_ROOT + i))
  BOOT_VARS+="${BOOT_NAMES[$i]}=setenv root_part ${PART}; boot"$'\n'
  ROOT_MAP_COMMENT+="  ${PART}=${BOOT_NAMES[$i]}"
done

cat << EOF | sudo tee "$BROOT/uEnv.txt" > /dev/null
# Refer to readme.txt for more information on setting up U-Boot Env
            #enable_overlay_i2c=1
            #enable_overlay_spi=1
            #enable_overlay_can=1
            #enable_overlay_dsi=1
            #enable_overlay_audio_codec=1
            #enable_overlay_csi_ov5640=1
            #enable_overlay_csi_ov5645=1
            #enable_overlay_csi22_ar1335=1
            #enable_overlay_csi23_ar1335=1
            prodsdboot=run mmc_do_boot

# Quick boot by label — run <name> at U-Boot prompt
#   e.g.  run weston   (run bsp, run minimal, ...)
${BOOT_VARS}
# Dung \${mmcdev} tu dong - V2H (0) -> mmcblk0, V2L (1) -> mmcblk1
mmc_args=if test -z "\${root_part}"; then setenv root_part ${FIRST_ROOT}; fi; setenv bootargs rootwait earlycon root=/dev/mmcblk\${mmcdev}p\${root_part}

${ROOT_MAP_COMMENT}

# Manual: setenv root_part N; boot
EOF
sudo umount "$BROOT"
rm -rf "$BROOT"

# Create /data mount point in each rootfs + data-mount.service
RROOT=$(mktemp -d)
for i in "${!LABELS[@]}"; do
  PART=$((FIRST_ROOT + i))
  sudo mount "${SD}${P}${PART}" "$RROOT"
  sudo mkdir -p "$RROOT/data"
  # Fix root HOME if WIC set it to /home/root (should be /root)
  sudo sed -i 's|^root:[^:]*:[^:]*:[^:]*:[^:]*:/home/root:|root:x:0:0:root:/root:|' "$RROOT/etc/passwd" 2>/dev/null || true
  sudo mkdir -p "$RROOT/etc/systemd/system"
  cat << 'SVC' | sudo tee "$RROOT/etc/systemd/system/data-mount.service" > /dev/null
[Unit]
Description=Mount DATA partition + persist /home /var/lib
DefaultDependencies=no
After=systemd-remount-fs.service
Before=local-fs.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'mount -o remount,rw / 2>/dev/null; for i in 1 2 3 4 5; do mount -o remount,rw / 2>/dev/null && break; sleep 0.2; done'
ExecStart=/bin/mkdir -p /data
ExecStart=/bin/sh -c 'B=$$(echo "$$(findmnt -n -o SOURCE /)" | sed "s/p[0-9]*$$//"); mount $$(ls "$$B"p* 2>/dev/null | sort -t"p" -k2 -n | tail -1) /data 2>&1 || (echo "mount /data failed, trying direct" && mount LABEL=DATA /data)'
ExecStart=/bin/mkdir -p /data/home /data/var_lib
ExecStart=/bin/sh -c '/usr/bin/test -z "$$(/bin/ls -A /data/home 2>/dev/null)" && /bin/cp -a /home/. /data/home/ 2>/dev/null || true'
ExecStart=/bin/sh -c '/usr/bin/test -z "$$(/bin/ls -A /data/var_lib 2>/dev/null)" && /bin/cp -a /var/lib/. /data/var_lib/ 2>/dev/null || true'
ExecStart=/bin/mount --bind /data/home /home
ExecStart=/bin/mount --bind /data/var_lib /var/lib
RemainAfterExit=yes

[Install]
WantedBy=local-fs.target
SVC
  sudo mkdir -p "$RROOT/etc/systemd/system/local-fs.target.wants"
  sudo ln -sf /etc/systemd/system/data-mount.service \
      "$RROOT/etc/systemd/system/local-fs.target.wants/"
  sudo umount "$RROOT"
done
rm -rf "$RROOT"

echo ""
echo "====== DONE ====="
lsblk "$SD" -o NAME,SIZE,FSTYPE,LABEL
echo ""
echo "=== Cach dung ==="
echo "  run weston                     # boot by label (nhanh nhat)"
echo "  setenv root_part 9; boot       # boot by partition (override)"
echo "  ${ROOT_MAP_COMMENT}"
echo ""
echo "  DATA ($SD$PART_DATA): /data (tu dong mount qua fstab)"
