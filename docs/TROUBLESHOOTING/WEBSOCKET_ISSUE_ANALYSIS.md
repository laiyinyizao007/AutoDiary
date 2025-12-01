# WebSocket 连接问题分析报告

## 🔴 核心问题

对比参考项目（XIAO-ESP32S3-Sense）和你的项目（AutoDiary），发现以下关键问题：

### 问题1️⃣：端口号不一致 ⚠️ 【最严重】

**main.cpp 中的配置：**
```cpp
const uint16_t server_port = 8888;
// WebSocket 连接
webSocket_video.begin(server_host, server_port, "/video");      // 连接 8888
webSocket_audio.begin(server_host, server_port + 1, "/audio");  // 连接 8889
```

**integrated_server.py 中的配置：**
```python
"video_port": 8000,   # 监听 8000
"audio_port": 8001,   # 监听 8001
```

**config.json 中的配置：**
```json
"port": 8000,         # 配置 8000
```

👉 **结果：** ESP32 尝试连接 8888/8889，但服务器监听 8000/8001，所以连不上！

---

### 问题2️⃣：服务器地址配置错误

**main.cpp 中：**
```cpp
const char* server_host = "172.20.10.1";  // 这是什么 IP？
```

**config.json 中：**
```json
"host": "192.168.137.1",  // 这是什么 IP？
```

👉 **问题：** 这些 IP 地址很可能不是你当前 PC 的实际 IP 地址！

---

### 问题3️⃣：setupWebSockets() 没有返回值检查

```cpp
void setupWebSockets() {
    if (!wifi_connected) {
        Serial.println("❌ WiFi未连接，跳过WebSocket初始化");
        return;
    }
    
    // 这里只是 begin()，没有实际连接！
    webSocket_video.begin(server_host, server_port, "/video");
    webSocket_audio.begin(server_host, server_port + 1, "/audio");
    // 没有等待连接建立就返回了
}
```

👉 **问题：** begin() 是异步的，需要在 loop() 中持续调用 webSocket.loop()

---

## ✅ 参考项目为什么能工作？

**Camera_HTTP_Server_STA.ino：**
- 使用 **HTTP WebServer**（不是 WebSocket 客户端）
- 工作模式：设备创建 Web 服务器，PC 连接设备
- 只需打开浏览器访问设备 IP 即可
- 更简单、更稳定

---

## 🛠️ 修复方案

### 第一步：修复端口号

**方案A：修改 main.cpp 使用正确端口**
```cpp
const uint16_t server_port = 8000;  // 改为 8000（匹配 server.py）
// 或改为 8888，但同时修改 server.py 的监听端口
```

### 第二步：找到并配置正确的 PC IP

**Windows 上查看 IP 地址的方法：**
```bash
# 打开命令行，执行：
ipconfig /all

# 查找 IPv4 地址，格式通常是：
# 192.168.x.x
# 172.16.x.x
# 10.x.x.x
```

**重要：** 确保 PC 和 ESP32 在同一个网络上！

### 第三步：更新配置

**main.cpp：**
```cpp
const char* server_host = "192.168.1.100";  // 改为你的实际 PC IP
const uint16_t server_port = 8000;          // 改为 8000
```

**config.json：**
```json
{
  "device": {
    "server": {
      "host": "192.168.1.100",    // 改为你的实际 PC IP
      "port": 8000                 // 改为 8000
    }
  }
}
```

### 第四步：验证 WebSocket 连接

在 main.cpp 中添加更多调试信息：
```cpp
void setupWebSockets() {
    if (!wifi_connected) {
        Serial.println("❌ WiFi未连接，跳过WebSocket初始化");
        return;
    }
    
    Serial.println("\n🌐 初始化WebSocket连接...");
    Serial.printf("📍 连接地址: ws://%s:%d/video\n", server_host, server_port);
    Serial.printf("📍 音频地址: ws://%s:%d/audio\n", server_host, server_port + 1);
    
    webSocket_video.begin(server_host, server_port, "/video");
    webSocket_video.onEvent(onVideoWebSocketEvent);
    webSocket_video.setReconnectInterval(5000);
    
    webSocket_audio.begin(server_host, server_port + 1, "/audio");
    webSocket_audio.onEvent(onAudioWebSocketEvent);
    webSocket_audio.setReconnectInterval(5000);
    
    Serial.println("✅ WebSocket 初始化完成（仍在连接中...）");
}
```

---

## 🧪 测试 WebSocket 连接

### 测试1：检查服务器是否在监听

```bash
# Windows 命令行
netstat -an | findstr :8000
netstat -an | findstr :8001

# 应该看到 LISTENING 状态
```

### 测试2：使用 Python 测试服务器

```bash
# 启动 integrated_server.py
python integrated_server.py

# 应该看到：
# 视频服务器启动: ws://0.0.0.0:8000/video
# 音频服务器启动: ws://0.0.0.0:8001/audio
```

### 测试3：ESP32 串口输出

上传代码后，打开串口监视器，应该看到：
```
🌐 初始化WebSocket连接...
📍 连接地址: ws://192.168.1.100:8000/video
📍 音频地址: ws://192.168.1.100:8001/audio
✅ WebSocket 初始化完成（仍在连接中...）

// 然后定期看到：
🔄 尝试重新连接视频WebSocket...
🔄 尝试重新连接音频WebSocket...

// 最后应该看到：
🎥 视频WebSocket连接成功！
🎤 音频WebSocket连接成功！
```

---

## 📋 参考项目的启发

虽然参考项目使用 HTTP（不是 WebSocket），但它有几个优点：
- 更简单：只需 WebServer 而不是客户端
- 更稳定：HTTP 协议更成熟
- 更易调试：可以直接用浏览器测试

如果你的 WebSocket 不工作，可以考虑改为 HTTP 服务器模式（虽然这样会改变整个架构）。

---

## 🚀 推荐的修复步骤

1. **立即修复：** 改变端口号为 8000/8001
2. **找到 PC IP：** 运行 `ipconfig /all` 找到真实 IP
3. **更新 main.cpp：** 改变 server_host 和 server_port
4. **编译上传：** 使用正确配置重新上传
5. **监控输出：** 观察串口输出检查连接状态
6. **启动服务器：** 运行 `python integrated_server.py`
7. **检查日志：** 查看 integrated_server.log

---

## ⚠️ 其他可能的问题

1. **WiFi 连接不稳定**
   - 检查信号强度
   - 尝试靠近路由器

2. **防火墙阻止连接**
   - 检查 Windows 防火墙设置
   - 允许 Python 通过防火墙

3. **网络不在同一子网**
   - 确保 PC 和 ESP32 连接同一个 WiFi
   - 检查 IP 地址是否在同一网段

4. **DNS 解析问题**
   - 直接使用 IP 地址而不是域名

---

这就是你的 WebSocket 连不上的真实原因！🎯
