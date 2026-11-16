# Main application component.
# No REQUIRES list on purpose: the main component then sees every component
# (Slint, ESP-SR, LovyanGFX, Wi-Fi, HTTP client, I2S...).
# The .slint file is compiled by slint_build.py (see platformio.ini), because
# PlatformIO doesn't run CMake custom steps like slint_target_sources().

idf_component_register(
    SRCS "main.cpp"
    INCLUDE_DIRS "."
)
