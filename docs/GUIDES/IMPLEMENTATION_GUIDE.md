# AutoDiary 摄像头功能实现指南

## 概述

本文档提供了基于测试结果的具体实现步骤和代码修复建议。

---

## 第一部分: 测试结果分析

### 当前状态
- ✅ ESP32 设备在线
- ✅ WiFi 已连接 (-54 dBm)
- ✅ 摄像头已初始化
- ✅ I2S 麦克风已初始化
- ❌ 视频帧获取超时 (5s read timeout)
- ❌ 拍照功能依赖帧获取失败
- ❌ 连续帧捕获失败

### 根本原因
**摄像头帧捕获性能瓶颈**：HTTP 请求时调用 `esp_camera_fb_get()` 会长时间阻塞

---

## 第二部分: 立即修复 (可部署)

### 修复 1: 使用原始 main.cpp 中的配置

**文件**: `src/main.cpp`

```cpp
// 修改 setupCamera() 函数中的帧大小配置
config.frame_size = FRAMESIZE_QVGA;      // 现有配置，可保持
config.grab_mode = CAMERA_GRAB_IFEMPTY;  // 改为 GRAB_LATEST
config.jpeg_quality = 12;                 // 保持现有
config.fb_count = 1;                      // 改为 1 (单缓冲)
```

**原因**:
- QVGA (320x240) 处理速度快
- GRAB_LATEST 避免阻塞等待帧
- 单缓冲节省内存，不会导致争用

### 修复 2: 添加超时和重试逻辑

```cpp
void handleVideoJpeg() {
    if (!camera_initialized) {
        server.send(503, "text/plain", "Camera not initialized");
        return;
    }
    
    // 添加重试逻辑
    camera_fb_t * fb = NULL;
    int max_retries = 3;
    
    for (int retry = 0; retry < max_retries; retry++) {
        fb = esp_camera_fb_get();
        if (fb) break;
        if (retry < max_retries - 1) {
            delay(10);  // 短延迟后重试
        }
    }
    
    if (fb) {
        server.sendHeader("Content-Type", "image/jpeg");
        server.sendHeader("Content-Length", String(fb->len));
        server.send_P(200, "image/jpeg", (const char *)fb->buf, fb->len);
        esp_camera_fb_return(fb);
        frame_count++;
    } else {
        Serial.println("[WARN] Frame capture failed after retries");
        server.send(503, "text/plain", "Camera timeout");
    }
}
```

### 修复 3: 简化后台任务

```cpp
void videoCaptureTask(void *parameter) {
    while (1) {
        // 不在这里获取帧，只做监控
        Serial.printf("[TASK] Heap: %d bytes\n", esp_get_free_heap_size());
        vTaskDelay(pdMS_TO_TICKS(30000));  // 每 30 秒打印一次
    }
}
```

---

## 第三部分: 中期改进 (1-2 天)

### 改进 1: 实现异步帧缓存

**目的**: 在后台持续缓存帧，HTTP 请求直接返回缓存

```cpp
// 全局变量
camera_fb_t * cached_frame = NULL;
SemaphoreHandle_t frame_lock = NULL;

// 初始化 (在 setup() 中)
frame_lock = xSemaphoreCreateMutex();

// 后台任务
void cachingTask(void *parameter) {
    while (1) {
        camera_fb_t * new_frame = esp_camera_fb_get();
        
        if (new_frame && xSemaphoreTake(frame_lock, pdMS_TO_TICKS(1000))) {
            if (cached_frame) {
                esp_camera_fb_return(cached_frame);
            }
            cached_frame = new_frame;
            xSemaphoreGive(frame_lock);
        } else if (new_frame) {
            esp_camera_fb_return(new_frame);
        }
        
        vTaskDelay(pdMS_TO_TICKS(200));  // 每 200ms 更新一次
    }
}

// HTTP 处理函数 (快速路径)
void handleVideoJpeg() {
    if (xSemaphoreTake(frame_lock, pdMS_TO_TICKS(100))) {
        if (cached_frame) {
            server.send_P(200, "image/jpeg", 
                          (const char *)cached_frame->buf, 
                          cached_frame->len);
            xSemaphoreGive(frame_lock);
            return;
        }
        xSemaphoreGive(frame_lock);
    }
    
    server.send(503, "text/plain", "No frame available");
}
```

### 改进 2: 添加详细诊断日志

```cpp
void handleStatus() {
    DynamicJsonDocument doc(512);
    
    doc["device"] = "XIAO-ESP32S3-Sense";
    doc["firmware_version"] = "v2.0";
    doc["wifi_connected"] = wifi_connected;
    doc["ip_address"] = WiFi.localIP().toString();
    doc["camera_initialized"] = camera_initialized;
    doc["frame_count"] = frame_count;
    doc["signal_strength"] = WiFi.RSSI();
    
    // 新增诊断信息
    doc["heap_free"] = esp_get_free_heap_size();
    doc["cache_size"] = cached_frame ? cached_frame->len : 0;
    doc["uptime"] = millis();
    
    String json_str;
    serializeJson(doc, json_str);
    
    server.send(200, "application/json", json_str);
}
```

---

## 第四部分: 测试验证步骤

### 步骤 1: 快速功能测试 (10 分钟)

```bash
# 1. 检查连接
curl http://192.168.1.11/status

# 2. 获取单个帧
curl -o test_frame.jpg http://192.168.1.11/video.jpg

# 3. 检查文件大小是否正常 (应该 > 1KB)
ls -lh test_frame.jpg
```

### 步骤 2: 性能测试 (5 分钟)

```bash
# Python 脚本测试
python -c "
import requests
import time

url = 'http://192.168.1.11/video.jpg'
times = []

for i in range(10):
    start = time.time()
    try:
        r = requests.get(url, timeout=3)
        elapsed = time.time() - start
        times.append(elapsed)
        print(f'Frame {i+1}: {len(r.content)} bytes, {elapsed:.3f}s')
    except Exception as e:
        print(f'Error {i+1}: {e}')

if times:
    print(f'Average: {sum(times)/len(times):.3f}s')
"
```

### 步骤 3: 运行完整测试

```bash
# 运行改进后的测试脚本
python test_camera_functionality.py 192.168.1.11 --timeout 15
```

---

## 第五部分: PSRAM 函数修复

如果编译时出现 `esp_psram_get_free_size` 不存在的错误，使用以下替代方案：

```cpp
// 方案 1: 直接移除 PSRAM 信息 (推荐，快速修复)
// 注释掉所有 esp_psram_get_free_size() 调用

// 方案 2: 使用条件编译
#ifdef CONFIG_SPIRAM
    uint32_t psram_free = esp_spiram_get_free_size();
#else
    uint32_t psram_free = 0;
#endif

// 方案 3: 检查 ESP-IDF 版本并使用相应函数
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(4, 3, 0)
    doc["free_psram"] = esp_spiram_get_free_size();
#else
    doc["free_psram"] = 0;
#endif
```

---

## 第六部分: 部署检查清单

### 编译前
- [ ] 确认 platformio.ini 中有 ArduinoJson 库
- [ ] 确认 XIAO_ESP32S3 board 定义已加载
- [ ] 检查 camera_pins.h 中 XIAO_ESP32S3 配置

### 编译后
- [ ] 编译通过无错误
- [ ] 固件大小 < 1.5 MB
- [ ] SPIFFS 分区配置正确

### 烧录后
- [ ] 连接串口监视器，查看启动日志
- [ ] 确认 WiFi 已连接
- [ ] 确认摄像头已初始化
- [ ] 确认 HTTP 服务器启动

### 功能验证
- [ ] `/status` 接口返回 200 OK
- [ ] `/video.jpg` 返回有效 JPEG 数据
- [ ] `/capture` 能保存照片
- [ ] 帧大小 > 1 KB

---

## 第七部分: 性能基准

### 预期性能指标

| 指标 | 预期值 | 备注 |
|-----|--------|------|
| 帧获取延迟 | < 500ms | 直接获取 |
| 缓存命中延迟 | < 100ms | 从缓存获取 |
| 帧大小 | 15-30 KB | QVGA JPEG |
| 帧率 | 2-5 FPS | 缓存更新频率 |
| 内存占用 | 150-200 KB | PSRAM + 堆 |

### 如果性能未达标

1. **帧获取超过 1s**: 降低分辨率到 QQVGA (160x120)
2. **缓存延迟超过 500ms**: 增加缓存任务优先级
3. **内存不足**: 关闭音频采集或降低缓冲区大小
4. **WiFi 断开**: 检查信号强度，考虑靠近路由器

---

## 第八部分: 故障排除

### 问题 1: 获取帧超时

**症状**: `/video.jpg` 返回 503 或超时

**解决方案**:
1. 检查摄像头初始化是否成功
2. 增加重试次数和延迟
3. 降低帧分辨率

```cpp
// 在 handleVideoJpeg 中
for (int retry = 0; retry < 5; retry++) {
    fb = esp_camera_fb_get();
    if (fb) break;
    delay(50);
}
```

### 问题 2: 内存不足

**症状**: 启动后不久出现重启或卡死

**解决方案**:
1. 减少后台任务数量
2. 关闭不必要的功能
3. 优化堆栈大小

```cpp
// 减少堆栈分配
xTaskCreatePinnedToCore(
    videoCaptureTask,
    "VideoCapture",
    4096,  // 降低到 4KB
    NULL,
    1,
    &videoTaskHandle,
    0
);
```

### 问题 3: WiFi 断开

**症状**: 设备连接后不久断开

**解决方案**:
1. 增加 WiFi 重连逻辑
2. 降低其他任务的 CPU 使用率

```cpp
void checkWiFi() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi disconnected, reconnecting...");
        WiFi.reconnect();
    }
}
```

### 问题 4: 拍照失败

**症状**: `/capture` 无法保存照片

**解决方案**:
1. 检查 SPIFFS 是否初始化成功
2. 检查 /photo.jpg 文件权限
3. 手动测试文件写入

```cpp
void testSPIFFS() {
    File test = SPIFFS.open("/test.txt", FILE_WRITE);
    if (test) {
        test.println("SPIFFS OK");
        test.close();
        Serial.println("SPIFFS working");
    } else {
        Serial.println("SPIFFS failed");
    }
}
```

---

## 第九部分: 代码版本对比

### 当前版本 (v2.0)
- 基础 HTTP 服务器
- 直接帧获取
- 无缓存机制

### 推荐版本 (v2.1)
- 改进的配置参数
- 异步帧缓存
- 更好的错误处理
- 详细的诊断信息

### 提交指南

```bash
# 备份当前版本
cp src/main.cpp src/main.cpp.backup

# 应用修复
# 1. 更新 setupCamera() 配置
# 2. 添加 handleVideoJpeg() 重试逻辑
# 3. 简化后台任务
# 4. 测试部署

# 如果成功，可考虑进一步优化:
# - 实现帧缓存
# - 添加诊断信息
# - 性能优化
```

---

## 参考资源

1. **ESP32-CAM 文档**: https://github.com/espressif/esp32-camera
2. **XIAO-ESP32S3 教程**: ../reference/XIAO-ESP32S3-Sense/
3. **测试报告**: ./test_results/test_report_*.json
4. **诊断报告**: ./CAMERA_TEST_DIAGNOSIS.md

---

## 总结

✅ **立即可做**: 调整帧获取配置，添加超时处理  
⏱️ **短期改进**: 实现异步缓存机制  
📊 **持续优化**: 监控和调优性能指标  

推荐顺序:
1. 应用修复 1-3 (今天)
2. 验证基本功能 (今天)
3. 应用改进 1-2 (明天)
4. 性能测试和优化 (本周)
