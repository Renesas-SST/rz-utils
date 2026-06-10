#!/usr/bin/env python3
"""Unified Bootloader Tool — combo firmware builder + multi-root SD card tool.

Interactive menu or CLI args.

Usage:
  ./unified-bootloader-tool.py                        Interactive menu
  ./unified-bootloader-tool.py --build --package       Build + package
  ./unified-bootloader-tool.py --wics "a.wic b.wic"   Custom WIC list
  sudo ./unified-bootloader-tool.py --flash /dev/sdX   Flash bootloader
  sudo ./unified-bootloader-tool.py --deploy /dev/sdX  Deploy .img.gz
  sudo ./unified-bootloader-tool.py --quick-test my.wic /dev/sdX  1 WIC + bootloader
"""

import os
import sys
import argparse
import subprocess
import glob
import platform
import time
import textwrap

SEP_WIDTH = 72
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RZ_UTILS = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))


def _user_home():
    u = os.environ.get('SUDO_USER')
    return os.path.expanduser(f'~{u}') if u else os.path.expanduser('~')


USER_HOME = _user_home()
DEFAULT_ATF_DIR = os.path.join(USER_HOME, 'quoctrinh/workspace/rz-atf-sst')
DEFAULT_UBOOT_DIR = os.path.join(USER_HOME, 'quoctrinh/workspace/u-boot')
DEFAULT_WIC_DIR = os.path.join(USER_HOME, 'quoctrinh/workspace/yocto_rz-cmn/target/images')
DEFAULT_WICS = [
    'core-image-minimal.wic',
    'core-image-bsp.wic',
    'core-image-weston.wic',
    'renesas-core-image-cli.wic',
    'renesas-core-image-weston.wic',
    'renesas-quickboot-cli.wic',
    'renesas-quickboot-wayland.wic',
    'ubuntu-core-image.wic',
    'ubuntu-lxde-image.wic',
]

BUILD_SCRIPT = os.path.join(SCRIPT_DIR, 'build_combo.sh')
COMBO_IMAGE = os.path.join(SCRIPT_DIR, 'target', 'images', 'renesas-multi-os-combo.img.gz')


def heading(text):
    print(f"\n{'=' * SEP_WIDTH}")
    print(text)
    print('=' * SEP_WIDTH)


def info(text):
    print(f"  {text}")


def error(text):
    print(f"  ERROR: {text}", file=sys.stderr)


def check_sudo():
    if os.geteuid() != 0:
        print("This operation requires root (sudo). Please re-run with sudo.")
        sys.exit(1)


def detect_sd_cards():
    devices = []
    devices.extend(sorted(glob.glob('/dev/sd[a-z]')))
    devices.extend(sorted(glob.glob('/dev/mmcblk[0-9]')))
    result = []
    for d in devices:
        try:
            out = subprocess.run(
                ['lsblk', '-no', 'MOUNTPOINT', d],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
            if '/' in out.split('\n'):
                continue
            result.append(d)
        except Exception:
            pass
    return result


def get_device_size(dev):
    try:
        out = subprocess.run(
            ['blockdev', '--getsize64', dev],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        return int(out) / 1024 / 1024 / 1024 if out else 0
    except Exception:
        return 0


def wics_str(wics):
    return ' '.join(wics)


def run_build(atf_dir, uboot_dir):
    heading("BUILD ATF + U-BOOT")
    env = os.environ.copy()
    env['RZ_ATF_DIR'] = atf_dir
    env['RZ_UBOOT_DIR'] = uboot_dir
    result = subprocess.run(
        ['bash', BUILD_SCRIPT, '--build'],
        env=env, cwd=SCRIPT_DIR
    )
    if result.returncode == 0:
        info("Build complete.")
    else:
        error(f"Build failed (exit code {result.returncode})")
        sys.exit(1)


def run_gen_artifacts(atf_dir, uboot_dir, g2l_only=False):
    heading("GENERATE BOOTLOADER ARTIFACTS")
    env = os.environ.copy()
    env['RZ_ATF_DIR'] = atf_dir
    env['RZ_UBOOT_DIR'] = uboot_dir
    cmd = ['bash', BUILD_SCRIPT]
    if g2l_only:
        cmd.append('--g2l-only')
    result = subprocess.run(cmd, env=env, cwd=SCRIPT_DIR)
    if result.returncode == 0:
        info("Artifacts generated in target/images/")
    else:
        error(f"Artifact generation failed (exit code {result.returncode})")
        sys.exit(1)


def run_package(atf_dir, uboot_dir, wic_dir, wics, active, g2l_only=False):
    check_sudo()
    enabled = [w for w, a in zip(wics, active) if a]
    if not enabled:
        print("  ERROR: No WICs selected. Enable some in option 7.")
        return
    heading(f"PACKAGE COMBO IMAGE ({len(enabled)} WICs)")
    env = os.environ.copy()
    env['RZ_ATF_DIR'] = atf_dir
    env['RZ_UBOOT_DIR'] = uboot_dir
    env['WIC_DIR'] = wic_dir
    env['CUSTOM_WICS'] = wics_str(enabled)
    cmd = ['bash', BUILD_SCRIPT, '--package-image']
    if g2l_only:
        cmd.append('--g2l-only')
    result = subprocess.run(cmd, env=env, cwd=SCRIPT_DIR)
    if result.returncode == 0:
        info("Combo image created.")
    else:
        error(f"Package failed (exit code {result.returncode})")
        sys.exit(1)


def run_flash_bootloader(device, atf_dir, uboot_dir, g2l_only=False):
    check_sudo()
    heading(f"FLASH BOOTLOADER TO {device}")
    env = os.environ.copy()
    env['RZ_ATF_DIR'] = atf_dir
    env['RZ_UBOOT_DIR'] = uboot_dir
    cmd = ['bash', BUILD_SCRIPT, '--flash', device]
    if g2l_only:
        cmd.append('--g2l-only')
    result = subprocess.run(cmd, env=env, cwd=SCRIPT_DIR)
    if result.returncode == 0:
        info("Bootloader flashed.")
    else:
        error(f"Flash failed (exit code {result.returncode})")
        sys.exit(1)


def run_deploy_image(device, image_path):
    check_sudo()
    heading(f"DEPLOY COMBO IMAGE TO {device}")

    if not image_path or not os.path.exists(image_path):
        image_path = COMBO_IMAGE
    if not os.path.exists(image_path):
        error(f"Combo image not found: {image_path}")
        print("  Build one first with: --package")
        sys.exit(1)

    img_size = os.path.getsize(image_path)
    info(f"Image: {image_path} ({img_size / 1024 / 1024 / 1024:.1f} GiB)")
    dev_size = get_device_size(device)
    info(f"Device: {device} ({dev_size:.0f} GiB)")

    print(f"\n{'=' * SEP_WIDTH}")
    print("WARNING: ALL DATA ON TARGET WILL BE OVERWRITTEN!")
    print('=' * SEP_WIDTH)
    confirm = input("Type 'yes' to continue: ").strip().lower()
    if confirm != 'yes':
        print("Aborted.")
        return

    print(f"\nDeploying {image_path} to {device}...")
    start = time.time()
    gz = subprocess.Popen(['gunzip', '-c', image_path], stdout=subprocess.PIPE)
    dd = subprocess.Popen(
        ['dd', f'of={device}', 'bs=4M', 'conv=fsync'],
        stdin=gz.stdout
    )
    gz.stdout.close()
    dd.communicate()
    if dd.returncode != 0:
        error(f"dd failed (exit code {dd.returncode})")
        sys.exit(1)
    subprocess.run(['sync'], check=False)
    elapsed = time.time() - start
    info(f"Done in {elapsed / 60:.0f}m {elapsed % 60:.0f}s")
    info("You can safely remove the SD card.")


def run_quick_test(wic_path, device):
    """Flash 1 WIC + combo bootloader to SD. Skips rootfs shrink/9-way split."""
    check_sudo()
    heading(f"QUICK TEST — {os.path.basename(wic_path)} -> {device}")

    if not os.path.exists(wic_path):
        error(f"WIC not found: {wic_path}")
        sys.exit(1)

    # 1. Parse WIC partition table
    result = subprocess.run(
        ['sfdisk', '-J', wic_path],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        error(f"sfdisk failed: {result.stderr}")
        sys.exit(1)

    import json
    pt = json.loads(result.stdout)
    parts = pt.get('partitiontable', {}).get('partitions', [])
    if len(parts) < 2:
        error(f"WIC has {len(parts)} partitions, expected >= 2 (FAT + rootfs)")
        sys.exit(1)

    # Expect: part1 = FAT (boot), part2 = ext4 (rootfs)
    p1 = parts[0]
    p2 = parts[1]
    BOOT_SECTOR = 8192  # right after bootloader + GAP, aligned to 2048
    for p, label in [(p1, 'FAT'), (p2, 'rootfs')]:
        print(f"  {label}: start={p['start']} size={p['size']} sectors "
              f"(offset={p['start']-2048})")

    # 2. Wipe + create partition table on SD
    subprocess.run(['wipefs', '-a', device],
                   capture_output=True, timeout=30)
    subprocess.run(['parted', '-s', device, 'mklabel', 'msdos'], check=True, timeout=30)

    p1_new_start = BOOT_SECTOR
    p1_new_end = p1_new_start + p1['size'] - 1
    p2_new_start = p1_new_end + 1
    p2_new_end = p2_new_start + p2['size'] - 1

    subprocess.run(['parted', '-s', device, 'mkpart', 'primary', 'fat32',
                    f'{p1_new_start}s', f'{p1_new_end}s'], check=True, timeout=30)
    subprocess.run(['parted', '-s', device, 'set', '1', 'boot', 'on'],
                   check=True, timeout=30)
    subprocess.run(['parted', '-s', device, 'mkpart', 'primary', 'ext4',
                    f'{p2_new_start}s', f'{p2_new_end}s'], check=True, timeout=30)
    subprocess.run(['partprobe', device], capture_output=True, timeout=30)
    print("  Partition table created (2 partitions).")

    # 3. Copy partition data at new offsets
    p1_offset = p1_new_start - p1['start']
    p2_offset = p2_new_start - p2['start']

    start = time.time()

    print(f"  Copying FAT ({p1['size']} sectors)...", end=' ')
    sys.stdout.flush()
    subprocess.run(['dd', f'if={wic_path}', f'of={device}',
                    f'bs=512', f'skip={p1["start"]}', f'seek={p1_new_start}',
                    f'count={p1["size"]}', 'conv=fsync'],
                   check=True, capture_output=True, timeout=300)
    print("done")

    print(f"  Copying rootfs ({p2['size']} sectors)...", end=' ')
    sys.stdout.flush()
    subprocess.run(['dd', f'if={wic_path}', f'of={device}',
                    f'bs=512', f'skip={p2["start"]}', f'seek={p2_new_start}',
                    f'count={p2["size"]}', 'conv=fsync'],
                   check=True, capture_output=True, timeout=600)
    print("done")

    subprocess.run(['sync'], check=False)

    # 4. Flash combo bootloader
    print("  Flashing bootloader...")
    env = os.environ.copy()
    env['RZ_ATF_DIR'] = os.environ.get('RZ_ATF_DIR', DEFAULT_ATF_DIR)
    env['RZ_UBOOT_DIR'] = os.environ.get('RZ_UBOOT_DIR', DEFAULT_UBOOT_DIR)
    result = subprocess.run(
        ['bash', BUILD_SCRIPT, '--flash', device],
        env=env, cwd=SCRIPT_DIR
    )
    if result.returncode != 0:
        error(f"Bootloader flash failed (exit {result.returncode})")
        sys.exit(1)

    elapsed = time.time() - start
    print(f"\n  Done in {elapsed / 60:.0f}m {elapsed % 60:.0f}s.")
    print(f"  Insert SD into board and boot.")


def pick_sd_card():
    devices = detect_sd_cards()
    if not devices:
        print("  No SD cards detected.")
        return None
    print("\n  Available devices:")
    for i, d in enumerate(devices, 1):
        sz = get_device_size(d)
        print(f"    {i}. {d} ({sz:.0f} GiB)")
    sel = input("  Select device: ").strip()
    try:
        return devices[int(sel) - 1]
    except (ValueError, IndexError):
        print("  Invalid selection.")
        return None


def edit_wic_list(wics, active, wic_dir):
    while True:
        n_enabled = sum(active)
        print(f"\n  WICs ({n_enabled} enabled / {len(active)} total, dir: {wic_dir}):")
        for i, w in enumerate(wics, 1):
            mark = "✓" if active[i - 1] else " "
            print(f"    {i}. [{mark}] {w}")
        print(f"\n    1-{len(wics)}  Toggle on/off")
        print(f"    0         Toggle all")
        print(f"    a         Add from directory")
        print(f"    d         Done")
        choice = input("  Select: ").strip().lower()
        if choice == 'd':
            break
        elif choice == 'a':
            try:
                all_wics = sorted(f for f in os.listdir(wic_dir) if f.endswith('.wic'))
            except FileNotFoundError:
                print(f"  Directory not found: {wic_dir}")
                continue
            existing = set(wics)
            available = [(n, f) for n, f in enumerate(all_wics, 1) if f not in existing]
            if not available:
                print("  All WICs in directory are already in the list.")
                continue
            print(f"\n  Available ({len(available)} files):")
            for num, f in available:
                print(f"    {num}. {f}")
            sel = input("  Select number to add (0 to cancel): ").strip()
            try:
                n = int(sel)
                if n == 0:
                    continue
                matched = [f for num, f in available if num == n]
                if matched:
                    wics.append(matched[0])
                    active.append(True)
                    print(f"  Added: {matched[0]}")
            except ValueError:
                pass
        elif choice == '0':
            any_off = not all(active)
            active[:] = [any_off] * len(active)
        else:
            try:
                n = int(choice)
                if 1 <= n <= len(wics):
                    active[n - 1] = not active[n - 1]
                else:
                    print("  Invalid number.")
            except ValueError:
                print("  Invalid.")
    return wics, active


def show_help():
    heading("HELP — When to use each option")
    helps = [
        ("1. Build ATF + U-Boot",
         "First run or after source changes.\n"
         "  Builds BL2, BL31 (G2L+V2H), and u-boot.bin."),
        ("2. Generate bootloader artifacts",
         "After build (opt 1) or with existing binaries.\n"
         "  Runs bpgen → Boot Parameter, gen_bid_blob → Board IDs, fiptool → FIP."),
        ("3. Package combo .img.gz",
         "Create a full distributable image.\n"
         "  Builds 9-rootfs multi-partition image + bootloader → .img.gz.\n"
         "  Deploy later via option 5 or gunzip+dd manually."),
        ("4. Flash bootloader to SD card",
         "SD card already has rootfs partitions.\n"
         "  Writes BP/BL2/BID/DTB/FIP to raw sectors 1-6911.\n"
         "  Leaves partition table and rootfs intact."),
        ("5. Deploy full combo image",
         "Create a new multi-root SD card from scratch.\n"
         "  gunzip + dd combo .img.gz to device.\n"
         "  Overwrites everything — easiest, one command."),
        ("6. Configure paths",
         "Change ATF/U-Boot/WIC directories."),
        ("7. Customize WIC list",
         "Select which rootfs WICs to include.\n"
         "  Toggle on/off (opt 3 packages only enabled ones)."),
        ("8. Quick test",
         "Fast single-board test — 1 WIC + bootloader.\n"
         "  Doesn't need pre-built .img.gz.\n"
         "  Good for development iteration."),
    ]
    for title, desc in helps:
        print(f"\n  {title}")
        for line in desc.split('\n'):
            print(f"    {line}")


def interactive_menu(atf_dir, uboot_dir, wic_dir, wics, active):
    while True:
        n_enabled = sum(active)
        print(f"\n{'=' * SEP_WIDTH}")
        print("  UNIFIED BOOTLOADER TOOL")
        print(f"{'=' * SEP_WIDTH}")
        print(f"  ATF dir:    {atf_dir}")
        print(f"  U-Boot dir: {uboot_dir}")
        print(f"  WIC dir:    {wic_dir}")
        print(f"  WICs:       {n_enabled}/{len(active)} enabled")
        print(f"{'=' * SEP_WIDTH}")
        print("  1. Build ATF + U-Boot")
        print("  2. Generate bootloader artifacts (bp/bid/fip)")
        print("  3. Package combo .img.gz")
        print("  4. Flash bootloader to SD card")
        print("  5. Deploy full combo .img.gz to SD card")
        print("  6. Configure paths")
        print("  7. Customize WIC list")
        print("  8. Quick test — 1 WIC + bootloader to SD")
        print("  h. Help — when to use each option")
        print("  0. Exit")
        print(f"{'=' * SEP_WIDTH}")

        choice = input("Select: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            run_build(atf_dir, uboot_dir)
        elif choice == '2':
            run_gen_artifacts(atf_dir, uboot_dir)
        elif choice == '3':
            run_package(atf_dir, uboot_dir, wic_dir, wics, active)
        elif choice == '4':
            dev = pick_sd_card()
            if dev:
                run_flash_bootloader(dev, atf_dir, uboot_dir)
        elif choice == '5':
            dev = pick_sd_card()
            if dev:
                run_deploy_image(dev, None)
        elif choice == '6':
            print()
            new = input(f"  ATF dir [{atf_dir}]: ").strip()
            if new:
                atf_dir = os.path.abspath(os.path.expanduser(new))
            new = input(f"  U-Boot dir [{uboot_dir}]: ").strip()
            if new:
                uboot_dir = os.path.abspath(os.path.expanduser(new))
            new = input(f"  WIC dir [{wic_dir}]: ").strip()
            if new:
                wic_dir = os.path.abspath(os.path.expanduser(new))
        elif choice == '7':
            wics, active = edit_wic_list(wics, active, wic_dir)
        elif choice == '8':
            wic = input("  Path to WIC file: ").strip()
            if not wic:
                continue
            dev = pick_sd_card()
            if dev:
                run_quick_test(wic, dev)
        elif choice in ('h', 'H', 'help', '?'):
            show_help()
        else:
            print("  Invalid choice.")

    print("\nBye.\n")


def main():
    parser = argparse.ArgumentParser(
        description='Unified Bootloader Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              ./unified-bootloader-tool.py                         Interactive menu
              ./unified-bootloader-tool.py --build --package        Build + package
              ./unified-bootloader-tool.py --wics "a.wic b.wic"    Custom WIC list
              sudo ./unified-bootloader-tool.py --flash /dev/sdc   Flash bootloader
              sudo ./unified-bootloader-tool.py --deploy /dev/sdc  Deploy full image
              sudo ./unified-bootloader-tool.py --quick-test my.wic /dev/sdc  1 WIC + bootloader

            After deploying, select rootfs in U-Boot:
              run core-image-weston       # by label
              setenv root_part 9; boot    # by partition
        """)
    )
    parser.add_argument('--build', action='store_true', help='Build ATF + U-Boot')
    parser.add_argument('--package', action='store_true', help='Package combo .img.gz')
    parser.add_argument('--flash', metavar='DEVICE', help='Flash bootloader to SD card')
    parser.add_argument('--deploy', metavar='DEVICE', help='Deploy full combo .img.gz to SD card')
    parser.add_argument('--g2l-only', action='store_true', help='G2L/V2L only (skip V2H)')
    parser.add_argument('--atf-dir', default=os.environ.get('RZ_ATF_DIR', DEFAULT_ATF_DIR),
                        help=f'ATF source directory (default: {DEFAULT_ATF_DIR})')
    parser.add_argument('--uboot-dir', default=os.environ.get('RZ_UBOOT_DIR', DEFAULT_UBOOT_DIR),
                        help=f'U-Boot source directory (default: {DEFAULT_UBOOT_DIR})')
    parser.add_argument('--wic-dir', default=os.environ.get('WIC_DIR', DEFAULT_WIC_DIR),
                        help=f'WIC images directory (default: {DEFAULT_WIC_DIR})')
    parser.add_argument('--wics', default=None,
                        help='Space-separated WIC filenames (default: all 9 standard images)')
    parser.add_argument('--image', metavar='PATH',
                        help='Path to combo .img.gz (default: auto-detect)')
    parser.add_argument('--quick-test', nargs=2, metavar=('WIC', 'DEVICE'),
                        help='Flash 1 WIC + bootloader to SD (fast test)')

    args = parser.parse_args()

    atf_dir = os.path.abspath(os.path.expanduser(args.atf_dir))
    uboot_dir = os.path.abspath(os.path.expanduser(args.uboot_dir))
    wic_dir = os.path.abspath(os.path.expanduser(args.wic_dir))
    wics = args.wics.split() if args.wics else list(DEFAULT_WICS)
    active = [True] * len(wics)

    has_action = args.build or args.package or args.flash or args.deploy or args.quick_test

    if not has_action:
        interactive_menu(atf_dir, uboot_dir, wic_dir, wics, active)
        return

    if args.quick_test:
        run_quick_test(args.quick_test[0], args.quick_test[1])
        return

    if args.build:
        run_build(atf_dir, uboot_dir)
    if args.package:
        run_package(atf_dir, uboot_dir, wic_dir, wics, active, args.g2l_only)
    if args.flash:
        run_flash_bootloader(args.flash, atf_dir, uboot_dir, args.g2l_only)
    if args.deploy:
        run_deploy_image(args.deploy, args.image)


if __name__ == '__main__':
    main()
