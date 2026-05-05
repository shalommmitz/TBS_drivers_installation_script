# AGENTS.md

This folder contains the maintained installer wrappers for TBS DVB drivers.

## Goal

Keep the installer selecting between the two known-good paths:

- direct TBS driver package: `tbsdvb_v1013.tar.bz2` for Linux `6.8+`
- legacy `media_build` / `linux_media` workflow for older kernels
- load the hardware-matching top-level TBS runtime module
- scope: TBS satellite-capable PCIe and USB devices only on the direct-package path

## Current Working Model

The maintained entry points are:

- `install`
- `tbs_install_lib.py`
- `old/install_reuse_tree`
- `old/install_wo_fetch`

Historical reference only:

- `old/install_legacy_bash`

`tbs_install_lib.py` is the real implementation. The other scripts are thin entry points.

The scripts currently:

- install the matching kernel headers and build tools
- choose the direct TBS package for Linux `6.8+` and the legacy `media_build` / `linux_media` flow for older kernels
- on the direct path, download or reuse the direct TBS source tarball, extract it into `tbs_install_drivers_from_TBS`, rewrite the `Makefile` to a satellite-focused `MODDEFS` allowlist, build it, and run `sudo make install`
- on the legacy path, clone or reuse sibling `media_build` and `media` trees, prepare the backport tree via `make dir DIR=../media`, and run `./install.sh`
- install firmware
- detect the matching TBS PCI/USB module for the connected hardware
- load the detected module(s)
- persist the detected module(s) via `/etc/modules-load.d/tbs.conf`

## Do Not Reintroduce

For Linux `6.8+`, do not switch this folder back to the older `media_build` / `linux_media` flow unless the user explicitly asks for that legacy path.

For older kernels, do not force the direct-package path when the script has already selected the legacy workflow.

Do not assume the working module is `saa716x_tbs-dvb` or `tbsecp3`. The correct PCI runtime module can depend on which build path produced the installed driver.

Do not assume `tbsecp3` is always the correct runtime module. That is correct for supported TBS PCIe cards, but USB devices need their matching `dvb-usb-*` module.

Do not expand the build back to the full mixed upstream module set unless the user explicitly wants that.

## Build Scope

The direct-package build scope is controlled in:

- [tbs_install_lib.py](/workspace/code/TBS_drivers_installation_script/tbs_install_lib.py)

Look for:

- `SATELLITE_MODDEFS`
- `restrict_makefile_to_satellite_only()`
- `detect_target_modules()`

That allowlist intentionally keeps:

- TBS satellite-capable PCIe support
- TBS satellite-capable USB families
- shared frontend and tuner helpers required by those TBS satellite devices

That allowlist intentionally avoids:

- non-TBS drivers
- broad “build everything” behavior from the upstream tarball
- clearly terrestrial/cable-only TBS USB lines such as `5220`, `5230`, and `5881`

If you change the allowlist, preserve dependency completeness. Removing a shared frontend or tuner helper can break a TBS satellite device even if the top-level device module still builds.

The legacy `media_build` / `linux_media` path does not use that narrowed `MODDEFS` allowlist.

If you change runtime module detection, verify both PCI-only and USB-only hosts.

## Known Pitfalls

- A kernel upgrade can leave a stale installed module under `/lib/modules/.../updates/` with the wrong `vermagic`.
- `make clean` only cleans the extracted source tree; the installed module is updated by `sudo make install`.
- `modules_install` may print a `System.map` warning. Follow with `sudo depmod -a`.
- Success means the installed module under `/lib/modules/<running-kernel>/updates/...` matches the running kernel, not just the rebuilt source tree.

## Verification Checklist

After any meaningful change, verify these in this order:

1. `modinfo <top-level-module> | egrep '^(filename|vermagic|name):'`
2. `lsmod | egrep 'tb|tbs|dvb|saa716'`
3. `ls -la /dev/dvb`
4. `find /dev/dvb -maxdepth 2 -type c | sort`

Healthy state looks like:

- the hardware-matching top-level module installed for the running kernel
- the hardware-matching top-level module, `dvb_core`, and required helper modules loaded
- `/dev/dvb/adapter*` present
- each adapter exposing `frontend0`, `demux0`, `dvr0`, and `net0`

## Editing Guidance

Prefer changing `tbs_install_lib.py` instead of duplicating logic across entry-point scripts.

Keep historical files such as `install_legacy_bash` and the Ubuntu 24.04 fix notes as reference unless the user explicitly asks to clean them up.

If you update behavior, also update:

- [README.md](/workspace/code/TBS_drivers_installation_script/README.md)

If you are unsure whether a device family belongs in the satellite-focused allowlist, default to preserving the narrower scope and note the uncertainty rather than broadening the build blindly.
