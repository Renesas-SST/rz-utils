#!/usr/bin/python3

# Imports
import serial
import argparse
import time
import os
import subprocess
from subprocess import Popen, PIPE, CalledProcessError
import platform
from serial.tools.list_ports import comports
import json
import sys
if sys.version_info >= (3, 11):  # pragma: Python version >=3.11
    import tomllib
else:  # pragma: Python version <3.11
    import tomli as tomllib

DEFAULT_FASTBOOT_SERIAL = "Renesas_RZ_CMN"

class SdFlashUtil:
	def __init__(self, args=None):
		self.__scriptDir = os.path.dirname(os.path.abspath(__file__))
		self.__rootDir = os.path.abspath(os.path.join(self.__scriptDir, '..', '..', '..'))
		self.__imagesDir = os.path.abspath(os.path.join(self.__rootDir, 'target', 'images'))
		self.__fastbootDevice = DEFAULT_FASTBOOT_SERIAL

		if platform.system() == "Windows":
			self.__fastboot = os.path.abspath(os.path.join(self.__scriptDir, 'tools', 'fastboot.exe'))
		elif platform.system() == "Linux":
			self.__fastboot = "fastboot"

		self.__setupArgumentParser(args)
		self.__setupSerialPort()

	# Setup CLI parser
	def __setupArgumentParser(self, args):
		# Create parser
		self.__parser = argparse.ArgumentParser(description='Utility to flash WIC image on RZ Board.\n', epilog='Example:\n\t./sd_flash.py')

		# Add arguments
		# Board name
		self.__parser.add_argument('--board_name',
									default='rzg2l-sbc',
									dest='boardName',
									action='store',
									type=str,
									help='Board name to flash bootloader (defaults to: rzg2l-sbc).')

		# Fastboot arguments
		self.__parser.add_argument('--fastboot_type',
									default='udp',
									dest='fastbootType',
									action='store',
									type=str,
									choices=['otg', 'udp'],
									help='Fastboot type to use (defaults to: udp).')
		self.__parser.add_argument('--ether_port',
									default=1,
									dest='etherPort',
									action='store',
									type=int,
									help='[Only used in fastboot UDP] Ethernet port used to board communication (defaults to: 1).')
		self.__parser.add_argument('--ip_address',
									default="169.254.187.89",
									dest='ipAddress',
									action='store',
									type=str,
									help='[Only used in fastboot UDP] Ethernet IP address used to board communication (defaults to: 169.254.187.89).')

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

		# Images
		self.__parser.add_argument('--image_rootfs',
									default=f'{self.__imagesDir}/core-image-qt-rzg2l-sbc.wic',
									dest='rootfsImage',
									action='store',
									type=str,
									help='Path to rootfs (defaults to: <path/to/your/package>/target/images/core-image-qt-rzg2l-sbc.wic).')

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

	def __getEtherAddress(self):
		configFile = os.path.join(self.__scriptDir, ".." , "config", 'boards_flash_config.toml')
		with open(configFile, "rb") as f:
			eth_info = tomllib.load(f)

		self.__etherAddress = eth_info[self.__args.boardName]["ethernet"]

		if self.__etherAddress is None:
			print(f"Board name {self.__args.boardName} is not supported.")
			exit()

	def __listDevice(self):
		fb = self.__fastboot
		cmd = [fb, "devices"]
		try:
			res = subprocess.run(
				cmd,
				capture_output=True,
				text=True,
				check=False,
				timeout=10
			)
		except subprocess.TimeoutExpired:
			die(msg="fastboot timed out while listing devices")

		if res.returncode != 0:
			die(msg=f"fastboot failed (rc={res.returncode}): {res.stderr.strip()}")

		out = (res.stdout or "").strip()
		devices = []
		for line in out.splitlines():
			parts = line.split()
			if len(parts) >= 2 and parts[1].startswith("fastboot"):
				devices.append(parts[0])

		if devices:
			print("Fastboot device(s): " + ", ".join(devices))
		else:
			print("No fastboot devices detected.")
		return devices

	# Function to write bootloader
	def writeRootfs(self):
		start_time = time.time()

		# Check file exists
		if not os.path.exists(self.__args.rootfsImage):
			print(f"The file {self.__args.rootfsImage} does not exist.")
			exit()

		# Wait for device to be ready to receive image.
		print("Please power on the board and ensure the DIP switches are set to normal boot mode. Press RESET if available (on EVK boards); otherwise, power-cycle (e.g., toggle the POWER switch or unplug/replug power).")
		self.__serialRead('Hit any key to stop autoboot:')
		self.__writeSerialCmd('')
		self.__serialRead('=>')

		# UDP Fastboot
		if (self.__args.fastbootType == "udp"):
			self.__handle_udp_fastboot()
		# OTG Fastboot
		elif (self.__args.fastbootType == "otg"):
			self.__handle_otg_fastboot()

		print("Closed serial port.")
		self.__serialPort.close()

		end_time = time.time()
		elapsed_time = end_time - start_time
		print(f"Elapsed time: {elapsed_time:.6f} seconds")

	def __handle_udp_fastboot(self):
		self.__getEtherAddress()

		print('fastboot udp mode')
		self.__writeSerialCmd('setenv ipaddr ' + self.__args.ipAddress)
		self.__writeSerialCmd(f'setenv ethact ethernet@{self.__etherAddress[self.__args.etherPort]}')
		self.__writeSerialCmd('fastboot udp')
		self.__serialRead('Listening for fastboot command on')

		print('Starting fastboot command to write rootfs image...')

		if platform.system() == "Windows":
			fastboot_command = f"{self.__fastboot} -s udp:{self.__args.ipAddress} -v"
		elif platform.system() == "Linux":
			# fasboot in linux does not support the -v flag for verbose output
			fastboot_command = f"{self.__fastboot} -s udp:{self.__args.ipAddress}"

		self.__runSubprocessCommand(f"{fastboot_command} getvar version-bootloader")
		self.__runSubprocessCommand(f"{fastboot_command} getvar version")
		self.__runSubprocessCommand(f"{fastboot_command} flash rawimg {self.__args.rootfsImage}")

	def __handle_otg_fastboot(self):
		print('fastboot usb otg mode')
		self.__writeSerialCmd(f"setenv serial# {self.__fastbootDevice}")
		self.__writeSerialCmd('saveenv')
		self.__serialRead('OK')
		self.__writeSerialCmd('fastboot usb 27')
		time.sleep(3)

		devs = self.__listDevice()
		if f"{self.__fastbootDevice}" not in devs:
			die(msg=(
				f"Fastboot device '{self.__fastbootDevice}' not found.\n"
				"Ensure the board is connected via the USB OTG port and that all prerequisites (see README) are met"
			))

		self.__runSubprocessCommand(f"{self.__fastboot} -s {self.__fastbootDevice} flash mmc0 {self.__args.rootfsImage}")

	def __runSubprocessCommand(self, command):
		try:
			subprocess.run(command, shell=True, check=True)
		except CalledProcessError as e:
			die(msg=f"Command '{command}' failed with error: {e.stderr.decode().strip()}")

	def __writeSerialCmd(self, cmd):
		self.__serialPort.write(f'{cmd}\r'.encode())

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
	sdFlashUtil = SdFlashUtil()

	sdFlashUtil.writeRootfs()

if __name__ == '__main__':
	main()
