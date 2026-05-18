#!/usr/bin/env python3

import re
import shlex
import shutil
import subprocess
import tarfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
HOME_DIR = SCRIPT_DIR.parent

DIRECT_KERNEL_MIN = (6, 8)

DRIVER_URL = "https://www.tbsiptv.com/download/common/tbsdvb_v1013.tar.bz2"
DRIVER_ARCHIVE = SCRIPT_DIR / "tbsdvb_v1013.tar.bz2"
SOURCE_DIR = HOME_DIR / "tbs_install_drivers_from_TBS"

LEGACY_MEDIA_BUILD_REPO = "https://github.com/tbsdtv/media_build.git"
LEGACY_MEDIA_REPO = "https://github.com/tbsdtv/linux_media.git"
LEGACY_MEDIA_BUILD_DIR = HOME_DIR / "media_build"
LEGACY_MEDIA_DIR = HOME_DIR / "media"

FIRMWARE_URL = "http://www.tbsdtv.com/download/document/linux/tbs-tuner-firmwares_v1.0.tar.bz2"
FIRMWARE_ARCHIVE = SCRIPT_DIR / "tbs-tuner-firmwares_v1.0.tar.bz2"
FIRMWARE_DIR = Path("/lib/firmware")

MODULE_LOAD_CONF = Path("/etc/modules-load.d/tbs.conf")
# Some TBS PCIe cards expose only the bridge chip as the primary PCI device,
# for example Philips/NXP SAA7160 [1131:7160], and identify TBS through the
# subsystem vendor instead.
TBS_PCI_VENDOR_IDS = {"544d"}
TBS_PCI_SUBSYSTEM_VENDOR_IDS = {"6985"}
SAA716X_TBS_PCI_IDS = {("1131", "7160")}
SAA716X_PCI_MODULE_CANDIDATES = ["saa716x_tbs-dvb", "saa716x_tbs_dvb"]
PCI_MODULE_CANDIDATES = ["tbsecp3"] + SAA716X_PCI_MODULE_CANDIDATES
USB_MODULES = [
    "dvb-usb-tbsqbox",
    "dvb-usb-tbsqbox2",
    "dvb-usb-tbsqbox22",
    "dvb-usb-tbs5520",
    "dvb-usb-tbs5520se",
    "dvb-usb-tbs5530",
    "dvb-usb-tbs5580",
    "dvb-usb-tbs5590",
    "dvb-usb-tbs5922se",
    "dvb-usb-tbs5925",
    "dvb-usb-tbs5927",
    "dvb-usb-tbs5930",
    "dvb-usb-tbs5931",
]

# Limit the build to TBS satellite-capable PCIe/USB device modules plus the
# shared demod/tuner helpers those devices need. Pure terrestrial/cable-only
# TBS USB devices are intentionally left out of this allowlist.
SATELLITE_MODDEFS = [
    "CONFIG_DVB_CORE=m",
    "CONFIG_DVB_TBSECP3=m",
    "CONFIG_TBS_PCIE_CI=m",
    "CONFIG_TBS_PCIE_MOD=m",
    "CONFIG_DVB_TBSPRIV=m",
    "CONFIG_DVB_USB=m",
    "CONFIG_DVB_USB_TBSQBOX=m",
    "CONFIG_DVB_USB_TBSQBOX2=m",
    "CONFIG_DVB_USB_TBSQBOX22=m",
    "CONFIG_DVB_USB_TBS5520=m",
    "CONFIG_DVB_USB_TBS5520se=m",
    "CONFIG_DVB_USB_TBS5530=m",
    "CONFIG_DVB_USB_TBS5580=m",
    "CONFIG_DVB_USB_TBS5590=m",
    "CONFIG_DVB_USB_TBS5922SE=m",
    "CONFIG_DVB_USB_TBS5925=m",
    "CONFIG_DVB_USB_TBS5927=m",
    "CONFIG_DVB_USB_TBS5930=m",
    "CONFIG_DVB_USB_TBS5931=m",
    "CONFIG_DVB_TAS2101=m",
    "CONFIG_DVB_GX1133=m",
    "CONFIG_DVB_SI2168=m",
    "CONFIG_DVB_SI2183=m",
    "CONFIG_DVB_STV090x=m",
    "CONFIG_DVB_STV6110x=m",
    "CONFIG_DVB_STV091X=m",
    "CONFIG_DVB_STV0910=m",
    "CONFIG_DVB_STV0299=m",
    "CONFIG_DVB_STV0288=m",
    "CONFIG_DVB_STB6000=m",
    "CONFIG_DVB_STB6100=m",
    "CONFIG_DVB_STV6111=m",
    "CONFIG_DVB_STID135=m",
    "CONFIG_DVB_CX24117=m",
    "CONFIG_DVB_MXL58X=m",
    "CONFIG_DVB_MXL5XX=m",
    "CONFIG_DVB_M88RS6060=m",
    "CONFIG_MEDIA_TUNER_AV201X=m",
    "CONFIG_MEDIA_TUNER_STV6120=m",
    "CONFIG_MEDIA_TUNER_RDA5816=m",
    "CONFIG_MEDIA_TUNER_R848=m",
    "CONFIG_MEDIA_TUNER_R850=m",
    "CONFIG_DVB_NET=y",
]


def run(cmd, cwd=None, check=True):
    print(f">>> {cmd}")
    subprocess.run(cmd, shell=True, cwd=cwd, check=check)


def read_output(cmd):
    return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()


def running_kernel():
    return subprocess.check_output(["uname", "-r"], text=True).strip()


def kernel_version(kernel=None):
    kernel = kernel or running_kernel()
    match = re.match(r"^(\d+)\.(\d+)", kernel)
    if not match:
        raise SystemExit("Unable to parse the running kernel version.")
    return tuple(int(part) for part in match.groups())


def install_variant(kernel=None, pci_output=None):
    kernel = kernel or running_kernel()
    if has_saa716x_tbs_pci_hardware(pci_output):
        return "legacy"
    return "direct" if kernel_version(kernel) >= DIRECT_KERNEL_MIN else "legacy"


def selected_install_variant():
    kernel = running_kernel()
    pci_output = pci_hardware_output()
    variant = install_variant(kernel, pci_output=pci_output)
    if has_saa716x_tbs_pci_hardware(pci_output):
        print(
            f"Detected kernel {kernel} with TBS SAA716x PCI hardware; "
            "using the legacy media_build workflow for saa716x_tbs-dvb support."
        )
    elif variant == "direct":
        print(f"Detected kernel {kernel}; using the direct TBS package workflow.")
    else:
        print(f"Detected kernel {kernel}; using the legacy media_build workflow.")
    return variant


def ensure_packages(packages):
    quoted = " ".join(shlex.quote(package) for package in packages)
    run("sudo apt-get update")
    run("sudo apt-get -y install " + quoted)


def ensure_direct_packages():
    kernel = running_kernel()
    packages = [
        f"linux-headers-{kernel}",
        "build-essential",
        "dvb-apps",
        "dwarves",
        "libelf-dev",
        "libproc-processtable-perl",
        "patchutils",
        "wget",
    ]
    ensure_packages(packages)


def ensure_legacy_packages():
    kernel = running_kernel()
    packages = [
        f"linux-headers-{kernel}",
        "build-essential",
        "dvb-apps",
        "gcc",
        "git",
        "libproc-processtable-perl",
        "patchutils",
        "wget",
    ]
    ensure_packages(packages)


def ensure_download(url, destination):
    if destination.exists():
        print(f"Reusing {destination.name}")
        return
    run(f"wget -O {destination} {url}")


def source_tree_exists():
    return (SOURCE_DIR / "Makefile").exists() and (SOURCE_DIR / "pci").exists()


def extract_driver_tree(force_refresh=False):
    ensure_download(DRIVER_URL, DRIVER_ARCHIVE)

    if source_tree_exists() and not force_refresh:
        print(f"Reusing existing source tree: {SOURCE_DIR}")
        return

    if SOURCE_DIR.exists():
        print(f"Removing existing source tree: {SOURCE_DIR}")
        shutil.rmtree(SOURCE_DIR)

    extract_root = SCRIPT_DIR / ".tbs_extract_tmp"
    if extract_root.exists():
        shutil.rmtree(extract_root)
    extract_root.mkdir()

    try:
        with tarfile.open(DRIVER_ARCHIVE, "r:bz2") as archive:
            archive.extractall(extract_root)

        extracted_items = list(extract_root.iterdir())
        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            shutil.move(str(extracted_items[0]), str(SOURCE_DIR))
        else:
            SOURCE_DIR.mkdir(parents=True, exist_ok=True)
            for item in extracted_items:
                shutil.move(str(item), str(SOURCE_DIR / item.name))
    finally:
        if extract_root.exists():
            shutil.rmtree(extract_root)

    if not source_tree_exists():
        raise SystemExit(f"Expected TBS source tree was not created at {SOURCE_DIR}")


def ensure_firmware_archive():
    ensure_download(FIRMWARE_URL, FIRMWARE_ARCHIVE)


def install_firmware():
    ensure_firmware_archive()
    run(f"sudo tar jxvf {FIRMWARE_ARCHIVE} -C {FIRMWARE_DIR}")


def satellite_moddefs_block():
    lines = ["# --- Module Configurations ---"]
    for index, item in enumerate(SATELLITE_MODDEFS):
        prefix = "MODDEFS := " if index == 0 else "\t"
        suffix = " \\" if index != len(SATELLITE_MODDEFS) - 1 else ""
        lines.append(f"{prefix}{item}{suffix}")
    return "\n".join(lines)


def restrict_makefile_to_satellite_only():
    makefile = SOURCE_DIR / "Makefile"
    contents = makefile.read_text()
    pattern = r"# --- Module Configurations ---\r?\nMODDEFS :=.*?\r?\n\r?\n# --- Compilation Flags ---"
    replacement = satellite_moddefs_block() + "\n\n# --- Compilation Flags ---"
    updated, count = re.subn(pattern, replacement, contents, flags=re.S)
    if count != 1:
        raise SystemExit(f"Unable to rewrite {makefile} to the satellite-only module list.")
    makefile.write_text(updated)
    print("Restricted the TBS source Makefile to the satellite-focused module list.")


def build_source_tree(clean=True):
    if not source_tree_exists():
        raise SystemExit(f"Missing TBS source tree: {SOURCE_DIR}")
    restrict_makefile_to_satellite_only()
    if clean:
        run("make clean", cwd=SOURCE_DIR)
    run("make -j$(nproc)", cwd=SOURCE_DIR)


def install_source_tree():
    run("sudo make install", cwd=SOURCE_DIR)
    run("sudo depmod -a")


def modinfo_field(module, field):
    try:
        output = subprocess.check_output(
            ["modinfo", "-F", field, module],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def canonical_module_name(module):
    names = modinfo_field(module, "name")
    return names[0] if names else module.replace("-", "_")


def module_exists(module):
    try:
        return subprocess.run(
            ["modinfo", module],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
    except FileNotFoundError:
        return False


def detected_usb_ids():
    try:
        output = read_output(["lsusb"])
    except (FileNotFoundError, subprocess.CalledProcessError):
        return set()

    usb_ids = set()
    for line in output.splitlines():
        match = re.search(r"ID\s+([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})", line)
        if match:
            usb_ids.add((match.group(1).lower(), match.group(2).lower()))
    return usb_ids


def detected_pci_ids(output):
    return {
        (match.group(1).lower(), match.group(2).lower())
        for match in re.finditer(
            r"(?:\[|\s)([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})(?:\]|\b)",
            output,
        )
    }


PCI_SLOT_RE = re.compile(
    r"^(?:[0-9A-Fa-f]{4}:)?[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}\.[0-9A-Fa-f]\b"
)
PCI_ID_RE = re.compile(r"(?:\[|\s)([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})(?:\]|\b)")
PCI_ALIAS_RE = re.compile(
    r"^pci:v([0-9A-Fa-f]{8}|\*)d([0-9A-Fa-f]{8}|\*)"
    r"sv([0-9A-Fa-f]{8}|\*)sd([0-9A-Fa-f]{8}|\*)"
)


def detected_pci_devices(output):
    devices = []
    current = None

    for line in output.splitlines():
        ids = [(match.group(1).lower(), match.group(2).lower()) for match in PCI_ID_RE.finditer(line)]
        if PCI_SLOT_RE.search(line):
            if ids:
                vendor, device = ids[-1]
                current = {
                    "vendor": vendor,
                    "device": device,
                    "subvendor": None,
                    "subdevice": None,
                }
                devices.append(current)
            else:
                current = None
        elif current and line.lstrip().startswith("Subsystem:") and ids:
            current["subvendor"], current["subdevice"] = ids[-1]

    return devices


def pci_hardware_output():
    try:
        return read_output(["lspci", "-nn", "-v"])
    except (FileNotFoundError, subprocess.CalledProcessError):
        try:
            return read_output(["lspci", "-n"])
        except (FileNotFoundError, subprocess.CalledProcessError):
            return ""


def is_tbs_pci_device(device):
    return (
        device["vendor"] in TBS_PCI_VENDOR_IDS
        or device["subvendor"] in TBS_PCI_SUBSYSTEM_VENDOR_IDS
    )


def is_saa716x_tbs_pci_device(device):
    return (
        (device["vendor"], device["device"]) in SAA716X_TBS_PCI_IDS
        and device["subvendor"] in TBS_PCI_SUBSYSTEM_VENDOR_IDS
    )


def has_tbs_pci_hardware(pci_output=None):
    pci_output = pci_output if pci_output is not None else pci_hardware_output()
    return any(is_tbs_pci_device(device) for device in detected_pci_devices(pci_output))


def has_saa716x_tbs_pci_hardware(pci_output=None):
    pci_output = pci_output if pci_output is not None else pci_hardware_output()
    return any(
        is_saa716x_tbs_pci_device(device) for device in detected_pci_devices(pci_output)
    )


def pci_alias_component_matches(pattern, value):
    pattern = pattern.lower()
    if pattern == "*":
        return True
    if value is None:
        return False
    value = value.lower().zfill(8)
    if "*" not in pattern:
        return value == pattern.zfill(8)
    regex = "^" + re.escape(pattern).replace(r"\*", "[0-9a-f]*") + "$"
    return re.fullmatch(regex, value) is not None


def pci_alias_matches_device(alias, device):
    match = PCI_ALIAS_RE.search(alias)
    if not match:
        return False

    return (
        pci_alias_component_matches(match.group(1), device["vendor"])
        and pci_alias_component_matches(match.group(2), device["device"])
        and pci_alias_component_matches(match.group(3), device["subvendor"])
        and pci_alias_component_matches(match.group(4), device["subdevice"])
    )


def pci_module_matches_hardware(module, pci_devices):
    return any(
        pci_alias_matches_device(alias, device)
        for alias in modinfo_field(module, "alias")
        for device in pci_devices
    )


def installed_pci_module(pci_output=None):
    pci_output = pci_output if pci_output is not None else pci_hardware_output()
    pci_devices = [
        device for device in detected_pci_devices(pci_output) if is_tbs_pci_device(device)
    ]
    for module in PCI_MODULE_CANDIDATES:
        if module_exists(module) and pci_module_matches_hardware(module, pci_devices):
            return canonical_module_name(module)
    return None


def usb_module_matches_hardware(module, usb_ids):
    for alias in modinfo_field(module, "alias"):
        match = re.search(r"usb:v([0-9A-Fa-f]{4})p([0-9A-Fa-f]{4})", alias)
        if match and (match.group(1).lower(), match.group(2).lower()) in usb_ids:
            return True
    return False


def detect_target_modules():
    modules = []
    pci_output = pci_hardware_output()

    if has_tbs_pci_hardware(pci_output):
        pci_module = installed_pci_module(pci_output)
        if not pci_module:
            raise SystemExit(
                "Detected TBS PCI hardware but could not find an installed TBS PCI runtime "
                "module matching its PCI alias. "
                "Expected one of: " + ", ".join(PCI_MODULE_CANDIDATES)
            )
        modules.append(pci_module)

    usb_ids = detected_usb_ids()
    for module in USB_MODULES:
        if usb_module_matches_hardware(module, usb_ids):
            modules.append(module)

    canonical = []
    seen = set()
    for module in modules:
        name = canonical_module_name(module)
        if name not in seen:
            seen.add(name)
            canonical.append(name)

    if not canonical:
        raise SystemExit(
            "Could not match the connected TBS hardware to a supported module. "
            "Inspect lsusb/lspci output and update the module allowlist if needed."
        )

    print("Detected TBS modules to load:", ", ".join(canonical))
    return canonical


def load_driver_modules(modules):
    unload_conflicting_driver_modules(modules)
    for module in modules:
        run(f"sudo modprobe {module}")


def unload_conflicting_driver_modules(modules):
    module_set = set(modules)
    if "saa716x_tbs_dvb" in module_set:
        # A previous direct-package run can leave tbsecp3 and its helper stack
        # loaded. That stale dvb_core instance has different symbol versions
        # from the legacy media_build modules and makes saa716x_core fail with
        # "Unknown symbol ... (err -22)" / modprobe "Invalid argument".
        stale_modules = [
            "tbsecp3",
            "gx1133",
            "tas2101",
            "dvb_core",
            "mc",
        ]
        run("sudo modprobe -r " + " ".join(stale_modules), check=False)


def enable_autoload(modules):
    quoted = " ".join(shlex.quote(module) for module in modules)
    run(f"printf '%s\\n' {quoted} | sudo tee {MODULE_LOAD_CONF} >/dev/null")


def verify_installation():
    run("ls -la /dev/dvb", check=False)
    run("find /dev/dvb -maxdepth 2 -type c | sort", check=False)


def remove_tree(path):
    if path.exists():
        run(f"sudo rm -rf {shlex.quote(str(path))}")


def legacy_source_tree_exists():
    return (
        (LEGACY_MEDIA_BUILD_DIR / "Makefile").exists()
        and (LEGACY_MEDIA_BUILD_DIR / "install.sh").exists()
        and LEGACY_MEDIA_DIR.exists()
    )


def prepare_legacy_source_tree(force_refresh=False):
    if force_refresh:
        remove_tree(LEGACY_MEDIA_BUILD_DIR)
        remove_tree(LEGACY_MEDIA_DIR)

    if LEGACY_MEDIA_BUILD_DIR.exists():
        print(f"Reusing existing source tree: {LEGACY_MEDIA_BUILD_DIR}")
    else:
        run(
            "git clone "
            + shlex.quote(LEGACY_MEDIA_BUILD_REPO)
            + " "
            + shlex.quote(str(LEGACY_MEDIA_BUILD_DIR))
        )

    if LEGACY_MEDIA_DIR.exists():
        print(f"Reusing existing source tree: {LEGACY_MEDIA_DIR}")
    else:
        run(
            "git clone --depth=1 --branch latest "
            + shlex.quote(LEGACY_MEDIA_REPO)
            + " "
            + shlex.quote(str(LEGACY_MEDIA_DIR))
        )

    if not legacy_source_tree_exists():
        raise SystemExit(
            "Expected legacy media_build and linux_media trees were not created at "
            f"{LEGACY_MEDIA_BUILD_DIR} and {LEGACY_MEDIA_DIR}"
        )


def pm_runtime_get_if_active_uses_one_arg():
    header = Path("/lib/modules") / running_kernel() / "build/include/linux/pm_runtime.h"
    try:
        contents = header.read_text()
    except OSError:
        return False

    match = re.search(r"pm_runtime_get_if_active\s*\(([^;]*)\)", contents, flags=re.S)
    if not match:
        return False
    return "," not in match.group(1)


def patch_file_once(path, old, new, description):
    if not path.exists():
        return

    contents = path.read_text()
    if old not in contents:
        return

    path.write_text(contents.replace(old, new))
    print(f"Applied legacy kernel compatibility patch to {path}: {description}.")


def apply_legacy_kernel_compat_patches():
    if pm_runtime_get_if_active_uses_one_arg():
        old = "pm_runtime_get_if_active(&client->dev, true)"
        new = "pm_runtime_get_if_active(&client->dev)"
        description = "pm_runtime_get_if_active has one argument on this kernel"
        for path in (
            LEGACY_MEDIA_DIR / "drivers/media/i2c/ccs/ccs-core.c",
            LEGACY_MEDIA_BUILD_DIR / "v4l/ccs-core.c",
        ):
            patch_file_once(path, old, new, description)


def apply_legacy_backport_patches():
    run("make -C linux apply_patches", cwd=LEGACY_MEDIA_BUILD_DIR)


def build_legacy_modules():
    kernel = running_kernel()
    v4l_dir = shlex.quote(str(LEGACY_MEDIA_BUILD_DIR / "v4l"))
    run(f"make -C /lib/modules/{kernel}/build M={v4l_dir} -j$(nproc) modules")


def build_legacy_source_tree():
    if not legacy_source_tree_exists():
        raise SystemExit(
            f"Missing legacy source trees: {LEGACY_MEDIA_BUILD_DIR} and/or {LEGACY_MEDIA_DIR}"
        )
    run("make dir DIR=../media", cwd=LEGACY_MEDIA_BUILD_DIR)
    apply_legacy_backport_patches()
    apply_legacy_kernel_compat_patches()
    build_legacy_modules()


def install_legacy_source_tree():
    kernel = running_kernel()
    v4l_dir = shlex.quote(str(LEGACY_MEDIA_BUILD_DIR / "v4l"))
    run(f"sudo make -C /lib/modules/{kernel}/build M={v4l_dir} modules_install")
    run("sudo depmod -a")


def direct_fresh_install(force_refresh_source=False):
    ensure_direct_packages()
    extract_driver_tree(force_refresh=force_refresh_source)
    build_source_tree(clean=True)
    install_source_tree()
    install_firmware()
    modules = detect_target_modules()
    load_driver_modules(modules)
    enable_autoload(modules)
    verify_installation()
    print("TBS driver install completed.")


def legacy_fresh_install(force_refresh_source=False):
    ensure_legacy_packages()
    prepare_legacy_source_tree(force_refresh=force_refresh_source)
    build_legacy_source_tree()
    install_legacy_source_tree()
    install_firmware()
    modules = detect_target_modules()
    load_driver_modules(modules)
    enable_autoload(modules)
    verify_installation()
    print("TBS driver install completed.")


def direct_rebuild_existing_source():
    ensure_direct_packages()
    if not source_tree_exists():
        raise SystemExit(
            f"Expected existing source tree at {SOURCE_DIR}. "
            "Run ./install first or extract the TBS source archive there."
        )
    build_source_tree(clean=True)
    install_source_tree()
    if FIRMWARE_ARCHIVE.exists():
        install_firmware()
    modules = detect_target_modules()
    load_driver_modules(modules)
    enable_autoload(modules)
    verify_installation()
    print("TBS driver rebuild completed.")


def legacy_rebuild_existing_source():
    ensure_legacy_packages()
    if not legacy_source_tree_exists():
        raise SystemExit(
            "Expected existing legacy source trees at "
            f"{LEGACY_MEDIA_BUILD_DIR} and {LEGACY_MEDIA_DIR}. "
            "Run ./install first."
        )
    build_legacy_source_tree()
    install_legacy_source_tree()
    if FIRMWARE_ARCHIVE.exists():
        install_firmware()
    modules = detect_target_modules()
    load_driver_modules(modules)
    enable_autoload(modules)
    verify_installation()
    print("TBS driver rebuild completed.")


def fresh_install(force_refresh_source=False):
    variant = selected_install_variant()
    if variant == "direct":
        direct_fresh_install(force_refresh_source=force_refresh_source)
    else:
        legacy_fresh_install(force_refresh_source=force_refresh_source)


def rebuild_existing_source():
    variant = selected_install_variant()
    if variant == "direct":
        direct_rebuild_existing_source()
    else:
        legacy_rebuild_existing_source()
