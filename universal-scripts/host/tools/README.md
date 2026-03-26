
# universal-scripts

The **universal flash script** supports flashing RZ images across multiple boards by using information from a JSON configuration file.

This script offers cross-platform support (for both Windows and Linux operating systems) and handles three key flashing operations for embedded devices:

- Flashing the bootloader
- Flashing the uload-bootloader (only supports xSPI flashing)
- Flashing the Root Filesystem (rootfs) to an SD card / eMMC

Supported boards:

- [RZG2L-SBC](https://www.renesas.com/en/design-resources/boards-kits/rz-g2l-sbc?srsltid=AfmBOopW7k6H7kvdtnxYYs72c6Pm_8u667-UDBi8v9-WXPHjQvzWlhLN)
- [RZG2L-EVK](https://www.renesas.com/en/design-resources/boards-kits/rz-g2l-evkit?srsltid=AfmBOoqqLvuA9ZrzAhhRLi9JR1JVUcoc9MUICwtZ78ZER-hchmQ3ps5I)
- [RS-G2L100](https://www.renesas.com/en/products/microcontrollers-microprocessors/rz-mpus/rz-partner-solutions/geniatech-g2l100)
- [RZV2L-EVK](https://www.renesas.com/en/design-resources/boards-kits/rz-v2l-evkit?srsltid=AfmBOooz3AGWNCJNed1qk6NS0qeZBngU79XQ4h2KUkmMam82y615JPjr)
- [RZV2H-EVK](https://www.renesas.com/en/design-resources/boards-kits/rz-v2h-evk?srsltid=AfmBOooL-eoj5j3zum-HIL5v0JE9SROaKosWHYCOHfvySpJ4g39N9R_V)
- [RZV2H-RDK](https://www.renesas.com/en/design-resources/boards-kits/ws125-v2hrdkrefz)
- [IMDT V2H-SBC](https://www.renesas.com/en/products/microcontrollers-microprocessors/rz-mpus/rz-partner-solutions/imdt-v2-sbc)

## Prerequisites:

Before running the scripts, ensure the following dependencies are installed.

### Python

- **Windows**: Download and install Python from the [official website](https://www.python.org/downloads/). Make sure Python is installed with the "Add Python to environment variables" and "Install pip" options enabled.

- **Linux**:  
  ```sh
  sudo apt install python3
  ```

#### Required Python packages

The flashing script depends on the following Python packages. Install them if missing:

- **pyserial**
- **dataclasses** (only if using Python < 3.7)

1. On Linux:

If Python 3.12 is in use: set up a virtual environment first.

```shell
renesas@builder-pc:~/rz-cmn-srp-3.0/host/tools#  sudo apt update
renesas@builder-pc:~/rz-cmn-srp-3.0/host/tools#  sudo apt install python3.12-venv
renesas@builder-pc:~/rz-cmn-srp-3.0/host/tools#  python3 -m venv .venv
renesas@builder-pc:~/rz-cmn-srp-3.0/host/tools#  source .venv/bin/activate
```

After the virtual environment is active, choose one of the two install methods:

- Option 1 - Use `requirements.txt` (recommended)
  ```sh
  cd <path/to/your/package/host/tools>
  pip3 install -r requirements.txt
  ```

- Option 2 - Install manually

```sh
# Ensure pip is available
sudo apt install python3-pip

# Install required packages
pip3 install pyserial
pip3 install dataclasses
```

2. On windows, there are two ways to install:

- If `pip` is missing, repair your Python installation or download [get-pip.py](https://bootstrap.pypa.io/get-pip.py) and run:
    ```powershell
    py get-pip.py
    ```
- Install required packages:
  1. Option 1 - Use `requirements.txt` (recommended)
    ```powershell
    cd <path/to/your/package/host/tools>
    py -m pip install -r requirements.txt
    ```
  2. Option 2 - Install manually
  - Using the Python launcher:

  ```powershell
  py -m pip install pyserial
  py -m pip install tomli
  py -m pip install dataclasses       # Only if Python < 3.7
  ```
 - Or using `pip` directly (if already in PATH):

 ```powershell
  pip install pyserial
  pip install tomli
  pip install dataclasses   # only if Python < 3.7
 ```

### Environment and Tool Dependencies

Make sure you have the following installed or available in `tools/bin/<os>` or `host/tools/bin/<os>`:
- `bpgen` - unified boot parameter generator (already included in the release package)
- `fiptool` - TF-A utility (already included in the release package)
- `objcopy` - part of GNU binutils (see installation steps above)
- `dd` - used to write bootloader binaries directly to the raw SD card device during eSD flashing

Firmware binaries and DTBs must be available in the following location (already included in the release package):

```
target/images/
```

#### Linux

Install the required toolchain and fastboot:

```sh
sudo apt-get update
sudo apt-get install build-essential android-tools-fastboot -y
```

#### Windows

**USB OTG Flashing on Windows**

Fastboot/OTG flashing on Windows requires the device's **Fastboot / USB-download** interface to use the **WinUSB** driver.

> **Note:** Windows binds drivers to the **device/interface present at install time** (VID/PID[/MI]). This Fastboot interface exists **only while** the board is connected over OTG **and** go to OTG download mode.

**Steps to verify USB OTG dependencies are installed correctly:**

1. **Prepare connections**
   - Connect the board's USB-to-serial to the PC and open a terminal (115200 8-N-1).
   - Open **Tera Term** (or any serial console) on the correct COM port/baud.

2. **Enter U-Boot and switch to USB OTG Fastboot**
   - **Power on** the board and **interrupt autoboot** to get a `U-Boot>` prompt.
   - Connect the board's **USB OTG** port to the PC.
   - At the U-Boot prompt, run:
     ```bash
     setenv serial# 'Renesas1'
     fastboot usb 27
     ```
     > This places the board into **USB OTG fastboot/download** mode.\
     > `27` is the index used on RZ Common System

3. **Bind WinUSB using Zadig**
   - Download the latest **[Zadig](https://zadig.akeo.ie/)** and run it (no installation needed).
   - In Zadig, go to **Options → List All Devices**.
   - From the dropdown, select the device that represents the bootloader/fastboot interface.
     - **USB Download Gadget**
   - On the right, set **Driver** to **WinUSB**.
   - Click **Install Driver** (or **Replace Driver**).

4. **Verify**
   - Open **PowerShell** or **Command Prompt** and run:
     ```powershell
     .\path\to\package\sd_creator\tools\fastboot.exe devices
     ```

     Expected:
     ```
      Renesas1         fastboot
     ```

> [!NOTE]  
> **All dependencies bundled for Windows - No Installation Required**  
> All required tools and runtime libraries are pre-bundled in `tools/bin/windows/`:
> - `fiptool.exe` + `libcrypto-3-x64.dll` (OpenSSL library)
> - `bpgen.exe` (statically linked, no DLLs needed)
> - `objcopy.exe` + `libwinpthread-1.dll` (MinGW runtime)
>
> **You do NOT need to install MinGW-w64, MSYS2, or OpenSSL.** The scripts automatically use the bundled binaries.

## JSON Configuration for a New Board

The `flash_images.json` file contains predefined image mappings for supported devices.

`flash_images.json` supports several default boards. You can add a custom board to the configuration file by providing the following information:

- **SoC**: Soc type
- **bl2**: BL2 image name
- **board_identification**: Board identification image name
- **fip**: FIP image name
- **atf_fdts**: FCONF device tree name
- **uboot_dtb**: U-boot device tree name
- **flash_writer**: Flash Writer image name
- **ipl_flash_method**: Method used by the IPL bootloader for flashing (`xspi` or `emmc`)
- **rootfs**: Root filesystem image name (`*.wic`)
- **rootfs_flash_method**: Method to flash the SD card (`udp` or `otg`)

This table below lists the available options (and sensible defaults) for `ipl_flash_method` and `rootfs_flash_method` per board.

| Board           | SoC/MPU | ipl_flash_method      | Default | rootfs_flash_method | Default |
|-----------------|---------|-----------------------|---------|---------------------|---------|
| rzg2l-sbc       | g2l     | xspi                  | xspi    | udp                 | udp     |
| rs-g2l100       | g2l     | xspi                  | xspi    | udp, otg            | otg     |
| rzg2l-evk       | g2l     | xspi, emmc, esd       | xspi    | udp, otg            | otg     |
| rzv2l-evk       | v2l     | xspi, emmc, esd       | xspi    | udp, otg            | otg     |
| rzv2h-evk       | v2h     | xspi, esd             | xspi    | udp, otg            | otg     |
| rzv2h-rdk       | v2h     | xspi, esd             | xspi    | udp                 | udp     |
| imdt-v2h-sbc    | v2h     | xspi                  | xspi    | udp, otg            | otg     |

**Notes:**
- *IPL flash method*: `emmc` for `rzv2h` devices is **not supported yet**.
- *RZ/G2L-SBC*: `otg` flashing is not supported. This board supports UDP flashing only.
---

## Field Reference

- **`ipl_flash_method`**
  Defines where the **IPL/BL2** image is flashed:
  - `xspi` — xSPI flash for RZ/V2H, QSPI for RZV2L/RZG2L
  - `emmc` — eMMC device
  - `esd` — eSD card
- **`rootfs_flash_method`**
  How the **root filesystem (.wic)** is delivered to the SD/eMMC target:
  - `udp` — U-Boot `fastboot udp` over Ethernet
  - `otg` — U-Boot `fastboot usb` (USB-OTG)

Example of a sample board configuration in JSON:

```json
"rzg2l-sbc": {
    "soc": "g2l",
    "bl2": "bl2_bp_rzg2l-sbc.srec",
    "board_identification": "rzg2l-sbc-platform-settings.bin",
    "fip": "fip_rzg2l-sbc.srec",
    "atf_fdts": "rzg2l-sbc.dtb",
    "uboot_dtb": "rzg2l-sbc.dtb",
    "flash_writer": "Flash_Writer_SCIF_rzg2l-sbc.mot",
    "ipl_flash_method": "xspi",
    "rootfs": "core-image-minimal.wic",
    "rootfs_flash_method": "udp"
}
```

**Note**: When adding a new board entry or adding filename fields for a board, the values for the "bl2" and "fip" fields must include the board identifier (the JSON object key) as a substring.

```
"rzg2l-sbc": {
  "bl2": "bl2_bp_rzg2l-sbc.srec",
  "fip": "fip_rzg2l-sbc.srec",
  ...
}
```

## Flowchart

The universal flash script prompts the user for options and proceeds through the flashing process based on the input. The detailed procedure is as follows:
### Help Menu Flowchart

The following flowchart illustrates the logic when running the help command for the universal flash tool. It shows the user interaction steps and options available:

```mermaid
flowchart TD
  classDef default fill:#f0f4f8,stroke:#333,stroke-width:1px,font-size:14px
  classDef decision fill:#fef6e4,stroke:#c89b3c,stroke-width:2px,font-weight:bold
  classDef action fill:#dbeafe,stroke:#3b82f6,stroke-width:2px
  classDef terminal fill:#d1fae5,stroke:#10b981,stroke-width:2px,font-weight:bold

  H1[Start]:::terminal --> H2[Display Help Menu with options]:::action
  H2 --> H3{"User selects option 1, 2, or 3"}:::decision
  H3 -->|1: Installation| H4[Show installation and setup instructions]:::action
  H4 --> H5[Refer user to README.md for details]:::action
  H5 --> H6{"Prompt: Run flash tool now?"}:::decision
  H6 -->|y| H7[Run flash tool]:::action
  H6 -->|n| H8[Exit]:::terminal
  H3 -->|2: Run tool| H7[Run flash tool]:::action
  H3 -->|3: Exit| H8[Exit]:::terminal
```

To display this help menu, use the following command:

- **On Linux:**
  ```bash
  python3 universal_flash.py --help
  ```

- **On Windows:**
  ```powershell
  py universal_flash.py --help
  ```

### Installation Flowchart
This flowchart shows the process when running the universal flash tool directly (without the --help argument). The script will immediately start the flashing workflow:

```mermaid
flowchart TD
  classDef default fill:#f0f4f8,stroke:#333,stroke-width:1px,font-size:14px
  classDef decision fill:#fef6e4,stroke:#c89b3c,stroke-width:2px,font-weight:bold
  classDef action fill:#dbeafe,stroke:#3b82f6,stroke-width:2px
  classDef terminal fill:#d1fae5,stroke:#10b981,stroke-width:2px,font-weight:bold

  A[Start]:::terminal --> B[Display available boards]:::action
  B --> C[User selects board]:::action
  C --> D[Get board IPL flash method]:::action
  D --> E{"IPL method is eSD?"}:::decision

  E -->|Yes| E1[Check for sudo/admin privileges]:::action
  E1 --> E2{"Privileges OK?"}:::decision
  E2 -->|No| E3["Exit: Requires sudo/admin"]:::terminal
  E2 -->|Yes| E4[Prompt for eSD device selection]:::action
  E4 --> G{"Write IPL?"}:::decision

  E -->|No| F1[Display available serial ports]:::action
  F1 --> F2[User selects port]:::action
  F2 --> G{"Write IPL?"}:::decision

  G -->|Yes| H{"Select IPL method"}:::decision
  H -->|BootloaderFlash| M[Compile firmware: build BL2 & FIP with per-board DTB at runtime]:::action
  M --> J[Write IPL by BootloaderFlash]:::action
  H -->|ULoadFlash| K[Write IPL by ULoadFlash]:::action

  J --> F3{"Write RootFS?"}:::decision
  K --> F3{"Write RootFS?"}:::decision
  G -->|No| F3{"Write RootFS?"}:::decision

  F3 -->|Yes| FR[Write RootFS to SD/eMMC via Fastboot]:::action
  FR --> L[End]:::terminal
  F3 -->|No| L[End]:::terminal
```

**Explanation:**
When you run the script without any arguments, it will skip the help menu and immediately prompt you to select a board and begin the flashing process. You will be guided through board selection, serial port setup, IPL and rootfs flashing steps.

Refer to the [Basic Usage](#basic-usage) section for commands to run the tool.

**Notes:**
- Ensure the board is powered off before flashing.
- Insert the SD card if rootfs flashing is selected.
- For Bootloader-flash: set boot switches to SCIF download mode.
- For Uload-flash or rootfs flashing: set boot switches to normal mode.
- **Reset and power-cycle behavior by board:**
  - **RZ/G2L-SBC**
    This board does not provide a dedicated **RESET** button. To restart the board or apply a boot mode change, you must power-cycle it.
  - **RZ/G2L-EVK** and **RZ/V2L-EVK**
    These boards provide a **RESET** button. You can reset the board without removing power, and the USB connection and serial port typically remain available.
  - **RS-G2L100**
    This board does not provide a dedicated **RESET** button. To restart the board or apply a boot mode change, you must power-cycle it.
  - **RZ/V2H-EVK**
    This board provides a **RESET** button. You can reset the board without removing power, and the USB connection and serial port typically remain available.
  - **RZ/V2H-RDK**
    This board does not provide a dedicated **RESET** button. To restart the board or apply a boot mode change, you must power-cycle it by unplugging and reconnecting the power adapter. Because the USB serial interface is powered from the same source, the USB device disconnects during power-cycle and the serial port disappears from the host PC. When power-cycling the board, keep the USB cable connected to the same USB port on the host PC to avoid enumeration or reconnection issues.
  - **IMDT V2H-SBC**
    This board provides a **RESET** button. You can reset the board without removing power, and the USB connection and serial port typically remain available.
- Rootfs flash (UDP Fastboot): U-Boot fastboot-udp uses a single active Ethernet MAC per board. If multiple RJ45/PHY ports exist, only one is active (depending on board support). The script automatically selects the appropriate Ethernet port based on board configuration in `boards_flash_config.toml`. For boards with multiple available ports, the script will prompt you to select which port to use.

  | Board         | Ethernet port(s) used |
  |-------------|----------------------|
  | rzg2l-sbc    | 1                    |
  | rs-g2l100    | 0, 1                 |
  | rzv2l-evk    | 0                    |
  | rzg2l-evk    | 0                    |
  | rzv2h-evk    | 0, 1                 |
  | rzv2h-rdk    | 0                    |
  | imdt-v2h-sbc | 0, 1                 |

Both fastboot-otg and fastboot-udp write to U-Boot's current MMC device (typically mmc0). Depending on board and revision, mmc0 may point to the SD card or eMMC.

| Board/Rev                                   | Fastboot Method | Typical mmc0 target                                 | How to change target           |
|---------------------------------------------|-----------------|-----------------------------------------------------|-------------------------------|
| RZ/G2L-SBC                                  | UDP             | Carrier SD (board default)                          | N/A (single device)           |
| RS-G2L100                                   | UDP, OTG        | eMMC                                                | N/A (single device)           |
| RZ/V2L-EVK                                  | UDP, OTG        | SD (CN3 on SOM or eMMC device depending on SW1)     | Set SW1-2 ON to SD and OFF to eMMC |
| RZ/G2L-EVK                                  | UDP, OTG        | SD (CN3 on SOM or eMMC device depending on SW1)     | Set SW1-2 ON to SD and OFF to eMMC |
| RZ/V2H-EVK (Rev 1 – 2 SD cards)             | UDP, OTG        | SD card slot 0                                      | N/A (single device)           |
| RZ/V2H-EVK (Rev 2 – SD & eMMC)              | UDP, OTG        | eMMC                                                | N/A (single device)           |
| RZ/V2H-RDK                                  | UDP             | SD card                                             | N/A (single device)           |
| IMDT V2H-SBC                                | UDP, OTG        | eMMC                                                | N/A (single device)           |

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

### Dedicated Flashing Scripts

If preferred, individual scripts can be used for each flashing operation.

#### Flash Bootloader

This script is used to flash the initial bootloader image onto the board via a serial interface. It is typically used when setting up the board for the first time or recovering from a corrupted bootloader.

Location:
```
host/tools/bootloader_flasher/
```

Refer to the `Readme.md` file in that folder for detailed instructions.

#### Flash Bootloader from U-Boot Console

This method allows bootloader updates directly from the U-Boot console without requiring changes to hardware boot modes. It is ideal for in-system updates after the system is already running.

Location
```
host/tools/uload_bootloader/
```

Refer to the `Readme.md` file in that folder for detailed instructions.

#### Flash Root Filesystem to microSD Card

This script is used to write the root filesystem and related images to a SD card, which the board uses to boot and run Linux.

Location
```
host/tools/sd_creator/
```

Refer to the `Readme.md` file in that folder for detailed instructions.