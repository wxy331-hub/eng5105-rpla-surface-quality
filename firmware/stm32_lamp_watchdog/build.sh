#!/bin/sh
# Build wd.elf / wd.bin with arm-none-eabi-gcc (tested with xPack 15.2.1); set ARM_GCC_BIN to its
# bin directory if it is not on PATH. Flash from the Pi (ST-LINK needs no driver on Linux):
#   openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c "program wd.elf verify reset exit"
set -e
cd "$(dirname "$0")"
BIN="${ARM_GCC_BIN:+$ARM_GCC_BIN/}"
"${BIN}arm-none-eabi-gcc" -mcpu=cortex-m4 -mthumb -mfloat-abi=soft -O2 -std=c11 \
  -ffreestanding -fno-builtin -fno-tree-loop-distribute-patterns -nostdlib \
  -Wall -Wextra -Wno-override-init -T link.ld main.c startup.c -lgcc -o wd.elf
"${BIN}arm-none-eabi-objcopy" -O binary wd.elf wd.bin
"${BIN}arm-none-eabi-size" wd.elf
