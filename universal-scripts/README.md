# universal-scripts

Scripts for flashing RZ images, compatible with both Windows and Linux.

# Folder hierarchy:

```shell
universal-scripts/
├── host
│   └── tools
│       ├── bin
│       │   ├── linux
│       │   │   ├── bpgen
│       │   │   ├── fiptool
│       │   │   ├── libcrypto.so.3
│       │   │   ├── OPENSSL_LICENSE.txt
│       │   │   └── Readme.md
│       │   ├── Readme.md
│       │   └── windows
│       │       ├── bpgen.exe
│       │       ├── fiptool.exe
│       │       ├── objcopy.exe
│       │       ├── libcrypto-3-x64.dll
│       │       ├── libwinpthread-1.dll
│       │       ├── GNU_BINUTILS_LICENSE.txt
│       │       ├── LIBWINPTHREAD_LICENSE.txt
│       │       ├── OPENSSL_LICENSE.txt
│       │       └── Readme.md
│       ├── bootloader_flasher
│       │   ├── bootloader_flash.py
│       │   └── README.md
│       ├── config
│       │   ├── boards_flash_config.toml
│       │   └── README.md
│       ├── firmware_compile
│       │   ├── firmware_compile.py
│       │   └── Readme.md
│       ├── flash_images.json
│       ├── README.md
│       ├── requirements.txt
│       ├── sd_creator
│       │   ├── README.md
│       │   ├── sd_flash.py
│       │   └── tools
│       │       ├── AdbWinApi.dll
│       │       ├── AdbWinUsbApi.dll
│       │       ├── fastboot.exe
│       │       └── NOTICE.txt
│       ├── uload_bootloader
│       │   ├── README.md
│       │   └── uload_bootloader_flash.py
│       └── universal_flash.py
└── README.md
```

Each subdirectory includes its own Readme.md file with detailed descriptions and instructions.
