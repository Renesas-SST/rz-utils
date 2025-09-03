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

class UloadFlashUtil:
	def __init__(self, args=None):
		self.__scriptDir = os.path.dirname(os.path.abspath(__file__))

		self.__setupArgumentParser(args)
		self.__setupSerialPort()

	# Setup CLI parser
	def __setupArgumentParser(self, args):
		# Create parser
		self.__parser = argparse.ArgumentParser(description='Util to flash bootloader from U-Boot console on RZ Board.\n', epilog='Example:\n\t./uload_bootloader_flash.py')

		# Add arguments
		# Board name
		self.__parser.add_argument('--board_name',
									default='rzg2l-sbc',
									dest='boardName',
									action='store',
									type=str,
									help='Board name to flash bootloader (defaults to: rzg2l-sbc).')

		# Serial port arguments
		self.__parser.add_argument('--serial_port',
									default=None,
									dest='serialPort',
									action='store',
									help='Serial port used to talk to board (defaults to: most recently connected port).')

		self.__parser.add_argument('--serial_port_baud',
									default=115200,
									dest='baudRate',
									action='store',
									type=int,
									help='Baud rate for serial port (defaults to: 115200).')

		if args:
			self.__args = self.__parser.parse_args(args)
		else:
			self.__args = self.__parser.parse_args()

	# Setup Serial Port
	def __setupSerialPort(self):
		try:
			if (self.__args.serialPort is None):
				ports = [port.device for port in comports()]
				print(f"Available serial ports: {ports}")
				print(f"Using serial port: {ports[0]}")
				self.__serialPort = serial.Serial(port= ports[0], baudrate = self.__args.baudRate, timeout=15)
			else:
				self.__serialPort = serial.Serial(port=self.__args.serialPort, baudrate = self.__args.baudRate, timeout=15)
		except:
			die(msg='Unable to open serial port.')

	def __getUloadFlashInfo(self):
		configFile = os.path.join(self.__scriptDir, ".." , "config", 'boards_flash_config.toml')
		with open(configFile, "rb") as f:
			flash_info = tomllib.load(f)

		self.__uloadFlashInfo = flash_info[self.__args.boardName]

		if self.__uloadFlashInfo is None:
			print(f"Board name {self.__args.boardName} is not supported.")
			exit()

	# Function to write bootloader
	def writeUloadBootloader(self):
		self.__getUloadFlashInfo()
		xspiFlashAddress = self.__uloadFlashInfo["flash_address"]
		loadAddress = self.__uloadFlashInfo["load_address"]

		start_time = time.time()

		# Wait for device to be ready to receive image.
		print('Please power on board. Make sure you changed switches to normal boot mode.')
		self.__serialRead('Hit any key to stop autoboot:')
		self.__writeSerialCmd('')

		self.__serialRead('=>')

		# sf probe
		self.__writeSerialCmd('sf probe')
		self.__serialRead('MiB')

		# true
		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# sf erase
		print('erase QSPI/xSPI: please wait a minute...')
		start_time_erase = time.time()
		self.__writeSerialCmd('sf erase 0 100000')
		self.__serialRead('OK')
		end_time_erase = time.time()
		erase_time = end_time_erase - start_time_erase
		print(f"erase time: {erase_time:.6f} seconds")

		# true
		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# loading bl2...
		if (self.__args.boardName == "rzv2h-evk"):
			self.__writeSerialCmd(f'fatload mmc 0:1 {loadAddress} uload-bootloader/bl2_bp_spi_{self.__args.boardName}.bin')
		else:
			self.__writeSerialCmd(f'fatload mmc 0:1 {loadAddress} uload-bootloader/bl2_bp_{self.__args.boardName}.bin')
		self.__serialRead('MiB/s)')

		# true
		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# writing bl2...
		self.__writeSerialCmd(f'sf write {loadAddress} {xspiFlashAddress[0]} $filesize')
		self.__serialRead('OK')

		# true
		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# loading fip...
		self.__writeSerialCmd(f'fatload mmc 0:1 {loadAddress} uload-bootloader/fip_{self.__args.boardName}.bin')
		self.__serialRead('MiB/s)')

		# true
		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# writing fip...
		self.__writeSerialCmd(f'sf write {loadAddress} {xspiFlashAddress[1]} $filesize')
		self.__serialRead('OK')

		# true
		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# loading board indentification...
		self.__writeSerialCmd(f'fatload mmc 0:1 {loadAddress} uload-bootloader/{self.__args.boardName}-platform-settings.bin')
		self.__serialRead('MiB/s)')

		# true
		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# writing bl2...
		self.__writeSerialCmd(f'sf write {loadAddress} {xspiFlashAddress[2]} $filesize')
		self.__serialRead('OK')

		# true
		self.__writeSerialCmd('true')
		self.__serialRead('=>')

		# Closed serial port.
		print("Closed serial port.")
		self.__serialPort.close()

		end_time = time.time()
		elapsed_time = end_time - start_time
		print(f"Elapsed time: {elapsed_time:.6f} seconds")

	def __writeSerialCmd(self, cmd):
		self.__serialPort.write(f'{cmd}\r'.encode())

	# Function to write file over serial
	def __writeFileToSerial(self, file):
		with open(file, 'rb') as f:
			self.__serialPort.write(f.read())
			f.close()

	# Function to wait and print contents of serial buffer
	def __serialRead(self, cond='\n'):
		buf = self.__serialPort.read_until(cond.encode())

		if not buf:
			print("Returned value is not the expectation. Exiting.")
			exit()

		print(f'{buf.decode(errors="ignore")}')

# Util function to die with error
def die(msg='', code=1):
	print(f'Error: {msg}')
	exit(code)

def main():
	uloadFlashUtil = UloadFlashUtil()

	uloadFlashUtil.writeUloadBootloader()

if __name__ == '__main__':
	main()
