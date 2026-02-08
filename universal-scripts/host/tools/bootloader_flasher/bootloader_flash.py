#!/usr/bin/env python3

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

# Constants
SEPARATOR_WIDTH = 85  # Width for separator lines in console output
WAIT_POWER_TIMEOUT = 120
SERIAL_RECONNECT_TIMEOUT = 30
SERIAL_RECONNECT_CHECK_INTERVAL = 0.1
SERIAL_READ_TIMEOUT = 10
SERIAL_READ_BUFFER_SIZE = 4096
DEVICE_READY_WAIT = 0.2
BUFFER_CLEAR_WAIT = 0.5
BUFFER_CHECK_WAIT = 0.3
MAX_RECONNECT_RETRIES = 3
SERIAL_BY_ID_DIR = "/dev/serial/by-id"

class BootloaderFlashUtil:
	def __init__(self, args=[]):
		self.__scriptDir = os.path.dirname(os.path.abspath(__file__))
		self.__rootDir = os.path.abspath(os.path.join(self.__scriptDir, '..', '..', '..'))
		self.__imagesDir = os.path.abspath(os.path.join(self.__rootDir, 'target', 'images'))
		self.__oldPort = None
		self.__initialConnection = True

		self.__setupArgumentParser(args)
		self.__getFlashAddress()
		self.__setupSerialPort()

	# Setup CLI parser
	def __setupArgumentParser(self, args=[]):
		# Create parser
		self.__parser = argparse.ArgumentParser(description='Util to flash bootloader on RZ Board.\n', epilog='Example:\n\t./bootloader_flash.py')

		# Add arguments
		# Board name
		self.__parser.add_argument('--board_name',
									default='rzg2l-sbc',
									dest='boardName',
									action='store',
									type=str,
									help='Board name to flash bootloader (defaults to: rzg2l-sbc).')
		self.__parser.add_argument('--flash_method',
									default='xspi',
									dest='flashMethod',
									action='store',
									type=str,
									choices=['emmc', 'xspi', 'esd'],
									help='Flash method to use (defaults to: xspi).')

		# Serial port arguments
		self.__parser.add_argument('--serial_port',
									default=None,
									dest='serialPort',
									action='store',
									help='Serial port used to talk to board (defaults to: most recently connected port).')
		self.__parser.add_argument('--serial_port_by_id',
									default=None,
									dest='serialPortById',
									action='store',
									help='Serial port by-id path for reliable reconnection (e.g., /dev/serial/by-id/...).')
		self.__parser.add_argument('--serial_port_baud',
									default=115200,
									dest='baudRate',
									action='store',
									type=int,
									help='Baud rate for serial port (defaults to: 115200).')

		# Images
		self.__parser.add_argument('--image_writer',
									default=f'{self.__imagesDir}/Flash_Writer_SCIF_rzg2l-sbc.mot',
									dest='flashWriterImage',
									action='store',
									type=str,
									help="Path to Flash Writer image (defaults to: <path/to/your/package>/target/images/Flash_Writer_SCIF_rzg2l-sbc.mot).")
		self.__parser.add_argument('--image_bl2',
									default=f'{self.__imagesDir}/bl2_bp_rzg2l-sbc.srec',
									dest='bl2Image',
									action='store',
									type=str,
									help='Path to bl2 image (defaults to: <path/to/your/package>/target/images/bl2_bp_rzg2l-sbc.srec).')
		self.__parser.add_argument('--image_fip',
									default=f'{self.__imagesDir}/fip_rzg2l-sbc.srec',
									dest='fipImage',
									action='store',
									type=str,
									help='Path to FIP image (defaults to: <path/to/your/package>/target/images/fip_rzg2l-sbc.srec).')
		self.__parser.add_argument('--image_bid',
									default=f'{self.__imagesDir}/rzg2l-sbc-platform-settings.bin',
									dest='bidImage',
									action='store',
									type=str,
									help='Path to board identification image (defaults to: <path/to/your/package>/target/images/rzg2l-sbc-platform-settings.bin).')

		if args:
			self.__args = self.__parser.parse_args(args)
		else:
			self.__args = self.__parser.parse_args()

	# Setup Serial Port
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

	def __getFlashAddress(self):
		configFile = os.path.join(self.__scriptDir, ".." , "config", 'boards_flash_config.toml')
		with open(configFile, "rb") as f:
			flash_info = tomllib.load(f)

		self.__flashAddress = flash_info[self.__args.boardName]

		if self.__flashAddress is None:
			print(f"Board name {self.__args.boardName} is not supported.")
			exit()

	# Setup Serial Port SUP
	def __setupSerialPort_SUP(self):
		try:
			self.__serialPort.baudrate = 921600
		except:
			die(msg='Unable to open serial port 921600 bps.')

	def __wait_for_prompt(self, timeout=30):
		end_time = time.time() + timeout
		buffer = b""
		sent_y = False

		while time.time() < end_time:
			if self.__serialPort.in_waiting:
				buffer += self.__serialPort.read(self.__serialPort.in_waiting)
				decoded = buffer.decode(errors='ignore')

				if not sent_y and "Clear OK" in decoded:
					self.__writeSerialCmd('y')
					sent_y = True  # prevent sending again

				if ">" in decoded:
					break

			time.sleep(0.1)

		print(f'{buffer.decode(errors="ignore")}')

	# Function to write bootloader
	def writeBootloader(self):
		start_time = time.time()

		# Check file exists
		if not os.path.exists(self.__args.flashWriterImage):
			print(f"The file {self.__args.flashWriterImage} does not exist.")
			exit()
		if not os.path.exists(self.__args.bl2Image):
			print(f"The file {self.__args.bl2Image} does not exist.")
			exit()
		if not os.path.exists(self.__args.fipImage):
			print(f"The file {self.__args.fipImage} does not exist.")
			exit()
		if not os.path.exists(self.__args.bidImage):
			print(f"The file {self.__args.bidImage} does not exist.")
			exit()

		# Wait for device to be ready to receive image.
		print("\nPlease power off the board, set the DIP switches to SCIF download mode, and then power the board back on." \
		"\nNote: Setting an incorrect boot mode may lead to unexpected behavior.")
		print(f"\n{'='*SEPARATOR_WIDTH}")
		print("** IMPORTANT: Do not change the Serial port compared to the initial setup. **")
		print(f"{'='*SEPARATOR_WIDTH}\n")

		# TODO: Each board has the different responses.
		# We need to list out all the supported responses corresponding to the supported boards.
		# Try to read from serial with reconnection support
		if (self.__args.boardName == "rzv2h-evk" or self.__args.boardName == "imdt-v2h-sbc"):
			ok = self.__serialReadWithReconnect('Load Program to SRAM', allow_uboot_prompt=True)
		elif (self.__args.boardName == "rzv2h-rdk"):
			ok = self.__serialReadNoResponseWithReconnect()
		else:
			ok = self.__serialReadWithReconnect('please send !', allow_uboot_prompt=True)

		if not ok:
			die(msg='Failed to communicate with board after reconnection attempts.')

		# Write flash writer application
		time1 = time.time()
		print("\nWriting Flash Writer application...")
		self.__writeFileToSerial(self.__args.flashWriterImage)
		self.__serialRead('>')

		time2 = time.time()
		elapsed_time = time2 - time1
		print(f"Elapsed time: Flash Writer: {elapsed_time:.6f} seconds")
		print("Flash Writer has finished successfully.\n")

		self.__writeSerialCmd('')
		self.__serialRead('>')

		# emmc flash
		if (self.__args.flashMethod == "emmc"):
			self.__handle_emmc_flash(self.__flashAddress["emmc"])
		# xspi flasj
		elif (self.__args.flashMethod == "xspi"):
			self.__handle_xspi_flash(self.__flashAddress["xspi"])

		print("Closed serial port.")
		self.__serialPort.close()

		end_time = time.time()
		elapsed_time = end_time - start_time
		print(f"Elapsed time: {elapsed_time:.6f} seconds")

	def __handle_emmc_flash(self, flashAddress):
		self.__writeSerialCmd('EM_E')
		self.__serialRead('Select area')
		self.__writeSerialCmd('1')
		self.__serialRead('>')

		# Changing speed to 921600 bps.
		self.__writeSerialCmd('SUP')
		self.__serialRead('the terminal.')

		self.__setupSerialPort_SUP()
		time.sleep(1)
		self.__writeSerialCmd('')
		self.__serialRead('>')

		# Write BL2
		BL2FlashAddress = flashAddress["BL2"]
		self.__writeSerialCmd('EM_W')
		self.__serialRead('Select area')
		self.__writeSerialCmd(BL2FlashAddress[0])

		self.__serialRead('Please Input Start Address in sector')
		self.__writeSerialCmd(BL2FlashAddress[1])

		self.__serialRead('Please Input Program Start Address')
		self.__writeSerialCmd(BL2FlashAddress[2])
		self.__serialRead('please send !')

		print("Writing BL2...")
		self.__writeFileToSerial(self.__args.bl2Image)
		self.__serialRead('>')
		print("BL2 write complete.\n")

		# Write FIP
		FIPFlashAddress = flashAddress["FIP"]
		self.__writeSerialCmd('EM_W')
		self.__serialRead('Select area')
		self.__writeSerialCmd(FIPFlashAddress[0])

		self.__serialRead('Please Input Start Address in sector')
		self.__writeSerialCmd(FIPFlashAddress[1])

		self.__serialRead('Please Input Program Start Address')
		self.__writeSerialCmd(FIPFlashAddress[2])
		self.__serialRead('please send !')
		print("Writing FIP...")
		self.__writeFileToSerial(self.__args.fipImage)

		self.__serialRead('EM_W Complete!')
		print("FIP write completed.\n")

		# Write EXT_CSD
		self.__writeSerialCmd('EM_SECSD')
		self.__serialRead('Please Input EXT_CSD Index')
		self.__writeSerialCmd('B1')
		self.__serialRead('Please Input Value')
		self.__writeSerialCmd(FIPFlashAddress[3])
		self.__serialRead('>')

		self.__writeSerialCmd('EM_SECSD')
		self.__serialRead('Please Input EXT_CSD Index')
		self.__writeSerialCmd('B3')
		self.__serialRead('Please Input Value')
		self.__writeSerialCmd(FIPFlashAddress[4])
		self.__serialRead('>')

		# Write board identification
		BIDFlashAddress = flashAddress["BID"]
		self.__writeSerialCmd('EM_WB')
		self.__serialRead('Select area')
		self.__writeSerialCmd(BIDFlashAddress[0])

		self.__serialRead('Please Input Start Address in sector')
		self.__writeSerialCmd(BIDFlashAddress[1])

		self.__serialRead('Please Input File size(byte)')
		self.__writeSerialCmd(BIDFlashAddress[2])
		self.__serialRead('please send binary file!')

		print("Writing board identification...")
		self.__writeFileToSerial(self.__args.bidImage)
		self.__serialRead('>')
		print("Board identification write completed.\n")

	def __handle_xspi_flash(self, flashAddress):
		if not (self.__args.boardName == "rzv2h-evk") and not (self.__args.boardName == "rzv2h-rdk"):
			print("\n" + "="*SEPARATOR_WIDTH)
			print("** ERASING QSPI FLASH MEMORY **")
			print("="*SEPARATOR_WIDTH)
			print("This operation will erase the SpiFlash memory.")
			print("Please wait, this may take up to 60 seconds...")
			print("The terminal will appear to freeze during this time - this is normal.")
			print("="*SEPARATOR_WIDTH + "\n")

			self.__writeSerialCmd('XCS')
			self.__wait_for_prompt(60)

			print("\n" + "="*SEPARATOR_WIDTH)
			print("QSPI flash erase complete!")
			print("="*SEPARATOR_WIDTH + "\n")

		# Changing speed to 921600 bps.
		self.__writeSerialCmd('SUP')
		self.__serialRead('the terminal.')

		self.__setupSerialPort_SUP()
		time.sleep(1)
		self.__writeSerialCmd('')
		self.__serialRead('>')

		# Write BL2
		BL2FlashAddress = flashAddress["BL2"]
		self.__writeSerialCmd('XLS2')
		self.__serialRead('Please Input : H')
		self.__writeSerialCmd(BL2FlashAddress[0])

		self.__serialRead('Please Input : H')
		self.__writeSerialCmd(BL2FlashAddress[1])
		self.__serialRead('please send !')

		print("Writing BL2...")
		self.__writeFileToSerial(self.__args.bl2Image)
		self.__serialRead('>')
		print("BL2 write completed.\n")

		# Write FIP
		FIPFlashAddress = flashAddress["FIP"]
		self.__writeSerialCmd('XLS2')
		self.__serialRead('Please Input : H')
		self.__writeSerialCmd(FIPFlashAddress[0])

		self.__serialRead('Please Input : H')
		self.__writeSerialCmd(FIPFlashAddress[1])
		self.__serialRead('please send !')

		print("Writing FIP...")
		self.__writeFileToSerial(self.__args.fipImage)
		self.__wait_for_prompt()
		print("FIP write completed.\n")

		# Write board identification
		BIDFlashAddress = flashAddress["BID"]
		if (self.__args.bidImage.endswith('.srec')):
			self.__writeSerialCmd('XLS2')
		else:
			self.__writeSerialCmd('XLS3')
		self.__serialRead('Please Input : H')
		self.__writeSerialCmd(BIDFlashAddress[0])

		self.__serialRead('Please Input : H')
		self.__writeSerialCmd(BIDFlashAddress[1])
		self.__serialRead('please send !')

		print("Writing board identification...")
		self.__writeFileToSerial(self.__args.bidImage)
		self.__wait_for_prompt()
		print("Board identification write completed.\n")

	def __serialReadWithReconnect(self, cond='\n', max_retries=MAX_RECONNECT_RETRIES, allow_uboot_prompt=False) -> bool:
		"""Read from serial with automatic reconnection on failure.
		Args:
			cond: The condition string to wait for
			max_retries: Maximum number of retry attempts
			allow_uboot_prompt: If True, also accept U-Boot prompt (=>) as success condition
		"""
		for attempt in range(max_retries):
			try:
				# Clear any existing buffer data
				discarded = None
				if self.__serialPort.in_waiting > 0:
					discarded = self.__serialPort.read(self.__serialPort.in_waiting)

				# If we discarded data, wait for board to power cycle and come back
				if discarded:
					print("Waiting for board to power cycle...", flush=True)
					boot_timeout = WAIT_POWER_TIMEOUT
					boot_start = time.time()
					while time.time() - boot_start < boot_timeout:
						if self.__serialPort.in_waiting > 0:
							break
						time.sleep(0.2)
					else:
						print("Timeout waiting for power on", flush=True)
						return False

				# Wait for the expected prompt
				prompt_timeout = WAIT_POWER_TIMEOUT
				prompt_start = time.time()
				accumulated_data = ""

				while time.time() - prompt_start < prompt_timeout:
					if self.__serialPort.in_waiting > 0:
						new_data = self.__serialPort.read(self.__serialPort.in_waiting).decode(errors='ignore')
						print(new_data, end='', flush=True)
						accumulated_data += new_data
						
						if cond in accumulated_data or (allow_uboot_prompt and '=>' in accumulated_data):
							return True

					time.sleep(0.1)

				# Timeout reached without seeing the expected prompt
				print(f"Timeout waiting for prompt '{cond}'", flush=True)
				return False

			except serial.SerialException as e:
				if attempt < max_retries - 1:
					if self._reconnect_serial():
						if allow_uboot_prompt:
							return True
						continue

				print(f"Serial exception: {e}", flush=True)
				return False

			except Exception as e:
				if attempt < max_retries - 1:
					if self._reconnect_serial():
						if allow_uboot_prompt:
							return True
						continue

				print(f"Unexpected error: {type(e).__name__}: {e}")
				return False

		print(f"Failed to communicate with board after {max_retries} attempts.")
		return False

	def __serialReadNoResponseWithReconnect(self, max_retries=MAX_RECONNECT_RETRIES) -> bool:
		"""Read from a serial without any response with automatic reconnection on failure.

		Args:
			max_retries: Maximum number of retry attempts
			allow_uboot_prompt: If True, also accept U-Boot prompt (=>) as success condition
		"""
		for attempt in range(max_retries):
			try:
				while self.__initialConnection:
					ports = [port.device for port in comports()]
					self.__serialPortPath = ports[0]
					if self.__serialPortPath != self.__oldPort:
						self.__initialConnection = False
					else:
						time.sleep(0.5)

				# Need reconnection
				if attempt < max_retries - 1:
					if self._reconnect_serial():
						return True

			except Exception as e:
				print(f"Unexpected error: {type(e).__name__}: {e}")
				return False

		print(f"Failed to communicate with board after {max_retries} attempts.")
		return False

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

	# Function to write file over serial
	def __writeFileToSerial(self, file):
		with open(file, 'rb') as f:
			self.__serialPort.write(f.read())
			f.close()

	# Function to wait and print contents of serial buffer
	def __serialRead(self, cond='\n', timeout=10, retry_interval=1):
		"""
		Read data from the serial port until the condition string 'cond' is encountered or the timeout is reached.

		Parameters:
		- cond: The condition string to stop reading (default is '\n').
		- timeout: Maximum wait time (in seconds) before raising an error if no data is received.
		- retry_interval: Time interval between retry attempts (in seconds).

		Returns:
		- Data read from the serial port.
		"""
		start_time = time.time()
		while time.time() - start_time < timeout:
			try:
				# Attempt to read data from the serial port
				buf = self.__serialPort.read_until(cond.encode())

				if not buf:
					print(f"Returned value {cond} is not the expectation. Exiting.")
					exit()

				print(f'{buf.decode(errors="ignore")}')
				return buf

			except serial.SerialException as e:
				# If the error is due to a disconnection
				if "device reports readiness to read but returned no data" in str(e):
					print(f"Device disconnected. Retrying in {retry_interval} seconds...")
					time.sleep(retry_interval)  # Wait before retrying
				else:
					# If it's another error, re-raise the exception
					raise serial.SerialException(f"read failed: {e}")

		# If the timeout is reached without a connection, raise an error
		raise serial.SerialException("Device disconnected and did not reconnect within 10 seconds")

# Util function to die with error
def die(msg='', code=1):
	print(f'Error: {msg}')
	exit(code)

def main():
	bootloaderFlashUtil = BootloaderFlashUtil()

	bootloaderFlashUtil.writeBootloader()

if __name__ == '__main__':
	main()
