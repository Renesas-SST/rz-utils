#!/usr/bin/python3

# Imports
import serial
import argparse
import time
import os
import glob
from serial.tools.list_ports import comports
import sys
if sys.version_info >= (3, 11):  # pragma: Python version >=3.11
	import tomllib
else:  # pragma: Python version <3.11
	import tomli as tomllib

DEFAULT_MEDIA_DIR = "uload-bootloader"   # on FAT32 partition
SEPARATOR_WIDTH = 85  # Width for separator lines in console output
SERIAL_RECONNECT_TIMEOUT = 30
SERIAL_RECONNECT_CHECK_INTERVAL = 0.1
SERIAL_READ_TIMEOUT = 10
SERIAL_READ_BUFFER_SIZE = 4096
DEVICE_READY_WAIT = 0.2
BUFFER_CLEAR_WAIT = 0.5
BUFFER_CHECK_WAIT = 0.3
MAX_RECONNECT_RETRIES = 3
SERIAL_BY_ID_DIR = "/dev/serial/by-id"

class UloadFlashUtil:
	def __init__(self, args=None):
		self.__scriptDir = os.path.dirname(os.path.abspath(__file__))
		self.__oldPort = None

		self.__setupArgumentParser(args)
		self.__setupSerialPort()

	def __setupArgumentParser(self, args):
		self.__parser = argparse.ArgumentParser(
			description='Util to flash bootloader from U-Boot console on RZ Board.\n'
						'NOTE: Images must be on SD card partition 1 (FAT32), i.e. mmc 0:1.\n',
			epilog='Example:\n  ./uload_bootloader_flash.py --board_name rzg2l-sbc'
		)
		# Board name
		self.__parser.add_argument('--board_name',
									default='rzg2l-sbc',
									dest='boardName',
									type=str,
									help='Board name to flash bootloader (default: rzg2l-sbc).')

		# Serial
		self.__parser.add_argument('--serial_port',
									default=None,
									dest='serialPort',
									help='Serial port to talk to the board (default: newest connected port).')
		self.__parser.add_argument('--serial_port_by_id',
									default=None,
									dest='serialPortById',
									action='store',
									help='Serial port by-id path for reliable reconnection (e.g., /dev/serial/by-id/...).')
		self.__parser.add_argument('--serial_port_baud',
									default=115200,
									dest='baudRate',
									type=int,
									help='Baud rate (default: 115200).')

		# media paths on the FAT32 partition
		# If only a filename is provided, it will search DEFAULT_MEDIA_DIR/ (uload-bootloader)
		self.__parser.add_argument('--bl2_path',
									dest='bl2Path',
									default=None,
									type=str,
									help='Path/filename of BL2 image on SD (e.g., "uload-bootloader/bl2_bp_rzg2l-sbc.bin" '
									'or just "bl2_bp_rzg2l-sbc.bin").')
		self.__parser.add_argument('--fip_path',
									dest='fipPath',
									default=None,
									type=str,
									help='Path/filename of FIP image on SD.')
		self.__parser.add_argument('--image_bid',
									dest='bidPath',
									default=None,
									type=str,
									help='Path/filename of board-ID/platform-settings binary on SD.')

		if args:
			self.__args = self.__parser.parse_args(args)
		else:
			self.__args = self.__parser.parse_args()

	def __setupSerialPort(self):
		try:
			# Store the by-id path if provided
			self.__serialPortById = getattr(self.__args, 'serialPortById', None)

			if (self.__args.serialPort is None):
				ports = [port.device for port in comports()]
				print(f"Available serial ports: {ports}")
				print(f"Using serial port: {ports[0]}")
				self.__serialPortPath = ports[0]
				self.__serialPort = serial.Serial(port=ports[0], baudrate=self.__args.baudRate, timeout=15)
			else:
				self.__serialPortPath = self.__args.serialPort
				self.__serialPort = serial.Serial(port=self.__args.serialPort, baudrate=self.__args.baudRate, timeout=15)

			# Store old port session
			self.__oldPort = self.__serialPortPath

			# If no by-id path provided, try to resolve it
			if not self.__serialPortById:
				self.__serialPortById = self._get_by_id_path(self.__serialPortPath)

		except:
			die(msg='Unable to open serial port.')

	def _get_by_id_path(self, tty_device: str) -> str:
		"""Get the /dev/serial/by-id/ path for a given tty device."""
		if not os.path.exists(SERIAL_BY_ID_DIR):
			return tty_device

		device_name = os.path.basename(tty_device)

		try:
			for by_id_link in glob.glob(os.path.join(SERIAL_BY_ID_DIR, "*")):
				real_path = os.path.realpath(by_id_link)
				if os.path.basename(real_path) == device_name:
					return by_id_link
		except Exception as e:
			print(f"Warning: Could not resolve by-id path: {e}")

		return tty_device

	def _wait_for_serial_reconnect(self, timeout: int = SERIAL_RECONNECT_TIMEOUT) -> bool:
		"""Wait for serial port to reconnect after power cycle."""

		start_time = time.time()
		last_print_time = 0

		while (time.time() - start_time) < timeout:
			elapsed = time.time() - start_time
			remaining = int(timeout - elapsed)

			# Update status display every second
			if elapsed - last_print_time >= 1.0:
				print(f"\rWaiting for device reconnection... {remaining}s remaining  ", end="", flush=True)
				last_print_time = elapsed

			# Check if device appeared
			target_port = self.__oldPort

			if target_port:
				# Try to open the port to verify it's ready
				try:
					test_port = serial.Serial(port=target_port, baudrate=self.__args.baudRate, timeout=1)
					test_port.close()

					print(f"\n\nDevice detected: {target_port}")
					self.__serialPortPath = target_port
					return True

				except Exception:
					# Port exists but not ready yet, wait a bit
					time.sleep(DEVICE_READY_WAIT)
					continue

			# Short sleep before next check
			time.sleep(SERIAL_RECONNECT_CHECK_INTERVAL)

		print(f"\n\nTimeout: Device did not reconnect within {timeout} seconds.")
		return False

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
		start_time = time.time()

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

		# Wait for device to be ready to receive image.
		print("\nPlease power off the board, set the DIP switches to the normal boot mode, and then power the board back on!")
		print(f"\n{'='*SEPARATOR_WIDTH}")
		print("** IMPORTANT: Do not change the Serial port compared to the initial setup. **")
		print(f"{'='*SEPARATOR_WIDTH}\n")

		# Try to read from serial with reconnection support
		if not self.__serialReadWithReconnect('Hit any key to stop autoboot:', allow_uboot_prompt=True):
			die(msg='Failed to communicate with board after reconnection attempts.')

		# Send enter to get fresh prompt (in case we're already at prompt)
		self.__writeSerialCmd('')
		time.sleep(BUFFER_CHECK_WAIT)

		# Clear any buffered data and verify we have prompt
		if self.__serialPort.in_waiting > 0:
			data = self.__serialPort.read(self.__serialPort.in_waiting).decode(errors='ignore')
			print(data, end='', flush=True)

		# Send another enter to get prompt
		self.__writeSerialCmd('')
		self.__serialRead('=>')

		# Probe xSPI flash
		self.__writeSerialCmd('sf probe')
		self.__serialRead('MiB')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# Pre-check: Verify all files exist on SD card before erasing SPI flash
		print('\n' + '='*SEPARATOR_WIDTH)
		print('** Pre-check: Verifying all required files on SD card **')
		print('='*SEPARATOR_WIDTH)

		files_to_check = [
			('BL2', bl2_path),
			('FIP', fip_path),
			('BID', bid_path)
		]

		# Use fatls to list the directory once
		print(f'\nListing files in {DEFAULT_MEDIA_DIR}/')
		self.__writeSerialCmd(f'fatls mmc ${{mmcdev}}:${{mmcpart}} {DEFAULT_MEDIA_DIR}/')

		# Read the directory listing - wait for file(s) indicator then prompt
		buf = self.__serialPort.read_until(b'file(s)', size=8192)
		buf += self.__serialPort.read_until(b'=>', size=1024)
		dir_listing = buf.decode(errors='ignore')
		print(dir_listing, end='', flush=True)

		# Check if each file exists in the directory listing
		all_files_ok = True
		for file_type, file_path in files_to_check:
			# Extract just the filename from the path (e.g., "uload-bootloader/bl2_bp_rzg2l-sbc.bin" -> "bl2_bp_rzg2l-sbc.bin")
			filename = file_path.split('/')[-1]

			if filename in dir_listing:
				print(f'  [OK] {file_type}: {filename}')
			else:
				print(f'  [MISSING] {file_type}: {filename}')
				all_files_ok = False

		if not all_files_ok:
			print('\n' + '='*SEPARATOR_WIDTH)
			print('** Pre-check FAILED: Missing or inaccessible files on SD card **')
			print('='*SEPARATOR_WIDTH)
			print(f'\nPlease verify that all files exist in {DEFAULT_MEDIA_DIR}/ on SD card partition 1 (FAT32).')
			print('SPI flash was NOT erased. Board is still in bootable state.')
			print('\nFor troubleshooting and detailed instructions, refer to:')
			print('  universal-scripts/host/tools/uload_bootloader/README.md -> Troubleshooting section')
			self.__serialPort.close()
			die(msg='Pre-check failed. Aborting flash operation.')

		print('\n' + '='*SEPARATOR_WIDTH)
		print('** Pre-check PASSED: All files verified on SD card **')
		print('='*SEPARATOR_WIDTH)
		print('\nProceeding with SPI flash erase and write operations...\n')

		# Erase a safe region (adjust size as needed)
		print('Erasing xSPI: please wait...')
		start_time_erase = time.time()
		self.__writeSerialCmd('sf erase 0 100000')
		self.__serialRead('OK')
		print(f"Erase time: {time.time() - start_time_erase:.3f} s")

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# Loading BL2
		print('\nWriting BL2 to SPI flash...')
		self.__writeSerialCmd(f'fatload mmc ${{mmcdev}}:${{mmcpart}} {loadAddress} {bl2_path}')
		self.__serialRead('MiB/s)')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		self.__writeSerialCmd(f'sf write {loadAddress} {xspiFlashAddress[0]} $filesize')
		self.__serialRead('OK')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# Loading FIP
		print('\nWriting FIP to SPI flash...')
		self.__writeSerialCmd(f'fatload mmc ${{mmcdev}}:${{mmcpart}} {loadAddress} {fip_path}')
		self.__serialRead('MiB/s)')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		self.__writeSerialCmd(f'sf write {loadAddress} {xspiFlashAddress[1]} $filesize')
		self.__serialRead('OK')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# Loading Board Identification
		print('\nWriting Board ID to SPI flash...')
		self.__writeSerialCmd(f'fatload mmc ${{mmcdev}}:${{mmcpart}} {loadAddress} {bid_path}')
		self.__serialRead('MiB/s)')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		self.__writeSerialCmd(f'sf write {loadAddress} {xspiFlashAddress[2]} $filesize')
		self.__serialRead('OK')

		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		print('\n' + '='*SEPARATOR_WIDTH)
		print('** Bootloader flashing completed successfully! **')
		print('='*SEPARATOR_WIDTH)
		print("Closed serial port.")
		self.__serialPort.close()

		print(f"Total elapsed time: {time.time() - start_time:.3f} s")

	def __serialReadWithReconnect(self, cond='\n', max_retries=MAX_RECONNECT_RETRIES, allow_uboot_prompt=False) -> bool:
		"""Read from serial with automatic reconnection on failure.

		Args:
			cond: The condition string to wait for
			max_retries: Maximum number of retry attempts
			allow_uboot_prompt: If True, also accept U-Boot prompt (=>) as success condition
		"""

		for attempt in range(max_retries):
			try:
				# First check if there's already data in buffer
				time.sleep(BUFFER_CHECK_WAIT)
				if self.__serialPort.in_waiting > 0:
					existing_data = self.__serialPort.read(self.__serialPort.in_waiting).decode(errors='ignore')
					print(existing_data, end='', flush=True)

					# Check if we already have what we're looking for
					if cond in existing_data or (allow_uboot_prompt and '=>' in existing_data):
						return True

				# If not in buffer, wait for it with timeout
				self.__serialPort.timeout = SERIAL_READ_TIMEOUT
				buf = self.__serialPort.read_until(cond.encode(), size=SERIAL_READ_BUFFER_SIZE)

				if buf:
					decoded = buf.decode(errors="ignore")
					print(decoded, end='', flush=True)

					# Check if we got what we expected
					if cond in decoded or (allow_uboot_prompt and '=>' in decoded):
						return True

				# Need reconnection
				if attempt < max_retries - 1:
					if self._reconnect_serial():
						if allow_uboot_prompt:
							# After reconnect, just return success - we'll verify prompt in writeRootfs
							return True
						continue

				return False

			except serial.SerialException as e:
				# Removed serial error print as requested
				if attempt < max_retries - 1:
					# Removed reconnection attempt print as requested
					if self._reconnect_serial():
						if allow_uboot_prompt:
							return True
						continue
				return False
			except Exception as e:
				print(f"Unexpected error: {type(e).__name__}: {e}")
				if attempt < max_retries - 1:
					if self._reconnect_serial():
						if allow_uboot_prompt:
							return True
						continue
				return False

		print(f"Failed to communicate with board after {max_retries} attempts.")
		return False

	def _reconnect_serial(self) -> bool:
		"""Attempt to reconnect to the serial port."""
		try:
			if self.__serialPort and self.__serialPort.is_open:
				self.__serialPort.close()
		except:
			pass

		# Wait for device to reappear
		if not self._wait_for_serial_reconnect():
			return False

		try:
			# Reopen the port for normal communication
			self.__serialPort = serial.Serial(
				port=self.__serialPortPath,
				baudrate=self.__args.baudRate,
				timeout=15
			)

			# Clear any buffered data
			time.sleep(BUFFER_CLEAR_WAIT)
			if self.__serialPort.in_waiting > 0:
				self.__serialPort.read(self.__serialPort.in_waiting)

			return True

		except Exception as e:
			print(f"Failed to reconnect to serial port: {e}")
			return False

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
