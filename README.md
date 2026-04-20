# A Script to Install Drivers for TBS Sat Receivers

Note: You can download the following drivers from the [TBS site](https://www.tbsiptv.com/index.php?route=product/download/drivers&path=6&id=27):

  - [For Kernel V6.8 ~ V6.18](https://www.tbsiptv.com/download/common/tbsdvb_v1013.tar.bz2)
  - [For Kernel V4.19 - V6.12](https://www.tbsdtv.com/download/document/linux/media_build-2025-04-28.tar.bz2)

Tested on Ubuntu 24.04 with kernel 6.8.0-110-generic.

The original script is from https://www.tbsdtv.com/forum/viewtopic.php?f=87&t=25391

This original script was written by andreril at Mon Oct 26 2020. I could not find any farther info on the original author.

The current scripts no longer use the older `media_build` / `linux_media` flow for 6.8+ kernels. That path produced broken installs on Ubuntu 24.04 and left stale `saa716x_tbs-dvb` assumptions in place.

The main scripts now use the direct TBS driver package and detect the matching TBS runtime module for the connected hardware:

- `install`
  Full fresh path. Re-extracts the TBS source archive into `tbs_install_drivers_from_TBS`, rebuilds, reinstalls, installs firmware, detects the matching TBS PCI/USB module, loads it, and writes `/etc/modules-load.d/tbs.conf`.
- `install_reuse_tree`
  Downloads `tbsdvb_v1013.tar.bz2`, extracts it to a sibling folder named `tbs_install_drivers_from_TBS` if needed, rewrites the extracted `Makefile` to a satellite-focused TBS module list, builds it for the running kernel, installs firmware, runs `depmod`, detects the matching TBS PCI/USB module, loads it, and writes `/etc/modules-load.d/tbs.conf`.
- `install_wo_fetch`
  Rebuilds and reinstalls from an existing `tbs_install_drivers_from_TBS` tree, again using the satellite-focused TBS module list and hardware-based module selection. Use this after a kernel update when the source tree is already present.
- `install_legacy_bash`
  Historical reference only. Not maintained.

The narrowed build list is intended to keep the install focused on TBS satellite-capable PCIe cards and USB boxes instead of compiling the full mixed terrestrial/cable/device set from the upstream tarball. Shared frontend and tuner helpers that those TBS satellite devices depend on are still built.

The autoload configuration is no longer hardcoded to `tbsecp3`. On PCI systems that module may be correct, but USB systems need their matching `dvb-usb-*` driver instead, for example `dvb_usb_tbs5931` on a TBS 5931 host.

The historical `install_legacy_bash` script is left in place only as reference.

There is an alternative script at: https://cesbo.com/download/astra/scripts/drv-tbs.sh
This script, which was not tested, might be better because it installs support for more controller-chips.

MIT license.
