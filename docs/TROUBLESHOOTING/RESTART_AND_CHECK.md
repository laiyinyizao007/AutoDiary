# ESP32 重启并检查 WebSocket 连接 🔄

## 🎯 重启步骤

### 步骤 1：重启 ESP32 设备

**有三种方法可以重启 ESP32：**

#### 方法 A：物理重启（最可靠）
1. 拔掉 ESP32 的 USB 线
2. 等待 3 秒
3. 重新插入 USB 线
4. 设备将自动启动并开始初始化

#### 方法 B：按下复位按钮
1. 在 XIAO ESP32S3 开发板上找到 Reset 按钮
2. 按下 Reset 按钮
3. 设备将重新启动

#### 方法 C：通过 PlatformIO 重启
```bash
pio device monitor -e seeed_xiao_esp32s3 --baud 115200
# 在监视器界面中，按 Ctrl+T，然后按 R（或按两次 Ctrl+D）
```

---

## 📊 检查清单

### ✅ 检查 1：ESP32 串口输出

**打开串口监视器：**
```bash
cd c:\Dev\projects\AutoDiary\AutoDiary
pio device monitor -e seeed_xiao_esp32s3 --baud 115200
```

**预期看到的输出（按顺序）：**

1. **启动信息**
   ```
   ets Jun  8 2016 00:22:57 rst:0x1 (POWERON_RESET),boot:0x28 (SPI_FAST_BOOT)
   ```

2. **初始化过程**
   ```
   ========================================
   AutoDiary - 调试版本 v1.0-debug
   ========================================
   固件版本: v1.0-debug
   编译时间: Nov 29 2025 ...
   正在初始化系统...
   
   🔧 开始初始化硬件组件...
   
   1️⃣ 初始化WiFi...
   连接WiFi...
   SSID: ChinaNet-YIJU613
   连接中...
   ✅ WiFi连接成功！
   IP地址: 192.168.1.XXX
   信号强度: -XX dBm
   
   📷 初始化摄像头...
   ✅ 摄像头初始化成功！
   
   🎤 初始化I2S麦克风...
   ✅ I2S麦克风初始化成功！
   
   🌐 初始化WebSocket连接...
   连接视频WebSocket: 192.168.1.5:8000/video
   连接音频WebSocket: 192.168.1.5:8001/audio
   ✅ WebSocket连接初始化完成
   
   🚀 创建任务...
   🎥 视频捕获任务已启动
   🎤 音频捕获任务已启动
   
   ✅ 系统初始化完成！
   
   📡 等待连接服务器...
   🎥 视频服务器: ws://192.168.1.5:8000/video
   🎤 音频服务器: ws://192.168.1.5:8001/audio
   ```

3. **连接过程（关键！）**
   ```
   📊 定期状态报告:
   WiFi连接: ✅ 已连接
   摄像头: ✅ 已初始化
   视频WebSocket: ❌ 未连接    <- 这个会变成 ✅
   音频WebSocket: ❌ 未连接    <- 这个也会变成 ✅
   
   🔄 尝试重新连接视频WebSocket...
   🔄 尝试重新连接音频WebSocket...
   
   // 几秒钟后（最重要的部分！）：
   🎥 视频WebSocket连接成功！
   📱 发送设备信息: {...}
   
   🎤 音频WebSocket连接成功！
   🎵 发送音频配置: {...}
   ```

4. **数据流开始**
   ```
   📸 视频统计: 30帧, 15.0fps, 图像大小: 25000 bytes
   🎵 音频统计: 发送 16000 样本 (1.0秒), 数据大小: 32000 bytes
   💓 发送心跳包...
   ```

**⚠️ 问题排查：**
- 如果看到 `❌ WiFi连接失败!` → 检查 WiFi 密码
- 如果看到频繁的 `🔄 尝试重新连接` → 检查 PC IP 地址
- 如果没有 `视频WebSocket连接成功` → 检查服务器是否运行

---

### ✅ 检查 2：Python 服务器日志

**在另一个终端查看服务器日志：**
```bash
# 方法 1：实时查看日志
Get-Content websocket_compatible_server.log -Wait -Tail 50

# 方法 2：查看最新的日志
type websocket_compatible_server.log

# 方法 3：统计日志行数
(Get-Content websocket_compatible_server.log | Measure-Object -Line).Lines
```

**预期看到的日志（设备连接时）：**

```
============================================================
🚀 AutoDiary 兼容 WebSocket 服务器启动
============================================================
🎥 视频服务器启动: ws://0.0.0.0:8000/video
🎤 音频服务器启动: ws://0.0.0.0:8001/audio
✅ 所有服务器已启动，等待设备连接...

// 设备连接后，你会看到：
2025-11-29 19:XX:XX INFO - 🎥 视频客户端已连接: 192.168.1.XXX
2025-11-29 19:XX:XX INFO - 📨 视频消息: device_info
2025-11-29 19:XX:XX INFO - 📱 设备信息: XIAO_ESP32S3_SENSE_DEBUG

2025-11-29 19:XX:XX INFO - 🎤 音频客户端已连接: 192.168.1.XXX
2025-11-29 19:XX:XX INFO - 📨 音频消息: audio_config
2025-11-29 19:XX:XX INFO - 🎤 音频配置: 16000Hz, 1ch

// 数据流开始：
2025-11-29 19:XX:XX INFO - 📸 图像已保存: autodiary_20251129_195245.jpg (25000 bytes)
2025-11-29 19:XX:XX INFO - 📸 图像已保存: autodiary_20251129_195315.jpg (25000 bytes)
2025-11-29 19:XX:XX DEBUG - 💓 收到视频心跳
2025-11-29 19:XX:XX DEBUG - 💓 收到音频心跳

// 定期状态报告（每 30 秒）：
2025-11-29 19:XX:XX INFO - 📊 系统状态: {"device_connected": true, 
                                      "video_clients": 1, 
                                      "audio_clients": 1, 
                                      "audio_buffer_size": 50, 
                                      "image_size": 25000}
```

**⚠️ 问题排查：**
- 如果没有看到连接日志 → 服务器可能未运行或被防火墙阻止
- 如果看到错误日志 → 查看具体错误信息
- 如果只有一个客户端连接 → 可能是音频或视频某一个未连接

---

### ✅ 检查 3：文件是否被保存

**在 PowerShell 中运行：**

```bash
# 1. 检查 Images 目录中的文件数量和大小
Get-ChildItem data/Images/ | Sort-Object LastWriteTime -Descending | Select-Object -First 5

# 预期输出应该是：
# Directory: C:\Dev\projects\AutoDiary\AutoDiary\data\Images
#
# Mode                LastWriteTime         Length Name
# ----                -------------         ------ ----
# -a---  11/29/2025 19:XX:XX          25000 autodiary_20251129_195315.jpg
# -a---  11/29/2025 19:XX:XX          25000 autodiary_20251129_195245.jpg

# 2. 统计总共有多少张图像
(Get-ChildItem data/Images/ | Measure-Object).Count

# 3. 统计总大小
"{0:N2} MB" -f ((Get-ChildItem data/Images/ | Measure-Object -Sum Length).Sum / 1MB)

# 4. 监测文件的实时变化
Get-ChildItem data/Images/ -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 10
```

**预期结果：**
- ✅ `data/Images/` 目录中应该有多个 `.jpg` 文件
- ✅ 文件按时间戳命名（如 `autodiary_20251129_195245.jpg`）
- ✅ 每 30 秒应该新增一个文件
- ✅ 每个文件大小约 20-30 KB

**如果没有文件被保存：**
- 检查 ESP32 是否真的连接到服务器
- 检查服务器是否在运行
- 检查 data 目录的写入权限

---

### ✅ 检查 4：网络连通性

**验证设备和 PC 之间的连接：**

```bash
# 1. 查看 ESP32 的 IP（从串口输出中获取）
# 例如：192.168.1.100

# 2. 从 PC ping ESP32（确保网络连通）
ping 192.168.1.100

# 预期输出：
# Pinging 192.168.1.100 with 32 bytes of data:
# Reply from 192.168.1.100: bytes=32 time=50ms TTL=255
# Reply from 192.168.1.100: bytes=32 time=45ms TTL=255

# 3. 查看网络连接
netstat -an | findstr :8000
netstat -an | findstr :8001

# 预期输出：
# TCP    0.0.0.0:8000           0.0.0.0:*               LISTENING
# TCP    0.0.0.0:8001           0.0.0.0:*               LISTENING
```

---

## 📋 完整的检查顺序

### 第一步（0-10 秒）：物理重启
1. 拔掉 USB 线
2. 等待 3 秒
3. 插入 USB 线

### 第二步（10-30 秒）：观察 ESP32 启动
```bash
pio device monitor -e seeed_xiao_esp32s3 --baud 115200
```
✅ 应该看到初始化完成，WebSocket 初始化完成

### 第三步（30-60 秒）：等待连接建立
继续观察串口输出，应该看到：
- 🎥 视频WebSocket连接成功！
- 🎤 音频WebSocket连接成功！

### 第四步（60+ 秒）：检查服务器日志
```bash
Get-Content websocket_compatible_server.log -Tail 20
```
✅ 应该看到设备连接的日志

### 第五步（90+ 秒）：检查文件保存
```bash
Get-ChildItem data/Images/ | Sort-Object LastWriteTime -Descending | Select-Object -First 5
```
✅ 应该看到新保存的图像文件

---

## 🎯 成功的标志

当你看到以下现象时，说明 WebSocket 连接已成功建立：

✅ **ESP32 串口输出：**
```
🎥 视频WebSocket连接成功！
🎤 音频WebSocket连接成功！
📸 视频统计: 30帧, 15.0fps, 图像大小: 25000 bytes
🎵 音频统计: 发送 16000 样本
```

✅ **Python 服务器日志：**
```
🎥 视频客户端已连接: 192.168.1.XXX
🎤 音频客户端已连接: 192.168.1.XXX
📸 图像已保存: autodiary_20251129_195245.jpg
```

✅ **文件系统：**
```
data/Images/ 目录中有新增的 .jpg 文件
每 30 秒一个新文件
```

✅ **网络连通性：**
```
ESP32 的 IP: 192.168.1.XXX (可以 ping 通)
PC 的 IP: 192.168.1.5
在同一子网 192.168.1.0/24
```

---

## ⚠️ 常见问题排查

### 问题 1：ESP32 没有连接到 WiFi
**症状：** 串口显示 "❌ WiFi连接失败"
**解决方案：**
```cpp
// 检查 main.cpp 中的 WiFi 配置
const char* ssid = "ChinaNet-YIJU613";
const char* password = "7ep58315";
```
- 确保 SSID 和密码正确
- 检查 WiFi 信号强度
- 尝试靠近路由器

### 问题 2：WebSocket 连接失败
**症状：** 串口显示频繁的 "🔄 尝试重新连接..."
**解决方案：**
1. 确认 PC IP 是 192.168.1.5
   ```bash
   ipconfig | findstr "IPv4"
   ```

2. 确认 main.cpp 中的地址正确
   ```cpp
   const char* server_host = "192.168.1.5";
   const uint16_t server_port = 8000;
   ```

3. 确认服务器在运行
   ```bash
   netstat -an | findstr :8000
   ```

4. 检查防火墙
   - Windows 防火墙应该允许 Python 应用
   - 应该允许端口 8000/8001

### 问题 3：服务器没有收到连接
**症状：** 服务器日志中没有连接信息
**解决方案：**
1. 确认 compatible_websocket_server_v2.py 正在运行
2. 查看 websocket_compatible_server.log
3. 检查是否有错误信息
4. 尝试重启服务器

### 问题 4：文件没有被保存
**症状：** data/Images/ 目录为空
**解决方案：**
1. 确认设备已连接（查看服务器日志）
2. 确认 data 目录有写入权限
3. 检查磁盘空间是否充足
4. 查看完整的服务器日志获取错误信息

---

## 📞 获取帮助

如果问题仍未解决，请收集以下信息：

1. **ESP32 串口输出（全部）**
   - 从启动到至少 2 分钟后

2. **服务器日志**
   ```bash
   type websocket_compatible_server.log > log_output.txt
   ```

3. **系统信息**
   ```bash
   ipconfig /all > network_info.txt
   netstat -an | findstr :8000 > port_info.txt
   ```

4. **当前状态**
   - ESP32 是否开启
   - 服务器是否运行
   - WiFi 是否连接

---

## 📚 相关文档

- **WEBSOCKET_ISSUE_ANALYSIS.md** - 问题分析
- **WEBSOCKET_FIX_COMPLETE.md** - 完整修复总结
- **VERIFICATION_GUIDE.md** - 验证指南

---

**祝重启成功！** 🚀
