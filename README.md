# RZ Utility

Useful scripts for RZ projects.

This repository holds scripts and tools to build various software stacks for RZ platforms.

## Hierarchy

```
.
├── local-build-script/
├── README.md
├── tools/
└── universal-scripts/

4 directories, 1 file
```

### local-build-scripts

This directory contains build scripts for all software stacks of the RZ Board Support Package (BSP).

### tools

A collection of useful tools for RZ platforms.

### combo-firmware

Multi-SoC (G2L/V2L + V2H) unified bootloader + 9-rootfs SD card image. Self-contained module that builds, flashes, and packages combo firmware. Uses bpgen/fiptool from `universal-scripts/host/tools/bin/linux/` via relative path.

See `combo-firmware/README.md` for usage.

### universal-scripts

Scripts for flashing RZ images, compatible with both Windows and Linux.

> [!IMPORTANT]
> Refer to the README in each folder to understand the usage and configuration specific to scripts and tools.

