# Jarvis voice assistant (ESP32-S3 + ESP-IDF + Slint)

A voice assistant on an ESP32-S3 N16R8 with a 1.8" ST7735S screen:

1. It listens for the wake word **"Jarvis"** (ESP-SR WakeNet) and plays a greeting.
2. It records your command and transcribes it with **Groq Whisper**.
3. It publishes the transcript over **MQTT** (HiveMQ Cloud, TLS).
4. It reads out reminders and replies from the backend with **Groq TTS** (Orpheus, voice "diana").

Every step is shown on a small **Slint** UI.

For design decisions, current status and gotchas, see [HANDOFF.md](HANDOFF.md).

## Hardware

| Part | Pins |
|---|---|
| ST7735S TFT (SPI) | SCLK 12, MOSI 11, DC 9, CS 10, RST 8, BL 7 |
| INMP441 mic (I2S0) | SD 4, SCK 5, WS 6, L/R → GND |
| MAX98357A amp (I2S1) | BCLK 16, LRC 17, DIN 15, VIN 5 V |
| BOOT button | GPIO 0: hold to record, press to stop a reminder, press on Home to dismiss the reminder card |

The console is the **native USB** port (USB-Serial/JTAG).

## Setup

1. Create `src/secrets.h` (it's git-ignored):
   ```c
   #define SEED_WIFI_SSID "..."
   #define SEED_WIFI_PASS "..."
   #define SEED_GROQ_KEY  "gsk_..."
   #define SEED_MQTT_HOST "<cluster>.s1.eu.hivemq.cloud"   // host only
   #define SEED_MQTT_USER "..."
   #define SEED_MQTT_PASS "..."
   ```
2. Build and flash the firmware:
   ```
   pio run -t upload
   ```
   The first build downloads ESP-SR, Slint and LovyanGFX.
3. Flash the wake-word model once. `pio run -t upload` doesn't do this.
   ```
   pio pkg exec -p tool-esptoolpy -- esptool --chip esp32s3 --port COM3 write-flash 0x610000 models\srmodels.bin
   ```
4. Watch the log with `pio device monitor`. You should see `[sr] wake model: wn9_jarvis_tts` and `[mqtt] connected`.

## MQTT topics

`<id>` is the last 3 bytes of the board's MAC address. It's printed at boot.

| Topic | Direction | Payload |
|---|---|---|
| `jarvis/<id>/transcript` | device → backend | `{"device","id","text","audio_ms"}` (QoS 1) |
| `jarvis/<id>/status` | device → backend | retained `online` / `offline` (Last Will) |
| `jarvis/<id>/reminder` | backend → device | `{"text","id"}` or plain text, spoken as "Reminder" |
| `jarvis/<id>/response` | backend → device | same, spoken as "Jarvis" |

## Serial commands

| Command | Does |
|---|---|
| `DUMP` | Sends the last recording as WAV + CRC32. Use `save_audio.py` on the PC to receive it; copy the script in from the Arduino project. |
| `TONE` | Speaker check: shows how the speaker pins are routed and plays a 1 kHz beep |
| `HEAP` | Free internal, DMA and PSRAM memory |
| `SET SIL <ms>` | How long a silence ends the command (200–10000) |
| `SET WAKE <x>` | Wake-word threshold (0.4–0.9999) |
| `SET GAIN <x>` | Mic gain (0.5–32) |

## How the build works

PlatformIO uses ESP-IDF's CMake only to configure the project, so two scripts take the place of Slint's own CMake steps:

- `slint_build.py` (runs before the build) downloads the matching `slint-compiler` into `.slint-compiler/`. It compiles `src/ui/*.slint` into `src/generated/*.h` whenever a `.slint` file changes.
- `slint_link.py` (runs after configure) adds `libslint_cpp.a` back to the link. PlatformIO would otherwise drop it, because it sits in the build folder.

To upgrade Slint, change only the pinned `==` version in `src/idf_component.yml`.
