#!/bin/bash

_usage="
Usage: 

$ ./main_build.sh <target_build> <sub_command> 

Option:
    <target_build>:
        1. kernel
            Build for Linux Kernel
            <sub_command>:
                - clean
                - distclean
                - defconfig
                - menuconfig
                - image
                - dtbs
                - all
                - modules

        2. uboot
            Build for U-Boot
            <sub_command>:
                - clean
                - disclean
                - defconfig
                - image
                - all

        3. atf
            Build for ATF
            <sub_command>:
                - clean
                - distclean
                - bl2
                - bl31
                - all
                - dtbs (not supported yet)

        4. flash-writer
            Build for Flash-Writer
            <sub_command>:
                - clean
                - all

        5. build-all
            Build for all software stacks (Linux Kernel, U-Boot, ATF, Flash-Writer)
            <sub_command>: None

        6. clean-all
            Clean for all software stacks (Linux Kernel, U-Boot, ATF, Flash-Writer)
            <sub_command>: None

For example: 
    Build all images (Kernel image and device tree) for the Linux Kernel:
        $ ./main-build.sh kernel full-image

    Clean the Linux Kernel (Kernel image and device tree) output:
        $ ./main-build.sh kernel clean

Note: Before executing the build, please make sure that you have updated the configuration file: config.ini at the top of the build scripts folder.

Platform Override:
    By default, PLATFORM is read from config.ini, but you can override it at runtime, for example:
        $ PLAT=RZ-CMN ./main-build.sh kernel full-image
"
# Help message
show_help() {
        echo 'Error: Invalid Syntax!'
        echo "${_usage}"
        exit 1
}