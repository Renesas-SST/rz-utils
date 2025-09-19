#!/usr/bin/python3

# Imports
import serial
import argparse
import time
import os
from serial.tools.list_ports import comports
import sys
if sys.version_info >= (3, 11):  # pragma: Python version >=3.11
	import tomllib
else:  # pragma: Python version <3.11
	import tomli as tomllib

DEFAULT_MEDIA_DIR = "uload-bootloader"   # on FAT32 partition

class UloadFlashUtil:
	def __init__(self, args=None):
		self.__scriptDir = os.path.dirname(os.path.abspath(__file__))
		self.__setupArgumentParser(args)
		self.__setupSerialPort()

	def __setupArgumentParser(self, args):
		p = argparse.ArgumentParser(
			description='Util to flash bootloader from U-Boot console on RZ Board.\n'
						'NOTE: Images must be on SD card partition 1 (FAT32), i.e. mmc 0:1.\n',
			epilog='Example:\n  ./uload_bootloader_flash.py --board_name rzg2l-sbc'
		)
		# Board name
		p.add_argument('--board_name', default='rzg2l-sbc', dest='boardName', type=str,
					help='Board name to flash bootloader (default: rzg2l-sbc).')

		# Serial
		p.add_argument('--serial_port', default=None, dest='serialPort',
					help='Serial port to talk to the board (default: newest connected port).')
		p.add_argument('--serial_port_baud', default=115200, dest='baudRate', type=int,
					help='Baud rate (default: 115200).')

		# media paths on the FAT32 partition
		# If only a filename is provided, it will search DEFAULT_MEDIA_DIR/ (uload-bootloader)
		p.add_argument('--bl2_path', dest='bl2Path', default=None, type=str,
					help='Path/filename of BL2 image on SD (e.g., "uload-bootloader/bl2_bp_rzg2l-sbc.bin" '
							'or just "bl2_bp_rzg2l-sbc.bin").')
		p.add_argument('--fip_path', dest='fipPath', default=None, type=str,
					help='Path/filename of FIP image on SD.')
		p.add_argument('--image_bid', dest='bidPath', default=None, type=str,
					help='Path/filename of board-ID/platform-settings binary on SD.')

		self.__parser = p
		self.__args = p.parse_args(args) if args else p.parse_args()

	def __setupSerialPort(self):
		try:
			if self.__args.serialPort is None:
				ports = [port.device for port in comports()]
				if not ports:
					die('No serial ports found.')
				print(f"Available serial ports: {ports}")
				print(f"Using serial port: {ports[0]}")
				self.__serialPort = serial.Serial(port=ports[0], baudrate=self.__args.baudRate, timeout=15)
			else:
				self.__serialPort = serial.Serial(port=self.__args.serialPort, baudrate=self.__args.baudRate, timeout=15)
		except Exception as e:
			die(msg=f'Unable to open serial port ({e}).')

	def __getUloadFlashInfo(self):
		configFile = os.path.join(self.__scriptDir, "..", "config", 'boards_flash_config.toml')
		with open(configFile, "rb") as f:
			flash_info = tomllib.load(f)

		try:
			self.__uloadFlashInfo = flash_info[self.__args.boardName]
		except KeyError:
			die(msg=f'Board name "{self.__args.boardName}" is not supported.')

	@staticmethod
	def __resolve_media_path(name_or_path: str) -> str:
		"""Return a path usable by U-Boot fatload.
		If only a filename is given (no '/'), prepend DEFAULT_MEDIA_DIR/."""
		if name_or_path is None:
			return None
		if '/' in name_or_path or '\\' in name_or_path:
			return name_or_path.replace('\\', '/')
		return f"{DEFAULT_MEDIA_DIR}/{name_or_path}"

	def writeUloadBootloader(self):
		self.__getUloadFlashInfo()
		xspiFlashAddress = self.__uloadFlashInfo["flash_address"]
		loadAddress = self.__uloadFlashInfo["load_address"]

		# Derive defaults from boardName if user didn’t pass custom paths
		default_bl2_name = f"bl2_bp_{self.__args.boardName}.bin"
		default_fip_name = f"fip_{self.__args.boardName}.bin"
		default_bid_name = f"{self.__args.boardName}-platform-settings.bin"

		bl2_path = self.__resolve_media_path(self.__args.bl2Path or default_bl2_name)
		fip_path = self.__resolve_media_path(self.__args.fipPath or default_fip_name)
		bid_path = self.__resolve_media_path(self.__args.bidPath or default_bid_name)

		print("Image sources on SD (mmc 0:1):")
		print(f"  BL2 : {bl2_path}")
		print(f"  FIP : {fip_path}")
		print(f"  BID : {bid_path}")

		start_time = time.time()

		# Wait for device to be ready to receive image.
		print("Please power on the board and ensure the DIP switches are set to normal boot mode. Press RESET if available (on EVK boards); otherwise, power-cycle (e.g., toggle the POWER switch or unplug/replug power).")
		self.__serialRead('Hit any key to stop autoboot:')
		self.__writeSerialCmd('')

		self.__serialRead('=>')

		# Probe xSPI flash
		self.__writeSerialCmd('sf probe')
		self.__serialRead('MiB')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# Erase a safe region (adjust size as needed)
		print('Erasing xSPI: please wait...')
		start_time_erase = time.time()
		self.__writeSerialCmd('sf erase 0 100000')
		self.__serialRead('OK')
		print(f"Erase time: {time.time() - start_time_erase:.3f} s")

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# Loading BL2
		# ${mmcdev} and ${mmcpart} are U-Boot environment variables.
		self.__writeSerialCmd(f'fatload mmc ${{mmcdev}}:${{mmcpart}} {loadAddress} {bl2_path}')
		self.__serialRead('MiB/s)')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		self.__writeSerialCmd(f'sf write {loadAddress} {xspiFlashAddress[0]} $filesize')
		self.__serialRead('OK')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# Loading FIP
		# ${mmcdev} and ${mmcpart} are U-Boot environment variables.
		self.__writeSerialCmd(f'fatload mmc ${{mmcdev}}:${{mmcpart}} {loadAddress} {fip_path}')
		self.__serialRead('MiB/s)')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		self.__writeSerialCmd(f'sf write {loadAddress} {xspiFlashAddress[1]} $filesize')
		self.__serialRead('OK')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# Loading Board Identification
		# ${mmcdev} and ${mmcpart} are U-Boot environment variables.
		self.__writeSerialCmd(f'fatload mmc ${{mmcdev}}:${{mmcpart}} {loadAddress} {bid_path}')
		self.__serialRead('MiB/s)')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		self.__writeSerialCmd(f'sf write {loadAddress} {xspiFlashAddress[2]} $filesize')
		self.__serialRead('OK')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		print("Closed serial port.")
		self.__serialPort.close()

		print(f"Elapsed time: {time.time() - start_time:.3f} s")

	def __writeSerialCmd(self, cmd):
		self.__serialPort.write(f'{cmd}\r'.encode())

	# Function to wait and print contents of serial buffer
	def __serialRead(self, cond='\n'):
		buf = self.__serialPort.read_until(cond.encode())
		if not buf:
			print("Returned value is not the expectation. Exiting.")
			exit()
		print(buf.decode(errors="ignore"))

# Util function to die with error
def die(msg='', code=1):
	print(f'Error: {msg}')
	exit(code)

def main():
	tool = UloadFlashUtil()
	tool.writeUloadBootloader()

if __name__ == '__main__':
	main()
