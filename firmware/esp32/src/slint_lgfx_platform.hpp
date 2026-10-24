// slint_lgfx_platform.hpp
// Glue between Slint (software renderer) and LovyanGFX on ESP-IDF.
//
//  - Slint renders into a full RGB565 frame buffer (128*160*2 = 40 KB).
//  - Only the rows that changed are pushed to the panel through LovyanGFX.
//  - The event loop sleeps when nothing is animating, and other FreeRTOS
//    tasks (mic, wake word, STT, Wi-Fi...) can safely update the UI with
//    slint::invoke_from_event_loop().
#pragma once

#include <algorithm>
#include <atomic>
#include <chrono>
#include <deque>
#include <memory>
#include <mutex>
#include <utility>
#include <vector>

#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "LGFX_ST7735S.hpp" // defines LGFX_USE_V1 before including LovyanGFX
#include <slint-platform.h>

class LgfxWindowAdapter : public slint::platform::WindowAdapter
{
public:
    LgfxWindowAdapter(lgfx::LGFX_Device &lcd, slint::PhysicalSize size)
        : m_lcd(lcd),
          m_size(size),
          m_renderer(slint::platform::SoftwareRenderer::RepaintBufferType::ReusedBuffer),
          m_buffer(size.width * size.height)
    {
    }

    slint::platform::AbstractRenderer &renderer() override { return m_renderer; }
    slint::PhysicalSize size() override { return m_size; }
    void request_redraw() override { m_needs_redraw = true; }

    // Called from the event loop
    void render_if_needed()
    {
        if (!std::exchange(m_needs_redraw, false)) {
            return;
        }

        const auto stride = m_size.width;
        auto region = m_renderer.render(m_buffer, stride);

        const auto origin = region.bounding_box_origin();
        const auto box = region.bounding_box_size();
        if (box.width == 0 || box.height == 0) {
            return;
        }

        // Push the full-width band of rows that contain changes. Because the
        // band is full width it is contiguous in memory: one SPI transfer.
        // Slint's Rgb565Pixel is native-endian RGB565 == lgfx::rgb565_t, so
        // LovyanGFX does the byte swap for the panel automatically.
        const auto *band = reinterpret_cast<const lgfx::rgb565_t *>(m_buffer.data()
                                                                     + origin.y * stride);
        m_lcd.startWrite();
        m_lcd.pushImage(0, origin.y, stride, box.height, band);
        m_lcd.endWrite();
    }

private:
    lgfx::LGFX_Device &m_lcd;
    slint::PhysicalSize m_size;
    slint::platform::SoftwareRenderer m_renderer;
    std::vector<slint::platform::Rgb565Pixel> m_buffer;
    bool m_needs_redraw = true;
};

class LgfxSlintPlatform : public slint::platform::Platform
{
public:
    explicit LgfxSlintPlatform(lgfx::LGFX_Device &lcd) : m_lcd(lcd) { }

    std::unique_ptr<slint::platform::WindowAdapter> create_window_adapter() override
    {
        // Use the panel's size *after* setRotation(), so landscape just works.
        auto size = slint::PhysicalSize({ uint32_t(m_lcd.width()), uint32_t(m_lcd.height()) });
        auto window = std::make_unique<LgfxWindowAdapter>(m_lcd, size);
        m_window = window.get();
        return window;
    }

    std::chrono::milliseconds duration_since_start() override
    {
        return std::chrono::milliseconds(esp_timer_get_time() / 1000);
    }

    void run_event_loop() override
    {
        m_task = xTaskGetCurrentTaskHandle();

        while (true) {
            slint::platform::update_timers_and_animations();

            // Run work posted from other tasks via slint::invoke_from_event_loop()
            std::deque<Task> tasks;
            {
                std::lock_guard<std::mutex> lock(m_mutex);
                if (std::exchange(m_quit, false)) {
                    break;
                }
                std::swap(tasks, m_queue);
            }
            for (auto &task : tasks) {
                std::move(task).run();
            }

            if (m_window) {
                m_window->render_if_needed();

                if (m_window->window().has_active_animations()) {
                    // Frame cap; also lets the idle task run (keeps the watchdog happy)
                    vTaskDelay(std::max<TickType_t>(1, pdMS_TO_TICKS(33))); // ~30 fps: leaves CPU for audio
                    continue;
                }
            }

            // Nothing animating: sleep until the next Slint timer or until
            // another task posts something with invoke_from_event_loop().
            TickType_t wait = portMAX_DELAY;
            if (auto next = slint::platform::duration_until_next_timer_update()) {
                wait = std::min<TickType_t>(wait, pdMS_TO_TICKS(next->count()));
            }
            ulTaskNotifyTake(pdTRUE, wait);
        }
    }

    void quit_event_loop() override
    {
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            m_quit = true;
        }
        wake();
    }

    // May be called from ANY FreeRTOS task
    void run_in_event_loop(Task task) override
    {
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            m_queue.push_back(std::move(task));
        }
        wake();
    }

private:
    void wake()
    {
        if (TaskHandle_t t = m_task.load()) {
            xTaskNotifyGive(t);
        }
    }

    lgfx::LGFX_Device &m_lcd;
    LgfxWindowAdapter *m_window = nullptr;
    std::atomic<TaskHandle_t> m_task { nullptr };
    std::mutex m_mutex;
    std::deque<Task> m_queue;
    bool m_quit = false;
};
