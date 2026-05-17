# A Script to Install Drivers for TBS Sat Receivers

## Usage

   `./install`

## The original TBS install package

   You can download the following drivers from the [TBS site](https://www.tbsiptv.com/index.php?route=product/download/drivers&path=6&id=27):

  - [For Kernel V6.8 ~ V6.18](https://www.tbsiptv.com/download/common/tbsdvb_v1013.tar.bz2)
  - [For Kernel V4.19 - V6.12](https://www.tbsdtv.com/download/document/linux/media_build-2025-04-28.tar.bz2)

Tested on Ubuntu 24.04 with kernel 6.8.0-110-generic and Ubuntu 22.04 5.2

The original script is from https://www.tbsdtv.com/forum/viewtopic.php?f=87&t=25391

This original script was written by andreril at Mon Oct 26 2020. I could not find any farther info on the original author.

The maintained entry points now auto-select the installation variant from the running kernel:

- Linux `6.8+`: direct TBS package `tbsdvb_v1013.tar.bz2`
- older kernels: legacy `media_build` / `linux_media` workflow

For `6.8+` kernels, the current scripts no longer use the older `media_build` / `linux_media` flow. That path produced broken installs on Ubuntu 24.04 and left stale `saa716x_tbs-dvb` assumptions in place. On older kernels the scripts fall back to that legacy workflow automatically.

The main scripts detect the matching TBS runtime module for the connected hardware after either build path completes:

- `install`
  Full fresh path. On Linux `6.8+`, re-extracts the direct TBS source archive into `tbs_install_drivers_from_TBS`, rebuilds, reinstalls, installs firmware, detects the matching TBS PCI/USB module, loads it, and writes `/etc/modules-load.d/tbs.conf`. On older kernels, refreshes the sibling `media_build` and `media` trees, builds and installs via the legacy workflow, then performs the same firmware, module-load, and autoload steps.
- `install_reuse_tree`
  Reuses existing source trees when possible. On Linux `6.8+`, downloads `tbsdvb_v1013.tar.bz2`, extracts it to a sibling folder named `tbs_install_drivers_from_TBS` if needed, rewrites the extracted `Makefile` to a satellite-focused TBS module list, builds it for the running kernel, installs firmware, runs `depmod`, detects the matching TBS PCI/USB module, loads it, and writes `/etc/modules-load.d/tbs.conf`. On older kernels, reuses the sibling `media_build` and `media` trees if they are already present, otherwise clones them before building and installing.
- `install_wo_fetch`
  Rebuilds and reinstalls without fetching new sources. On Linux `6.8+`, uses an existing `tbs_install_drivers_from_TBS` tree with the satellite-focused TBS module list and hardware-based module selection. On older kernels, uses existing `media_build` and `media` trees without recloning them. Use this after a kernel update when the relevant source tree is already present.
- `install_legacy_bash`
  Historical reference only. Not maintained.

The narrowed build list is intended to keep the install focused on TBS satellite-capable PCIe cards and USB boxes instead of compiling the full mixed terrestrial/cable/device set from the upstream tarball. Shared frontend and tuner helpers that those TBS satellite devices depend on are still built.

The autoload configuration is no longer hardcoded to `tbsecp3`. On PCI systems that module may be correct, but USB systems need their matching `dvb-usb-*` driver instead, for example `dvb_usb_tbs5931` on a TBS 5931 host.

The historical `install_legacy_bash` script is left in place only as reference.

There is an alternative script at: https://cesbo.com/download/astra/scripts/drv-tbs.sh
This script, which was not tested, might be better because it installs support for more controller-chips.

MIT license.
