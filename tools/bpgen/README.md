# bpgen - Unified Boot-Parameter Generator for Renesas RZ SoCs

`bpgen` creates the boot-parameter binary (bl2_bp.bin) that the Boot ROM reads before loading BL2.

It unifies the two historical tools:
- G2L/V2L (bootparameter.c, MBR-style 0x55AA sector)
- V2H (bptool.c, AA55FFFF structured record)

**Note** One binary cannot serve all SoCs. bpgen generates the correct format per SoC via --soc.

## Supported SoCs & Formats

### RZ/G2L, RZ/V2L
- Format: single 512-byte sector:
    - [0..3] 4-byte-aligned BL2 size
    - [4..509] padding 0xFF
    - [510] 0x55, [511] 0xAA

- Copies: always 1

### RZ/V2H

- Format: single 512-byte structured record:
  - [0..3]   4-byte-aligned BL2 size
  - [4..15]  reserved (0xFF)
  - [16..19] load offset (depends on boot mode)
  - [20..31] reserved (0xFF)
  - [32..35] destination address (`--dest`)
  - [36..511] reserved (0xFF)
  - [508..511] signature = 0xAA55FFFF
    (little-endian bytes appear as `FF FF 55 AA`)
- Copies: default 1, eSD = 7 (redundancy)

## Build

```
gcc -O2 -Wall -Wextra -o bpgen bpgen.c
```

## CLI Usage

```
G2L / V2L:
  bpgen --soc {g2l|v2l} --image bl2.bin -o bl2_bp.bin

V2H:
  bpgen --soc v2h --image IPL.bin --mode {spi|mmc|scif|esd} \
        --dest 0xADDR -o bl2_bp.bin [--copies N]
```

Options
- `--soc` {g2l|v2l|v2h} — target SoC family (required)
- `--image` <file> — input loader binary (preferred; aliases: --bl2, --ipl)
- `-o` <file> — output boot-parameter file (default: bl2_bp.bin)
- `--mode` {spi|mmc|scif|esd} — V2H only; selects load offset and default copies
- `--dest` 0xADDR — V2H only; destination address (hex), e.g. 0x44000000
- `--copies` N — V2H only; override record count (default: 1; esd: 7)