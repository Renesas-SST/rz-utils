# RZ uload-bootloader - Bootloader Programming/Flashing on U-Boot console

This section describes the ULoad-bootloader flow for programming the bootloader from the U-Boot console. It supports xSPI flashing and is intended for cases where the device can boot to U-Boot and program flash using images stored on the removable media.

> **IMPORTANT:** All steps in this README must be followed in order. The script performs pre-checks to verify files exist on the SD card before erasing the SPI flash. If any required files are missing, the script will abort safely without erasing the flash.

## Outline of the folder

```
uload-bootloader
├── uload_bootloader_flash.py
└── README.md
```

## Prerequisites

The release does not include prebuilt ULoad images on the SD card. The ULoad flow requires BL2 and FIP artifacts that are rebuilt for the selected board with the correct DTB/FCONF and configuration.

Run the `firmware_compile.py` script in the `firmware_compile` folder to generate these artifacts, then copy them to partition 1 (FAT32) under `/uload-bootloader/` before running the ULoad flasher. This ensures the programmed bootloader matches the exact board and release configuration, minimizing the risk of mismatch.

To begin compiling uLoad images, refer to `firmware_compile/Readme.md` for more details.

## Getting help

Run the following command to know how to use the script

- Windows:

```
py uload_bootloader_flash.py -h
```

- Linux:

```
python3 uload_bootloader_flash.py -h
```

## Flashing procedure

Please follow the steps below:

**1. Prepare necessary images (required)**

This step packages the artifacts built by `firmware_compile.py` and places them on the removable media so the ULoad-bootloader script (U-Boot console flow) can program xSPI.

From `target/images`, gather the per-board files:
- `bl2`: bl2_bp_&lt;board-name&gt;.bin
- `fip`: fip_&lt;board&gt;.bin
- `Board identification`: &lt;board&gt;-&lt;version&gt;-platform-settings.bin

Place all files on partition 1 (FAT32) of the SD card under this directory.

```
/uload-bootloader
```
**2. Connect debug serial port to Host PC, then change switches to enter normal boot mode**

**3. Run the script**

*Basic Usage*

To run the script, use the following command

- Windows:

```
py uload_bootloader_flash.py
```

- Linux:

```
python3 uload_bootloader_flash.py
```

When no arguments are provided, the script will use the following default info:
- Serial port: most recently connected port (E.g: COM8 in Windows or /dev/ttyUSB0 in Linux)
- Serial port baudrate: 115200
- `bl2`: bl2_bp_&lt;board-name&gt;.bin
- `fip`: fip_&lt;board&gt;.bin
- `Board identification`: &lt;board&gt;-&lt;version&gt;-platform-settings.bin

**Note:** default `board-name` is `rzg2l-sbc`

*Custom Usage*

To specify custom file paths or override the defaults, the following arguments can be passed:

- **--serial_port**: Serial port to use for communication with the board.
- **--serial_port_baud**: Baud rate for the serial port (must be `115200`).
- **--image_bl2**: Path or filename of the BL2 image
- **--image_fip**: Path or filename of the FIP image
- **--image_bid**: Path or filename of the board-identification file

Example Custom Command

- Windows:

```powershell
py uload_bootloader_flash.py \	
  --serial_port /dev/ttyUSB0 \
  --serial_port_baud 115200 \
  --image_bl2 /mnt/sd/uload-bootloader/bl2_bp-rzg2l-sbc.bin \
  --image_fip /mnt/sd/uload-bootloader/fip-rzg2l-sbc.bin \
  --image_bid /mnt/sd/uload-bootloader/rzg2l-sbc-platform-settings.bin
```

- Linux:

```shell
python3 uload_bootloader_flash.py \
  --serial_port /dev/ttyUSB0 \
  --serial_port_baud 115200 \
  --image_bl2 /mnt/sd/uload-bootloader/bl2_bp-rzg2l-sbc.bin \
  --image_fip /mnt/sd/uload-bootloader/fip-rzg2l-sbc.bin \
  --image_bid /mnt/sd/uload-bootloader/rzg2l-sbc-platform-settings.bin
```

**Notes:**
- If only a filename is provided (no path), the script searches the default directory (e.g., /uload-bootloader on partition 1, FAT32).
- If a path is provided, the script searches only partition 1 (FAT32), not the ext4 partition.
- Ensure the filenames match the board that was built with firmware_compile.py.

**4. Power on the board. It will start to load bootloader images from uboot into xSPI flash**

The script will:
1. First perform a **pre-check** to verify all required files exist on the SD card
2. If pre-check passes, proceed to erase and write the SPI flash
3. If pre-check fails, abort safely without erasing the flash

Wait for the script to run automatically. No input or operation is required during this period. After completing the process, you can set RZ board to boot from xSPI as your needs.

## Troubleshooting

### Pre-check Failed: Missing Files

If you see an error message stating:
```
** Pre-check FAILED: Missing or inaccessible files on SD card **
```

This means one or more required files are not found on the SD card partition 1 (FAT32).

**Solution:**
1. Verify that you completed **Step 1** (Prepare necessary images) in the "Flashing procedure" section above
2. Run `firmware_compile.py` to generate the required BL2, FIP, and Board ID files
3. Copy all generated files to `/uload-bootloader/` directory on SD card partition 1 (FAT32)
4. Ensure filenames match your board name (e.g., `bl2_bp_rzg2l-sbc.bin` for rzg2l-sbc)
5. Re-run the script

**Note:** The SPI flash is NOT erased if pre-check fails, so your board remains in a bootable state.

### Serial Communication Issues

If the serial port fails to open or communicate:
- Verify the serial cable is properly connected to the debug port
- Check that no other application is using the serial port
- Confirm the correct port is selected (default: most recent port)
- Try specifying the port manually with `--serial_port` argument

### Board Does Not Boot to U-Boot Prompt

If the board doesn't reach U-Boot prompt:
- Verify DIP switches are set to **normal boot mode** (not SCIF download mode)
- Check that power is properly connected
- Ensure the board has a valid bootloader already programmed (required for ULoad method)
- Try power cycling the board
