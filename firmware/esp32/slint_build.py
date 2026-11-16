# slint_build.py — PlatformIO pre-build script
#
# PlatformIO uses ESP-IDF's CMake only to *configure* the project and then
# compiles the sources itself, so CMake custom steps like slint_target_sources()
# never run. This script does that step instead: it compiles every .slint file
# in src/ui/ into a C++ header in src/generated/ before the firmware is built.
#
# The slint-compiler is downloaded once into .slint-compiler/ and its version
# always matches the Slint library pinned in src/idf_component.yml.

Import("env")  # noqa: F821  (provided by PlatformIO)

import os
import platform
import re
import sys
import tarfile
import urllib.request

PROJECT_DIR = env.subst("$PROJECT_DIR")  # noqa: F821
UI_DIR = os.path.join(PROJECT_DIR, "src", "ui")
OUT_DIR = os.path.join(PROJECT_DIR, "src", "generated")
TOOLS_DIR = os.path.join(PROJECT_DIR, ".slint-compiler")
MANIFEST = os.path.join(PROJECT_DIR, "src", "idf_component.yml")

# Slint options used for microcontrollers (same as the official CMake setup)
SLINT_ARGS = ["-f", "cpp", "--embed-resources=embed-for-software-renderer", "--style", "fluent"]


def log(msg):
    print("[slint] " + msg)


def slint_version():
    with open(MANIFEST, encoding="utf-8") as f:
        m = re.search(r"slint/slint:\s*[\"']?\s*(?:==)?\s*(\d+\.\d+\.\d+)", f.read())
    if not m:
        sys.exit("[slint] Pin an exact version in src/idf_component.yml, e.g.  slint/slint: \"==1.18.1\"")
    return m.group(1)


def host_asset():
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "slint-compiler-windows-AMD64.tar.gz", "slint-compiler.exe"
    if system == "Darwin":
        return "slint-compiler-Darwin-arm64.tar.gz", "slint-compiler"
    if machine in ("aarch64", "arm64"):
        return "slint-compiler-Linux-aarch64.tar.gz", "slint-compiler"
    return "slint-compiler-Linux-x86_64.tar.gz", "slint-compiler"


def ensure_compiler(version):
    asset, exe_name = host_asset()
    target_dir = os.path.join(TOOLS_DIR, version)
    exe = os.path.join(target_dir, exe_name)
    if os.path.isfile(exe):
        return exe

    os.makedirs(target_dir, exist_ok=True)
    url = "https://github.com/slint-ui/slint/releases/download/v%s/%s" % (version, asset)
    archive = os.path.join(target_dir, asset)
    log("Downloading slint-compiler %s ..." % version)
    urllib.request.urlretrieve(url, archive)
    with tarfile.open(archive) as tar:
        tar.extractall(target_dir)
    os.remove(archive)
    if not os.path.isfile(exe):
        sys.exit("[slint] slint-compiler not found after extracting " + asset)
    if os.name != "nt":
        os.chmod(exe, 0o755)
    return exe


def needs_rebuild(header, ui_files):
    if not os.path.isfile(header):
        return True
    h_time = os.path.getmtime(header)
    return any(os.path.getmtime(f) > h_time for f in ui_files)


def compile_ui():
    if not os.path.isdir(UI_DIR):
        return
    ui_files = [os.path.join(UI_DIR, f) for f in os.listdir(UI_DIR) if f.endswith(".slint")]
    if not ui_files:
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    compiler = None

    # Each top-level .slint file that exports a Window gets its own header.
    for src in ui_files:
        with open(src, encoding="utf-8") as f:
            if not re.search(r"export\s+component\s+\w+\s+inherits\s+Window", f.read()):
                continue  # helper/library file, imported by others
        header = os.path.join(OUT_DIR, os.path.splitext(os.path.basename(src))[0] + ".h")
        if not needs_rebuild(header, ui_files):
            continue

        compiler = compiler or ensure_compiler(slint_version())
        log("Compiling %s -> src/generated/%s" % (os.path.basename(src), os.path.basename(header)))
        cmd = [compiler, src] + SLINT_ARGS + ["-o", header]
        if env.Execute(" ".join('"%s"' % c for c in cmd)) != 0:  # noqa: F821
            if os.path.isfile(header):
                os.remove(header)
            sys.exit("[slint] Failed to compile %s (see errors above)" % os.path.basename(src))


compile_ui()
