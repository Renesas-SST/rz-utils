# Root filesystem Programming/Flashing Procedure for RZ board on multiple OS environment

This document introduces the comprehensive instructions for flashing a root filesystem (`.wic`) to RZ boards using `sd_flash.py`. It includes prerequisites, Fastboot availability, driver setup, usage for UDP and OTG fastboot, and troubleshooting.

---

## Prerequisites

### Windows

Fastboot is available on Windows via `host/tools/fastboot.exe`, but the device's **Fastboot / USB-download** interface must use the **WinUSB** driver.

1. **Prepare connections**
   - Connect the board's **USB-to-serial** to the PC.
   - Open **Tera Term** (or any serial console) on the correct COM port/baud.

2. **Enter U-Boot and switch to USB OTG Fastboot**
   - **Power on** the board and **interrupt autoboot** to get a `U-Boot>` prompt.
   - Connect the board's **USB OTG** port to the PC.
   - At the U-Boot prompt, run:
     ```bash
     setenv serial# 'Renesas1'
     fastboot usb 27
     ```
     > This places the board into **USB OTG fastboot/download** mode.

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

### Linux

```bash
sudo apt-get update
sudo apt-get install -y android-tools-fastboot || true
# Verify the installation
fastboot --version
```

Expected output:

```bash
renesas@builder-pc:~$ fastboot --version
Android Debug Bridge version <version>
Version <debian-version>
Installed as /usr/lib/android-sdk/platform-tools/adb
Running on Linux <kernel-version> (<architecture>)
```

---

## Outline of the folder


```
sd_creator/
├── tools/
│   ├── NOTICE.txt
│   ├── fastboot.exe
│   ├── AdbWinApi.dll
│   └── AdbWinUsbApi.dll
└── sd_flash.py
```

---

## Hardware Connections

| Fastboot Type | Connection to Host | Board Ports Used     | Notes                               |
|---|---|---|---|
| **UDP**       | Ethernet cable     | RJ45 + Debug Serial  | Requires IP address and Ethernet port index. |
| **OTG**       | USB cable          | USB OTG + Debug Serial | No Ethernet/IP required.                 |

> **UDP Fastboot — Single-Port Note**  
> U-Boot fastboot-udp uses a single active Ethernet MAC per board. If multiple RJ45/PHY ports exist, only one is active (depending on board support). Select the interface via `--ether_port`.

- `--ether_port` corresponds to the **U-Boot Ethernet device index**.

**UDP port index (required at runtime)**

Specify the Ethernet device index with `--ether_port` when using `--fastboot_type udp`.  
**Default = `1`** if not provided. Use the board-specific value below for reliable operation:

| Board       | `--ether_port` to use |
|------------|------------------------|
| rzg2l-sbc  | 1 |
| rzv2l-evk  | 0 |
| rzg2l-evk  | 0 |
| rzv2h-evk  | 0, 1 |

**Fastboot MMC Target**

Both fastboot-otg and fastboot-udp write to U-Boot's current MMC device (typically mmc0). Depending on board and revision, mmc0 may point to the SD card or eMMC.

| Board / Rev                                | Fastboot Method | Typical mmc0 target                                                     | How to change target                                           |
|--------------------------------------------|-----------------|-------------------------------------------------------------------------|----------------------------------------------------------------|
| rzg2l-sbc                                  | UDP             | Carrier SD (board default)                                              | N/A (single device)                                            |
| rzv2l-evk                                  | UDP, OTG        | SD (CN3 on SOM or eMMC device depending on SW1)                        | Set SW1-2 ON to SD and OFF to eMMC                             |
| rzg2l-evk                                  | UDP, OTG        | SD (CN3 on SOM or eMMC device depending on SW1)                        | Set SW1-2 ON to SD and OFF to eMMC                             |
| rzv2h-evk (rev 1: 2 SD cards)              | UDP, OTG        | SD card slot 0                                                          | N/A (single device)                                            |
| rzv2h-evk (rev 2: 1 SD & 1 eMMC)           | UDP, OTG        | eMMC                                                                    | N/A (single device)                                            |

---

## Usage Help

Run the following comamnd to know how to use the script:

- **Windows**
  ```powershell
  py sd_flash.py -h
  ```
- **Linux**
  ```bash
  python3 sd_flash.py -h
  ```

---

## Flashing Procedure with `sd_flash.py`

### Step 1 — Prepare the Rootfs Image (wic) (Optional)

```bash
mkdir -p /path/to/universal-scripts/target/images/
cp /path/to/your/wic/file/core-image-weston.wic /path/to/universal-scripts/target/images/
```

### Step 2 — Basic Invocation (defaults)
- **Windows**
  ```powershell
  py sd_flash.py
  ```
- **Linux**
  ```bash
  python3 sd_flash.py
  ```

**Defaults**
| Parameter | Default |
|---|---|
| Board name | `rzg2l-sbc` |
| Fastboot type | `udp` |
| Ethernet port | `1` |
| IP address | `169.254.187.89` |
| Serial port | latest detected (e.g., `COM8` or `/dev/ttyUSB0`) |
| Baud rate | `115200` |
| Rootfs image | `target/images/core-image-weston.wic` |

### Step 3 — Custom Invocation

**Common options**
| Option | Description |
|---|---|
| `--board_name` | e.g., `rzg2l-evk`, `rzv2l-evk`, `rzv2h-evk`, `rzg2l-sbc` |
| `--fastboot_type` | `udp` or `otg` |
| `--ether_port` | UDP only |
| `--ip_address` | UDP only |
| `--serial_port` | COM device (Windows) or `/dev/ttyUSBx` (Linux) |
| `--serial_port_baud` | Baud rate |
| `--image_rootfs` | Path to `.wic` |

**Examples**

- **Windows**
  - **UDP flash**
    ```powershell
    py sd_flash.py --fastboot_type udp --ip_address 169.254.187.9 --ether_port 0 --serial_port COM11 --serial_port_baud 115200 --image_rootfs D:\custom_images\core-image-weston.wic
    ```

  - **OTG flash**
    ```powershell
    py sd_flash.py --fastboot_type otg --serial_port COM11 --serial_port_baud 115200 --image_rootfs D:\custom_images\core-image-weston.wic
    ```
- **Linux**
  - **UDP flash**
    ```bash
    python3 sd_flash.py --fastboot_type udp --ip_address 169.254.187.9 --ether_port 0 --serial_port /dev/ttyUSB0 --serial_port_baud 115200 --image_rootfs ~/home/custom_images/core-image-weston.wic
    ```

  - **OTG flash**
    ```bash
    python3 sd_flash.py --fastboot_type otg --serial_port /dev/ttyUSB0 --serial_port_baud 115200 --image_rootfs ~/home/custom_images/core-image-weston.wic
    ```

> For **OTG**, `--ip_address` and `--ether_port` are not applicable.\
For **UDP**, choose the correct `--ether_port` for the target board (see the table in Hardware connection).

### Step 4 — Start Flashing
1. Configure boot switches for **normal boot** and power on.  
2. The script initializes fastboot (UDP or OTG) and transfers the image.  
3. Reboot to start from the newly programmed rootfs.