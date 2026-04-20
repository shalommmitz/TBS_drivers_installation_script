#!/bin/bash

# This script was originally copied from 
#    https://www.tbsdtv.com/forum/viewtopic.php?f=87&t=25391
# This script was written by andreril at Mon Oct 26 2020

# Check if installation already exists
# If yes, and we need to re-install due to kernel upgrade,
#             the only solution that worked for me is to rm both media and media_build
if [[ -d media ]]
then
    echo "Folder 'media' exists --> assuming installation pre-exists"
    echo "Will delete folders 'media' and 'media_build'
    echo 'press ^C to abort or Enter to continue"
    read AABBCCDD
    rm -rf media media_build
fi

#install compile essentials
sudo apt --yes install linux-headers-$(uname -r)
sudo apt --yes install build-essential
sudo apt --yes install patchutils libproc-processtable-perl
sudo apt --yes install dvb-apps
# add --allow-unauthenticated if failing gpg signature check

#download firmware
wget http://www.tbsdtv.com/download/document/linux/tbs-tuner-firmwares_v1.0.tar.bz2
sudo tar jxvf tbs-tuner-firmwares_v1.0.tar.bz2 -C /lib/firmware/

#new build
git clone https://github.com/tbsdtv/media_build.git
git clone --depth=1 https://github.com/tbsdtv/linux_media.git -b latest ./media
cd media_build
make dir DIR=../media
make allyesconfig
make -j4
sudo make install

#build and make tbs opensource drivers
sudo make rmmod
sudo modprobe saa716x_tbs-dvb
lspci
dmesg | grep frontend

#load "saa716x_tbs-dvb" modules
echo saa716x_tbs-dvb | sudo tee /etc/modules-load.d/tbs.conf

#install dvb-apps
sudo apt --yes install dvb-apps
sudo lsdvb

sudo reboot
