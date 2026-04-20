#!/usr/bin/env python3

import re
import shlex
import shutil
import subprocess
import tarfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
HOME_DIR = SCRIPT_DIR.parent

DRIVER_URL = "https://www.tbsiptv.com/download/common/tbsdvb_v1013.tar.bz2"
DRIVER_ARCHIVE = SCRIPT_DIR / "tbsdvb_v1013.tar.bz2"
SOURCE_DIR = HOME_DIR / "tbs_install_drivers_from_TBS"

FIRMWARE_URL = "http://www.tbsdtv.com/download/document/linux/tbs-tuner-firmwares_v1.0.tar.bz2"
FIRMWARE_ARCHIVE = SCRIPT_DIR / "tbs-tuner-firmwares_v1.0.tar.bz2"
FIRMWARE_DIR = Path("/lib/firmware")

MODULE_LOAD_CONF = Path("/etc/modules-load.d/tbs.conf")
TBS_PCI_VENDOR = "544d"
PCI_MODULES = ["tbsecp3"]
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


def ensure_supported_kernel():
    match = re.match(r"^(\d+)\.(\d+)", running_kernel())
    if not match:
        raise SystemExit("Unable to parse the running kernel version.")

    major, minor = (int(part) for part in match.groups())
    if (major, minor) < (6, 8):
        raise SystemExit(
            "This installer now targets the direct TBS package for Linux 6.8 and newer. "
            "Use the legacy media_build workflow only if you must support an older kernel."
        )


def ensure_packages():
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
    run("sudo apt-get update")
    run("sudo apt-get -y install " + " ".join(packages))


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


def has_tbs_pci_hardware():
    try:
        output = read_output(["lspci", "-n"])
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return re.search(rf"\b{TBS_PCI_VENDOR}:[0-9A-Fa-f]{{4}}\b", output) is not None


def usb_module_matches_hardware(module, usb_ids):
    for alias in modinfo_field(module, "alias"):
        match = re.search(r"usb:v([0-9A-Fa-f]{4})p([0-9A-Fa-f]{4})", alias)
        if match and (match.group(1).lower(), match.group(2).lower()) in usb_ids:
            return True
    return False


def detect_target_modules():
    modules = []

    if has_tbs_pci_hardware():
        modules.extend(PPCI for PPCI in PCI_MODULES)

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
    for module in modules:
        run(f"sudo modprobe {module}")


def enable_autoload(modules):
    quoted = " ".join(shlex.quote(module) for module in modules)
    run(f"printf '%s\\n' {quoted} | sudo tee {MODULE_LOAD_CONF} >/dev/null")


def verify_installation():
    run("ls -la /dev/dvb", check=False)
    run("find /dev/dvb -maxdepth 2 -type c | sort", check=False)


def fresh_install(force_refresh_source=False):
    ensure_supported_kernel()
    ensure_packages()
    extract_driver_tree(force_refresh=force_refresh_source)
    build_source_tree(clean=True)
    install_source_tree()
    install_firmware()
    modules = detect_target_modules()
    load_driver_modules(modules)
    enable_autoload(modules)
    verify_installation()
    print("TBS driver install completed.")


def rebuild_existing_source():
    ensure_supported_kernel()
    ensure_packages()
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
