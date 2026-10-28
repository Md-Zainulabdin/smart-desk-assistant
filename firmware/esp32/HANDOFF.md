# Jarvis Voice Assistant: Handoff Summary

Context for continuing this project in Claude Code. Put this file in the project root.

---

## 1. Overall goal

A voice assistant on an **ESP32-S3 N16R8** (16 MB flash, 8 MB octal PSRAM):

1. Listen continuously for the wake word **"Jarvis"** (ESP-SR WakeNet `wn9_jarvis_tts`).
2. Play a short greeting through the speaker, then record the spoken command into PSRAM. Recording ends on silence.
3. Send the WAV to **Groq Whisper** (`whisper-large-v3-turbo`) and get the transcript back.
4. Show every state on a **1.8" 128×160 ST7735S TFT** with a **Slint** UI.
4b. Publish the transcript over **MQTT (HiveMQ Cloud, `mqtts://…:8883`)** to a FastAPI backend.
   Topics: `jarvis/<id>/transcript` (QoS 1, JSON `{"device","id","text","audio_ms"}`) and
   `jarvis/<id>/status` (retained `online`/`offline`, Last Will). `<id>` = last 3 MAC bytes.
   Uses the built-in `esp-mqtt` + cJSON, the TLS CA bundle, and a non-blocking `enqueue`. Credentials are `SEED_MQTT_HOST/USER/PASS` in `secrets.h`.
4c. **Subscribes** to `jarvis/<id>/reminder` and `jarvis/<id>/response` (QoS 1, `{"text","id"}` or plain text, duplicates dropped by `id`).
   The text is spoken with **Groq TTS** (`canopylabs/orpheus-v1-english`, voice `diana`, same Groq key):
   - The text is split into ≤200-char pieces (the Orpheus limit), cut at sentence ends.
   - `ttsFetchTask` (core 0, prio 3) streams each WAV's PCM into a **1 MB PSRAM stream buffer**.
   - `ttsPlayTask` (core 0, prio 4) starts after 500 ms is buffered, re-buffers on an underrun, and switches the speaker's I2S clock to the WAV's sample rate (the greeting switches it back to 16 kHz).
   - The new `ST_SPEAKING` state is claimed by compare-exchange (`state` is now `std::atomic<int>`), so a reminder waits for any command session to finish.
   - Wake is ignored while speaking (no AEC yet), and BOOT stops playback.
5. Later (not built yet): forward the text to a Python backend for intent parsing, play backend audio replies, echo cancellation (AEC), barge-in, and a local "Stop" word.

The audio pipeline was first written and tested with the **Arduino** framework. It has been **ported to native ESP-IDF** so it can share one project with Slint.

---

## 2. Hardware and pins

| Part | Pins |
|---|---|
| ST7735S TFT (SPI2, LovyanGFX) | SCLK 12, MOSI 11, DC 9, CS 10, RST 8, BL 7 (PWM ch 7), 3-wire, 20 MHz |
| INMP441 mic (I2S0 RX) | SD 4, SCK 5, WS 6, L/R → GND (left slot) |
| MAX98357A amp (I2S1 TX) | BCLK 16, LRC 17, DIN 15 |
| BOOT button | GPIO 0, active low (hold to record) |
| Reserved | GPIO 35/36/37 (octal PSRAM) |

PlatformIO board id: `4d_systems_esp32s3_gen4_r8n16`. Console is the **native USB** port (USB-Serial/JTAG).

---

## 3. Architecture decisions

### Build and toolchain
- **PlatformIO + ESP-IDF 5.5** (`framework = espidf`, `platform_packages = platformio/framework-espidf @ ~3.50505.0`). The log confirms IDF 5.5.5 is running.
- **Pure ESP-IDF, no Arduino.** The Arduino code was ported API by API:
  - `ESP_I2S` → `driver/i2s_std.h`
  - `WiFi` → `esp_wifi`
  - `WiFiClientSecure` → `esp_http_client` (TLS is verified with `esp_crt_bundle_attach` instead of `setInsecure()`)
  - `Serial` → stdout/stdin on USB-Serial/JTAG
- **Components via `src/idf_component.yml`:**
  - `slint/slint: "==1.18.1"` (exact pin, prebuilt binaries, no Rust needed)
  - `espressif/esp-sr: "^2.0.0"`
  - LovyanGFX from git, tag 1.2.33

### Two PlatformIO workarounds (both required)
PlatformIO uses ESP-IDF's CMake only to configure the build, then compiles with SCons. This causes two problems:
1. **`slint_target_sources()` never runs**, so the `.slint` file is never compiled into a header.
   → `slint_build.py` (`extra_scripts = pre:`) downloads the matching `slint-compiler` into `.slint-compiler/<ver>/` and compiles `src/ui/*.slint` into `src/generated/app-window.h`. It reads the version from `idf_component.yml` and only rebuilds when the `.slint` file changes. Arguments used: `-f cpp --embed-resources=embed-for-software-renderer --style fluent`.
2. **`libslint_cpp.a` gets dropped at link time**, because it is downloaded into `.pio/build/.../slint-prebuilt/` and PlatformIO treats archives in the build folder as its own build outputs.
   → `slint_link.py` (`extra_scripts = post:`) adds that lib dir and `slint_cpp` to `LIBPATH`/`LIBS`.
- `src/CMakeLists.txt` has **no `REQUIRES`**, so the main component can see every component. `main.cpp` includes `"generated/app-window.h"`.

### Display and UI
- **Slint software renderer with a custom platform** (`src/slint_lgfx_platform.hpp`), not `slint_esp_init()`, because the panel is driven by LovyanGFX rather than an `esp_lcd` handle.
  - Full RGB565 framebuffer, 40 KB internal RAM. `ReusedBuffer` mode pushes only the changed full-width row band via `pushImage` as `lgfx::rgb565_t`, and LovyanGFX does the byte swap.
  - Event loop: about **30 fps** cap while animating (`vTaskDelay(33 ms)`), otherwise it sleeps on `ulTaskNotifyTake` until the next Slint timer or a posted task.
  - `run_in_event_loop` is implemented with a mutex-protected queue plus task notify, so `slint::invoke_from_event_loop()` is safe from any FreeRTOS task.
- **UI (`src/ui/app-window.slint`)**: custom elements only (the std-widgets are too big for 128×160). A header with a Wi-Fi dot, an animated orb, a status label and wrapped transcript text.
  - Inputs: `assistant-state` (enum: idle, listening, thinking, speaking, error), `status-text`, `transcript`, `wifi-connected`, and `level` (0..1; the orb pulses with the mic level while listening).
- **The Slint event loop runs in `app_main`** on core 0 at low priority. Setup runs in a separate `setupTask`, so the screen is live during boot.
- C++ helper: `ui(AssistantState, status, text, revertMs)`. It is thread-safe. A non-zero `revertMs` returns the screen to Standby via `slint::Timer::single_shot`, guarded by a `uiGen` counter so newer screens aren't overwritten.

### State machine → screens
| Firmware state | Screen |
|---|---|
| boot | "Starting" / "Loading wake word..." |
| `ST_IDLE` | Home (`src/ui/home.slint`): SNTP clock + date (`CLOCK_TZ`), latest reminder card or "Say Jarvis" hint |
| `ST_GREETING` | Speaking, green bars, "Jarvis" + the greeting line |
| `ST_LISTEN` | Listening, blue orb pulsing with the mic level |
| `ST_UPLOAD` | Thinking, purple orb + dots, "Transcribing" |
| success | Idle, "You said" + transcript, 8 s |
| cancelled | Idle, "Didn't catch that", 3 s |
| errors | Error, red orb + reason (no Wi-Fi / network / 429 / HTTP code), 4 s |
| setup failure | Error + reason (e.g. "No wake model"), stops |

### Audio pipeline (ported from Arduino, logic unchanged)
- **Tasks:**

  | Task | Core | Priority | Stack | Job |
  |---|---|---|---|---|
  | `feedTask` | 0 | 5 | 6 KB | I2S → HPF + gain → `afe->feed` |
  | `fetchTask` | 1 | 5 | 8 KB | `afe->fetch_with_delay` → wake/VAD → state machine |
  | `uploadTask` | 0 | 3 | 16 KB, **PSRAM** | Groq Whisper HTTPS upload |
  | `speakerTask` | 0 | 3 | 4 KB | Greeting playback |
  | `ttsFetchTask` | 0 | 3 | 12 KB, **PSRAM** | Groq Orpheus requests → PCM into the 1 MB PSRAM stream buffer |
  | `ttsPlayTask` | 0 | 4 | 4 KB | Stream buffer → speaker (500 ms pre-buffer) |
  | `consoleTask` | 1 | 2 | 4 KB | Serial commands |
  | `buttonTask` | 1 | 2 | 2 KB | BOOT button |
  | `mqtt_task` | — | — | esp-mqtt default | HiveMQ TLS connection, created by `esp_mqtt_client_start` |

  The two network tasks keep their stacks in PSRAM (`xTaskCreatePinnedToCoreWithCaps`) to save internal RAM. They do no flash writes, so that's safe.

- **AFE settings:** `afe_config_init("MN", models, AFE_TYPE_SR, AFE_MODE_HIGH_PERF)`, `aec_init=false`, `vad_min_noise_ms=100`, `AFE_MEMORY_ALLOC_MORE_PSRAM`.
- **Mic sample handling:** I2S std Philips, 32-bit, mono left slot. Each sample is `raw32 >> 16` (assumed equivalent to Arduino's `I2S_RX_TRANSFORM_32_TO_16`; **not yet verified on hardware**).
- **Recording:** PSRAM buffer of 44-byte WAV header + 30 s PCM (960,044 bytes). The header is written at the end with the real lengths.
- **Settings:**

  | Setting | Value |
  |---|---|
  | `SILENCE_END_MS` | 1200 |
  | `NO_SPEECH_TIMEOUT_MS` | 5000 |
  | `MAX_CMD_SECONDS` | 30 |
  | `MIN_SPEECH_MS` | 250 |
  | `WAKE_GUARD_MS` | 300 |
  | `MIC_GAIN` | 2.0 |
  | `HP_CUTOFF_HZ` | 120 |
  | `MANUAL_MIN_PEAK` | 300 |

- **Serial commands:**
  - `DUMP`: sends the last recording as WAV + CRC32, read on the PC by `save_audio.py`. The script is still in the Arduino project; copy it to the project root.
  - `TONE`: shows how the speaker pins are routed, then plays a 1 kHz test beep.
  - `HEAP`: free internal, DMA and PSRAM memory.
  - `SET SIL <ms>`, `SET WAKE <x>`, `SET GAIN <x>`.
- **Wi-Fi** connects in the background and reconnects automatically. Audio starts without waiting for it, and an upload without Wi-Fi shows an error.
- **Fixed during the port:** a stale `hasRecording` after a cancelled wake (it is now cleared on wake).

### Flash layout (`partitions.csv`)
| Name | Offset | Size | Notes |
|---|---|---|---|
| nvs | 0x9000 | 0x6000 | |
| phy_init | 0xf000 | 0x1000 | |
| factory | 0x10000 | 0x600000 (6 MB) | grew from 3 MB for Slint + ESP-SR + TLS + greeting PCM |
| **model** | **0x610000** | 0x500000 (5 MB) | label must stay `model`. **Moved from 0x310000** |
| storage | 0xB10000 | 0x4F0000 | spare |

### Key `sdkconfig.defaults` choices
- Octal PSRAM at 80 MHz, malloc from PSRAM, Wi-Fi/LWIP and mbedTLS buffers in PSRAM.
- 64 KB data cache with 64 B lines (recommended by ESP-SR).
- `CONFIG_MODEL_IN_FLASH`, `CONFIG_SR_WN_WN9_JARVIS_TTS`, MultiNet set to none.
- Certificate bundle enabled.
- `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y` with LF line endings (so `DUMP` binary data isn't altered).
- Main task stack 16 KB, `FREERTOS_HZ=1000`, `-O2`.
- **Internal RAM headroom.** At 9 KB free, TLS uploads, sockets and Wi-Fi frames were failing. These settings fix that:
  - Hardware AES off (`# CONFIG_MBEDTLS_HARDWARE_AES is not set`). The AES DMA engine copied every TLS record through internal RAM.
  - `ESP_WIFI_IRAM_OPT` / `ESP_WIFI_RX_IRAM_OPT` off (about 25 KB back).
  - Wi-Fi static RX buffers 16 → 10.
  - `SPIRAM_ALLOW_STACK_EXTERNAL_MEMORY=y`, for the PSRAM task stacks.

---

## 4. Files

```
<project root>/
├─ platformio.ini          env 4d_systems_esp32s3_gen4_r8n16, espidf, extra_scripts pre/post
├─ CMakeLists.txt          standard IDF project file (project name jarvis-slint-ui)
├─ sdkconfig.defaults      see above (delete sdkconfig.<env> after changing it)
├─ partitions.csv          see above
├─ slint_build.py          .slint → src/generated/*.h
├─ slint_link.py           links libslint_cpp.a
├─ models/
│  ├─ wn9_jarvis_tts/      wn9_data, wn9_index, _MODEL_INFO_
│  └─ srmodels.bin         packed model (pack_model.py writes into the -m folder)
└─ src/
   ├─ CMakeLists.txt       idf_component_register(SRCS "main.cpp" INCLUDE_DIRS ".")
   ├─ idf_component.yml    slint ==1.18.1, esp-sr ^2.0.0, LovyanGFX 1.2.33
   ├─ main.cpp             whole firmware (UI helpers, I2S, Wi-Fi, Groq STT/TTS, MQTT, AFE tasks, console)
   ├─ slint_lgfx_platform.hpp  Slint platform + window adapter on LovyanGFX
   ├─ LGFX_ST7735S.hpp     display config (offsets/invert/rgb_order may need tuning); defines LGFX_USE_V1
   ├─ secrets.h            SEED_WIFI_SSID/PASS, SEED_GROQ_KEY, SEED_MQTT_HOST/USER/PASS (git-ignored)
   ├─ welcoming_audio.h    GREETING_HELP_SAMPLES, GREETING_ASSIST_SAMPLES (int16, no PROGMEM/Arduino.h)
   ├─ generated/app-window.h   auto-generated, don't edit
   └─ ui/app-window.slint  the UI
```

Git-ignored: `.pio/`, `.slint-compiler/`, `src/generated/`, `managed_components/`, the generated `sdkconfig.4d_systems_esp32s3_gen4_r8n16`, `src/secrets.h`, `.vscode`.
Committed on purpose: `sdkconfig.defaults` (the real config) and `dependencies.lock` (pins the component versions).

---

## 5. Current status

| Item | Status |
|---|---|
| Slint demo UI (standalone) | Host-tested via stubs; firmware build linked after the two scripts |
| Integrated firmware | **Builds, flashes and boots** on the board (IDF 5.5.5) |
| Boot log | mic started, speaker started, PSRAM 7204 KB free, record buffer allocated |
| ESP-SR model | **Fixed (2026-10-19):** model flashed to 0x610000, AFE loads `wn9_jarvis_tts`; Wi-Fi connects |
| Wake word | Works: "Jarvis" detected, greeting started, command recorded (peak 18350) |
| MQTT | Works: TLS to HiveMQ, transcript delivered, reminder/response messages received |
| Groq STT / TTS | Failed with internal RAM exhaustion (`esp-aes: Failed to allocate`, `Failed to create socket`, 9 KB free). RAM fixes are built (see §3); **not yet flashed/verified** |
| Speaker | **Silent** for both greeting and TTS, although I2S writes succeed and the greeting data is loud. Suspect wiring/amp. `TONE` added to check |
| Not yet verified on hardware | mic `>>16` scaling, `DUMP` over USB-Serial/JTAG, UI on the real panel (offsets/colors) |

---

## 6. Immediate next steps

1. **Flash the RAM-fix build** (`pio run -t upload`, Serial Monitor closed). Check `[heap] ready` and `HEAP`; aim for more than 25 KB internal free.
2. **Speaker:** run `TONE`.
   - No beep: check the MAX98357A wiring: VIN 5 V, common GND, SD not tied to GND, BCLK→16, LRC→17, DIN→15.
   - Beep: the problem is in the audio path.
3. **End-to-end:** "Jarvis" → command → transcript on `jarvis/<id>/transcript`. Then publish to `jarvis/<id>/reminder` and confirm it's spoken.
4. **If mic audio is wrong** (`peak 0`, too quiet, distorted): copy `save_audio.py` from the Arduino project, run `DUMP` and listen. Adjust the `>>16` shift or `MIC_GAIN` in `feedTask`.
5. **Tune the display** in `LGFX_ST7735S.hpp` (`offset_x/y`, `invert`, `rgb_order`, maybe raise `freq_write` to 27–40 MHz).
6. **Model partition** (only after erasing flash or changing `partitions.csv`):
   ```
   pio pkg exec -p tool-esptoolpy -- esptool --chip esp32s3 --port COM3 write-flash 0x610000 models\srmodels.bin
   ```
   To repack: `python managed_components\espressif__esp-sr\model\pack_model.py -m models -o srmodels.bin`. The output lands in `models\`.
7. **Later work:**
   - **Context layer (planned, not built):** LD2410B radar presence + BLE tags for identity in a shared home. Plan: `~/.claude/plans/uptill-now-i-federated-chipmunk.md`.
   - **Python backend (FastAPI):** consumes `transcript`, publishes `reminder`/`response`.
   - **Barge-in and AEC:** switch the AFE format from `"MN"` to `"MR"` with the playback reference and `aec_init=true`.
   - Optional local "Stop" word.

## 7. Gotchas

- After any `sdkconfig.defaults` or dependency change, delete `sdkconfig.<env>`, `.pio/`, `dependencies.lock` and `managed_components/` before rebuilding. Commit the regenerated `dependencies.lock`.
- If CMake re-runs (after an `sdkconfig` change or a new file), the component manager can fail, because VS Code locks `managed_components/*` or the git checkout fails.
  - If a component folder is left empty, delete it and rebuild.
  - If you see `Couldn't find target config …ldgen…`, delete `.pio/build/<env>/CMakeCache.txt` and `.pio/build/<env>/.cmake`, then rebuild.
- `pio run -t upload` does **not** flash the model partition. ESP-SR's own `srmodels_bin` CMake target doesn't run under PlatformIO.
- Never include `Arduino.h` anywhere. `src/` must contain only `main.cpp` as a source file (no leftover `Code.cpp`, `.ino` or `main.c`).
- Upgrading Slint: change only the version in `src/idf_component.yml` and keep `==`.
- Slint licence: GPLv3 for an open-source personal project is free. A commercial embedded product needs a paid licence.
