# Multi-Root SD Card Guide

> Hướng dẫn chi tiết sử dụng thẻ SD 9-rootfs + 1 DATA.
> Script: `tools/setup_multiroot.sh`

---

## 1. Tạo thẻ từ đầu (máy mới)

### Yêu cầu

- **SD card** ≥ 32 GB
- **WIC images** trong `~/quoctrinh/workspace/yocto_rz-cmn/target/images/`
  - `core-image-minimal.wic`
  - `core-image-bsp.wic`
  - `core-image-weston.wic`
  - `renesas-core-image-cli.wic`
  - `renesas-core-image-weston.wic`
  - `renesas-quickboot-cli.wic`
  - `renesas-quickboot-wayland.wic`
  - `ubuntu-core-image.wic`
  - `ubuntu-lxde-image.wic`

### Chạy

```bash
sudo bash tools/setup_multiroot.sh /dev/sdX
```

Script tự động:
1. Đo real size của từng rootfs (bỏ padding)
2. Tạo partition table (MBR + extended: p1 BOOT, p5-p13 rootfs, p14 DATA)
3. Format
4. Copy boot data + rootfs (cp -a, không padding)
5. Cài `overlay-data.service` (systemd) vào mỗi rootfs
6. Ghi `uEnv.txt` lên BOOT

---

## 2. Partition layout

```
p1  BOOT  FAT32   200 MB   Kernel + DTB + uEnv.txt
p5  rootfs ext4   782 MB   core-image-minimal
p6  rootfs ext4   870 MB   core-image-bsp
p7  rootfs ext4   1.3 GB   core-image-weston
p8  rootfs ext4   1.1 GB   renesas-core-image-cli
p9  rootfs ext4   2.8 GB   renesas-core-image-weston
p10 rootfs ext4   1.1 GB   renesas-quickboot-cli
p11 rootfs ext4   2.8 GB   renesas-quickboot-wayland
p12 rootfs ext4   3.0 GB   ubuntu-core-image
p13 rootfs ext4   5.1 GB   ubuntu-lxde-image
p14 DATA   ext4   ~10 GB   Shared RW (home, var_lib)
```

---

## 3. U-Boot boot commands

| Mục đích | Lệnh |
|----------|------|
| Boot minimal | `setenv root_part 5; boot` |
| Boot bsp | `setenv root_part 6; boot` |
| Boot weston | `setenv root_part 7; boot` |
| Boot cli | `setenv root_part 8; boot` |
| Boot core-weston | `setenv root_part 9; boot` |
| Boot quickboot-cli | `setenv root_part 10; boot` |
| Boot quickboot-wayland | `setenv root_part 11; boot` |
| Boot ubuntu-core | `setenv root_part 12; boot` |
| Boot ubuntu-lxde | `setenv root_part 13; boot` |

### Lưu ý

- Nếu chưa set `root_part`, mặc định là **5** (minimal)
- `root_part` không bị overwrite khi uEnv.txt được import (vì không có dòng `root_part=` trong uEnv.txt)

---

## 4. Cơ chế overlay-data.service

Mỗi rootfs có systemd service `overlay-data.service` chạy trước `local-fs.target`:

```
1. mount -L DATA /data
2. mkdir -p /data/p{part}/home /data/p{part}/var_lib
3. if empty: cp -a /home/. /data/p{part}/home/    # preserve content gốc
   if empty: cp -a /var/lib/. /data/p{part}/var_lib/
4. mount --bind /data/p{part}/home /home
5. mount --bind /data/p{part}/var_lib /var/lib
```

### Tại sao không overlay?
- OverlayFS gây split-brain với systemd (root bị đè sau khi systemd đã mount)
- Bind-mount đơn giản, an toàn, không cần rebuild WIC

### Tại sao không bind /var/log?
- Yocto có symlink `/var/log -> volatile/log` → bind mount sẽ đè lên tmpfs
- Chỉ bind `/home` (user data) và `/var/lib` (app data)

---

## 5. Kernel cmdline

Từ `uEnv.txt` (BOOT partition):

```
mmc_args=if test -z "${root_part}"; then setenv root_part 5; fi; \
          setenv bootargs ro rootwait earlycon root=/dev/mmcblk1p${root_part}
```

- `ro`: rootfs read-only (ngăn ghi rác vào partition shrunk)
- `mmcblk1p`: hầu hết board Renesas dùng mmcblk1 cho SD slot ngoài
- Nếu board dùng mmcblk0, sửa lại trong uEnv.txt và script

---

## 6. DATA partition

Partition `p14` (DATA) chứa thư mục riêng cho từng rootfs:

```
/data/
├── p5/
│   ├── home/      → /home (bind mount)
│   └── var_lib/   → /var/lib (bind mount)
├── p6/
│   ├── home/
│   └── var_lib/
├── p7/
...
```

### Xoá dữ liệu 1 rootfs

```bash
# Trên board (rootfs đang chạy)
rm -rf /data/p5/*   # xoá toàn bộ data của p5
```

### Xem dung lượng

```bash
df -h /data
du -sh /data/p*/
```

---

## 7. Sửa / thêm rootfs (không cần chạy lại script)

### Sửa filesystem 1 rootfs (ví dụ p5)

```bash
# Trên host — USB reader
sudo mount /dev/sdX5 /mnt
sudo chroot /mnt bash
  apt update && apt upgrade   # ubuntu
  dnf upgrade                 # yocto
  exit
sudo umount /mnt
```

### Sửa systemd service

```bash
sudo mount /dev/sdX5 /mnt
sudo vim /mnt/etc/systemd/system/overlay-data.service
sudo umount /mnt
```

### Sửa uEnv.txt

```bash
sudo mount /dev/sdX1 /mnt
sudo vim /mnt/uEnv.txt
sudo umount /mnt
```

---

## 8. Xử lý sự cố

### "mmc device not found"

```bash
# Trên U-Boot console
mmc rescan
```

### Boot fail — kernel panic không tìm thấy rootfs

```bash
# Kiểm tra root_part đúng chưa
print root_part
# Kiểm tra partition có tồn tại trên thẻ không
mmc dev 1
mmc part
```

### DATA không mount

```bash
# Trên board (login root)
mount | grep data
journalctl -u overlay-data.service
```

### /home trống hoặc không phải từ rootfs

```bash
# Lần đầu boot: service sẽ copy từ rootfs. Nếu không:
cp -a /usr/etc/skel/. /data/pX/home/ 2>/dev/null || true
mount --bind /data/pX/home /home
```

---

## 9. `--package-image` (tạo file .img duy nhất)

Tạo file `.img` chứa sẵn bootloader + 9 rootfs, chỉ cần `dd` vào thẻ là chạy.

```bash
cd ~/ticket_R_X_ATF/tools
sudo bash build_combo_unified.sh --package-image

# Output: target/images/renesas-multi-os-combo.img.gz (~2.2 GB)
# Time: ~6.5 phút

# Ghi vào thẻ:
zcat target/images/renesas-multi-os-combo.img.gz | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress
```

Luồng xử lý:
1. Generate bootloader (BPs, BIDs, FIPs) từ ATF + U-Boot đã build
2. `truncate -s 28G` tạo file ảnh sparse
3. `losetup` map vào loop device
4. Flash bootloader vào raw sectors loop
5. Gọi `setup_multiroot.sh` trên loop device (parted MBR + copy WICs + services)
6. `losetup -d` detach
7. `gzip` nén output

> **Lưu ý:** script dùng **parted** thay sfdisk vì parted xử lý MBR + extended + logical đúng trên cả physical `/dev/sdb` và virtual `/dev/loop0`.

---

## 10. Files tham khảo

| File | Vai trò |
|------|---------|
| `tools/setup_multiroot.sh` | Script tạo thẻ (chạy trên host) |
| `tools/setup_multiroot.sh` dòng 217 | uEnv.txt template |
| `tools/setup_multiroot.sh` dòng 163-194 | overlay-data.service template |
| `README.md` section 9 | Tổng quan + partition map |
| `projects/KNOWLEDGE.md` Bug #9 | Chi tiết kỹ thuật + issues fixed |
