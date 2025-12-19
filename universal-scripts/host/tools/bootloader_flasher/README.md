# Bootloader Flashing on RZ devices

This document introduces the Python script `bootloader_flash.py` that simplifies the process by automating the flashing of bootloader images onto the RZ board in a multiple OS environment.

## Outline of the folder

```
bootloader-flasher
├── bootloader_flash.py
└── README.md
```

## Getting help

Run the following command to know how to use the script

- Windows:

```
py bootloader_flash.py -h
```

- Linux:

```
python3 bootloader_flash.py -h
```

## Flashing procedure

**1. Prepare necessary bootloader files under `target/images` folder (optional)**

Place all bootloader images (e.g., for RZG2L-SBC board) in the /path/to/universal-scripts/target/images/ folder on the Host PC.

```bash
mkdir -p /path/to/universal-scripts/target/images/
cp /path/to/your/bootloader/file/Flash_Writer_SCIF_rzg2l-sbc.mot /path/to/universal-scripts/target/images/
cp /path/to/your/bootloader/file/bl2_bp_rzg2l-sbc.srec /path/to/universal-scripts/target/images/
cp /path/to/your/bootloader/file/fip-rzg2l-sbc.srec /path/to/universal-scripts/target/images/
cp /path/to/your/bootloader/file/rzg2l-sbc-platform-settings.bin /path/to/universal-scripts/target/images/
```

**2. Connect debug serial port to Host PC, then change switches to enter SCIF download mode**

**3. Run the script**

*Basic Usage*

To run the script without passing any arguments, simply execute the following command:

- Windows:

```
py bootloader_flash.py
```

- Linux:

```
python3 bootloader_flash.py
```

When no arguments are provided, the script will use the following default info:

- Board name: rzg2l-sbc
- Flash method: xspi
- Serial port: most recently connected port (E.g: COM8 in Windows or /dev/ttyUSB0 in Linux)
- Serial port baud: 115200
- Flash Writer Image: /path/to/universal-scripts/target/images/Flash_Writer_SCIF_rzg2l-sbc.mot
- BL2 Image: /path/to/universal-scripts/target/images/bl2_bp_rzg2l-sbc.srec
- FIP Image: /path/to/universal-scripts/target/images/fip-rzg2l-sbc.srec
- Board identification Image: /path/to/universal-scripts/target/images/rzg2l-sbc-platform-settings.bin

Ensure these files are present in the current directory before executing the script.

*Custom Usage*

If you want to specify different file paths or change the serial port settings or images file, you can pass the arguments as shown below:

- **--board_name**: Board name to flash bootloader.
- **--flash_method**: Flash method to use (xspi or emmc).
- **--serial_port**: Serial port to use for communication with the board.
- **--serial_port_baud**: Baud rate for the serial port (must be `115200`).
- **--image_writer**: Path to the Flash Writer image.
- **--image_bl2**: Path to the BL2 image.
- **--image_fip**: Path to the FIP image.
- **--image_bid**: Path to the board identification image.

Example Custom Command

- Windows:

```
py bootloader_flash.py --board_name rzg2l-evk --flash_method emmc --serial_port COM11 --serial_port_baud 115200 --image_writer D:\custom_images\Flash_Writer_SCIF_rzg2l-sbc.mot --image_bl2 D:\custom_images\bl2_bp_rzg2l-sbc.srec --image_fip D:\custom_images\fip-rzg2l-sbc.srec --image_bid D:\custom_images\rzg2l-evk-platform-settings.bin
```

- Linux:

```
python3 bootloader_flash.py --board_name rzg2l-evk --flash_method emmc --serial_port /dev/ttyUSB0 --serial_port_baud 115200 --image_writer /home/renesas/custom_images/Flash_Writer_SCIF_rzg2l-sbc.mot --image_bl2 /home/renesas/custom_images/bl2_bp_rzg2l-sbc.srec --image_fip /home/renesas/custom_images/fip-rzg2l-sbc.srec --image_bid /home/renesas/custom_images/rzg2l-evk-platform-settings.bin
```

**3. Power on the board. It will start to flash bootloader images**

Wait for the script running automatically, and no input or operation is required during this period. After completing the process, you can set RZ board to boot from xSPI/eMMC as your needs.
