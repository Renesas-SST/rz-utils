# RZ uload-bootloader - Bootloader Programming/Flashing on U-Boot console

This directory contains tools used for flashing uload bootloader (only support QSPI/xSPI flashing) on the RZ devices

## Outline of the folder

```
uload-bootloader
├── uload_bootloader_flash.py
└── README.md
```

## Getting help

Run the following comamnd to know how to use the script

- Windows:

```
py uload_bootloader_flash.py -h
```

- Linux:

```
python3 uload_bootloader_flash.py -h
```

## Flashing procedure

Please follow below steps:

**1. Prepare necessary images (optional)**

Place all bootloader images in the /boot/uload-bootloader folder on eMMC/SD Card.

We have already prepared the .bin images in the /boot/uload-bootloader folder on partition 1 (FAT32). If you want to update the images, replace the files in this folder using the correct partition.

The `/boot/uload-bootloader` folder should contain the following files (e.g., RZG2L-SBC board):

- fip-rzg2l-sbc.bin
- bl2_bp-rzg2l-sbc.bin

**2. Connect debug serial port to Host PC, then change switches to enter SCIF download mode**

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

*Custom Usage*

If you want to change the serial port settings, you can pass the arguments as shown below:

- **--serial_port**: Serial port to use for communication with the board.
- **--serial_port_baud**: Baud rate for the serial port.

Example Custom Command

- Windows:

```
py uload_bootloader_flash.py --serial_port COM11 --serial_port_baud 9600
```

- Linux:

```
python3 uload_bootloader_flash.py --serial_port /dev/ttyUSB0 --serial_port_baud 9600
```

**4. Power on the board. It will start to load bootloader images from uboot into QSPI/xSPI flash**

Wait for the script running automatically, and no input or operation is required during this period. After completing the process, you can set RZ board to boot from QSPI/xSPI as your needs.
