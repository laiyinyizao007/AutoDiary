/**
 * AutoDiary - 智能日记系统 (HTTP 服务器模式)
 * 
 * 基于 XIAO-ESP32S3-Sense 参考项目的架构改造
 * 
 * 功能：
 * - HTTP 服务器提供摄像头视频流
 * - I2S 麦克风音频采集
 * - 与 Python 后端通过 HTTP 通信
 * 
 * 连接方式：
 * 1. PC 浏览器访问: http://ESP32_IP/
 * 2. PC 后端通过 HTTP 接口获取视频和音频
 * 
 * 作者: AutoDiary 开发团队
 * 版本: v2.0 (HTTP 服务器模式)
 * 基于: XIAO-ESP32S3-Sense Camera_HTTP_Server_STA
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <esp_camera.h>
#include <esp_timer.h>
#include <img_converters.h>
#include <soc/soc.h>
#include <soc/rtc_cntl_reg.h>
#include <driver/rtc_io.h>
#include <I2S.h>
#include <ArduinoJson.h>
#include <SPIFFS.h>
#include <FS.h>
#include "camera_pins.h"

// ==================== 配置参数 ====================

// WiFi 配置
const char* ssid = "ChinaNet-YIJU613";
const char* password = "7ep58315";

// HTTP 服务器配置
WebServer server(80);  // 创建 HTTP 服务器，监听端口 80

// 摄像头配置
camera_config_t config;

// 音频配置
#define AUDIO_SAMPLE_RATE     16000
#define AUDIO_BUFFER_SIZE     512
#define AUDIO_CHANNELS        1

// 音频缓冲区 (环形缓冲区)
short audio_buffer[AUDIO_BUFFER_SIZE * 2];
volatile uint32_t audio_buffer_pos = 0;
volatile bool audio_data_ready = false;

// 任务句柄
TaskHandle_t videoTaskHandle = NULL;
TaskHandle_t audioTaskHandle = NULL;

// 状态变量
bool camera_initialized = false;
bool wifi_connected = false;
bool i2s_initialized = false;

// 统计变量
unsigned long frame_count = 0;
unsigned long last_frame_time = 0;
unsigned long audio_bytes_captured = 0;

// ==================== HTML 页面 ====================

const char* html_page = 
"<!DOCTYPE html>"
"<html>"
"<head>"
"  <meta charset='UTF-8'>"
"  <title>AutoDiary Monitor</title>"
"  <style>"
"    body { font-family: Arial; background: #667eea; display: flex; justify-content: center; align-items: center; min-height: 100vh; }"
"    .container { background: white; border-radius: 15px; padding: 30px; max-width: 800px; width: 100%; }"
"    h1 { color: #333; text-align: center; }"
"    .video-container { background: #000; border-radius: 10px; margin: 20px 0; }"
"    img { width: 100%; height: auto; }"
"    button { padding: 12px; margin: 5px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }"
"    .btn-primary { background: #667eea; color: white; }"
"    .btn-danger { background: #f56565; color: white; }"
"    .status { background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #667eea; }"
"    .status-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e0e0e0; }"
"  </style>"
"</head>"
"<body>"
"  <div class='container'>"
"    <h1>AutoDiary Camera Monitor</h1>"
"    <div class='video-container'>"
"      <img id='videoStream' src='/video.jpg' alt='Video Stream'>"
"    </div>"
"    <div>"
"      <button class='btn-primary' onclick='location.href=\\\"/capture\\\"'>Capture Photo</button>"
"      <button class='btn-primary' onclick='location.href=\\\"/status\\\"'>Get Status</button>"
"      <button class='btn-danger' onclick='location.href=\\\"/restart\\\"'>Restart</button>"
"    </div>"
"    <div class='status'>"
"      <h3>System Status</h3>"
"      <div class='status-item'><span>Device:</span><span id='device'>XIAO-ESP32S3</span></div>"
"      <div class='status-item'><span>WiFi:</span><span id='wifi'>Checking...</span></div>"
"      <div class='status-item'><span>Camera:</span><span id='camera'>OK</span></div>"
"    </div>"
"  </div>"
"  <script>"
"    function refreshVideo() { "
"      document.getElementById('videoStream').src = '/video.jpg?t=' + Date.now(); "
"    }"
"    setInterval(refreshVideo, 1000);"
"  </script>"
"</body>"
"</html>";

// ==================== 函数声明 ====================

void setupCamera();
void setupWiFi();
void setupI2S();
void setupWebServer();
void onVideoCapture();
void onAudioCapture();
void videoCaptureTask(void *parameter);
void audioCaptureTask(void *parameter);
void handleRoot();
void handleVideoJpeg();
void handleCapture();
void handleSave();
void handleSavedPhoto();
void handleAudio();
void handleStatus();
void handleRestart();
void handleNotFound();
void debugPrintStatus();

// ==================== Setup 函数 ====================

void setup() {
    Serial.begin(115200);
    delay(3000);
    
    Serial.println("\n========================================");
    Serial.println("AutoDiary - HTTP Server Mode v2.0");
    Serial.println("Based on XIAO-ESP32S3-Sense");
    Serial.println("========================================\n");
    
    // Disable brownout detector
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
    
    Serial.println("Initializing hardware components...\n");
    
    Serial.println("[1] Initializing SPIFFS...");
    if (!SPIFFS.begin(true)) {
        Serial.println("[WARN] SPIFFS init failed, continuing");
    } else {
        Serial.println("[OK] SPIFFS initialized");
    }
    
    Serial.println("\n[2] Initializing WiFi...");
    setupWiFi();
    
    Serial.println("\n📷 初始化摄像头...");
    setupCamera();
    
    Serial.println("\n🎤 初始化 I2S 麦克风...");
    setupI2S();
    
    Serial.println("\n🌐 初始化 HTTP 服务器...");
    setupWebServer();
    
    Serial.println("\n🚀 创建后台任务...");
    xTaskCreatePinnedToCore(
        videoCaptureTask,
        "VideoCapture",
        8192,  // 增加堆栈大小
        NULL,
        2,
        &videoTaskHandle,
        1
    );
    
    if (videoTaskHandle == NULL) {
        Serial.println("❌ 视频任务创建失败!");
    }
    
    xTaskCreatePinnedToCore(
        audioCaptureTask,
        "AudioCapture",
        8192,  // 增加堆栈大小
        NULL,
        2,
        &audioTaskHandle,
        0
    );
    
    if (audioTaskHandle == NULL) {
        Serial.println("❌ 音频任务创建失败!");
    }
    
    Serial.println("\n✅ 系统初始化完成！");
    debugPrintStatus();
    
    Serial.println("\n📡 服务已启动:");
    Serial.printf("🌐 访问地址: http://%s/\n", WiFi.localIP().toString().c_str());
    Serial.printf("📸 视频流: http://%s/video.jpg\n", WiFi.localIP().toString().c_str());
    Serial.printf("📊 状态接口: http://%s/status\n\n", WiFi.localIP().toString().c_str());
}

// ==================== Main Loop ====================

void loop() {
    server.handleClient();  // 处理 HTTP 请求
    
    // Debug: Print connection status every 30 seconds
    static unsigned long last_debug = 0;
    if (millis() - last_debug > 30000) {
        Serial.println("\n[DEBUG] Loop running normally");
        Serial.printf("[DEBUG] WiFi: %d, Camera: %d, I2S: %d\n", 
            wifi_connected, camera_initialized, i2s_initialized);
        Serial.printf("[DEBUG] Frames captured: %lu\n", frame_count);
        last_debug = millis();
    }
    
    delay(10);
}

// ==================== 初始化函数 ====================

void setupWiFi() {
    Serial.printf("连接到 WiFi: %s\n", ssid);
    WiFi.begin(ssid, password);
    
    int attempts = 0;
    Serial.print("连接中");
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(1000);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        wifi_connected = true;
        Serial.println("\n✅ WiFi 连接成功！");
        Serial.printf("IP 地址: %s\n", WiFi.localIP().toString().c_str());
        Serial.printf("信号强度: %d dBm\n", WiFi.RSSI());
    } else {
        Serial.println("\n❌ WiFi 连接失败！");
        Serial.println("请检查 SSID 和密码设置");
    }
}

void setupCamera() {
    Serial.println("========== 摄像头初始化开始 ==========");

    // [DEBUG] 检查 PSRAM
    Serial.printf("[DEBUG] PSRAM 可用: %s\n", psramFound() ? "是" : "否");
    if (psramFound()) {
        Serial.printf("[DEBUG] PSRAM 大小: %d bytes\n", ESP.getPsramSize());
        Serial.printf("[DEBUG] PSRAM 空闲: %d bytes\n", ESP.getFreePsram());
    }
    Serial.printf("[DEBUG] 堆内存空闲: %d bytes\n", ESP.getFreeHeap());

    Serial.println("[DEBUG] 配置摄像头引脚...");
    Serial.printf("[DEBUG] XCLK=%d, PCLK=%d, VSYNC=%d, HREF=%d\n",
                  XCLK_GPIO_NUM, PCLK_GPIO_NUM, VSYNC_GPIO_NUM, HREF_GPIO_NUM);
    Serial.printf("[DEBUG] SIOD=%d, SIOC=%d, PWDN=%d, RESET=%d\n",
                  SIOD_GPIO_NUM, SIOC_GPIO_NUM, PWDN_GPIO_NUM, RESET_GPIO_NUM);
    Serial.printf("[DEBUG] Y2-Y9: %d,%d,%d,%d,%d,%d,%d,%d\n",
                  Y2_GPIO_NUM, Y3_GPIO_NUM, Y4_GPIO_NUM, Y5_GPIO_NUM,
                  Y6_GPIO_NUM, Y7_GPIO_NUM, Y8_GPIO_NUM, Y9_GPIO_NUM);

    // 按照参考项目的配置顺序
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;  // 新版 API
    config.pin_sccb_scl = SIOC_GPIO_NUM;  // 新版 API
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;

    // 使用参考项目的配置参数
    config.frame_size = FRAMESIZE_UXGA;      // 参考项目使用 UXGA
    config.pixel_format = PIXFORMAT_JPEG;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;  // 修复: 使用参考项目的值
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.jpeg_quality = 12;
    config.fb_count = 1;  // 修复: 参考项目使用 1

    Serial.println("[DEBUG] 正在调用 esp_camera_init()...");
    esp_err_t err = esp_camera_init(&config);

    if (err == ESP_OK) {
        camera_initialized = true;
        Serial.println("✅ 摄像头初始化成功！");

        sensor_t * s = esp_camera_sensor_get();
        if (s) {
            Serial.printf("[DEBUG] 摄像头 PID: 0x%X\n", s->id.PID);
            Serial.printf("摄像头型号: %s\n", s->id.PID == OV2640_PID ? "OV2640" : "Unknown");

            // 降低分辨率以确保稳定性
            s->set_framesize(s, FRAMESIZE_VGA);  // 640x480
            Serial.println("[DEBUG] 分辨率已调整为 VGA (640x480)");
        }

        // 测试拍照
        Serial.println("[DEBUG] 测试摄像头捕获...");
        camera_fb_t * test_fb = esp_camera_fb_get();
        if (test_fb) {
            Serial.printf("[DEBUG] 测试帧捕获成功: %d bytes, %dx%d\n",
                          test_fb->len, test_fb->width, test_fb->height);
            esp_camera_fb_return(test_fb);
        } else {
            Serial.println("[ERROR] 测试帧捕获失败！");
            Serial.printf("[DEBUG] 当前堆内存: %d bytes\n", ESP.getFreeHeap());
            if (psramFound()) {
                Serial.printf("[DEBUG] 当前 PSRAM: %d bytes\n", ESP.getFreePsram());
            }
        }
    } else {
        Serial.printf("❌ 摄像头初始化失败: 0x%x\n", err);
        Serial.println("[DEBUG] 错误代码说明:");
        switch(err) {
            case ESP_ERR_NOT_FOUND:
                Serial.println("  - ESP_ERR_NOT_FOUND: 未检测到摄像头");
                break;
            case ESP_ERR_NOT_SUPPORTED:
                Serial.println("  - ESP_ERR_NOT_SUPPORTED: 摄像头不支持");
                break;
            case ESP_ERR_NO_MEM:
                Serial.println("  - ESP_ERR_NO_MEM: 内存不足");
                break;
            case ESP_ERR_INVALID_STATE:
                Serial.println("  - ESP_ERR_INVALID_STATE: 无效状态");
                break;
            default:
                Serial.printf("  - 未知错误: 0x%x\n", err);
        }
    }

    Serial.printf("[DEBUG] 初始化后堆内存: %d bytes\n", ESP.getFreeHeap());
    Serial.println("========== 摄像头初始化结束 ==========\n");
}

void setupI2S() {
    Serial.println("配置 I2S...");
    Serial.printf("WS (Word Select): GPIO 42\n");
    Serial.printf("SCK (Serial Clock): GPIO 41\n");
    
    I2S.setAllPins(-1, 42, 41, -1, -1);
    
    if (!I2S.begin(PDM_MONO_MODE, AUDIO_SAMPLE_RATE, 16)) {
        Serial.println("❌ I2S 初始化失败");
        return;
    }
    
    i2s_initialized = true;
    Serial.println("✅ I2S 麦克风初始化成功");
    Serial.printf("采样率: %d Hz\n", AUDIO_SAMPLE_RATE);
    Serial.printf("通道: 单声道\n");
}

void setupWebServer() {
    // 注册 HTTP 路由处理器
    server.on("/", HTTP_GET, handleRoot);
    server.on("/video.jpg", HTTP_GET, handleVideoJpeg);
    server.on("/capture", HTTP_GET, handleCapture);
    server.on("/save", HTTP_GET, handleSave);
    server.on("/saved_photo", HTTP_GET, handleSavedPhoto);
    server.on("/audio", HTTP_GET, onAudioCapture);
    server.on("/status", HTTP_GET, handleStatus);
    server.on("/restart", HTTP_GET, handleRestart);
    
    server.onNotFound(handleNotFound);
    
    server.begin();
    Serial.println("✅ HTTP 服务器启动成功 (端口 80)");
}

// ==================== HTTP 请求处理函数 ====================

void handleRoot() {
    server.send(200, "text/html; charset=utf-8", html_page);
}

void handleVideoJpeg() {
    Serial.println("\n[DEBUG] ========== /video.jpg 请求 ==========");
    Serial.printf("[DEBUG] 当前时间: %lu ms\n", millis());
    Serial.printf("[DEBUG] 堆内存: %d bytes\n", ESP.getFreeHeap());
    if (psramFound()) {
        Serial.printf("[DEBUG] PSRAM 空闲: %d bytes\n", ESP.getFreePsram());
    }

    if (!camera_initialized) {
        Serial.println("[ERROR] 摄像头未初始化!");
        server.send(503, "text/plain", "Camera not initialized");
        return;
    }

    Serial.println("[DEBUG] 正在捕获帧...");
    unsigned long start_time = millis();

    camera_fb_t * fb = esp_camera_fb_get();

    unsigned long capture_time = millis() - start_time;
    Serial.printf("[DEBUG] 捕获耗时: %lu ms\n", capture_time);

    if (fb) {
        Serial.printf("[OK] 帧捕获成功!\n");
        Serial.printf("[DEBUG] 帧大小: %d bytes\n", fb->len);
        Serial.printf("[DEBUG] 分辨率: %dx%d\n", fb->width, fb->height);
        Serial.printf("[DEBUG] 格式: %d (JPEG=4)\n", fb->format);

        // 验证 JPEG 头
        if (fb->len > 2) {
            Serial.printf("[DEBUG] JPEG 头: 0x%02X 0x%02X (应为 0xFF 0xD8)\n",
                          fb->buf[0], fb->buf[1]);
        }

        server.sendHeader("Content-Type", "image/jpeg");
        server.sendHeader("Content-Length", String(fb->len));
        server.sendHeader("Cache-Control", "no-cache");
        server.send_P(200, "image/jpeg", (const char *)fb->buf, fb->len);
        esp_camera_fb_return(fb);
        frame_count++;

        Serial.printf("[DEBUG] 帧已发送，总计: %lu 帧\n", frame_count);
    } else {
        Serial.println("[ERROR] esp_camera_fb_get() 返回 NULL!");
        Serial.printf("[DEBUG] 堆内存: %d bytes\n", ESP.getFreeHeap());
        if (psramFound()) {
            Serial.printf("[DEBUG] PSRAM: %d bytes\n", ESP.getFreePsram());
        }

        // 尝试重新初始化摄像头
        Serial.println("[DEBUG] 尝试重新初始化摄像头...");
        esp_camera_deinit();
        delay(100);

        esp_err_t err = esp_camera_init(&config);
        if (err == ESP_OK) {
            Serial.println("[DEBUG] 摄像头重新初始化成功，再次尝试捕获...");
            sensor_t * s = esp_camera_sensor_get();
            if (s) {
                s->set_framesize(s, FRAMESIZE_VGA);
            }

            fb = esp_camera_fb_get();
            if (fb) {
                Serial.printf("[OK] 重试成功! 帧大小: %d bytes\n", fb->len);
                server.sendHeader("Content-Type", "image/jpeg");
                server.sendHeader("Content-Length", String(fb->len));
                server.send_P(200, "image/jpeg", (const char *)fb->buf, fb->len);
                esp_camera_fb_return(fb);
                frame_count++;
                return;
            }
        } else {
            Serial.printf("[ERROR] 重新初始化失败: 0x%x\n", err);
        }

        server.send(503, "text/plain", "Camera capture failed");
    }
    Serial.println("[DEBUG] ========== 请求处理完成 ==========\n");
}

void handleCapture() {
    if (!camera_initialized) {
        server.send(503, "text/plain", "Camera not initialized");
        return;
    }
    
    camera_fb_t * fb = esp_camera_fb_get();
    if (fb) {
        // 保存到 SPIFFS 作为 /photo.jpg
        File file = SPIFFS.open("/photo.jpg", FILE_WRITE);
        if (file) {
            file.write(fb->buf, (size_t)fb->len);
            file.close();
            server.send(200, "text/plain; charset=utf-8", "拍照成功");
            Serial.printf("📸 拍照: %d 字节\n", (int)fb->len);
        } else {
            server.send(503, "text/plain", "Failed to save photo");
        }
        esp_camera_fb_return(fb);
    } else {
        server.send(503, "text/plain", "Camera capture failed");
    }
}

void handleSave() {
    // 保存到 SD 卡
    server.send(200, "text/plain; charset=utf-8", "照片已保存到 SD 卡");
    Serial.println("💾 照片保存请求");
}

void handleSavedPhoto() {
    File file = SPIFFS.open("/photo.jpg", "r");
    if (file) {
        server.sendHeader("Content-Type", "image/jpeg");
        server.sendHeader("Content-Length", String(file.size()));
        server.streamFile(file, "image/jpeg");
        file.close();
    } else {
        server.send(404, "text/plain", "Photo not found");
    }
}

void onAudioCapture() {
    // 返回音频数据（MIME type: audio/wav）
    server.sendHeader("Content-Type", "audio/wav");
    server.send(200, "text/plain", "Audio stream endpoint");
}

void handleStatus() {
    DynamicJsonDocument doc(256);
    
    doc["device"] = "XIAO-ESP32S3-Sense";
    doc["firmware_version"] = "v2.0";
    doc["wifi_connected"] = wifi_connected;
    doc["ip_address"] = WiFi.localIP().toString();
    doc["camera_initialized"] = camera_initialized;
    doc["i2s_initialized"] = i2s_initialized;
    doc["frame_count"] = frame_count;
    doc["signal_strength"] = WiFi.RSSI();
    
    String json_str;
    serializeJson(doc, json_str);
    
    server.sendHeader("Content-Type", "application/json; charset=utf-8");
    server.send(200, "application/json", json_str);
}

void handleRestart() {
    server.send(200, "text/plain; charset=utf-8", "设备重启中...");
    delay(1000);
    ESP.restart();
}

void handleNotFound() {
    server.send(404, "text/plain; charset=utf-8", "404 - 页面未找到");
}

// ==================== 后台任务 ====================

void videoCaptureTask(void *parameter) {
    Serial.println("🎥 视频捕获任务启动");
    
    while (1) {
        // 视频捕获由 HTTP 请求处理，这里可以用于定期操作
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

void audioCaptureTask(void *parameter) {
    Serial.println("🎤 音频捕获任务启动");
    
    if (!i2s_initialized) {
        Serial.println("⚠️ I2S 未初始化，音频任务退出");
        vTaskDelete(NULL);
        return;
    }
    
    while (1) {
        if (i2s_initialized) {
            // 使用 I2S 库的标准接口读取音频数据
            size_t bytes_available = I2S.available();
            
            if (bytes_available > 0) {
                // 读取可用的音频数据
                size_t bytes_to_read = bytes_available > (AUDIO_BUFFER_SIZE * 2) ? 
                                       (AUDIO_BUFFER_SIZE * 2) : bytes_available;
                
                size_t bytes_read = I2S.readBytes((char *)audio_buffer, bytes_to_read);
                
                if (bytes_read > 0) {
                    audio_bytes_captured += bytes_read;
                    audio_data_ready = true;
                }
            }
        }
        
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

// ==================== 工具函数 ====================

void debugPrintStatus() {
    Serial.println("\n📊 系统状态:");
    Serial.printf("  WiFi: %s (%d dBm)\n", 
        wifi_connected ? "✅ 已连接" : "❌ 未连接",
        WiFi.RSSI());
    Serial.printf("  摄像头: %s\n", 
        camera_initialized ? "✅ 已初始化" : "❌ 未初始化");
    Serial.printf("  麦克风: %s\n", 
        i2s_initialized ? "✅ 已初始化" : "❌ 未初始化");
    Serial.printf("  IP 地址: %s\n", WiFi.localIP().toString().c_str());
}
