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
- TBS SAA716x PCI cards, such as TBS6985 on Philips/NXP SAA7160
  `[1131:7160]`, use the legacy workflow even on `6.8+` because the direct
  package does not include `saa716x_tbs-dvb`

For most `6.8+` kernels, the current scripts no longer use the older `media_build` / `linux_media` flow. That path produced broken installs on Ubuntu 24.04 and left stale `saa716x_tbs-dvb` assumptions in place. SAA716x-based TBS PCI cards are the exception because the direct TBS package does not ship that runtime driver. On older kernels the scripts fall back to the legacy workflow automatically.

The main script detects the matching TBS runtime module for the connected hardware after either build path completes:

- `install`
  Full fresh path. On Linux `6.8+`, re-extracts the direct TBS source archive into `tbs_install_drivers_from_TBS`, rebuilds, reinstalls, installs firmware, detects the matching TBS PCI/USB module, loads it, and writes `/etc/modules-load.d/tbs.conf`. On older kernels and SAA716x PCI systems, refreshes the sibling `media_build` and `media` trees, prepares the backported `v4l` tree, applies local compatibility patches, builds modules through the running kernel's Kbuild tree, installs them with `modules_install`, then performs the same firmware, module-load, and autoload steps.

Older entry point variants are archived under `old/` for reference only and are not maintained.

The narrowed build list is intended to keep the install focused on TBS satellite-capable PCIe cards and USB boxes instead of compiling the full mixed terrestrial/cable/device set from the upstream tarball. Shared frontend and tuner helpers that those TBS satellite devices depend on are still built.

PCI detection checks verbose PCI IDs, including subsystem IDs. This covers TBS cards that show the bridge chip as the primary PCI device, for example Philips/NXP SAA7160 `[1131:7160]`, while the TBS identity is exposed as a subsystem vendor such as `[6985:0002]`. PCI runtime module selection is alias-based, so an installed `tbsecp3` module is not chosen for SAA716x hardware unless its PCI aliases actually match.

Run the installer as the normal user, not with `sudo`. The script invokes `sudo` internally only for package installation, module installation, firmware installation, and module loading.

On legacy `media_build` builds, the script lets media_build initialize the generated `v4l` tree and then patches `v4l/ccs-core.c` when the running kernel exposes the one-argument `pm_runtime_get_if_active(struct device *dev)` API. This keeps newer Ubuntu kernels from failing on older generated media source that still calls `pm_runtime_get_if_active(&client->dev, true)`.

When switching from the direct-package PCI driver to the legacy SAA716x driver, the script unloads a stale `tbsecp3` stack first. Otherwise the old in-memory `dvb_core` module can have incompatible symbol versions and make `saa716x_core` fail with `Invalid argument`.

The autoload configuration is no longer hardcoded to `tbsecp3`. On PCI systems that module may be correct, but USB systems need their matching `dvb-usb-*` driver instead, for example `dvb_usb_tbs5931` on a TBS 5931 host.

Some PCI cards also need a frontend helper module loaded explicitly before the main PCI bridge driver. The TBS 6909 `6909:0001` card uses `mxl58x`; without it `tbsecp3` can bind to PCI while no `/dev/dvb` adapter appears.

The historical `old/install_legacy_bash` script is left in place only as reference.

There is an alternative script at: https://cesbo.com/download/astra/scripts/drv-tbs.sh
This script, which was not tested, might be better because it installs support for more controller-chips.

MIT license.
