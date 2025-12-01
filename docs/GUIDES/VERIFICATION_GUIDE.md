# WebSocket 连接验证指南 🔍

## 当前状态 ✅

| 组件 | 状态 |
|------|------|
| 代码修复 | ✅ 完成 |
| 代码编译 | ✅ 成功 |
| 代码上传 | ✅ 成功 |
| Python 服务器 | ✅ 运行中 |
| 服务器端口 | ✅ 8000/8001 监听中 |

---

## 🎯 验证 WebSocket 连接的方法

### 方法一：查看 Python 服务器日志

**当前 Python 服务器日志显示：**
```
INFO:websockets.server:server listening on 0.0.0.0:8000
INFO:__main__:视频服务器启动: ws://0.0.0.0:8000/video
INFO:websockets.server:server listening on 0.0.0.0:8001
INFO:__main__:音频服务器启动: ws://0.0.0.0:8001/audio
INFO:camera_web_server:Web服务器启动成功: http://0.0.0.0:8080
INFO:websockets.server:server listening on 0.0.0.0:8002
INFO:camera_web_server:WebSocket服务器启动成功: ws://0.0.0.0:8002
```

✅ **服务器已准备好接收设备连接！**

---

### 方法二：监控 ESP32 串口输出

设备启动后，你应该在串口监视器中看到：

```
========================================
AutoDiary - 调试版本 v1.0-debug
========================================

🔧 开始初始化硬件组件...

1️⃣ 初始化WiFi...
连接WiFi...
SSID: ChinaNet-YIJU613
连接中.................
✅ WiFi连接成功！
IP地址: 192.168.1.XXX
信号强度: -XX dBm

📷 初始化摄像头...
✅ 摄像头初始化成功！
摄像头型号: OV2640
分辨率: 640x480

🎤 初始化I2S麦克风...
✅ I2S麦克风初始化成功！

🌐 初始化WebSocket连接...
初始化WebSocket连接...
连接视频WebSocket: 192.168.1.5:8000/video
连接音频WebSocket: 192.168.1.5:8001/audio
✅ WebSocket连接初始化完成

🚀 创建任务...

✅ 系统初始化完成！

📡 等待连接服务器...
🎥 视频服务器: ws://192.168.1.5:8000/video
🎤 音频服务器: ws://192.168.1.5:8001/audio
```

---

### 方法三：查看连接建立的证据

**在 Python 服务器日志中，你会看到：**

```
// 当设备连接时：
INFO:websockets.server:connection received from 192.168.1.XXX
INFO:__main__:视频客户端连接: video_xxxxxxxxxxxxxxxxx
INFO:__main__:设备信息更新: {'type': 'device_info', 'device': 'XIAO_ESP32S3_SENSE_DEBUG', ...}

INFO:websockets.server:connection received from 192.168.1.XXX
INFO:__main__:音频客户端连接: audio_xxxxxxxxxxxxxxxxx
INFO:__main__:设备信息更新: {'type': 'audio_config', 'sample_rate': 16000, ...}

// 定期心跳：
INFO:__main__:收到设备心跳 (video)
INFO:__main__:收到设备心跳 (audio)

// 数据流：
INFO:__main__:图像已保存: autodiary_20251129_195245.jpg
INFO:__main__:实时音频处理结果: ...
```

---

## ⚡ 快速检查清单

### ✅ 立即检查

1. **ESP32 设备是否开启？**
   - 如果设备还在上传后重启，等待 10-30 秒

2. **WiFi 连接是否正常？**
   - 查看串口输出：是否显示 "✅ WiFi连接成功"

3. **IP 地址是否匹配？**
   - 串口输出中的 IP：应该是 192.168.1.XXX
   - PC 的 IP：192.168.1.5
   - 应该在同一个 192.168.1.0 子网

4. **服务器是否还在运行？**
   - Python 进程是否还活着
   - 控制台是否还在输出日志

---

## 🔧 故障排除

### 问题 1：ESP32 连接失败（串口显示频繁重连尝试）

**检查项：**
1. WiFi 密码是否正确
   ```cpp
   const char* ssid = "ChinaNet-YIJU613";
   const char* password = "7ep58315";
   ```

2. 检查 WiFi 信号强度
   - 串口输出中的 RSSI 值应该在 -40 到 -60 dBm 之间
   - 如果小于 -80，说明信号太弱

3. 确认 ESP32 获得了 IP
   - 串口输出中应该显示 "IP地址: 192.168.1.XXX"

---

### 问题 2：WebSocket 连接失败

**检查项：**
1. 确认 Python 服务器还在运行
   ```bash
   netstat -an | findstr :8000
   netstat -an | findstr :8001
   ```
   应该看到 `LISTENING` 状态

2. 确认防火墙没有阻止
   - Windows 防火墙允许 Python 应用
   - 允许端口 8000 和 8001

3. 检查网络连通性
   - 在 PC 上 ping ESP32 的 IP
   - 在 ESP32 上 ping PC 的 IP（通过添加代码）

---

### 问题 3：数据没有被保存

**检查项：**
1. 检查 data 目录是否创建
   ```bash
   dir data/Images
   dir data/Audio
   dir data/Transcriptions
   ```

2. 检查服务器权限
   - data 目录是否有写入权限

3. 查看服务器日志
   ```bash
   type integrated_server.log
   ```

---

## 📊 测试完整流程

### 第一阶段：初始化测试（预期：10-30 秒）
1. ✅ 设备上电
2. ✅ WiFi 连接建立
3. ✅ 摄像头初始化
4. ✅ I2S 初始化
5. ✅ WebSocket 连接建立

**预期输出：**
- 串口显示所有初始化成功
- Python 服务器日志显示连接接收
- 文件系统已准备好

---

### 第二阶段：数据流测试（预期：持续运行）
1. ✅ 视频帧开始发送
2. ✅ 音频数据开始发送
3. ✅ 图像定期保存到 data/Images/
4. ✅ 心跳包定期发送

**预期输出：**
- 串口显示帧率和 FPS 统计
- 音频样本计数增加
- 服务器日志显示数据接收
- data/Images 目录中出现新文件

---

### 第三阶段：稳定性测试（预期：持续数小时）
1. ✅ 连接保持稳定
2. ✅ 没有频繁重连
3. ✅ 数据持续流动
4. ✅ 日志文件正常更新

**预期输出：**
- 每 10 秒一次心跳日志
- 每 30 秒一次图像保存日志
- 没有错误或异常日志

---

## 💡 调试技巧

### 1. 实时监控服务器日志
```bash
# 在另一个终端查看实时日志
Get-Content integrated_server.log -Wait -Tail 50
```

### 2. 检查文件生成
```bash
# 监控 Images 目录的变化
Get-ChildItem data/Images/ -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 10
```

### 3. 分析性能
```bash
# 检查图像大小和数量
Get-ChildItem data/Images/ | Measure-Object -Sum Length -Average
```

### 4. 测试网络连通性
```bash
# 检查 ESP32 是否能 ping 通 PC
# 在 ESP32 代码中添加：
# Serial.println(WiFi.ping(WiFi.gatewayIP()));

# 从 PC ping ESP32
ping 192.168.1.XXX  # 替换为 ESP32 的 IP
```

---

## 🎯 成功的标志

当你看到以下现象时，说明 WebSocket 连接已成功建立：

✅ **串口输出：**
```
🎥 视频WebSocket连接成功！
🎤 音频WebSocket连接成功！
📸 视频统计: 30帧, 15.0fps, 图像大小: 25000 bytes
🎵 音频统计: 16000 样本
```

✅ **Python 服务器日志：**
```
INFO:__main__:视频客户端连接: video_xxxxxxxxx
INFO:__main__:音频客户端连接: audio_xxxxxxxxx
INFO:__main__:图像已保存: autodiary_20251129_195245.jpg
```

✅ **文件系统：**
```
data/Images/
  └── autodiary_20251129_195245.jpg  (不断增加)
  └── autodiary_20251129_195315.jpg
  └── ...

data/Transcriptions/
  └── realtime_20251129_195300.json  (如果启用了语音识别)
```

---

## 📞 获取帮助

如果仍有问题，请：

1. **查看完整的分析报告：**
   ```
   WEBSOCKET_ISSUE_ANALYSIS.md
   ```

2. **查看详细的修复总结：**
   ```
   FIX_SUMMARY.md
   ```

3. **检查所有日志文件：**
   - `integrated_server.log` - Python 服务器日志
   - `autodiary_server.log` - 备用日志
   - `data/Logs/` - 详细日志目录

4. **常见问题检查：**
   - WiFi 密码正确吗？
   - PC IP 地址是 192.168.1.5 吗？
   - ESP32 获得 IP 了吗？
   - 防火墙允许 Python 了吗？

---

## 🚀 下一步

一旦 WebSocket 连接稳定工作，你可以：

1. **启用语音识别（FunASR）**
   ```bash
   pip install funasr
   ```

2. **集成图像识别**
   - 配置 intelligent_analyzer.py

3. **设置 Web 界面**
   - 访问 http://localhost:8080 查看摄像头直播

4. **配置数据存储**
   - 调整 config.json 中的数据保留策略
   - 设置备份和同步

---

**祝你成功！** 🎉
