#!/usr/bin/env bash
export TARGET_KERNEL=realtime
export GRUB_ENTRY=$(grep menuentry /boot/grub/grub.cfg  | awk -F\' '{print $2}' |grep $TARGET_KERNEL$ | tail -n1)

echo $GRUB_ENTRY
sudo sed -i 's/^GRUB_DEFAULT=.*$/GRUB_DEFAULT="'${GRUB_MENU_ENTRY}'"/' /etc/default/grub
sudo update-grub
~
