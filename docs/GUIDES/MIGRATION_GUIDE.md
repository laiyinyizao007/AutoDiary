# AutoDiary HTTP 改造迁移指南

## 📋 概述

AutoDiary 已成功从 **WebSocket 客户端模式** 改造为 **HTTP 服务器模式**，完全参照 XIAO-ESP32S3-Sense 参考项目的架构。

### ✨ 改造的优势

| 方面 | WebSocket 模式 | HTTP 服务器模式 |
|------|------|------|
| **连接稳定性** | ⭐⭐ (握手复杂) | ⭐⭐⭐⭐⭐ (简单可靠) |
| **易用性** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **浏览器支持** | ❌ 需要特殊库 | ✅ 所有浏览器支持 |
| **调试难度** | ⭐⭐⭐ | ⭐ 易调试 |
| **参考项目** | ❌ 无 | ✅ XIAO-ESP32S3-Sense |

---

## 🚀 快速开始

### 1️⃣ 上传 ESP32 固件

#### 方法 A: 使用 VSCode + PlatformIO

```bash
# 在项目根目录
pio run -t upload
```

#### 方法 B: 使用 Arduino IDE

1. 打开 `src/main.cpp`
2. 在 Arduino IDE 中编译上传
3. 等待上传完成

#### 查看串口输出验证固件

```
========================================
AutoDiary - HTTP 服务器模式 v2.0
基于 XIAO-ESP32S3-Sense
========================================

✅ WiFi 连接成功！
IP 地址: 192.168.1.11
...
📡 服务已启动:
🌐 访问地址: http://192.168.1.11/
📸 视频流: http://192.168.1.11/video.jpg
📊 状态接口: http://192.168.1.11/status
```

### 2️⃣ 运行 Python 后端

#### 方式 1: 直接运行

```bash
# 确保 ESP32 IP 地址正确 (可通过 config.json 配置)
python http_server.py
```

#### 方式 2: 指定 ESP32 IP

```bash
python http_server.py 192.168.1.11
```

#### 方式 3: 使用提供的脚本

```bash
# Windows
python http_server.py

# Linux/Mac
python3 http_server.py
```

### 3️⃣ 访问管理界面

#### ESP32 网页

在浏览器访问：**http://ESP32_IP/**

显示内容：
- 📸 实时视频预览
- 📊 系统状态（WiFi、摄像头、麦克风）
- 🎤 音频采集状态
- 📈 性能指标（帧率、数据量）

#### Python 服务器管理界面

在浏览器访问：**http://localhost:8080/**

显示内容：
- ✅ 服务器运行状态
- 🔌 ESP32 连接状态
- 📡 实时视频流
- 🎤 音频采集状态

---

## 📡 API 接口说明

### ESP32 HTTP API

所有接口基于 `http://ESP32_IP/`

#### 获取视频帧

```http
GET /video.jpg
Response: image/jpeg (JPEG 图像数据)
```

示例：
```bash
curl http://192.168.1.11/video.jpg > frame.jpg
```

#### 获取系统状态

```http
GET /status
Response: application/json
```

示例响应：
```json
{
  "device": "XIAO-ESP32S3-Sense",
  "firmware_version": "v2.0",
  "wifi_connected": true,
  "ip_address": "192.168.1.11",
  "camera_initialized": true,
  "i2s_initialized": true,
  "frame_count": 1234,
  "signal_strength": -45
}
```

#### 主页

```http
GET /
Response: text/html (管理界面)
```

#### 拍照预览

```http
GET /capture
Response: text/plain (返回成功信息)
```

#### 保存照片

```http
GET /save
Response: text/plain (返回保存信息)
```

### Python 服务器 HTTP API

基于 `http://localhost:8080/`

#### 获取服务器状态

```http
GET /status
Response: application/json
```

示例响应：
```json
{
  "server_running": true,
  "device_connected": true,
  "device_info": {
    "device": "XIAO-ESP32S3-Sense",
    "ip_address": "192.168.1.11",
    "firmware_version": "v2.0"
  },
  "current_time": 1701349200.123
}
```

#### 获取最新视频帧

```http
GET /video.jpg
Response: image/jpeg (缓存的最新帧)
```

---

## 🔧 配置文件说明

### config.json

```json
{
  "server": {
    "host": "0.0.0.0",    // 监听地址
    "port": 8080           // 监听端口
  },
  "esp32_ip": "192.168.1.11",  // ESP32 IP 地址（重要！）
  "features": {
    "funasr_enabled": true,     // 启用语音识别
    "intelligent_analysis": true // 启用智能分析
  },
  "funasr": {
    "model_name": "paraformer-zh",
    "device": "cuda",     // 或 "cpu"
    "sample_rate": 16000
  }
}
```

### 修改 ESP32 IP

编辑 `config.json`，找到：

```json
"esp32_ip": "192.168.1.11"
```

改为你的 ESP32 IP，例如：

```json
"esp32_ip": "192.168.1.100"
```

### 修改 WiFi 配置

编辑 `src/main.cpp`，找到：

```cpp
const char* ssid = "ChinaNet-YIJU613";
const char* password = "7ep58315";
```

改为你的 WiFi 信息：

```cpp
const char* ssid = "Your-SSID";
const char* password = "Your-Password";
```

---

## 🐛 故障排查

### ❌ 无法连接到 ESP32

**检查清单：**

1. ✅ ESP32 已上传新固件
2. ✅ ESP32 已连接 WiFi（检查串口输出）
3. ✅ PC 和 ESP32 在同一网络
4. ✅ 检查 ESP32 IP 地址（在 `config.json` 中）
5. ✅ 在浏览器测试：`http://ESP32_IP/` 是否能访问

**解决方案：**

```bash
# 1. 检查网络连通性
ping 192.168.1.11

# 2. 直接在浏览器打开 ESP32 主页
# http://192.168.1.11/

# 3. 检查串口输出获取正确的 IP 地址
```

### ❌ Python 服务器无法获取视频

**检查清单：**

1. ✅ 检查 ESP32 是否在线（访问 `/status`)
2. ✅ 检查摄像头是否初始化成功
3. ✅ 检查网络连接

**解决方案：**

```bash
# 查看 http_server.log
tail -f http_server.log

# 或者用 curl 测试
curl http://192.168.1.11/video.jpg > test.jpg
file test.jpg
```

### ❌ 固件编译失败

**常见原因：**

1. 缺少必要的库
2. Arduino 框架版本不兼容

**解决方案：**

```bash
# 更新库
pio lib update

# 清理构建缓存
pio run -t clean

# 重新编译
pio run -t upload
```

---

## 📊 性能指标

### 典型配置性能

- **视频帧率**: 15-20 FPS @ 640x480 JPEG
- **延迟**: ~100-200ms
- **带宽**: 200-500 KB/s (取决于 WiFi 信号)
- **内存占用**: ~80% (PSRAM)

### 优化建议

1. 增加 WiFi 信号强度（接近路由器）
2. 减少其他 WiFi 设备数量
3. 调整 JPEG 质量（在 `src/main.cpp` 中）

```cpp
config.jpeg_quality = 12;  // 0-63，数字越小质量越好
```

---

## 📚 相关文档

- **ARCHITECTURE_COMPARISON.md** - 架构对比分析
- **README.md** - 项目说明
- **platformio.ini** - PlatformIO 配置

---

## 🎯 下一步计划

1. ✅ HTTP 服务器模式改造（已完成）
2. ⏳ WebRTC 实时流传输（可选）
3. ⏳ 多设备支持（可选）
4. ⏳ 加密安全连接（可选）

---

## 📞 常见问题

### Q: 能否同时连接多个客户端？

**A:** 可以。HTTP 服务器支持多客户端并发访问，但视频帧是共享的（最新一帧）。

### Q: WebSocket 模式怎么办？

**A:** WebSocket 模式已弃用。HTTP 服务器模式更稳定可靠。

### Q: 如何启用 HTTPS？

**A:** 目前不支持。可以在反向代理（如 Nginx）中配置 SSL。

### Q: 为什么改用 HTTP 而不是 WebSocket？

**A:** 
1. 参考项目 (XIAO-ESP32S3-Sense) 使用 HTTP 服务器模式
2. HTTP 握手简单，更容易调试
3. 浏览器原生支持，无需特殊库
4. 稳定性和兼容性更好

---

## 🎉 改造完成！

你的 AutoDiary 项目现已采用稳定的 HTTP 服务器模式运行！

**接下来你可以：**

1. 🎥 实时查看视频流
2. 🎤 采集音频数据进行语音识别
3. 🤖 使用 FunASR 进行实时转录
4. 📊 分析和总结日记内容

**祝你使用愉快！** 🚀
