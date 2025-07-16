# universal-scripts

The **universal flash script** supports flashing RZ images across multiple boards by using information from a JSON configuration file.

This script offers cross-platform support (for both Windows and Linux operating systems) and handles three key flashing operations for embedded devices:

- Flashing the bootloader
- Flashing the uload-bootloader (only support QSPI flashing)
- Flashing the Root Filesystem (rootfs) to an SD card / eMMC

Supported boards:

- [RZG2L-SBC](https://www.renesas.com/en/design-resources/boards-kits/rz-g2l-sbc?srsltid=AfmBOopW7k6H7kvdtnxYYs72c6Pm_8u667-UDBi8v9-WXPHjQvzWlhLN)
- [RZG2L-EVK](https://www.renesas.com/en/design-resources/boards-kits/rz-g2l-evkit?srsltid=AfmBOoqqLvuA9ZrzAhhRLi9JR1JVUcoc9MUICwtZ78ZER-hchmQ3ps5I)
- [RZV2L-EVK](https://www.renesas.com/en/design-resources/boards-kits/rz-v2l-evkit?srsltid=AfmBOooz3AGWNCJNed1qk6NS0qeZBngU79XQ4h2KUkmMam82y615JPjr)
- [RZV2H-EVK](https://www.renesas.com/en/design-resources/boards-kits/rz-v2h-evk?srsltid=AfmBOooL-eoj5j3zum-HIL5v0JE9SROaKosWHYCOHfvySpJ4g39N9R_V)

## Prerequisites:

- python
  - For Windows install: please refer to [this page](https://www.python.org/downloads/) to download the setup file.
  - For Linux install: `sudo apt install python3`

- python packages: Follows package is required to be using the flashing script. Please install if one of them is missing:

```
pip install pyserial
pip install dataclasses (if using python <3.7)
```

## JSON Configuration for a New Board

The `flash_images.json` file contains predefined image mappings for supported devices.

`flash_images.json` supports several default boards. You can add a custom board to the configuration file by providing the following information:

- **bl2**: BL2 image name
- **board_identification**: Board identification image name
- **fip**: FIP image name
- **flash_writer**: Flash Writer image name
- **ipl_flash_method**: Method used by the IPL bootloader for flashing (`qspi` or `emmc`)
- **rootfs**: Root filesystem image name (`*.wic`)
- **rootfs_flash_method**: Method to flash the SD card (`udp` or `otg`)

Example of a sample board configuration in JSON:

```json
"rzg2l-sbc": {
    "bl2": "bl2_bp-rzg2l-sbc.srec",
    "board_identification": "rzg2l-sbc-platform-settings.bin",
    "fip": "fip-rzg2l-sbc.srec",
    "flash_writer": "Flash_Writer_SCIF_rzg2l-sbc.mot",
    "ipl_flash_method": "qspi",
    "rootfs": "core-image-weston.wic",
    "rootfs_flash_method": "udp"
}
```

---

## Flowchart

The universal flash script prompts the user for options and proceeds through the flashing process based on the input. The detailed procedure is as follows:

```mermaid
flowchart TD
    classDef default fill:#f0f4f8,stroke:#333,stroke-width:1px,font-size:14px
    classDef decision fill:#fef6e4,stroke:#c89b3c,stroke-width:2px,font-weight:bold
    classDef action fill:#dbeafe,stroke:#3b82f6,stroke-width:2px
    classDef terminal fill:#d1fae5,stroke:#10b981,stroke-width:2px,font-weight:bold

    A[Start]:::terminal --> B[Display available boards]:::action
    B --> C[User selects board]:::action
    C --> D[Display available serial ports]:::action
    D --> E[User selects port and baud rate]:::action
    E --> F["Ask: Write rootfs (y/n)"]:::decision
    F -->|n| G["Ask: Write IPL (y/n)"]:::decision
    G -->|y| H["Ask: Select IPL method"]:::decision
    H --> I{Method}:::decision
    I -->|1| J[Write IPL by BootloaderFlash]:::action
    I -->|2| K[Write IPL by UloadFlash]:::action
    G -->|n| L[End]:::terminal
    J --> L
    K --> L
```

---

## Basic Usage

### On Windows:

```bash
py universal_flash.py
```

### On Linux:

```bash
python3 universal_flash.py
```
