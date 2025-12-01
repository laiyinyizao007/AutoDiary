# C++ 服务器崩溃修复报告

## 问题诊断

通过分析 `src/main.cpp` 代码，发现了以下导致服务器崩溃的关键问题：

### 1. **SPIFFS 文件系统未初始化** ❌
- **问题**：代码在 `handleCapture()` 中尝试保存文件到 SPIFFS，但 `setup()` 函数中未初始化 SPIFFS
- **影响**：文件保存操作会崩溃或返回空指针异常
- **修复**：在 `setup()` 中添加 `SPIFFS.begin(true)`

```cpp
Serial.println("1️⃣ 初始化 SPIFFS...");
if (!SPIFFS.begin(true)) {
    Serial.println("⚠️ SPIFFS 初始化失败，继续运行");
} else {
    Serial.println("✅ SPIFFS 初始化成功");
}
```

### 2. **I2S API 调用不正确** ❌
- **问题**：使用了不存在的 `esp_i2s::i2s_read()` 函数
  ```cpp
  esp_i2s::i2s_read(
      esp_i2s::I2S_NUM_0,
      audio_buffer,
      AUDIO_BUFFER_SIZE * 2,
      &bytes_read,
      pdMS_TO_TICKS(100)
  );
  ```
- **影响**：编译失败或运行时崩溃（undefined reference）
- **修复**：使用 Arduino I2S 库的标准接口
  ```cpp
  size_t bytes_available = I2S.available();
  if (bytes_available > 0) {
      size_t bytes_to_read = bytes_available > (AUDIO_BUFFER_SIZE * 2) ? 
                             (AUDIO_BUFFER_SIZE * 2) : bytes_available;
      size_t bytes_read = I2S.readBytes((char *)audio_buffer, bytes_to_read);
  }
  ```

### 3. **任务堆栈大小不足** ⚠️
- **问题**：视频和音频任务堆栈仅为 4096 字节
- **影响**：处理 JSON 序列化、文件操作时可能堆栈溢出
- **修复**：增加到 8192 字节
  ```cpp
  xTaskCreatePinnedToCore(
      videoCaptureTask,
      "VideoCapture",
      8192,  // 从 4096 增加到 8192
      NULL,
      2,
      &videoTaskHandle,
      1
  );
  ```

### 4. **缺少任务创建错误检查** ⚠️
- **问题**：没有验证任务是否成功创建
- **影响**：任务创建失败时无法感知
- **修复**：添加错误检查
  ```cpp
  if (videoTaskHandle == NULL) {
      Serial.println("❌ 视频任务创建失败!");
  }
  ```

### 5. **WebServer.send_P() 参数格式错误** ⚠️
- **问题**：`server.send_P()` 用于发送 PROGMEM 数据，但参数顺序不正确
- **影响**：可能导致内存访问错误
- **修复**：保持现有代码，确保参数格式正确（已验证为正确用法）

## 修复清单

- [x] 初始化 SPIFFS 文件系统
- [x] 修复 I2S 音频读取 API 调用
- [x] 增加任务堆栈大小（4096 → 8192）
- [x] 添加任务创建错误检查
- [x] 保留所有必要的错误处理

## 代码改进详情

### setup() 函数改进
```cpp
// 添加 SPIFFS 初始化
Serial.println("1️⃣ 初始化 SPIFFS...");
if (!SPIFFS.begin(true)) {
    Serial.println("⚠️ SPIFFS 初始化失败，继续运行");
} else {
    Serial.println("✅ SPIFFS 初始化成功");
}

// 增加任务堆栈大小并添加错误检查
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
```

### audioCaptureTask() 函数改进
```cpp
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
```

## 测试建议

### ✅ 编译测试（已完成）
```bash
pio run -e seeed_xiao_esp32s3
```
**结果：编译成功！** ✅
- RAM: 15.7% used (51360 bytes from 327680 bytes)
- Flash: 25.3% used (846257 bytes from 3342336 bytes)
- Binary: firmware.bin created successfully

### 上传测试（待执行）
烧写到设备并观察日志输出：
```bash
pio run -e seeed_xiao_esp32s3 -t upload
```

### 功能测试（待执行）
- [ ] 检查 SPIFFS 初始化是否成功
- [ ] 验证 WiFi 连接状态
- [ ] 测试摄像头视频流
- [ ] 验证照片保存功能
- [ ] 测试音频采集
- [ ] 检查系统状态接口

### 稳定性测试（待执行）
- [ ] 持续运行 30 分钟以上
- [ ] 频繁访问 HTTP 接口
- [ ] 监控内存使用情况
- [ ] 检查任务堆栈溢出

## 预期效果

修复后，服务器应该：
- ✅ 正常初始化所有硬件模块
- ✅ 稳定处理 HTTP 请求
- ✅ 成功保存摄像头照片
- ✅ 稳定采集音频数据
- ✅ 不再出现崩溃或栈溢出

## 文件修改日期

- 修复时间：2025-11-30 01:32:52
- 修复文件：`src/main.cpp`
- 修复版本：v2.0.1
