#pragma once
#define LGFX_USE_V1
#include <LovyanGFX.hpp>

class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_ST7735S _panel;
  lgfx::Bus_SPI       _bus;
  lgfx::Light_PWM     _light;

public:
  LGFX() {
    { // SPI bus
      auto cfg = _bus.config();
      cfg.spi_host    = SPI2_HOST;   // On ESP32-S3 use SPI2_HOST or SPI3_HOST
      cfg.spi_mode    = 0;
      cfg.freq_write  = 20000000;    // Start conservative, raise later
      cfg.freq_read   = 0;           // No MISO connected
      cfg.spi_3wire   = true;
      cfg.use_lock    = true;
      cfg.dma_channel = SPI_DMA_CH_AUTO;
      cfg.pin_sclk    = 12;
      cfg.pin_mosi    = 11;
      cfg.pin_miso    = -1;
      cfg.pin_dc      = 9;
      _bus.config(cfg);
      _panel.setBus(&_bus);
    }

    { // Panel
      auto cfg = _panel.config();
      cfg.pin_cs           = 10;
      cfg.pin_rst          = 8;
      cfg.pin_busy         = -1;
      cfg.panel_width      = 128;
      cfg.panel_height     = 160;
      cfg.memory_width     = 132;    // ST7735S RAM is 132x162
      cfg.memory_height    = 162;
      cfg.offset_x         = 0;      // Tune in Step 5
      cfg.offset_y         = 0;
      cfg.offset_rotation  = 0;
      cfg.readable         = false;
      cfg.invert           = false;  // Toggle if colors look inverted
      cfg.rgb_order        = false;  // Toggle if red/blue are swapped
      cfg.dlen_16bit       = false;
      cfg.bus_shared       = false;
      _panel.config(cfg);
    }

    { // Backlight (optional)
      auto cfg = _light.config();
      cfg.pin_bl      = 7;
      cfg.invert      = false;
      cfg.freq        = 44100;
      cfg.pwm_channel = 7;
      _light.config(cfg);
      _panel.setLight(&_light);
    }

    setPanel(&_panel);
  }
};