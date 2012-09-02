#!/bin/bash

set -x

WORKSPACE=$(pwd)
VERSION=2.6.34
#LINUX=$WORKSPACE/linux-$VERSION
LINUX=$(pwd)

find $LINUX \
	-path "$LINUX/arch/*" ! -path "$LINUX/arch/arm*" -prune -o \
	-path "$LINUX/Documentation" -prune -o \
	-path "$LINUX/scripts" -prune -o \
	-path "$LINUX/drivers/*" ! -path "$LINUX/drivers/base*" ! -path "$LINUX/drivers/input*" \
	! -path "$LINUX/drivers/rtc*" ! -path "$LINUX/drivers/leds*" ! -path "$LINUX/drivers/char*" \
	! -path "$LINUX/drivers/usb*" ! -path "$LINUX/drivers/hid*" -prune -o \
	-path "$LINUX/net" -prune -o \
	-path "$LINUX/crypto" -prune -o \
	-path "$LINUX/security" -prune -o \
	-path "$LINUX/sound" -prune -o \
	-name "*.[chxsS]" -print > $LINUX/cscope.files
	#-path "$LINUX/include/asm-*" -prune -o \
	#-path "$LINUX/arch" ! -path "$LINUX/arch/x86" -prune -o \

cscope -b -q -k
