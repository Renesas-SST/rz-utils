import sys
import os
import json
import argparse
import glob
from dataclasses import dataclass
from serial.tools.list_ports import comports

# Importing utility applications
sys.path.append(os.path.join(os.path.dirname(__file__), 'firmware_compile'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'bootloader_flasher'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'sd_creator'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'uload_bootloader'))
from firmware_compile import FirmwareBuilder, parse_args
from bootloader_flash import BootloaderFlashUtil
from sd_flash import SdFlashUtil
from uload_bootloader_flash import UloadFlashUtil

try:
    import tomllib as tomli
except ImportError:
    try:
        import tomli
    except ImportError:
        print("ERROR: Neither tomllib (Python >=3.11) nor tomli package is available.")
        print("Please install tomli: pip install tomli")
        print("Or use Python 3.11 or later which includes tomllib.")
        sys.exit(1)

# Constants
MESSAGE_WIDTH = 85
# Fixed baud rate for serial communication
DEFAULT_BAUD_RATE = 115200

@dataclass
class FlashInfo:
    bl2: str
    board_identification: str
    fip: str
    flash_writer: str
    ipl_flash_method: str
    rootfs: str
    rootfs_flash_method: str

class UniversalFlashUtil:
    def __init__(self):
        self.__scriptDir = os.path.dirname(os.path.abspath(__file__))
        self.__rootDir = os.path.abspath(os.path.join(self.__scriptDir, '..', '..'))
        self.__imagesDir = os.path.abspath(os.path.join(self.__rootDir, 'target', 'images'))
        self.json_file = os.path.join(self.__scriptDir, "flash_images.json")
        self.boards_data = {}
        self.board_config = {}
        self.selected_port = None
        self.selected_port_by_id = None  # For reliable reconnection after power cycle
        self.selected_baud_rate = 115200
        self.selected_board_name = None
        self.selected_ip_address = "169.254.187.89"
        self.selected_info = None
        
        # Ensure bpgen and fiptool are executable
        self._ensure_tools_executable()
    
    def _ensure_tools_executable(self):
        """Make bpgen and fiptool executable if they exist"""
        import platform
        import stat
        
        # Determine OS-specific bin directory
        os_name = platform.system().lower()
        if os_name == "linux":
            bin_dir = os.path.join(self.__scriptDir, 'bin', 'linux')
        elif os_name == "windows":
            bin_dir = os.path.join(self.__scriptDir, 'bin', 'windows')
        else:
            return  # Unknown OS, skip
        
        tools = ['bpgen', 'fiptool']
        for tool in tools:
            tool_path = os.path.join(bin_dir, tool)
            if os.path.exists(tool_path):
                try:
                    # Add execute permission for owner, group, and others
                    current_permissions = os.stat(tool_path).st_mode
                    os.chmod(tool_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                except Exception as e:
                    print(f"Warning: Could not set execute permission for {tool}: {e}")

    def _get_by_id_path(self, tty_device: str) -> str:
        """Get the /dev/serial/by-id/ path for a given tty device.
        This allows reliable reconnection after power cycle."""
        by_id_dir = "/dev/serial/by-id"
        if not os.path.exists(by_id_dir):
            return tty_device
        
        device_name = os.path.basename(tty_device)
        
        try:
            for by_id_link in glob.glob(os.path.join(by_id_dir, "*")):
                real_path = os.path.realpath(by_id_link)
                if os.path.basename(real_path) == device_name:
                    return by_id_link
        except Exception as e:
            print(f"Warning: Could not resolve by-id path: {e}")
        
        return tty_device

    def load_json(self):
        try:
            with open(self.json_file, 'r') as f:
                self.boards_data = json.load(f)
        except FileNotFoundError:
            print(f"File '{self.json_file}' not found.")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
    
    def load_board_config(self):
        """Load board configuration from TOML file"""
        try:
            config_path = os.path.join(self.__scriptDir, 'config', 'boards_flash_config.toml')
            with open(config_path, 'rb') as f:
                self.board_config = tomli.load(f)
        except FileNotFoundError:
            print(f"Warning: Board configuration file not found.")
        except Exception as e:
            print(f"Warning: Error loading board config: {e}")

    def input_menu(self):
        # Board selection
        if not self.boards_data:
            print("No board data loaded.")
            return False

        print("Available boards:")
        for idx, board in enumerate(self.boards_data.keys()):
            print(f"{idx + 1}. {board}")

        board_names = list(self.boards_data.keys())
        try:
            selection = int(input("Select board by number: ")) - 1
            if selection < 0 or selection >= len(board_names):
                print("Invalid selection.")
                return False
            self.selected_board_name = board_names[selection]
            print(f"Selected board: {self.selected_board_name}\n")
        except (ValueError, KeyboardInterrupt):
            print("\nOperation cancelled by user.")
            return False

        # Serial port and baud rate selection
        ports = [p.device for p in comports()]
        if not ports:
            print("No serial ports detected. Please connect your board and try again.")
            return False
        print("Available serial ports:")
        for i, port in enumerate(ports):
            print(f"{i}: {port}")


        try:
            index = int(input(f"Select a port by number (Default {ports[0]}): ") or 0)
            if 0 <= index < len(ports):
                self.selected_port = ports[index]
                # Get by-id path for reliable reconnection
                self.selected_port_by_id = self._get_by_id_path(self.selected_port)
            else:
                print("Invalid number. Try again.")
                return False
        except (ValueError, KeyboardInterrupt):
            print("\nOperation cancelled by user.")
            return False

        # Use fixed baud rate - U-Boot console requires 115200
        self.selected_baud_rate = DEFAULT_BAUD_RATE
        
        print(f"Selected port [{self.selected_port}] with baud rate: {self.selected_baud_rate}")
        if self.selected_port_by_id and self.selected_port_by_id != self.selected_port:
            print(f"Device ID path: {self.selected_port_by_id}")
        print()
        return True

    def prepare_binaries(self):
        print("\n=== Building firmware artifacts ===")

        # Map paths from images dir + flash_images.json
        board_soc = self.boards_data[self.selected_board_name]["soc"]
        bl2_path = os.path.join(self.__imagesDir, "atf", "bl2-rz-cmn.bin")
        bl31_path = os.path.join(self.__imagesDir, "atf", "bl31-rz-cmn.bin")
        atf_fdts_path = os.path.join(self.__imagesDir, "atf", "fdts", self.boards_data[self.selected_board_name]['atf_fdts'])
        uboot_dtbs_path = os.path.join(self.__imagesDir, "u-boot", "dtbs", self.boards_data[self.selected_board_name]['uboot_dtb'])
        uboot_nodtb_path = os.path.join(self.__imagesDir, "u-boot", "u-boot-nodtb-rz-cmn.bin")

        # Build the args namespace exactly as firmware-compile expects
        args = parse_args([
            "--board", self.selected_board_name,
            "--soc", board_soc,
            "--method", self.boards_data[self.selected_board_name]["ipl_flash_method"],
            "--bl2", bl2_path,
            "--atf-fdts", atf_fdts_path,
            "--uboot-dtbs", uboot_dtbs_path,
            "--bl31", bl31_path,
            "--u-boot-nodtb", uboot_nodtb_path,
            #"--out-dir", os.path.join(self.__imagesDir, "build_artifacts") # it depends, it can be deployed to target/images or custom dir.
        ])

        builder = FirmwareBuilder(args)
        builder.run_all()

    def info_get(self):
        board_data = self.boards_data[self.selected_board_name]

        self.selected_info = FlashInfo(
            bl2=board_data["bl2"],
            board_identification=board_data["board_identification"],
            fip=board_data["fip"],
            flash_writer=board_data["flash_writer"],
            ipl_flash_method=board_data["ipl_flash_method"],
            rootfs=board_data["rootfs"],
            rootfs_flash_method=board_data["rootfs_flash_method"],
        )

    def print_selected_info(self):
        if not self.selected_info:
            print("No board selected.")
            return

        print(f"\nSelected Board: {self.selected_board_name}")
        print("Board Information:")
        print(f"  BL2: {self.selected_info.bl2}")
        print(f"  Board Identification: {self.selected_info.board_identification}")
        print(f"  Flash Writer: {self.selected_info.flash_writer}")
        print(f"  IPL Flash Method: {self.selected_info.ipl_flash_method}")
        print(f"  Rootfs Flash Method: {self.selected_info.rootfs_flash_method}")
        print(f"  Rootfs: {self.selected_info.rootfs}")

    def yes_no_prompt(self, message: str) -> bool:
        while True:
            answer = input(f"{message} (y/n): ").strip().lower()
            if answer in ['y', 'yes']:
                return True
            elif answer in ['n', 'no']:
                return False
            else:
                print("Please enter 'y' or 'n'.")

    def select_ipl_method(self):
        options = {
            1: "BootloaderFlash",
            2: "UloadFlash"
        }

        print("Write IPL method:")
        for key, value in options.items():
            print(f"{key}. {value}")

        while True:
            try:
                choice = int(input("Select write IPL method by number: "))
                return options[choice]
            except ValueError:
                print("Invalid input. Please enter a number.")

    def run(self):
        self.load_json()
        self.load_board_config()
        if not self.input_menu():
            return
        # Get information for the selected board
        self.info_get()

        # Write IPL
        if(self.yes_no_prompt("Do you want to write the IPL?")):
            # Check if IPL method is selected
            if (self.select_ipl_method() == "BootloaderFlash"):
                print("Writing IPL by bootloader flash...\n")
                # Prepare firmware binaries before flashing
                self.prepare_binaries()

                bootloader_args = [
                    '--board_name', f"{self.selected_board_name}",
                    '--flash_method', f"{self.selected_info.ipl_flash_method}",
                    '--serial_port', f"{self.selected_port}",
                    '--serial_port_baud', f"{self.selected_baud_rate}",
                    '--image_writer', f"{self.__imagesDir}/{self.selected_info.flash_writer}",
                    '--image_bl2', f"{self.__imagesDir}/{self.selected_info.bl2}",
                    '--image_fip', f"{self.__imagesDir}/{self.selected_info.fip}",
                    '--image_bid', f"{self.__imagesDir}/{self.selected_info.board_identification}"
                ]
                bootloaderFlashUtil = BootloaderFlashUtil(args=bootloader_args)
                bootloaderFlashUtil.writeBootloader()

            # UloadFlash
            else:
                # Write uload bootloader
                print("Writing IPL by Uload bootloader...\n")
                uload_bootloader_args = [
                    '--board_name', f"{self.selected_board_name}",
                    '--serial_port', f"{self.selected_port}",
                    '--serial_port_baud', f"{self.selected_baud_rate}"
                ]
                uloadFlashUtil = UloadFlashUtil(args=uload_bootloader_args)
                uloadFlashUtil.writeUloadBootloader()

        # Write Rootfs
        if(self.yes_no_prompt("Do you want to write the rootfs?")):
            print("Writing rootfs...")

            # Prepare arguments for SD Flash
            sdflash_args = [
                '--board_name', f"{self.selected_board_name}",
                '--serial_port', f"{self.selected_port}",
                '--serial_port_baud', f"{self.selected_baud_rate}",
                '--fastboot_type', f"{self.selected_info.rootfs_flash_method}",
                '--image_rootfs', f"{self.__imagesDir}/{self.selected_info.rootfs}",
            ]
            
            # Add by-id path for reliable reconnection after power cycle
            if self.selected_port_by_id:
                sdflash_args += ['--serial_port_by_id', self.selected_port_by_id]

            method = (self.selected_info.rootfs_flash_method or "").lower()

            if method == "udp":
                # Get ethernet port info from board config
                ethernet_port_info = ""
                ether_port = "1"  # default value
                available_ports = []
                
                if self.selected_board_name in self.board_config:
                    board_cfg = self.board_config[self.selected_board_name]
                    if 'ethernet_udp_index' in board_cfg:
                        udp_index = board_cfg['ethernet_udp_index']
                        if isinstance(udp_index, list):
                            # If multiple ports available, allow user to select
                            available_ports = [str(p) for p in udp_index]
                            ethernet_port_info = f" (Available ports: {', '.join(available_ports)})"
                        else:
                            ether_port = str(udp_index)
                            ethernet_port_info = f" (Using Ethernet port: {ether_port})"
                    else:
                        print(f"Warning: 'ethernet_udp_index' not found in board config for {self.selected_board_name}. Using default port 1.")
                        ether_port = "1"
                        ethernet_port_info = " (default port index: 1)"
                        available_ports = []
                
                print(f"\n{'='*MESSAGE_WIDTH}")
                print(f"** IMPORTANT: Ethernet Connection Required **")
                print(f"{'='*MESSAGE_WIDTH}")
                print(f"Please connect an Ethernet cable between:")
                print(f"  - Host (PC or router) Ethernet port")
                print(f"  - Board Ethernet port{ethernet_port_info}")
                print(f"\nEnsure both devices are on the same network segment.")
                print(f"{'='*MESSAGE_WIDTH}\n")
                
                # If multiple ports are available, let user select
                if available_ports:
                    print(f"Available Ethernet ports: {', '.join(available_ports)}")
                    while True:
                        selected_port = input(f"Select Ethernet port (default {available_ports[0]}): ").strip() or available_ports[0]
                        if selected_port in available_ports:
                            ether_port = selected_port
                            break
                        else:
                            print(f"Invalid port. Please select from: {', '.join(available_ports)}")
                
                self.selected_ip_address = input(f"Enter IP address for fastboot udp (default {self.selected_ip_address}): ") or self.selected_ip_address
                
                sdflash_args += ['--ether_port', ether_port,
                         '--ip_address', self.selected_ip_address]
            elif method == "otg":
                # No Ethernet/IP options needed for OTG/USB fastboot
                print(f"\n{'='*MESSAGE_WIDTH}")
                print(f"** IMPORTANT: USB OTG Flashing Mode **")
                print(f"{'='*MESSAGE_WIDTH}")
                print(f"USB OTG flashing will be used to write the rootfs.")
                print(f"Ensure the board's USB OTG port is connected to the PC.")
                print(f"{'='*MESSAGE_WIDTH}\n")
            else:
                print(f"Unsupported rootfs flash method: '{self.selected_info.rootfs_flash_method}'")
                print(f"Supported methods are: 'udp' or 'otg'")
                return False

            sdFlashUtil = SdFlashUtil(args=sdflash_args)
            sdFlashUtil.writeRootfs()

def show_help():
    """Display help menu with options"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    readme_path = os.path.join(script_dir, "README.md")
    
    print("\n" + "="*MESSAGE_WIDTH)
    print("Universal Flash Tool - Help Menu")
    print("="*MESSAGE_WIDTH)
    print("\nOptions:")
    print("  1. View installation and setup instructions")
    print("  2. Run the flash tool")
    print("  3. Exit")
    print("="*MESSAGE_WIDTH)
    
    while True:
        try:
            choice = input("\nSelect an option (1-3): ").strip()
            
            if choice == "1":
                # Display README.md path
                if os.path.exists(readme_path):
                    import platform
                    os_name = platform.system()
                    
                    # Determine which section to refer to based on OS
                    if os_name == "Windows":
                        prereq_section = "Prerequisites -> Python, Environment and Tool Dependencies -> Windows"
                    elif os_name == "Linux":
                        prereq_section = "Prerequisites -> Python, Environment and Tool Dependencies -> Linux"
                    else:
                        prereq_section = "Prerequisites section"
                    
                    print("\n" + "="*MESSAGE_WIDTH)
                    print("Installation and Setup Instructions")
                    print("="*MESSAGE_WIDTH)
                    print(f"\nPlease refer to the README.md file for detailed instructions:")
                    print(f"\nFile path: {readme_path}")
                    print(f"\n** IMPORTANT: Before running the flash tool **")
                    print(f"You must install all prerequisite tools listed in:")
                    print(f"  README.md -> {prereq_section}")
                    print(f"\nThis includes:")
                    print(f"  - Python and required packages (pyserial, tomli)")
                    if os_name == "Linux":
                        print(f"  - Fastboot (android-tools-fastboot)")
                    elif os_name == "Windows":
                        print(f"  - WinUSB driver (via Zadig) for USB OTG flashing")
                    print("="*MESSAGE_WIDTH)
                    
                    # Ask if user wants to continue to flash tool
                    continue_choice = input("\nDo you want to run the flash tool now? (y/n): ").strip().lower()
                    if continue_choice in ['y', 'yes']:
                        return True
                    else:
                        return False
                else:
                    print(f"\nError: README.md not found at {readme_path}")
                    return False
                    
            elif choice == "2":
                return True
                
            elif choice == "3":
                print("\nExiting...")
                return False
                
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                
        except (KeyboardInterrupt, EOFError):
            print("\n\nOperation cancelled.")
            return False

def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(
            description='Universal Flash Tool for RZ boards',
            add_help=False  # Disable default help to use custom help
        )
        parser.add_argument('--help', '-h', action='store_true', 
                          help='Show help menu with installation instructions')
        
        args = parser.parse_args()
        
        # If --help is provided, show help menu
        if args.help:
            if not show_help():
                sys.exit(0)
        
        # Run the flash tool
        universalFlashUtil = UniversalFlashUtil()
        universalFlashUtil.run()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        if "SerialException" in type(e).__name__ or "device disconnected" in str(e).lower():
            print("\n\nSerial connection lost or device disconnected.")
            print("Operation cancelled.")
            sys.exit(1)
        else:
            # Re-raise unexpected exceptions
            raise

if __name__ == '__main__':
    main()
