// =============================================================================
//  Jarvis voice assistant - ESP32-S3 N16R8 (ESP-IDF + Slint UI)
//  INMP441 -> ESP-SR AFE ("Jarvis") -> PSRAM WAV -> Groq Whisper, ST7735S UI
//  Transcript -> MQTT (HiveMQ Cloud, TLS) -> backend
// =============================================================================
//  Port of the Arduino version. Same state machine, same settings, same serial
//  commands. Arduino APIs replaced by ESP-IDF ones:
//    ESP_I2S         -> driver/i2s_std.h
//    WiFi.h          -> esp_wifi
//    WiFiClientSecure-> esp_http_client (TLS, certificate checked via the
//                       built-in CA bundle instead of setInsecure())
//    Serial          -> USB Serial/JTAG console (printf / read)
//
//  States -> screen:
//    IDLE      Home            clock + date, latest reminder card (or "Say Jarvis")
//    GREETING  "Jarvis"        green bars, greeting text
//    LISTEN    "Listening"     blue orb, pulses with your voice
//    UPLOAD    "Transcribing"  purple orb + dots
//    result    "You said"      transcript (8 s), then back to Home
//    errors    red orb         message (4 s), then back to Home
//
//  Serial: DUMP | TONE | HEAP | SET SIL <ms> | SET WAKE <0.4-0.9999> | SET GAIN <x>
//  BOOT button: hold to record (manual session, ends on release);
//               press while a reminder is speaking to stop it;
//               press on Home while a reminder card shows to dismiss it.
//
//  MQTT topics (<id> = last 3 MAC bytes, e.g. cee330):
//    jarvis/<id>/transcript  QoS 1  {"device","id","text","audio_ms"}
//    jarvis/<id>/status      retained "online" / "offline" (Last Will)
//    jarvis/<id>/reminder    subscribed: {"text","id"} or plain text -> spoken
//    jarvis/<id>/response    subscribed: same, for backend replies
//
//  Speech out: Groq Orpheus TTS (voice "diana", <=200 chars per request) ->
//  WAV -> 1 MB PSRAM stream buffer -> speaker. Playback starts after
//  TTS_PREBUFFER_MS is buffered; BOOT stops it.
//
//  Needs in src/: secrets.h (SEED_WIFI_SSID, SEED_WIFI_PASS, SEED_GROQ_KEY,
//                            SEED_MQTT_HOST, SEED_MQTT_USER, SEED_MQTT_PASS)
//                 welcoming_audio.h (GREETING_HELP_SAMPLES, GREETING_ASSIST_SAMPLES)
//  Needs flashed: srmodels.bin (wn9_jarvis_tts) in the "model" partition.
// =============================================================================

#include <atomic>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fcntl.h>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <string>
#include <unistd.h>
#include <vector>

#include "cJSON.h"
#include "driver/gpio.h"
#include "driver/i2s_std.h"
#include "esp_crt_bundle.h"
#include "esp_event.h"
#include "esp_heap_caps.h"
#include "esp_http_client.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "mqtt_client.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/stream_buffer.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include "esp_afe_config.h"
#include "esp_afe_sr_models.h"
#include "model_path.h"

#include "secrets.h"
#include "welcoming_audio.h" // embedded greeting PCM in application flash

#include "LGFX_ST7735S.hpp"
#include "slint_lgfx_platform.hpp"
#include "generated/app-window.h"

// ------------------------------- SETTINGS ------------------------------------
#define SAMPLE_RATE          16000
#define SILENCE_END_MS       1200   // silence after speech that ends the command
#define NO_SPEECH_TIMEOUT_MS 5000   // cancel if nobody speaks after the wake word
#define MAX_CMD_SECONDS      30     // hard cap on one command (sizes the PSRAM buffer)
#define MIN_SPEECH_MS        250    // less speech than this = noise, not a command
#define WAKE_GUARD_MS        300    // ignore VAD right after the wake word
#define WAKE_THRESHOLD       0.0f   // 0 = model default, else 0.4..0.9999
#define HP_CUTOFF_HZ         120
#define MIC_GAIN             2.0f
#define MANUAL_MIN_PEAK      300    // BOOT sessions: below this peak = silence

#define PIN_BUTTON   GPIO_NUM_0
#define PIN_MIC_SD   GPIO_NUM_4
#define PIN_MIC_SCK  GPIO_NUM_5
#define PIN_MIC_WS   GPIO_NUM_6
#define PIN_SPK_BCLK GPIO_NUM_16
#define PIN_SPK_LRC  GPIO_NUM_17
#define PIN_SPK_DIN  GPIO_NUM_15

#define GROQ_URL  "https://api.groq.com/openai/v1/audio/transcriptions"
#define STT_MODEL "whisper-large-v3-turbo"
#define BOUNDARY  "----speechtotext"

#define MQTT_URI        "mqtts://" SEED_MQTT_HOST ":8883"
#define MQTT_TOPIC_ROOT "jarvis"
#define MQTT_MAX_TEXT   4000 // longer transcripts are cut (fits the 8 KB out buffer)

#define TTS_URL          "https://api.groq.com/openai/v1/audio/speech"
#define TTS_MODEL        "canopylabs/orpheus-v1-english"
#define TTS_VOICE        "diana"
#define TTS_MAX_CHARS    200               // Orpheus limit per request
#define TTS_MAX_MSG      2000              // longer messages are cut
#define TTS_BUF_BYTES    (1024 * 1024)     // PSRAM stream buffer, ~21 s at 24 kHz
#define TTS_PREBUFFER_MS 500               // audio piled up before playback (re)starts
#define TTS_QUEUE_LEN    8                 // messages waiting to be spoken

#define CLOCK_TZ   "PKT-5"         // POSIX TZ string: Pakistan, UTC+5
#define CLOCK_NTP  "pool.ntp.org"

#define WAV_HDR      44
#define PCM_CAPACITY ((size_t)MAX_CMD_SECONDS * SAMPLE_RATE * 2)
// -----------------------------------------------------------------------------

enum { ST_IDLE = 0, ST_LISTEN = 1, ST_UPLOAD = 2, ST_GREETING = 3, ST_SPEAKING = 4 };

static i2s_chan_handle_t micRx = nullptr;
static i2s_chan_handle_t spkTx = nullptr;
static bool speakerOk = false;

static const esp_afe_sr_iface_t *afe = nullptr;
static esp_afe_sr_data_t *afeData = nullptr;

static uint8_t *rec = nullptr; // PSRAM: [44-byte WAV header][PCM data]
static size_t recBytes = 0;
static uint32_t recPeak = 0;
static bool hasRecording = false;

// Atomic: leaving IDLE is a compare-exchange, so a wake word and an incoming
// reminder can't both claim the speaker.
static std::atomic<int> state { ST_IDLE };
static volatile uint32_t silenceEndMs = SILENCE_END_MS;
static volatile float micGain = MIC_GAIN;
static volatile float pendingWake = 0;
static volatile bool manualWake = false;
static volatile bool dumping = false;
static volatile bool wifiUp = false;
static volatile bool mqttUp = false;
static esp_mqtt_client_handle_t mqtt = nullptr;
static TaskHandle_t uploadTaskH = nullptr;
static TaskHandle_t speakerTaskH = nullptr;
static int16_t speakerStereoBuf[256 * 2];

static inline uint32_t millis() { return (uint32_t)(esp_timer_get_time() / 1000); }

// Internal RAM is the scarce one (DMA, task stacks, Slint framebuffer).
static void logHeap(const char *where)
{
    printf("[heap] %s: internal %u KB free (largest %u KB), DMA %u KB, PSRAM %u KB\n", where,
           (unsigned)(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024),
           (unsigned)(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL) / 1024),
           (unsigned)(heap_caps_get_free_size(MALLOC_CAP_DMA) / 1024),
           (unsigned)(heap_caps_get_free_size(MALLOC_CAP_SPIRAM) / 1024));
}

// ================================================================== UI =======
static LGFX tft;
static slint::ComponentWeakHandle<AppWindow> g_ui;
static std::atomic<uint32_t> uiGen { 0 }; // bumps on every screen change

static std::atomic<bool> onHome { false };    // Home screen is showing
static std::atomic<bool> cardShown { false }; // a reminder card is on Home
static uint32_t cardAtMs = 0;                 // when it arrived (event loop only)

static void showIdle();

// Thread-safe: call from any task. revertMs > 0 returns to Home later,
// unless something else changed the screen in the meantime.
static void ui(AssistantState s, const char *status, std::string text, uint32_t revertMs = 0)
{
    const uint32_t gen = ++uiGen;
    slint::invoke_from_event_loop([=, text = std::move(text)] {
        auto h = g_ui.lock();
        if (!h) return;
        onHome = s == AssistantState::Home;
        (*h)->set_assistant_state(s);
        (*h)->set_status_text(status);
        (*h)->set_transcript(slint::SharedString(text));
        (*h)->set_level(0);
        if (revertMs) {
            slint::Timer::single_shot(std::chrono::milliseconds(revertMs), [gen] {
                if (uiGen == gen && state == ST_IDLE) showIdle();
            });
        }
    });
}

static void showIdle() { ui(AssistantState::Home, "", ""); }

// Thread-safe. Puts text on the Home reminder card; empty text removes it.
static void uiReminder(std::string text)
{
    cardShown = !text.empty();
    slint::invoke_from_event_loop([text = std::move(text)] {
        cardAtMs = millis();
        if (auto h = g_ui.lock()) {
            (*h)->set_reminder_text(slint::SharedString(text));
            (*h)->set_reminder_ago("now");
        }
    });
}

// Runs every second in the Slint event loop: clock, date, card age.
static void clockTick()
{
    auto h = g_ui.lock();
    if (!h) return;

    char t[8] = "--:--", d[32] = "Waiting for Wi-Fi";
    const time_t now = time(nullptr);
    if (now > 1700000000) { // SNTP has synced (any date after Nov 2023)
        struct tm tm;
        localtime_r(&now, &tm);
        char wd[12], mon[12];
        strftime(t, sizeof t, "%H:%M", &tm);
        strftime(wd, sizeof wd, "%A", &tm);
        strftime(mon, sizeof mon, "%B", &tm);
        snprintf(d, sizeof d, "%s %d %s", wd, tm.tm_mday, mon); // "Saturday 25 October"
    } else if (wifiUp) {
        strcpy(d, "Syncing time...");
    }
    (*h)->set_time_text(t);
    (*h)->set_date_text(d);

    if (cardShown) {
        const uint32_t min = (millis() - cardAtMs) / 60000;
        char a[16] = "now";
        if (min >= 60)    snprintf(a, sizeof a, "%uh ago", (unsigned)(min / 60));
        else if (min > 0) snprintf(a, sizeof a, "%um ago", (unsigned)min);
        (*h)->set_reminder_ago(a);
    }
}

static void uiLevel(float v)
{
    slint::invoke_from_event_loop([v] {
        if (auto h = g_ui.lock()) (*h)->set_level(v);
    });
}

static void uiWifi(bool up)
{
    slint::invoke_from_event_loop([up] {
        if (auto h = g_ui.lock()) (*h)->set_wifi_connected(up);
    });
}

// ============================================================= MIC + SPEAKER ==
static bool micStart()
{
    i2s_chan_config_t cc = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    i2s_std_config_t sc = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = { .mclk = I2S_GPIO_UNUSED, .bclk = PIN_MIC_SCK, .ws = PIN_MIC_WS,
                      .dout = I2S_GPIO_UNUSED, .din = PIN_MIC_SD,
                      .invert_flags = { .mclk_inv = false, .bclk_inv = false, .ws_inv = false } },
    };
    sc.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT; // L/R pin tied to GND
    const bool micOk = i2s_new_channel(&cc, nullptr, &micRx) == ESP_OK
         && i2s_channel_init_std_mode(micRx, &sc) == ESP_OK
         && i2s_channel_enable(micRx) == ESP_OK;
    printf("[mic] SD=%d SCK=%d WS=%d -> %s\n", PIN_MIC_SD, PIN_MIC_SCK, PIN_MIC_WS,
           micOk ? "started" : "I2S INIT FAILED");
    return micOk;
}

// MAX98357A: stereo TX, mono PCM duplicated to both slots.
static bool speakerStart()
{
    i2s_chan_config_t cc = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1, I2S_ROLE_MASTER);
    cc.auto_clear = true; // output silence (not stale DMA data) when idle
    i2s_std_config_t sc = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = { .mclk = I2S_GPIO_UNUSED, .bclk = PIN_SPK_BCLK, .ws = PIN_SPK_LRC,
                      .dout = PIN_SPK_DIN, .din = I2S_GPIO_UNUSED,
                      .invert_flags = { .mclk_inv = false, .bclk_inv = false, .ws_inv = false } },
    };
    speakerOk = i2s_new_channel(&cc, &spkTx, nullptr) == ESP_OK
             && i2s_channel_init_std_mode(spkTx, &sc) == ESP_OK
             && i2s_channel_enable(spkTx) == ESP_OK;
    printf("[speaker] BCLK=%d LRC=%d DIN=%d -> %s\n", PIN_SPK_BCLK, PIN_SPK_LRC, PIN_SPK_DIN,
           speakerOk ? "started" : "I2S INIT FAILED");
    return speakerOk;
}

// Greeting is 16 kHz, TTS uses whatever its WAV header says (Orpheus: 24 kHz).
static uint32_t spkRate = SAMPLE_RATE;
static bool speakerSetRate(uint32_t hz)
{
    if (!speakerOk || !hz) return false;
    if (hz == spkRate) return true;
    i2s_std_clk_config_t clk = I2S_STD_CLK_DEFAULT_CONFIG(hz);
    i2s_channel_disable(spkTx);
    const bool ok = i2s_channel_reconfig_std_clock(spkTx, &clk) == ESP_OK;
    i2s_channel_enable(spkTx);
    if (ok) spkRate = hz;
    else printf("[speaker] can't switch to %u Hz\n", (unsigned)hz);
    return ok;
}

static bool playPcm(const int16_t *pcm, size_t sampleCount)
{
    if (!speakerOk || !pcm || !sampleCount) return false;
    for (size_t pos = 0; pos < sampleCount;) {
        size_t frames = sampleCount - pos;
        if (frames > 256) frames = 256;
        for (size_t i = 0; i < frames; ++i)
            speakerStereoBuf[i * 2] = speakerStereoBuf[i * 2 + 1] = pcm[pos + i];
        size_t written = 0;
        if (i2s_channel_write(spkTx, speakerStereoBuf, frames * 4, &written, pdMS_TO_TICKS(1000)) != ESP_OK)
            return false;
        pos += frames;
    }
    return true;
}

static void speakerTask(void *)
{
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (state != ST_GREETING) continue;

        const bool help = (esp_random() & 1U) != 0;
        const char *line = help ? "How can I help you today?" : "How can I assist you today?";
        printf("[speaker] greeting: %s\n", line);
        ui(AssistantState::Speaking, "Jarvis", line);
        bool ok = speakerSetRate(SAMPLE_RATE) && help ? playPcm(GREETING_HELP_SAMPLES, sizeof(GREETING_HELP_SAMPLES) / sizeof(int16_t))
                       : playPcm(GREETING_ASSIST_SAMPLES, sizeof(GREETING_ASSIST_SAMPLES) / sizeof(int16_t));
        if (!ok) printf("[speaker] playback failed\n");
        vTaskDelay(pdMS_TO_TICKS(350)); // let the speaker tail and AFE frames drain

        if (state == ST_GREETING) {
            state = ST_LISTEN;
            ui(AssistantState::Listening, "Listening", "Speak now...");
            printf("[wake] greeting finished - listening for command...\n");
        }
    }
}

// Two cascaded one-pole high-pass filters (DC + rumble), used only by feedTask.
static float hpA, hpY1, hpX1, hpY2, hpX2;
static void filterReset()
{
    float rc = 1.0f / (2.0f * (float)M_PI * HP_CUTOFF_HZ);
    hpA = rc / (rc + 1.0f / SAMPLE_RATE);
    hpY1 = hpX1 = hpY2 = hpX2 = 0.0f;
}
static inline int16_t filterSample(float x)
{
    float a = hpA * (hpY1 + x - hpX1); hpX1 = x; hpY1 = a;
    float b = hpA * (hpY2 + a - hpX2); hpX2 = a; hpY2 = b;
    int32_t v = (int32_t)(b * micGain);
    return v > 32767 ? 32767 : v < -32768 ? -32768 : (int16_t)v;
}

// ============================================================== WAV HEADER ===
static void writeWavHeader(uint8_t *h, uint32_t dataBytes)
{
    const uint32_t riffSize = 36 + dataBytes, rate = SAMPLE_RATE, byteRate = rate * 2, fmtLen = 16;
    const uint16_t pcm = 1, channels = 1, blockAlign = 2, bits = 16;
    memcpy(h + 0, "RIFF", 4);       memcpy(h + 4, &riffSize, 4);
    memcpy(h + 8, "WAVEfmt ", 8);   memcpy(h + 16, &fmtLen, 4);
    memcpy(h + 20, &pcm, 2);        memcpy(h + 22, &channels, 2);
    memcpy(h + 24, &rate, 4);       memcpy(h + 28, &byteRate, 4);
    memcpy(h + 32, &blockAlign, 2); memcpy(h + 34, &bits, 2);
    memcpy(h + 36, "data", 4);      memcpy(h + 40, &dataBytes, 4);
}

// =================================================================== WIFI ====
static void wifiEvent(void *, esp_event_base_t base, int32_t id, void *)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        if (wifiUp) { printf("[wifi] disconnected, retrying\n"); uiWifi(false); }
        wifiUp = false;
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        wifi_ap_record_t ap = {};
        esp_wifi_sta_get_ap_info(&ap);
        printf("[wifi] connected, rssi %d\n", ap.rssi);
        wifiUp = true;
        uiWifi(true);
        static bool mqttStarted = false; // the client reconnects on its own after this
        if (mqtt && !mqttStarted) mqttStarted = esp_mqtt_client_start(mqtt) == ESP_OK;
    }
}

static void wifiStart()
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // Clock: SNTP keeps retrying in the background until Wi-Fi is up
    setenv("TZ", CLOCK_TZ, 1);
    tzset();
    esp_sntp_config_t sc = ESP_NETIF_SNTP_DEFAULT_CONFIG(CLOCK_NTP);
    esp_netif_sntp_init(&sc);

    esp_netif_create_default_wifi_sta();
    wifi_init_config_t ic = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&ic));
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifiEvent, nullptr);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifiEvent, nullptr);
    wifi_config_t wc = {};
    strncpy((char *)wc.sta.ssid, SEED_WIFI_SSID, sizeof(wc.sta.ssid) - 1);
    strncpy((char *)wc.sta.password, SEED_WIFI_PASS, sizeof(wc.sta.password) - 1);
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wc));
    ESP_ERROR_CHECK(esp_wifi_start());
    printf("[wifi] connecting to %s...\n", SEED_WIFI_SSID);
}

static void trimInPlace(std::string *s)
{
    while (!s->empty() && isspace((unsigned char)s->back())) s->pop_back();
    size_t i = 0;
    while (i < s->size() && isspace((unsigned char)(*s)[i])) i++;
    s->erase(0, i);
}

// =================================================================== MQTT ====
static char deviceId[8];          // last 3 MAC bytes, e.g. "cee330"
static char mqttClientId[16];     // "jarvis-cee330"
static char topicTranscript[48];  // "jarvis/cee330/transcript"
static char topicStatus[48];      // "jarvis/cee330/status"
static char topicReminder[48];    // "jarvis/cee330/reminder"  (subscribed)
static char topicResponse[48];    // "jarvis/cee330/response"  (subscribed)
static uint32_t bootId = 0, transcriptSeq = 0;

static void ttsEnqueue(const std::string &topic, const std::string &payload);

static void mqttEvent(void *, esp_event_base_t, int32_t id, void *data)
{
    auto *ev = (esp_mqtt_event_handle_t)data;
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
        printf("[mqtt] connected as %s\n", mqttClientId);
        mqttUp = true;
        esp_mqtt_client_publish(mqtt, topicStatus, "online", 0, 1, 1);
        // Clean session: subscriptions must be renewed on every connect
        esp_mqtt_client_subscribe_single(mqtt, topicReminder, 1);
        esp_mqtt_client_subscribe_single(mqtt, topicResponse, 1);
        printf("[mqtt] listening on %s, %s\n", topicReminder, topicResponse);
        break;
    case MQTT_EVENT_DATA: {
        // Messages larger than the input buffer arrive in several fragments
        static std::string inTopic, inData;
        if (ev->current_data_offset == 0) {
            inTopic.assign(ev->topic, ev->topic_len);
            inData.clear();
        }
        if (ev->total_data_len > TTS_MAX_MSG * 4) {
            if (ev->current_data_offset == 0) printf("[mqtt] %d-byte message dropped\n", ev->total_data_len);
            break;
        }
        inData.append(ev->data, ev->data_len);
        if (ev->current_data_offset + ev->data_len >= ev->total_data_len) ttsEnqueue(inTopic, inData);
        break;
    }
    case MQTT_EVENT_DISCONNECTED:
        if (mqttUp) printf("[mqtt] disconnected, retrying\n");
        mqttUp = false;
        break;
    case MQTT_EVENT_PUBLISHED:
        printf("[mqtt] delivered msg %d\n", ev->msg_id);
        break;
    case MQTT_EVENT_ERROR:
        if (ev->error_handle->error_type == MQTT_ERROR_TYPE_CONNECTION_REFUSED)
            printf("[mqtt] refused (code %d) - check SEED_MQTT_USER / SEED_MQTT_PASS\n",
                   ev->error_handle->connect_return_code);
        else if (ev->error_handle->error_type == MQTT_ERROR_TYPE_TCP_TRANSPORT)
            printf("[mqtt] transport error: tls 0x%x, errno %d\n",
                   ev->error_handle->esp_tls_last_esp_err, ev->error_handle->esp_transport_sock_errno);
        break;
    default:
        break;
    }
}

// Creates the client; wifiEvent starts it on the first IP.
static void mqttInit()
{
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(deviceId, sizeof deviceId, "%02x%02x%02x", mac[3], mac[4], mac[5]);
    snprintf(mqttClientId, sizeof mqttClientId, "jarvis-%s", deviceId);
    snprintf(topicTranscript, sizeof topicTranscript, MQTT_TOPIC_ROOT "/%s/transcript", deviceId);
    snprintf(topicStatus, sizeof topicStatus, MQTT_TOPIC_ROOT "/%s/status", deviceId);
    snprintf(topicReminder, sizeof topicReminder, MQTT_TOPIC_ROOT "/%s/reminder", deviceId);
    snprintf(topicResponse, sizeof topicResponse, MQTT_TOPIC_ROOT "/%s/response", deviceId);    bootId = esp_random();

    if (strstr(SEED_MQTT_HOST, "YOUR-")) {
        printf("[mqtt] disabled - fill in SEED_MQTT_* in secrets.h\n");
        return;
    }
    esp_mqtt_client_config_t mc = {};
    mc.broker.address.uri = MQTT_URI;
    mc.broker.verification.crt_bundle_attach = esp_crt_bundle_attach; // HiveMQ uses Let's Encrypt
    mc.credentials.client_id = mqttClientId;
    mc.credentials.username = SEED_MQTT_USER;
    mc.credentials.authentication.password = SEED_MQTT_PASS;
    mc.session.keepalive = 30;
    mc.session.last_will.topic = topicStatus;
    mc.session.last_will.msg = "offline";
    mc.session.last_will.qos = 1;
    mc.session.last_will.retain = 1;
    mc.buffer.size = 2048; // input; bigger messages are reassembled from fragments
    mc.buffer.out_size = 8192;
    mqtt = esp_mqtt_client_init(&mc);
    if (!mqtt) { printf("[mqtt] init failed\n"); return; }
    esp_mqtt_client_register_event(mqtt, MQTT_EVENT_ANY, mqttEvent, nullptr);
    printf("[mqtt] broker %s, topic %s\n", MQTT_URI, topicTranscript);
}

// Non-blocking: queued in the client's outbox and sent by its own task,
// so a broker hiccup never stalls uploadTask. QoS 1 = at least once; "id"
// lets the backend drop duplicates.
static void mqttPublishTranscript(const std::string &text, uint32_t audioMs)
{
    if (!mqtt) return;
    char msgId[24];
    snprintf(msgId, sizeof msgId, "%08x-%u", (unsigned)bootId, (unsigned)++transcriptSeq);
    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "device", deviceId);
    cJSON_AddStringToObject(j, "id", msgId);
    cJSON_AddStringToObject(j, "text", text.substr(0, MQTT_MAX_TEXT).c_str());
    cJSON_AddNumberToObject(j, "audio_ms", audioMs);
    char *payload = cJSON_PrintUnformatted(j);
    cJSON_Delete(j);
    if (!payload) { printf("[mqtt] out of memory\n"); return; }
    int msg = esp_mqtt_client_enqueue(mqtt, topicTranscript, payload, 0, 1, 0, true);
    printf("[mqtt] %s %s (msg %d)\n", mqttUp ? "sending" : "queued until reconnect,", msgId, msg);
    cJSON_free(payload);
}

// ============================================================= HTTP / GROQ ===
static bool httpWriteAll(esp_http_client_handle_t c, const uint8_t *d, size_t len)
{
    size_t off = 0;
    uint32_t last = millis();
    while (off < len) {
        size_t n = len - off;
        if (n > 4096) n = 4096;
        int w = esp_http_client_write(c, (const char *)d + off, n);
        if (w < 0) return false;
        if (w == 0) {
            if (millis() - last > 10000) return false;
            vTaskDelay(pdMS_TO_TICKS(5));
            continue;
        }
        off += w;
        last = millis();
    }
    return true;
}

// Returns HTTP status (0 = network failure). Body (transcript or error) in *text.
static int uploadToGroq(std::string *text)
{
    static const char *FORM =
        "--" BOUNDARY "\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n" STT_MODEL "\r\n"
        "--" BOUNDARY "\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\nen\r\n"
        "--" BOUNDARY "\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\ntext\r\n"
        "--" BOUNDARY "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n"
        "Content-Type: audio/wav\r\n\r\n";
    static const char *TAIL = "\r\n--" BOUNDARY "--\r\n";

    const size_t wavLen = WAV_HDR + recBytes;
    const size_t contentLen = strlen(FORM) + wavLen + strlen(TAIL);

    esp_http_client_config_t cfg = {};
    cfg.url = GROQ_URL;
    cfg.method = HTTP_METHOD_POST;
    cfg.timeout_ms = 30000;
    cfg.crt_bundle_attach = esp_crt_bundle_attach;
    cfg.buffer_size = 2048;
    cfg.buffer_size_tx = 1024;
    esp_http_client_handle_t c = esp_http_client_init(&cfg);
    if (!c) return 0;
    const std::string auth = std::string("Bearer ") + SEED_GROQ_KEY;
    esp_http_client_set_header(c, "Authorization", auth.c_str());
    esp_http_client_set_header(c, "User-Agent", "SpeechToText/1.0");
    esp_http_client_set_header(c, "Content-Type", "multipart/form-data; boundary=" BOUNDARY);

    const uint32_t t0 = millis();
    int status = 0;
    if (esp_http_client_open(c, (int)contentLen) != ESP_OK) {
        printf("[net] connect failed\n");
    } else if (!(httpWriteAll(c, (const uint8_t *)FORM, strlen(FORM))
                 && httpWriteAll(c, rec, wavLen)
                 && httpWriteAll(c, (const uint8_t *)TAIL, strlen(TAIL)))) {
        printf("[net] upload aborted\n");
    } else {
        const uint32_t sent = millis();
        printf("[net] uploaded %u bytes in %u ms\n", (unsigned)contentLen, (unsigned)(sent - t0));
        esp_http_client_fetch_headers(c); // also handles chunked replies
        status = esp_http_client_get_status_code(c);
        char buf[512];
        int n;
        while ((n = esp_http_client_read(c, buf, sizeof buf)) > 0 && text->size() < 8192) text->append(buf, n);
        printf("[stt] %u ms\n", (unsigned)(millis() - sent));
    }
    esp_http_client_close(c);
    esp_http_client_cleanup(c);

    trimInPlace(text);
    return status;
}

// ==================================================================== TTS ====
// MQTT text -> Groq Orpheus -> WAV -> PSRAM stream buffer -> speaker.
// ttsFetchTask downloads sentence-sized pieces (<= 200 chars each) while
// ttsPlayTask plays from the buffer, so the next piece arrives during playback.
// Playback starts once TTS_PREBUFFER_MS is buffered, and on an underrun it
// pauses to re-buffer instead of stuttering.
struct TtsMsg { std::string text; const char *title; };

static QueueHandle_t ttsQueue = nullptr;
static StreamBufferHandle_t ttsStream = nullptr;
static StaticStreamBuffer_t ttsStreamCtl;
static TaskHandle_t ttsFetchH = nullptr, ttsPlayH = nullptr;
static std::atomic<uint32_t> ttsRate { 0 }; // Hz from the WAV header, 0 = not known yet
static std::atomic<bool> ttsDone { false }; // producer finished the current message
static std::atomic<bool> ttsStop { false }; // BOOT pressed: abort playback

// Runs in the MQTT task. Payload: {"text":"...","id":"..."} or plain text.
static void ttsEnqueue(const std::string &topic, const std::string &payload)
{
    std::string text = payload, id;
    if (cJSON *j = cJSON_ParseWithLength(payload.data(), payload.size())) {
        if (cJSON_IsObject(j)) {
            const cJSON *t = cJSON_GetObjectItem(j, "text");
            const cJSON *i = cJSON_GetObjectItem(j, "id");
            text = cJSON_IsString(t) ? t->valuestring : "";
            if (cJSON_IsString(i)) id = i->valuestring;
        }
        cJSON_Delete(j);
    }
    trimInPlace(&text);
    if (text.empty()) { printf("[mqtt] message on %s has no text\n", topic.c_str()); return; }

    static std::string lastId; // QoS 1 may deliver the same message twice
    if (!id.empty()) {
        if (id == lastId) { printf("[mqtt] duplicate %s ignored\n", id.c_str()); return; }
        lastId = id;
    }
    if (text.size() > TTS_MAX_MSG) text.resize(TTS_MAX_MSG);

    const bool reminder = topic.size() >= 9 && topic.compare(topic.size() - 9, 9, "/reminder") == 0;
    auto *m = new TtsMsg { std::move(text), reminder ? "Reminder" : "Jarvis" };
    printf("[mqtt] %s received (%u chars)\n", m->title, (unsigned)m->text.size());
    if (!ttsQueue || xQueueSend(ttsQueue, &m, 0) != pdTRUE) {
        printf("[tts] %s, message dropped\n", ttsQueue ? "queue full" : "disabled");
        delete m;
    }
}

// Splits text into pieces of <= TTS_MAX_CHARS bytes, preferring sentence
// ends, then clause marks, then spaces. (Bytes >= characters, so the
// character limit always holds.)
static std::vector<std::string> ttsSplit(const std::string &s)
{
    std::vector<std::string> out;
    size_t i = 0;
    while (i < s.size()) {
        while (i < s.size() && isspace((unsigned char)s[i])) i++;
        if (i >= s.size()) break;
        size_t cut = s.size() - i;
        if (cut > TTS_MAX_CHARS) {
            cut = 0;
            for (const char *marks : { ".!?\n", ",;:", " " }) {
                for (size_t k = TTS_MAX_CHARS; k > TTS_MAX_CHARS / 3 && !cut; k--)
                    if (strchr(marks, s[i + k - 1])) cut = k;
                if (cut) break;
            }
            if (!cut) { // one long word: cut, but not inside a UTF-8 sequence
                cut = TTS_MAX_CHARS;
                while (cut > 1 && ((unsigned char)s[i + cut] & 0xC0) == 0x80) cut--;
            }
        }
        std::string part = s.substr(i, cut);
        trimInPlace(&part);
        if (!part.empty()) out.push_back(std::move(part));
        i += cut;
    }
    return out;
}

// Finds where the PCM starts in a (partial) WAV header and reads the sample
// rate. Returns the offset, -1 = need more bytes, -2 = unsupported format.
static long wavDataOffset(const uint8_t *h, size_t len, uint32_t *rate)
{
    if (len < 12) return -1;
    if (memcmp(h, "RIFF", 4) || memcmp(h + 8, "WAVE", 4)) return -2;
    bool fmtOk = false;
    for (size_t pos = 12; pos + 8 <= len;) {
        uint32_t sz;
        memcpy(&sz, h + pos + 4, 4);
        if (!memcmp(h + pos, "data", 4)) return fmtOk ? (long)(pos + 8) : -2; // size may be 0xFFFFFFFF when streamed
        if (!memcmp(h + pos, "fmt ", 4)) {
            if (pos + 8 + 16 > len) return -1;
            uint16_t fmt, ch, bits;
            memcpy(&fmt, h + pos + 8, 2);
            memcpy(&ch, h + pos + 10, 2);
            memcpy(rate, h + pos + 12, 4);
            memcpy(&bits, h + pos + 22, 2);
            if ((fmt != 1 && fmt != 0xFFFE) || ch != 1 || bits != 16) {
                printf("[tts] WAV format %u, %u ch, %u bit not supported\n", fmt, ch, bits);
                return -2;
            }
            fmtOk = true;
        }
        if (sz > 4096) return -2; // a non-data chunk this big isn't a header we know
        pos += 8 + sz + (sz & 1);
    }
    return -1;
}

// Waits for room so every write is whole: the buffer only ever holds
// complete 16-bit samples. Returns false if playback was stopped.
static bool ttsPush(const uint8_t *d, size_t len)
{
    while (len) {
        const size_t n = len > 2048 ? 2048 : len;
        while (xStreamBufferSpacesAvailable(ttsStream) < n) {
            if (ttsStop) return false;
            vTaskDelay(pdMS_TO_TICKS(20));
        }
        xStreamBufferSend(ttsStream, d, n, 0);
        d += n;
        len -= n;
    }
    return !ttsStop;
}

// Reads one WAV response and pushes its PCM into ttsStream.
static bool ttsReadWav(esp_http_client_handle_t c)
{
    static uint8_t buf[2048]; // only ttsFetchTask gets here
    uint8_t hdr[512];
    size_t hdrLen = 0;
    bool inData = false, haveOdd = false;
    uint8_t odd = 0;

    // HTTP reads split anywhere: carry an odd byte to the next read.
    auto push = [&](const uint8_t *d, size_t len) {
        if (haveOdd && len) {
            const uint8_t pair[2] = { odd, d[0] };
            if (!ttsPush(pair, 2)) return false;
            d++, len--, haveOdd = false;
        }
        if (len & 1) { odd = d[len - 1]; haveOdd = true; len--; }
        return ttsPush(d, len);
    };

    int n;
    while ((n = esp_http_client_read(c, (char *)buf, sizeof buf)) > 0) {
        const uint8_t *p = buf;
        size_t len = n;
        if (!inData) {
            const size_t take = len < sizeof hdr - hdrLen ? len : sizeof hdr - hdrLen;
            memcpy(hdr + hdrLen, p, take);
            hdrLen += take;
            p += take;
            len -= take;
            uint32_t rate = 0;
            const long off = wavDataOffset(hdr, hdrLen, &rate);
            if (off == -2 || (off == -1 && hdrLen == sizeof hdr)) { printf("[tts] bad WAV header\n"); return false; }
            if (off == -1) continue;
            if (ttsRate == 0) ttsRate = rate;
            else if (ttsRate != rate) printf("[tts] rate changed %u -> %u Hz\n", (unsigned)ttsRate, (unsigned)rate);
            inData = true;
            if (!push(hdr + off, hdrLen - off)) return false;
        }
        if (!push(p, len)) return false;
    }
    return inData && n == 0;
}

// One request for one piece. Returns HTTP status (0 = network / format error).
static int ttsFetchPiece(const std::string &text)
{
    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "model", TTS_MODEL);
    cJSON_AddStringToObject(j, "input", text.c_str());
    cJSON_AddStringToObject(j, "voice", TTS_VOICE);
    cJSON_AddStringToObject(j, "response_format", "wav");
    char *body = cJSON_PrintUnformatted(j);
    cJSON_Delete(j);
    if (!body) return 0;

    esp_http_client_config_t cfg = {};
    cfg.url = TTS_URL;
    cfg.method = HTTP_METHOD_POST;
    cfg.timeout_ms = 30000;
    cfg.crt_bundle_attach = esp_crt_bundle_attach;
    cfg.buffer_size = 4096;
    cfg.buffer_size_tx = 1024;
    esp_http_client_handle_t c = esp_http_client_init(&cfg);
    if (!c) { cJSON_free(body); return 0; }
    const std::string auth = std::string("Bearer ") + SEED_GROQ_KEY;
    esp_http_client_set_header(c, "Authorization", auth.c_str());
    esp_http_client_set_header(c, "Content-Type", "application/json");

    int status = 0;
    const size_t bodyLen = strlen(body);
    if (esp_http_client_open(c, (int)bodyLen) != ESP_OK
        || !httpWriteAll(c, (const uint8_t *)body, bodyLen)) {
        printf("[tts] connect failed\n");
    } else {
        esp_http_client_fetch_headers(c);
        status = esp_http_client_get_status_code(c);
        if (status != 200) {
            char err[256];
            const int n = esp_http_client_read(c, err, sizeof err - 1);
            err[n > 0 ? n : 0] = 0;
            printf("[tts] HTTP %d: %.200s\n", status, err);
        } else if (!ttsReadWav(c) && !ttsStop) {
            status = 0;
        }
    }
    esp_http_client_close(c);
    esp_http_client_cleanup(c);
    cJSON_free(body);
    return status;
}

// Producer: one message at a time, waits until the assistant is idle.
static void ttsFetchTask(void *)
{
    for (;;) {
        TtsMsg *m = nullptr;
        xQueueReceive(ttsQueue, &m, portMAX_DELAY);

        // Don't talk over a wake / command session: wait for it to finish
        for (int idle = ST_IDLE; !state.compare_exchange_strong(idle, ST_SPEAKING); idle = ST_IDLE)
            vTaskDelay(pdMS_TO_TICKS(100));

        printf("[tts] %s: %s\n", m->title, m->text.c_str());
        logHeap("before speech");
        ui(AssistantState::Speaking, m->title, m->text);
        xStreamBufferReset(ttsStream); // safe: ttsPlayTask is waiting for its notify
        ttsRate = 0;
        ttsDone = false;
        ttsStop = false;
        xTaskNotifyGive(ttsPlayH);

        const auto parts = ttsSplit(m->text);
        const uint32_t t0 = millis();
        std::string err;
        for (size_t i = 0; i < parts.size() && !ttsStop; i++) {
            const int st = wifiUp ? ttsFetchPiece(parts[i]) : -1;
            if (st == 200) {
                printf("[tts] piece %u/%u ready (%u chars, %u ms)\n", (unsigned)(i + 1),
                       (unsigned)parts.size(), (unsigned)parts[i].size(), (unsigned)(millis() - t0));
                continue;
            }
            if (st == -1)       err = "No Wi-Fi connection";
            else if (st == 0)   err = "Speech network error";
            else if (st == 429) err = "Speech rate limited";
            else                err = "Speech error " + std::to_string(st);
            break;
        }
        ttsDone = true;
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY); // ttsPlayTask has drained the buffer

        state = ST_IDLE;
        const bool isReminder = strcmp(m->title, "Reminder") == 0;
        if (isReminder) uiReminder(m->text); // stays on the Home card, even if speech failed
        if (ttsStop)           { printf("[tts] stopped\n"); showIdle(); }
        else if (!err.empty()) { printf("[tts] failed: %s\n", err.c_str()); ui(AssistantState::Error, "Error", err, 4000); }
        else if (isReminder)   showIdle();
        else                   ui(AssistantState::Idle, m->title, m->text, 6000);
        delete m;
        printf("[idle] say \"Jarvis\"...\n");
    }
}

// Consumer: PSRAM buffer -> speaker, with pre-buffering.
static void ttsPlayTask(void *)
{
    static int16_t pcm[256];
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        bool primed = false;
        while (!ttsStop) {
            if (!primed) {
                const size_t avail = xStreamBufferBytesAvailable(ttsStream);
                const uint32_t rate = ttsRate;
                const size_t need = rate ? (size_t)rate * 2 * TTS_PREBUFFER_MS / 1000 : SIZE_MAX;
                if (ttsDone && avail == 0) break;              // finished, or nothing arrived
                if (avail < need && !ttsDone) { vTaskDelay(pdMS_TO_TICKS(10)); continue; }
                if (!speakerSetRate(rate)) break;
                primed = true;
            }
            const size_t n = xStreamBufferReceive(ttsStream, pcm, sizeof pcm, pdMS_TO_TICKS(50));
            if (n == 0) {
                if (ttsDone && xStreamBufferIsEmpty(ttsStream)) break;
                printf("[tts] underrun, re-buffering\n");
                primed = false;
                continue;
            }
            playPcm(pcm, n / 2);
        }
        xTaskNotifyGive(ttsFetchH);
    }
}

// Needs the speaker; call before mqttInit so no message arrives without a queue.
static void ttsInit()
{
    auto *store = (uint8_t *)heap_caps_malloc(TTS_BUF_BYTES + 1, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (store) ttsStream = xStreamBufferCreateStatic(TTS_BUF_BYTES, 1, store, &ttsStreamCtl);
    printf("[tts] PSRAM buffer %u KB -> %s\n", (unsigned)(TTS_BUF_BYTES / 1024),
           ttsStream ? "allocated" : "ALLOC FAILED");
    QueueHandle_t q = ttsStream && speakerOk ? xQueueCreate(TTS_QUEUE_LEN, sizeof(TtsMsg *)) : nullptr;
    if (!q) { printf("[tts] disabled\n"); return; }
    ttsQueue = q;
    xTaskCreatePinnedToCore(ttsPlayTask, "ttsPlay", 4096, nullptr, 4, &ttsPlayH, 0);
    // Network-only task (TLS, no flash writes): its stack can live in PSRAM
    xTaskCreatePinnedToCoreWithCaps(ttsFetchTask, "ttsFetch", 12288, nullptr, 3, &ttsFetchH, 0,
                                    MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
}

// ================================================================== TASKS ====
// feedTask: I2S -> clean-up -> AFE. Must never block on anything but the mic.
static void feedTask(void *)
{
    const int chunk = afe->get_feed_chunksize(afeData);   // samples per channel per frame
    const int chans = afe->get_feed_channel_num(afeData); // 2 for "MN"
    // The INMP441 sends 24-bit audio in 32-bit slots. Keep the top 16 bits
    // (same as Arduino's I2S_RX_TRANSFORM_32_TO_16).
    const size_t rawBytes = (size_t)chunk * sizeof(int32_t);
    int32_t *raw = (int32_t *)heap_caps_malloc(rawBytes, MALLOC_CAP_INTERNAL);
    int16_t *feed = (int16_t *)heap_caps_malloc((size_t)chunk * chans * sizeof(int16_t), MALLOC_CAP_INTERNAL);
    if (!raw || !feed) { printf("[feed] out of memory\n"); vTaskDelete(nullptr); }
    printf("[feed] chunk=%d samples (%d ms), %d channels\n", chunk, chunk * 1000 / SAMPLE_RATE, chans);

    filterReset();
    for (;;) {
        size_t got = 0;
        while (got < rawBytes) {
            size_t n = 0;
            i2s_channel_read(micRx, (uint8_t *)raw + got, rawBytes - got, &n, portMAX_DELAY);
            got += n;
        }
        for (int i = 0; i < chunk; i++) {
            int16_t s = filterSample((float)(raw[i] >> 16));
            feed[i * chans] = s;                                       // channel 0 = microphone
            for (int c = 1; c < chans; c++) feed[i * chans + c] = 0;   // N = unused
        }
        afe->feed(afeData, feed);
    }
}

// Finish the current command: send it to Groq if it contained real speech.
static void endCommand(const char *why, bool valid)
{
    if (valid) {
        writeWavHeader(rec, (uint32_t)recBytes);
        hasRecording = recBytes > 0;
        printf("[rec] end (%s): %u bytes, %.1f s, peak %u\n", why, (unsigned)recBytes,
               recBytes / (float)(SAMPLE_RATE * 2), (unsigned)recPeak);
        state = ST_UPLOAD;
        ui(AssistantState::Thinking, "Transcribing", "...");
        xTaskNotifyGive(uploadTaskH);
    } else {
        printf("[rec] cancelled (%s)\n", why);
        state = ST_IDLE;
        ui(AssistantState::Idle, "Standby", "Didn't catch that", 3000);
    }
}

// fetchTask: cleaned audio + wake/VAD flags from the AFE -> state machine.
static void fetchTask(void *)
{
    const uint32_t perMs = SAMPLE_RATE / 1000;
    uint32_t listenSamples = 0, silenceSamples = 0, speechSamples = 0, guardSamples = 0;
    bool speechSeen = false, manualSession = false;
    uint32_t lastLevelMs = 0, framePeak = 0;

    for (;;) {
        if (pendingWake > 0) {
            afe->set_wakenet_threshold(afeData, 1, pendingWake);
            printf("[cfg] wake threshold = %.3f\n", pendingWake);
            pendingWake = 0;
        }

        afe_fetch_result_t *res = afe->fetch_with_delay(afeData, pdMS_TO_TICKS(200));
        if (!res || res->ret_value == ESP_FAIL) continue;
        const int samples = res->data_size / 2;

        if (state == ST_IDLE) {
            bool wake = res->wakeup_state != WAKENET_NO_DETECT;
            bool manual = manualWake;
            if ((wake || manual) && !dumping && rec) {
                manualWake = false;
                const bool greet = !manual && speakerOk && speakerTaskH;
                int idle = ST_IDLE; // a reminder may have claimed the speaker meanwhile
                if (!state.compare_exchange_strong(idle, greet ? ST_GREETING : ST_LISTEN)) continue;
                manualSession = manual;
                hasRecording = false; // buffer is about to be overwritten
                recBytes = 0; recPeak = 0;
                listenSamples = silenceSamples = speechSamples = 0;
                guardSamples = manualSession ? 0 : WAKE_GUARD_MS * perMs;
                speechSeen = false;

                if (greet) {
                    printf("[wake] Jarvis detected - playing greeting...\n");
                    xTaskNotifyGive(speakerTaskH);
                } else {
                    printf(manualSession ? "[wake] BOOT held - recording until release...\n"
                                         : "[wake] Jarvis detected - listening...\n");
                    ui(AssistantState::Listening, "Listening",
                       manualSession ? "Recording... release BOOT" : "Speak now...");
                }
            }
            continue;
        }
        if (state != ST_LISTEN) continue; // GREETING / UPLOAD / SPEAKING: keep draining the AFE

        // ---- LISTEN ----
        if (recBytes + (size_t)res->data_size > PCM_CAPACITY) {
            bool valid = manualSession ? (recPeak >= MANUAL_MIN_PEAK) : (speechSamples >= MIN_SPEECH_MS * perMs);
            endCommand("buffer full", valid);
            manualSession = false;
            continue;
        }
        memcpy(rec + WAV_HDR + recBytes, res->data, res->data_size);
        recBytes += res->data_size;
        for (int i = 0; i < samples; i++) {
            uint32_t m = res->data[i] < 0 ? -res->data[i] : res->data[i];
            if (m > recPeak) recPeak = m;
            if (m > framePeak) framePeak = m;
        }
        listenSamples += samples;

        // Mic level for the orb, ~10 updates per second
        if (millis() - lastLevelMs >= 100) {
            lastLevelMs = millis();
            float lv = sqrtf(framePeak / 32768.0f);
            uiLevel(lv > 1 ? 1 : lv);
            framePeak = 0;
        }

        if (guardSamples > 0) {
            guardSamples = guardSamples > (uint32_t)samples ? guardSamples - samples : 0;
        } else if (res->vad_state == VAD_SPEECH) {
            speechSeen = true;
            speechSamples += samples;
            silenceSamples = 0;
        } else if (speechSeen) {
            silenceSamples += samples;
        }

        // BOOT manual mode is hold-to-record: release ends it.
        if (manualSession && gpio_get_level(PIN_BUTTON) == 1) {
            endCommand("BOOT released", recPeak >= MANUAL_MIN_PEAK);
            manualSession = false;
            continue;
        }

        if (!manualSession && speechSeen && silenceSamples >= silenceEndMs * perMs) {
            if (speechSamples >= MIN_SPEECH_MS * perMs) {
                endCommand("silence", true);
            } else { // a short blip, not a command - keep waiting
                speechSeen = false; speechSamples = 0; silenceSamples = 0;
            }
        } else if (!manualSession && !speechSeen && listenSamples >= NO_SPEECH_TIMEOUT_MS * perMs) {
            endCommand("no speech after wake word", false);
        } else if (listenSamples >= (uint32_t)MAX_CMD_SECONDS * SAMPLE_RATE) {
            bool valid = manualSession ? (recPeak >= MANUAL_MIN_PEAK) : (speechSamples >= MIN_SPEECH_MS * perMs);
            endCommand("max length", valid);
            manualSession = false;
        }
    }
}

// uploadTask: the slow network part, so the mic/AFE never stall.
static void uploadTask(void *)
{
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        std::string text;
        logHeap("before upload");
        int status = wifiUp ? uploadToGroq(&text) : 0;

        if (status == 200 && !text.empty()) {
            printf("-------------------------------------------\nYou said: %s\n"
                   "-------------------------------------------\n\n", text.c_str());
            mqttPublishTranscript(text, (uint32_t)(recBytes / (SAMPLE_RATE * 2 / 1000)));
            state = ST_IDLE;
            ui(AssistantState::Idle, "You said", "\"" + text + "\"", 8000);
        } else {
            std::string msg;
            if (!wifiUp)            msg = "No Wi-Fi connection";
            else if (status == 0)   msg = "Network error";
            else if (status == 429) msg = "Rate limited, try later";
            else if (status == 200) msg = "Heard nothing";
            else                    msg = "Server error " + std::to_string(status);
            if (status && status != 200) printf("[stt] HTTP %d: %.160s\n", status, text.c_str());
            state = ST_IDLE;
            ui(AssistantState::Error, "Error", msg, 4000);
        }
        printf("[idle] say \"Jarvis\"...\n");
    }
}

// ============================================================ SERIAL / DUMP ==
static uint32_t crc32Update(uint32_t crc, const uint8_t *d, size_t len)
{
    static const uint32_t T[16] = {
        0x00000000, 0x1DB71064, 0x3B6E20C8, 0x26D930AC, 0x76DC4190, 0x6B6B51F4, 0x4DB26158, 0x5005713C,
        0xEDB88320, 0xF00F9344, 0xD6D6A3E8, 0xCB61B38C, 0x9B64C2B0, 0x86D3D2D4, 0xA00AE278, 0xBDBDF21C };
    for (size_t i = 0; i < len; i++) {
        crc ^= d[i];
        crc = (crc >> 4) ^ T[crc & 0x0F];
        crc = (crc >> 4) ^ T[crc & 0x0F];
    }
    return crc;
}

static bool serialWriteAll(const uint8_t *d, size_t len)
{
    size_t off = 0;
    uint32_t last = millis();
    while (off < len) {
        size_t w = fwrite(d + off, 1, len - off, stdout);
        if (w == 0) {
            clearerr(stdout);
            if (millis() - last > 5000) return false;
            vTaskDelay(1);
            continue;
        }
        off += w;
        last = millis();
    }
    return true;
}

static void dumpWav()
{
    if (state != ST_IDLE) { printf("BUSY\n"); return; }
    if (!hasRecording)    { printf("NOREC\n"); return; }
    dumping = true; // blocks a new wake from overwriting rec
    const size_t total = WAV_HDR + recBytes;
    printf("WAVDUMP %u\n", (unsigned)total);
    fflush(stdout);
    uint32_t crc = 0xFFFFFFFF;
    bool ok = true;
    for (size_t off = 0; off < total && ok;) {
        size_t c = total - off;
        if (c > 1024) c = 1024;
        crc = crc32Update(crc, rec + off, c);
        ok = serialWriteAll(rec + off, c);
        off += c;
    }
    fflush(stdout);
    if (ok) printf("\nWAVEND %08X\n", (unsigned)(crc ^ 0xFFFFFFFF));
    fflush(stdout);
    dumping = false;
}

// Speaker check: shows how the I2S pins are routed, then 1.5 s of 1 kHz.
static void toneTest()
{
    int idle = ST_IDLE;
    if (!state.compare_exchange_strong(idle, ST_SPEAKING)) { printf("BUSY\n"); return; }
    printf("[tone] speaker %s, %u Hz. Pin routing (BCLK %d, LRC %d, DIN %d):\n",
           speakerOk ? "ok" : "NOT STARTED", (unsigned)spkRate, PIN_SPK_BCLK, PIN_SPK_LRC, PIN_SPK_DIN);
    gpio_dump_io_configuration(stdout, (1ULL << PIN_SPK_BCLK) | (1ULL << PIN_SPK_LRC) | (1ULL << PIN_SPK_DIN));
    static int16_t tone[160]; // 10 ms at 16 kHz = 10 periods of 1 kHz
    for (int i = 0; i < 160; i++) tone[i] = (int16_t)(12000 * sinf(2 * (float)M_PI * 1000 * i / SAMPLE_RATE));
    bool ok = speakerSetRate(SAMPLE_RATE);
    for (int i = 0; i < 150 && ok; i++) ok = playPcm(tone, 160);
    printf("[tone] %s\n", ok ? "played 1.5 s - did you hear a beep?" : "I2S write FAILED");
    state = ST_IDLE;
}

static void handleCommand(std::string cmd)
{
    while (!cmd.empty() && isspace((unsigned char)cmd.back())) cmd.pop_back();
    if (cmd == "DUMP") { dumpWav(); return; }
    if (cmd == "TONE") { toneTest(); return; }
    if (cmd == "HEAP") { logHeap("now"); return; }
    if (cmd.rfind("SET SIL ", 0) == 0) {
        long v = atol(cmd.c_str() + 8);
        if (v >= 200 && v <= 10000) { silenceEndMs = v; printf("[cfg] silence end = %ld ms\n", v); }
        else printf("[cfg] SET SIL expects 200..10000\n");
    } else if (cmd.rfind("SET WAKE ", 0) == 0) {
        float v = atof(cmd.c_str() + 9);
        if (v >= 0.4f && v <= 0.9999f) pendingWake = v;
        else printf("[cfg] SET WAKE expects 0.4..0.9999\n");
    } else if (cmd.rfind("SET GAIN ", 0) == 0) {
        float v = atof(cmd.c_str() + 9);
        if (v >= 0.5f && v <= 32.0f) { micGain = v; printf("[cfg] mic gain = %.2f\n", v); }
        else printf("[cfg] SET GAIN expects 0.5..32\n");
    }
}

// Replaces Arduino loop(), part 1: serial commands.
static void consoleTask(void *)
{
    fcntl(fileno(stdin), F_SETFL, O_NONBLOCK);
    std::string line;
    for (;;) {
        char buf[64];
        int n = read(fileno(stdin), buf, sizeof buf);
        for (int i = 0; i < n; i++) {
            if (buf[i] == '\n' || buf[i] == '\r') {
                if (!line.empty()) handleCommand(line);
                line.clear();
            } else if (line.size() < 64) {
                line += buf[i];
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

// Replaces Arduino loop(), part 2: BOOT button (own task, never blocked by serial).
static void buttonTask(void *)
{
    bool buttonArmed = true;
    uint32_t buttonLowSince = 0;
    for (;;) {
        if (gpio_get_level(PIN_BUTTON) == 0) {
            if (buttonLowSince == 0) buttonLowSince = millis();
            if (buttonArmed && millis() - buttonLowSince >= 30) {
                if (state == ST_IDLE) {
                    if (onHome && cardShown) uiReminder(""); // dismiss the reminder card
                    else manualWake = true;
                } else if (state == ST_SPEAKING) ttsStop = true; // BOOT interrupts a reminder
                buttonArmed = false; // one trigger per physical press
            }
        } else {
            buttonLowSince = 0;
            buttonArmed = true;
        }
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

// ============================================================ AUDIO SETUP ====
// Returns an error message for the screen, or nullptr on success.
static const char *audioSetup()
{
    // Order matters: I2S first (its DMA must not land in PSRAM), then big allocations.
    if (!micStart()) return "Mic init failed";
    speakerStart();

    rec = (uint8_t *)heap_caps_malloc(WAV_HDR + PCM_CAPACITY, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    printf("[psram] %u KB free, record buffer %u KB -> %s\n",
           (unsigned)(heap_caps_get_free_size(MALLOC_CAP_SPIRAM) / 1024),
           (unsigned)((WAV_HDR + PCM_CAPACITY) / 1024), rec ? "allocated" : "ALLOC FAILED");
    if (!rec) return "PSRAM alloc failed";

    srmodel_list_t *models = esp_srmodel_init("model");
    if (!models) { printf("[sr] model partition NOT found - flash srmodels.bin\n"); return "Flash srmodels.bin"; }

    afe_config_t *cfg = afe_config_init("MN", models, AFE_TYPE_SR, AFE_MODE_HIGH_PERF);
    if (!cfg) return "AFE config failed";
    cfg->aec_init = false;
    cfg->vad_min_noise_ms = 100; // our own timer does the 1.2 s (SILENCE_END_MS)
    cfg->memory_alloc_mode = AFE_MEMORY_ALLOC_MORE_PSRAM;
    printf("[sr] wake model: %s\n", cfg->wakenet_model_name ? cfg->wakenet_model_name : "NONE");
    if (!cfg->wakenet_model_name) return "No wake model";

    afe = esp_afe_handle_from_config(cfg);
    afeData = afe ? afe->create_from_config(cfg) : nullptr;
    if (!afeData) return "AFE create failed";
    afe->print_pipeline(afeData);
    if (WAKE_THRESHOLD > 0) afe->set_wakenet_threshold(afeData, 1, WAKE_THRESHOLD);
    return nullptr;
}

// Runs once in its own task so the screen is already live during setup.
static void setupTask(void *)
{
    printf("\n\nVoice assistant - wake word \"Jarvis\" -> Groq\n");

    gpio_config_t io = {};
    io.pin_bit_mask = 1ULL << PIN_BUTTON;
    io.mode = GPIO_MODE_INPUT;
    io.pull_up_en = GPIO_PULLUP_ENABLE;
    gpio_config(&io);

    const char *err = audioSetup();
    if (err) {
        ui(AssistantState::Error, "Error", err);
        printf("[setup] stopped: %s\n", err);
        vTaskDelete(nullptr);
    }

    // NVS is needed by Wi-Fi (calibration data, credentials cache)
    esp_err_t e = nvs_flash_init();
    if (e == ESP_ERR_NVS_NO_FREE_PAGES || e == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }
    ttsInit();  // before MQTT: incoming messages need the queue
    mqttInit(); // before Wi-Fi: the first IP event starts the client
    wifiStart();

    // Network-only task (TLS, no flash writes): its stack can live in PSRAM
    xTaskCreatePinnedToCoreWithCaps(uploadTask, "upload", 16384, nullptr, 3, &uploadTaskH, 0,
                                    MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    xTaskCreatePinnedToCore(speakerTask, "speaker", 4096, nullptr, 3, &speakerTaskH, 0);
    xTaskCreatePinnedToCore(fetchTask, "fetch", 8192, nullptr, 5, nullptr, 1);
    xTaskCreatePinnedToCore(feedTask, "feed", 6144, nullptr, 5, nullptr, 0);
    xTaskCreatePinnedToCore(consoleTask, "console", 4096, nullptr, 2, nullptr, 1);
    xTaskCreatePinnedToCore(buttonTask, "button", 2048, nullptr, 2, nullptr, 1);

    printf("\nReady. Say \"Jarvis\", then your command. Silence for %u ms ends it.\n",
           (unsigned)silenceEndMs);
    printf("Commands: DUMP | TONE | HEAP | SET SIL <ms> | SET WAKE <0.4-0.9999> | SET GAIN <x>   (BOOT = hold to record)\n\n");
    logHeap("ready");
    showIdle();
    vTaskDelete(nullptr);
}

// ================================================================ ENTRY ======
extern "C" void app_main(void)
{
    // Display + Slint first, so every later step can show its status.
    tft.init();
    tft.setRotation(0);
    tft.setBrightness(200);
    tft.fillScreen(TFT_BLACK);

    slint::platform::set_platform(std::make_unique<LgfxSlintPlatform>(tft));
    auto win = AppWindow::create();
    g_ui = win;
    win->set_status_text("Starting");
    win->set_transcript("Loading wake word...");

    xTaskCreatePinnedToCore(setupTask, "setup", 12288, nullptr, 4, nullptr, 1);

    slint::Timer clock(std::chrono::seconds(1), clockTick); // Home clock, lives as long as run()

    win->run(); // Slint event loop on core 0, lowest priority of the busy tasks
}
