# Root filesystem Programming/Flashing Procedure for RZ board on multiple OS environment

This document introduces the relevant tools and outlines the specific steps for using the Python script `sd_flash.py` to program a filesystem image.

## Outline of the folder

```
├── README.md
├── sd_flash.py
└── tools
    ├── AdbWinApi.dll
    └── fastboot.exe
```

## Getting help

Run the following comamnd to know how to use the script

- Windows:

```
py sd_flash.py -h
```

- Linux:

```
python3 sd_flash.py -h
```

## Flashing procedure

Please following below steps:

**1. Prepare your own rootfs wic image under `target/images` folder (optional)**

```bash
mkdir -p /path/to/universal-scripts/target/images/
cp /path/to/your/wic/file/core-image-weston.wic /path/to/universal-scripts/target/images/
```

**2. Hardware connection**

- Connect debug serial port to Host PC
- Hardware connection to each type of fastboot:
   - [UDP] Connect Ethernet port to Host PC
   - [OTG] Connect USB OTG port to Host PC

**3. Run the script**

*Basic Usage*

To run the script without passing any arguments, simply execute the following command:

- Windows:

```
py sd_flash.py
```

- Linux:

```
python3 sd_flash.py
```

When no arguments are provided, the script will use the following default info:

- Board name: rzg2l-sbc
- Fastboot type: udp
- Ethernet port: 1
- IP address: 169.254.187.89
- Serial port: most recently connected port (E.g: COM8 in Windows or /dev/ttyUSB0 in Linux)
- Serial port baud: 115200
- WIC file: /path/to/universal-scripts/target/images/core-image-weston.wic

Ensure that these files are present in the current directory before executing the script.

*Custom Usage*

If you want to specify different file paths for the image, you can pass the arguments as shown below:

- **--board_name**: Board name to flash bootloader.
- **--fastboot_type**: Fastboot type to use (udp or otg).
- **--ether_port**: [Only used in fastboot UDP] Ethernet port used to board communication.
- **--ip_address**: [Only used in fastboot UDP] Ethernet IP address used to board communication.
- **--serial_port**: Serial port to use for communication with the board.
- **--serial_port_baud**: Baud rate for the serial port.
- **--image_rootfs**: Path to the root filesystem image.

Example Custom Command

- Windows:

```
py sd_flash.py --board_name rzg2l-evk --fastboot_type udp --ip_address 169.254.187.9 --ether_port 1 --serial_port COM11 --serial_port_baud 9600 --image_rootfs D:\custom_images\core-image-weston.wic
```

- Linux:

```
python3 sd_flash.py --board_name rzg2l-evk --fastboot_type udp --ip_address 169.254.187.9 --ether_port 1 --serial_port /dev/ttyUSB0 --serial_port_baud 9600 --image_rootfs /home/renesas/custom_images/core-image-weston.wic
```

**4. Power on the board. Please make sure you changed switches to normal boot mode. It will start to flash filesystem image**

Wait for the script running automatically, and no input or operation is required during this period. After finishing, you can boot with the filesystem image that you just flashed.
