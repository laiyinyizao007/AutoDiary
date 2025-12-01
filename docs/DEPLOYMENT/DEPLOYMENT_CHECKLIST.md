# AutoDiary 部署检查清单

## 🚀 部署前检查

### 环境准备
- [ ] Windows 11 操作系统
- [ ] VS Code 已安装 PlatformIO 扩展
- [ ] Python 3.8+ 已安装并添加到 PATH
- [ ] Git 已安装（可选）

### 硬件准备
- [ ] XIAO ESP32S3 Sense 开发板
- [ ] USB-C 数据线
- [ ] 稳定的 WiFi 网络
- [ ] PC 服务器（运行 Python 服务器）

## 📋 软件配置步骤

### 1. 设备端配置
- [ ] 编辑 `src/main.cpp`，修改 WiFi 配置：
  ```cpp
  const char* ssid = "你的WiFi名称";
  const char* password = "你的WiFi密码";
  ```
- [ ] 确认服务器 IP 地址正确：
  ```cpp
  const char* server_host = "192.168.137.1";  // 修改为你的PC IP
  ```

### 2. 服务器端配置
- [ ] 安装 Python 依赖：
  ```bash
  pip install -r requirements.txt
  ```
- [ ] 确认 `config.json` 中的服务器配置正确
- [ ] 检查防火墙设置，允许端口 8000

### 3. 编译和上传
在 VS Code 终端中执行：
- [ ] 编译项目：
  ```bash
  pio run -e seeed_xiao_esp32s3_sense
  ```
- [ ] 上传到设备：
  ```bash
  pio run --target upload -e seeed_xiao_esp32s3_sense
  ```

### 4. 启动服务器
- [ ] 方法1：使用启动脚本
  ```bash
  start_server.bat
  ```
- [ ] 方法2：直接运行
  ```bash
  python server.py
  ```

## 🔍 系统验证

### 设备端验证
- [ ] 设备正常启动，串口输出显示初始化信息
- [ ] WiFi 连接成功，显示 IP 地址
- [ ] 摄像头初始化成功
- [ ] PDM 麦克风初始化成功
- [ ] WebSocket 连接建立成功

### 服务器端验证
- [ ] 服务器成功启动，监听端口 8000
- [ ] 视频客户端连接成功
- [ ] 音频客户端连接成功
- [ ] 开始接收数据流
- [ ] 图像自动保存到 `data/Images/` 目录
- [ ] 音频数据正常缓存

### 功能验证
- [ ] 每30秒自动保存一张图片
- [ ] 图片命名格式正确：`autodiary_YYYYMMDD_HHMMSS.jpg`
- [ ] 音频数据正常接收和缓存
- [ ] 心跳包正常发送和接收
- [ ] 日志文件正常生成

## 🛠️ 故障排除

### 常见问题及解决方案

1. **编译错误**
   - 检查 PlatformIO 库依赖是否正确安装
   - 确认板型配置为 `seeed_xiao_esp32s3_sense`
   - 清理构建缓存：`pio run -t clean`

2. **WiFi 连接失败**
   - 检查 SSID 和密码是否正确
   - 确认 WiFi 信号强度
   - 检查是否启用了 MAC 地址过滤

3. **WebSocket 连接失败**
   - 确认服务器 IP 地址正确
   - 检查端口 8000 是否被占用
   - 确认防火墙设置

4. **摄像头初始化失败**
   - 检查硬件连接
   - 确认 PSRAM 配置
   - 重新插拔摄像头模块

5. **音频采集失败**
   - 检查 PDM 麦克风连接
   - 确认引脚配置
   - 调整采样率参数

### 调试命令

```bash
# 查看详细编译信息
pio run -e seeed_xiao_esp32s3_sense -v

# 监控串口输出
pio device monitor -e seeed_xiao_esp32s3_sense --baud 115200

# 测试网络连接
ping 192.168.137.1

# 检查端口占用
netstat -an | findstr :8000
```

## 📊 性能监控

### 关键指标
- [ ] 视频帧率：目标 15fps
- [ ] 音频采样率：16kHz
- [ ] 图像大小：约 20-50KB（JPEG压缩）
- [ ] 内存使用：PSRAM 利用率 < 80%
- [ ] 网络延迟：< 100ms

### 优化建议
- 调整摄像头质量以平衡图像质量和传输速度
- 优化音频缓冲区大小以减少延迟
- 使用 5GHz WiFi 网络减少干扰
- 定期清理旧数据文件

## 📁 文件结构验证

确认以下文件和目录已正确创建：

```
AutoDiary/
├── platformio.ini          ✅ PlatformIO 配置
├── src/main.cpp           ✅ 设备端主程序
├── include/camera_pins.h  ✅ 摄像头引脚配置
├── server.py              ✅ Python 服务器
├── requirements.txt       ✅ Python 依赖
├── config.json           ✅ 系统配置
├── start_server.bat      ✅ 服务器启动脚本
├── README.md             ✅ 项目文档
├── DEPLOYMENT_CHECKLIST.md ✅ 部署检查清单
└── data/                 ✅ 数据存储目录
    ├── Images/           ✅ 图像存档
    ├── Audio/            ✅ 音频缓存
    └── Logs/             ✅ 系统日志
```

## 🎯 部署完成

当以上所有检查项都完成后，系统已成功部署！

### 下一步
- 监控系统运行状态
- 根据需要调整配置参数
- 考虑集成 Whisper AI 进行语音识别
- 开发 Web 界面查看 lifelog 数据

### 技术支持
如果遇到问题，请：
1. 查看设备串口输出
2. 检查服务器日志文件 `autodiary_server.log`
3. 参考 README.md 中的故障排除部分
4. 确认网络连接和硬件状态

---

**祝你使用愉快！** 🎉
