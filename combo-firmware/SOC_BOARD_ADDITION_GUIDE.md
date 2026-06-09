# Hướng dẫn thêm SoC / Board mới vào Combo Firmware

## 1. Cấu trúc combo firmware

Combo firmware chứa bootloader cho nhiều SoC + board trên cùng một thẻ SD. BootROM **mỗi SoC quét từ sector 1 đến 7**, mỗi sector đọc BP, kiểm tra magic/signature. Nếu đúng → dừng, dùng BP đó. Nếu không → sector tiếp theo.

Cơ chế này là **fallback trong cùng 1 SoC** (vd: nếu sector 1 hỏng, vẫn có thể boot từ sector 2). Khi nhiều SoC共存, BootROM mỗi SoC có magic/signature khác nhau nên tự động bỏ qua sector của SoC khác.

```
Sector layout (512 B/sector):

  Sector   0 : MBR (partition table, BootROM bỏ qua)
  Sector   1 : G2L BP (magic 0x55AA @510)
  Sector   2 : V2H BP (magic 0xAA55FFFF @0x1FC)
  Sector   3 : (SoC mới BP — magic/signature khác)
  Sector   4-7: dự phòng

  Sector   8 : G2L BL2
  Sector 512 : V2H BL2
  Sector ... : (SoC mới BL2)

  Sector 1024 : G2L SBC Board Package (BID@1024 + DTB@1028)
  ...
  Sector 1280 : G2L FIP (BL31 + U-Boot)
  Sector 3328 : V2H FIP (BL31 + U-Boot)
  ...
  Sector 7168 : GAP — partition đầu tiên (BOOT/FAT)
```

BootROM mỗi SoC đọc:
```
V2H BootROM: sector 1 → magic 0x55AA? → không (format khác) → sector 2 → 0xAA55FFFF? → có → dùng BP
G2L BootROM: sector 1 → 0x55AA? → có → dùng BP (bỏ qua sector 2-7)
SoC mới:     sector 1 → magic SoC mới? → không → sector 2 → không → sector 3 → có → dùng BP
```

> **Không cần assign sector cố định cho từng SoC.** Chỉ cần ghi BP vào sector trống trong 1-7, BootROM mỗi SoC tự tìm đúng BP của nó.

---

## 2. eSD V2.0 BootROM Format (HW Manual)

Cả G2L và V2H đều dùng chuẩn **eSD V2.0** ([SD Specification Part 1 eSD Addendum Version 2.10]). Loader program size block (BP) 512 bytes ở sectors 1-7, tối đa 7 bản sao.

### 2.1 BP Format Chung

Byte offset | Size | Ý nghĩa
------------|------|--------
`+00h` | 4 | **Loader program data size** (BL2 size, little-endian)
`+10h` | 4 | **Load address** (byte offset trên SD — V2H dùng, G2L bỏ qua)
`+20h` | 4 | **Destination address** (RAM address — V2H dùng, G2L bỏ qua)
`+1FCh` | 2 | **SoC discriminator** (ghi đè `0x0000` cho G2L, để `0xFFFF` cho V2H)
`+1FEh` | 2 | **Signature** `0x55AA`

### 2.2 Cách BootROM phân biệt BP của SoC nào

```
G2L BootROM: chỉ check 0x55AA @510 → OK → dùng BP này (dừng ở sector 1)
V2H BootROM: check 0x55AA @510 + 0xFFFF @508 → sector 1 có 0x0000 @508 → skip
             → sector 2: 0x55AA OK + 0xFFFF OK → dùng BP này (dừng ở sector 2)
```

**Cơ chế discriminator:** bytes 508-509 (`+1FCh`). 
- `0xFFFF` = "Don't Care / unset" → V2H BootROM accepts
- `0x0000` = "not for me" → V2H BootROM rejects, fallback sector tiếp
- G2L BootROM bỏ qua bytes 508-509, chỉ check 0x55AA

### 2.3 G2L vs V2H — Sự khác biệt

| SoC | BP sector | Số bản sao | BL2 location | BL2 RAM addr | Discriminator @508 |
|-----|-----------|------------|--------------|--------------|-------------------|
| G2L | 1 | 1 (luôn) | **Hardcode sector 8** | Hardcode 0x00012000 | `0x0000` |
| V2H | 2-7 | 6 (fallback) | **Configurable** (offset 16 → 0x40000 = sector 512) | Configurable (offset 32 → 0x08103000) | `0xFFFF` |

> **G2L BootROM không đọc fields +10h/+20h** — ignore hoàn toàn. Dùng hardcode sector 8 và 0x00012000.
> **V2H BootROM đọc +10h (SD byte offset) và +20h (RAM addr)** — hoàn toàn linh hoạt.
> Đây là lý do ta patch `0x40000` vào offset 16 mỗi copy V2H BP: báo BootROM "BL2 ở byte 0x40000 (= sector 512)".

### 2.4 Thông tin cần thu thập — SoC mới

| Mục | Ví dụ G2L | Ví dụ V2H | Cần tìm ở đâu |
|-----|-----------|-----------|---------------|
| BP sector | 1 | 2 | BootROM chapter HW Manual |
| Số bản sao | 1 | 6 | HW Manual (esd V2.0: up to 7) |
| BL2 hardcode sector? | 8 (cứng) | 512 (config) | HW Manual — có field +10h không? |
| BL2 RAM addr | 0x00012000 (cứng) | 0x08103000 (config) | HW Manual — có field +20h không? |
| Discriminator bytes @508 | 0x0000 | 0xFFFF | BootROM signature check mô tả |
| Storage type | ESD | ESD | `PLAT_BL2_STORAGE` |
| ATF `RZ_SOC` | (none) | v2h | Makefile `plat/renesas/rz/soc/` |
| bpgen flag | `--soc g2l` | `--soc v2h --dest 0x08103000` | `bpgen --help` |

### 2.5 BP Generation

```
# G2L: bpgen tạo BP, sau đó zero bytes 508-509 để discriminator
bpgen --soc g2l --image "$G2L_BL2" -o bp_g2l.bin
python3 -c "with open('bp_g2l.bin','r+b') as f: f.seek(508); f.write(b'\x00\x00')"

# V2H: bpgen tạo 6 copies + dest addr, sau đó patch offset 16 = BL2 byte offset
bpgen --soc v2h --image "$V2H_BL2" --mode esd --dest 0x08103000 --copies 6 -o bp_v2h.bin
python3 -c "
import struct
with open('bp_v2h.bin','r+b') as f:
    for i in range(6):
        f.seek(i*512+16)
        f.write(struct.pack('<I', BL2_BYTE_OFFSET))  # 0x40000 = sector 512
"
```

### 2.6 ATF Build Config

```
# G2L (RZ_G2L family gồm G2L, V2L, G2LC)
make PLAT=cmn BOARD=rz_cmn RZ_SOC= DEBUG=0 PLAT_BL2_STORAGE=esd \
    CROSS_COMPILE=aarch64-poky-linux- bl2 bl31 dtbs

# V2H (RZ_V2H)
make PLAT=cmn BOARD=rz_cmn RZ_SOC=v2h DEBUG=0 \
    CROSS_COMPILE=aarch64-poky-linux- bl2 bl31 dtbs
```

> **Cần tìm:** Giá trị `RZ_SOC` hợp lệ (xem `plat/renesas/rz/soc/` trong ATF tree). `PLAT_BL2_STORAGE` nếu khác esd.

### 2.7 FIP Sector

FIP chứa BL31 + U-Boot, cần đặt sau tất cả Board Package của SoC trước đó.

```
G2L FIP: sector 1280 (sau G2L board packages kết thúc tại 1220+4 = 1224)
V2H FIP: sector 3328 (sau V2H FIP guard, trước V2H board packages)
```

> **Cần tính:** `FIP_START = prev_soc_last_package + ALIGN(fip_max_size, 512)`.

### 2.8 Unified BL2: Cùng sector, khác SoC

BootROM không quan tâm BL2 chạy SoC nào — chỉ load binary vào SRAM rồi jump. Nếu 2 SoC cùng hardcode sector 8 (hoặc 1 SoC hardcode + 1 SoC config trỏ về 8), chỉ cần:

| Điều kiện | Khả thi? | Giải thích |
|-----------|----------|------------|
| Cùng PIE load address | ✅ | BootROM load vào đâu cũng chạy |
| Cùng SD host controller | ✅ | Vì BootROM đã dùng SD để load BL2 rồi |
| BL2 đủ nhỏ cho SRAM nhỏ nhất | ✅ | BL2 thực chất chỉ cần SCIF + SD + FIP parser |

**BL2 tối thiểu chỉ cần:**
- SCIF/UART driver (console log)
- SD/MMC host driver (đọc FIP)
- FIP parser (extract BL31 + U-Boot)

DDR init, PLL, clock, PMIC — **không cần trong BL2**. Những thứ đó nằm trong BL31, được load từ FIP. Đây là đúng tinh thần ATF boot flow.

Nếu giữ BL2 tối giản, 1 binary duy nhất có thể chạy trên mọi SoC cùng storage medium, dispatch FIP theo board detect. Kích thước không phải vấn đề.

> **Lý do V2H BL2 hiện tại 226KB:** ATF Renesas nhồi DDR init + platform setup vào BL2. Refactor được — chỉ là công. Nếu làm unified BL2 đúng nghĩa (chỉ SCIF + SD), size < 80KB, fit G2L SRAM.

### 2.9 BL2 Output File Name

```
G2L: build/g2l_out/bl2.bin
V2H: build/v2h_out/bl2-v2h.bin
SoC mới: build/<soc>_out/bl2.bin
```

---

## 3. Thông tin cần thu thập — Board mới (trên SoC có sẵn)

### 3.1 Board Package Sector

Mỗi board package gồm 2 sector liên tiếp: BID blob (sector N) + DTB (sector N+4).

```
G2L boards:   1024..1220 (4 boards × 2 sectors each)
V2H boards:   5376..6404 (3 boards × 2 sectors each)
```

> **Cần tính:** `BOARD_START = prev_soc_fip_end + GAP`. Layout hiện tại:
> - G2L FIP ends ≤ 3327 → V2H boards start at 5376
> - V2H FIP ends ≤ 5375 → V2H boards start at 5376

### 3.2 Board ID (Model ID)

Xác định model ID 8-bit từ team HW hoặc ATF board definition:

| Board | Model ID | Vendor | Name in BID |
|-------|----------|--------|-------------|
| G2L-SBC | 0x11 | Renesas | rzg2l-sbc |
| G2L-EVK | 0x10 | Renesas | rzg2l-evk |
| V2L-EVK | 0x20 | Renesas | rzv2l-evk |
| RS-G2L100 | 0x12 | Renesas | rs-g2l100 |
| V2H-SBC | 0x32 | Renesas | imdt-v2h-sbc |
| V2H-EVK | 0x30 | Renesas | rzv2h-evk |
| V2H-RDK | 0x31 | Renesas | rzv2h-rdk |

> File tham khảo: `tools/renesas/rz_board_id/gen_bid_blob.py` trong ATF.

### 3.3 DTB File

Board-specific device tree blob, output từ ATF build:

```
G2L: build/g2l_out/fdts/<board>.dtb
V2H: build/v2h_out/fdts/<board>.dtb
```

### 3.4 uEnv.txt root_part Mapping

Khi thêm rootfs mới (WIC image), cập nhật bảng mapping trong:
- `tools/setup_multiroot.sh`: thêm vào mảng `WICS` và `LABELS`
- `tools/setup_multiroot.sh` (uEnv.txt template): cập nhật comment
- `tools/MULTIROOT_GUIDE.md`: cập nhật bảng partition

```
X=5:minimal  6:bsp  7:weston  8:cli
9:core-weston  10:quickboot-cli  11:quickboot-wayland
12:ubuntu-core  13:ubuntu-lxde
```

---

## 4. Nơi cần sửa — Từng bước cụ thể

### 4.1 File `tools/build_combo_unified.sh`

#### a) Header comment — SD card layout (dòng 4-17)

Thêm dòng mô tả sector layout cho SoC + board mới.

#### b) Biến ATF outputs (dòng 105-119)

```bash
# Thêm:
V3H_BL2="$ATF_DIR/build/v3h_out/bl2.bin"
V3H_BL31="$ATF_DIR/build/v3h_out/bl31.bin"
V3H_<BOARD>_DTB="$ATF_DIR/build/v3h_out/fdts/<board>.dtb"
```

#### c) Validation list (dòng 122-130)

```bash
for f in "$G2L_BL2" "$G2L_BL31" "$V2H_BL2" "$V2H_BL31" \
         "$V3H_BL2" "$V3H_BL31" \
         "$G2L_SBC_DTB" ... "$V3H_<BOARD>_DTB" \
         ...
```

#### d) ATF Build block (dòng 54-103)

```bash
# Thêm sau V2H build:
if [[ "$DO_BUILD" == "1" ]]; then
    ...
    # 6. Build V3H BL2 & BL31
    make PLAT=cmn BOARD=rz_cmn RZ_SOC=v3h DEBUG=0 \
        CROSS_COMPILE=aarch64-poky-linux- bl2 bl31 dtbs
    mkdir -p build/v3h_out/fdts
    cp build/cmn/release/bl2.bin  build/v3h_out/bl2.bin
    cp build/cmn/release/bl31.bin build/v3h_out/bl31.bin
    cp build/cmn/release/fdts/*.dtb build/v3h_out/fdts/
fi
```

> **Warning:** Build V2H hiện tại xoá `build/cmn` trước. Nếu thêm V3H, cần sắp xếp thứ tự build để tránh cross-contamination.

#### e) BPGEN cho SoC mới (dòng 134-150)

```bash
"$BPGEN" --soc v3h --image "$V3H_BL2" --mode esd --dest 0x<ADDR> --copies N \
    -o "$OUT_DIR/bp_v3h.bin"
```

#### f) Board ID + Board Package (dòng 152-160)

```bash
python3 "$BIDTOOL" 0x<N> "$OUT_DIR/bid_<soc>_<board>.bin"
```

#### g) FIP generation (dòng 162-165)

```bash
"$FIPTOOL" create --align 16 --soc-fw "$V3H_BL31" --nt-fw "$UBOOT_BIN" \
    "$OUT_DIR/fip_v3h_combo.bin"
```

#### h) FIP size guard (dòng 167-178)

```bash
V3H_FIP_SECTORS=$(( ($(wc -c < "$OUT_DIR/fip_v3h_combo.bin") + 511) / 512 ))
if (( V3H_FIP_START + V3H_FIP_SECTORS > NEXT_SOC_START )); then
    echo "ERROR: V3H FIP overlaps..." >&2; exit 1
fi
```

#### i) Flash section (dòng 180+)

Thêm các lệnh `dd` cho BPs, BL2s, BIDs, DTBs, FIPs của SoC mới. Cập nhật cả `--flash` path và `package_combo_image` function.

### 4.2 File `tools/setup_multiroot.sh`

- **Mảng `WICS`**: Thêm WIC image mới nếu có rootfs mới.
- **Mảng `LABELS`**: Label tương ứng.
- **uEnv.txt template**: Cập nhật comment mapping root_part.

### 4.3 File `tools/MULTIROOT_GUIDE.md`

- Cập nhật bảng partition mapping nếu thêm rootfs.

---

## 5. Checklist thêm SoC mới

```
[ ] 1. Xác định BootROM sector cho BP
[ ] 2. Xác định BL2 load address + storage type
[ ] 3. Xác định RZ_SOC value trong ATF
[ ] 4. Xác định bpgen --soc value + options
[ ] 5. Xác định số bản sao BP + magic offset
[ ] 6. Tính sector cho FIP (không overlap)
[ ] 7. Tính sector cho Board Packages (không overlap)
[ ] 8. Thêm ATF build targets vào script
[ ] 9. Thêm biến ATF outputs
[ ] 10. Cập nhật validation list
[ ] 11. Thêm BPGEN command
[ ] 12. Thêm BID generation command
[ ] 13. Thêm FIPTOOL command
[ ] 14. Thêm FIP size guard
[ ] 15. Thêm dd commands vào --flash path
[ ] 16. Thêm dd commands vào package_combo_image()
[ ] 17. Cập nhật header comment (layout)
[ ] 18. Build thử + boot test
```

## 6. Checklist thêm Board mới (SoC có sẵn)

```
[ ] 1. Xác định model ID từ ATF board definition
[ ] 2. Xác định DTB file name
[ ] 3. Tính sector cho board package
[ ] 4. Thêm BID generation command
[ ] 5. Thêm biến DTB path
[ ] 6. Cập nhật validation list
[ ] 7. Thêm dd command vào --flash path
[ ] 8. Thêm dd command vào package_combo_image()
[ ] 9. Cập nhật header comment
[ ] 10. Build thử + boot test
```
