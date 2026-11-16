# slint_link.py — PlatformIO post-configure script
#
# Slint's CMake package downloads its prebuilt library (libslint_cpp.a) into
# the build folder. PlatformIO treats every archive inside the build folder
# as one it builds itself and drops it from the final link, which causes
# "undefined reference to slint_property_init / RectangleVTable / ..." errors.
# This script adds the library back to the link explicitly.

Import("env")  # noqa: F821  (provided by PlatformIO)

import glob
import os
import re
import sys

BUILD_DIR = env.subst("$BUILD_DIR")  # noqa: F821
MANIFEST = os.path.join(env.subst("$PROJECT_DIR"), "src", "idf_component.yml")  # noqa: F821


def slint_version():
    with open(MANIFEST, encoding="utf-8") as f:
        m = re.search(r"slint/slint:\s*[\"']?\s*(?:==)?\s*(\d+\.\d+\.\d+)", f.read())
    return m.group(1) if m else "*"


pattern = os.path.join(BUILD_DIR, "slint-prebuilt", "Slint-cpp-%s-*" % slint_version(),
                       "lib", "libslint_cpp.a")
found = sorted(glob.glob(pattern), key=os.path.getmtime)

if not found:
    sys.exit("[slint] libslint_cpp.a not found (looked for %s).\n"
             "        Delete the .pio folder and build again." % pattern)

lib_dir = os.path.dirname(found[-1])
print("[slint] Linking " + os.path.relpath(found[-1], BUILD_DIR))
env.Append(LIBPATH=[lib_dir], LIBS=["slint_cpp"])  # noqa: F821
