# Main application component.
# No REQUIRES list on purpose: the main component then sees every component
# (Slint, ESP-SR, LovyanGFX, Wi-Fi, HTTP client, I2S...).
# The .slint file is compiled by slint_build.py (see platformio.ini), because
# PlatformIO doesn't run CMake custom steps like slint_target_sources().

idf_component_register(
    SRCS "main.cpp"
    INCLUDE_DIRS "."
)

# Add the esp-dl Conv kernels the wn10_heynova wake model needs that ESP-SR's
# own kernel list leaves out (fixes "Conv: no Conv kernel for packed key 0x0202").
idf_build_get_property(build_components BUILD_COMPONENTS)
if("espressif__esp-dl" IN_LIST build_components)
    idf_component_get_property(espdl_dir espressif__esp-dl COMPONENT_DIR)
elseif("esp-dl" IN_LIST build_components)
    idf_component_get_property(espdl_dir esp-dl COMPONENT_DIR)
endif()
if(espdl_dir)
    include(${espdl_dir}/cmake/compile_register.cmake)
    esp_dl_compile_add_yml(${COMPONENT_DIR}/nova-wn10-req.yml)
endif()
