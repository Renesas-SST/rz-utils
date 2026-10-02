# RZ Utility

Build scripts for the RZ/V2H RDK (ver1 16GB and ver101 8GB), the only supported board.

## Hierarchy

```
.
├── LICENSE
├── README.md
├── local-build-scripts/   # kernel, out-of-tree kernel modules and IPL (BL2 + FIP)
└── vendor/                # proprietary packages you download yourself (not committed)
```

### local-build-scripts

Builds the software for the board from source:
- the Linux kernel: Image, device trees and DT overlays, in-tree modules;
- the out-of-tree kernel modules: mmngr, mmngrbuf, vspm, vspm_if, mali_kbase, uvcs_drv;
- the IPL: BL2 and FIP with BL31/U-Boot, for RDK ver1/ver101, in each RZ/V2H Multi-OS mode.

Entry point: `local-build-scripts/main_build.sh`, configured by `local-build-scripts/config.ini`.
See [`local-build-scripts/README.md`](local-build-scripts/README.md).

### vendor

`mali_kbase` and `uvcs_drv` need proprietary tarballs that cannot be committed. Download them
and put them here, see [`vendor/README.md`](vendor/README.md).

> [!IMPORTANT]
> Refer to the README in each folder for the usage and configuration of its scripts.
