# Using binmake tool to convert platform_info.json into binary

## Prerequisites:

- CMake 
  - To install CMake, please refer to [this page](https://cmake.org/download/) to download the setup file for your specific platform.
- gcc
  - For Windows install: please refer to [this page](https://sourceforge.net/projects/mingw/) to download the setup file.
  - For Linux install: `sudo apt install build-essential`

## Build binmake tool:

```bash
git clone https://github.com/Renesas-SST/rz-utils -b main
cd rz-utils/tools/binmake
mkdir build
cd build
```

- Windows OS:

```bash
> cmake -G "MinGW Makefiles" ..
-- The C compiler identification is GNU 6.3.0
-- Detecting C compiler ABI info
-- Detecting C compiler ABI info - done
-- Check for working C compiler: C:/MinGW/bin/gcc.exe - skipped
-- Detecting C compile features
-- Detecting C compile features - done
-- Configuring done (2.0s)
-- Generating done (0.0s)
```

- Linux OS:

```bash
$ cmake ..
-- Toolchain file defaulted to '/opt/poky/3.1.14/sysroots/x86_64-pokysdk-linux/usr/share/cmake/OEToolchainConfig.cmake'
-- The C compiler identification is GNU 9.4.0
-- Check for working C compiler: /usr/bin/gcc
-- Check for working C compiler: /usr/bin/gcc -- works
-- Detecting C compiler ABI info
-- Detecting C compiler ABI info - done
-- Detecting C compile features
-- Detecting C compile features - done
-- Configuring done
-- Generating done
-- Build files have been written to: /home/renesas/rz-utils/tools/binmake/build
```

## Run the `make` command to compile the binmake tool.

```bash
$ make
-- Configuring done (0.2s)
-- Generating done (0.1s)
-- Build files have been written to: C:/Users/renesas/rz-utils/tools/binmake/build
[ 33%] Building C object CMakeFiles/binmake.dir/binmake.c.obj
[ 66%] Building C object CMakeFiles/binmake.dir/cjson/cJSON.c.obj
[100%] Linking C executable binmake.exe
[100%] Built target binmake
```

- Output files:

```bash
binmake
├── build/
│   ├── binmake                 <--- Target tool
│   ├── CMakeCache.txt
│   ├── cmake_install.cmake
│   ├── libbinmake.dll.a
│   └── Makefile
├── cjson/
│   ├── cJSON.c
│   └── cJSON.h
├── CMakeLists.txt
├── platform_info.json
└── README.md
```

## Convert platform_info.json into binary file for specific board:

If you're using RZ/G2L-SBC, run:

```bash
./binmake --input=../platform_info.json --board=RZG2L-SBC --output=RZG2L-SBC.bin
```

If you're using RZ/G2L-EVK, run:

```bash
./binmake --input=../platform_info.json --board=RZG2L-EVK --output=RZG2L-EVK.bin
```

- Output:

```bash
binmake
├── build/
│   ├── binmake
│   ├── CMakeCache.txt
│   ├── cmake_install.cmake
│   ├── libbinmake.dll.a
│   ├── Makefile
│   ├── RZG2L-EVK.bin           <--- Output binary
│   └── RZG2L-SBC.bin           <--- Output binary
├── cjson/
│   ├── cJSON.c
│   └── cJSON.h
├── CMakeLists.txt
├── platform_info.json
└── README.md
```
