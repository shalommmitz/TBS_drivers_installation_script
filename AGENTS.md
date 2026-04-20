# AGENTS.md

This folder contains the maintained installer wrappers for TBS DVB drivers.

## Goal

Keep the installer focused on the current known-good path for modern Ubuntu systems:

- direct TBS driver package: `tbsdvb_v1013.tar.bz2`
- kernel family: Linux `6.8+`
- top-level PCI module to load: `tbsecp3`
- scope: TBS satellite-capable PCIe and USB devices only

## Current Working Model

The maintained entry points are:

- `install`
- `partial_install`
- `exprimental_script`
- `tbs_install_lib.py`

`tbs_install_lib.py` is the real implementation. The other scripts are thin entry points.

The scripts currently:

- install the matching kernel headers and build tools
- download or reuse the direct TBS source tarball
- extract it into a sibling directory named `tbs_install_drivers_from_TBS`
- rewrite the extracted `Makefile` to a satellite-focused `MODDEFS` allowlist
- build for the running kernel
- run `sudo make install`
- install firmware
- run `depmod`
- load `tbsecp3`
- persist autoload via `/etc/modules-load.d/tbs.conf`

## Do Not Reintroduce

For Linux `6.8+`, do not switch this folder back to the older `media_build` / `linux_media` flow unless the user explicitly asks for that legacy path.

Do not assume the working module is `saa716x_tbs-dvb`.

Do not expand the build back to the full mixed upstream module set unless the user explicitly wants that.

## Build Scope

The build scope is controlled in:

- [tbs_install_lib.py](/workspace/code/TBS_drivers_installation_script/tbs_install_lib.py)

Look for:

- `SATELLITE_MODDEFS`
- `restrict_makefile_to_satellite_only()`

That allowlist intentionally keeps:

- TBS satellite-capable PCIe support
- TBS satellite-capable USB families
- shared frontend and tuner helpers required by those TBS satellite devices

That allowlist intentionally avoids:

- non-TBS drivers
- broad “build everything” behavior from the upstream tarball
- clearly terrestrial/cable-only TBS USB lines such as `5220`, `5230`, and `5881`

If you change the allowlist, preserve dependency completeness. Removing a shared frontend or tuner helper can break a TBS satellite device even if the top-level device module still builds.

## Known Pitfalls

- A kernel upgrade can leave a stale installed module under `/lib/modules/.../updates/` with the wrong `vermagic`.
- `make clean` only cleans the extracted source tree; the installed module is updated by `sudo make install`.
- `modules_install` may print a `System.map` warning. Follow with `sudo depmod -a`.
- Success means the installed module under `/lib/modules/<running-kernel>/updates/...` matches the running kernel, not just the rebuilt source tree.

## Verification Checklist

After any meaningful change, verify these in this order:

1. `modinfo tbsecp3 | egrep '^(filename|vermagic|name):'`
2. `lsmod | egrep 'tb|tbs|dvb|saa716'`
3. `ls -la /dev/dvb`
4. `find /dev/dvb -maxdepth 2 -type c | sort`

Healthy state looks like:

- `tbsecp3` installed for the running kernel
- `tbsecp3`, `dvb_core`, and required helper modules loaded
- `/dev/dvb/adapter*` present
- each adapter exposing `frontend0`, `demux0`, `dvr0`, and `net0`

## Editing Guidance

Prefer changing `tbs_install_lib.py` instead of duplicating logic across entry-point scripts.

Keep historical files such as `old_bash_script` and the Ubuntu 24.04 fix notes as reference unless the user explicitly asks to clean them up.

If you update behavior, also update:

- [README.md](/workspace/code/TBS_drivers_installation_script/README.md)

If you are unsure whether a device family belongs in the satellite-focused allowlist, default to preserving the narrower scope and note the uncertainty rather than broadening the build blindly.
