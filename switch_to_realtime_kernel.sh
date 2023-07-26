#!/usr/bin/env bash
#export TARGET_KERNEL=realtime
#export GRUB_ENTRY=$(grep menuentry /boot/grub/grub.cfg  | awk -F\' '{print $2}' |grep $TARGET_KERNEL$ | tail -n1)
export GRUB_MENU_ENTRY=$(sudo grub-mkconfig | grep -iE "menuentry 'Ubuntu, with Linux" | awk '{print i++ " : "$1, $2, $3, $4, $5, $6, $7}' |grep realtime\' | cut -f 1 -d ' ' )
echo $GRUB_ENTRY
sudo sed -i 's/^GRUB_DEFAULT=.*$/GRUB_DEFAULT="1>${GRUB_MENU_ENTRY}"/' /etc/default/grub
sudo update-grub
~
