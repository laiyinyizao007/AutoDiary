# AutoDiary - 全自动音视频 Lifelog 系统

## 项目概述

AutoDiary 是一个基于 XIAO ESP32S3 Sense 的全自动音视频 Lifelog 系统，能够：

1. **实时语音采集**：通过 PDM 麦克风采集语音，推流到 PC 进行 Whisper 识别
2. **自动图像存档**：每 30 秒自动捕获并存储一张照片到 PC
3. **双重 WebSocket 流**：独立的视频流和音频流传输

## 硬件要求

- XIAO ESP32S3 Sense 开发板
- OV2640 摄像头（集成）
- PDM 麦克风（集成）
- WiFi 网络

## 软件环境

- Windows 11
- VS Code + PlatformIO 扩展
- Python 3.8+
- Git

## 快速开始

### 1. 安装 Python 依赖

```bash
pip install -r config/requirements.txt
```

### 2. 配置设备端 WiFi

编辑 `src/main.cpp` 文件，修改以下配置：

```cpp
const char* ssid = "你的WiFi名称";           // 修改为你的WiFi名称
const char* password = "你的WiFi密码";       // 修改为你的WiFi密码
```

### 3. 编译和上传设备端代码

在 VS Code 终端中执行：

```bash
# 编译项目
pio run -e seeed_xiao_esp32s3_sense

# 上传到设备
pio run --target upload -e seeed_xiao_esp32s3_sense

# 查看串口输出（可选）
pio device monitor -e seeed_xiao_esp32s3_sense
```

### 4. 启动 Python 服务器

在新的终端窗口中执行：

```bash
python scripts/servers/server.py
```

## 系统架构

### 设备端 (XIAO ESP32S3 Sense)

- **摄像头配置**：OV2640，VGA (640x480)，JPEG 格式
- **音频配置**：PDM 麦克风，16kHz 采样率，16-bit PCM
- **WebSocket 连接**：
  - 视频流：`ws://192.168.137.1:8000/video`
  - 音频流：`ws://192.168.137.1:8000/audio`

### 服务器端 (Python)

- **WebSocket 服务器**：监听端口 8000
- **图像存档**：每 30 秒保存到 `data/Images/` 目录
- **音频缓存**：为 Whisper AI 语音识别准备数据
- **日志记录**：完整的系统运行日志

## 文件结构

```
AutoDiary/
├── .claude/                          # Claude 初始化配置
│   └── project.json                 # 项目元信息
├── docs/                            # 📚 文档目录
│   ├── DEPLOYMENT/                  # 部署指南
│   ├── GUIDES/                      # 使用指南
│   ├── ARCHITECTURE/                # 架构文档
│   ├── TROUBLESHOOTING/             # 故障排除
│   └── REPORTS/                     # 测试报告
├── scripts/                         # 🐍 Python 脚本
│   ├── servers/                     # 服务器代码
│   ├── tools/                       # 工具脚本
│   ├── deployment/                  # 部署脚本
│   ├── test/                        # 测试脚本
│   └── legacy/                      # 旧版本
├── config/                          # ⚙️ 配置文件
│   ├── platformio.ini              # PlatformIO 配置
│   ├── config.json                 # 应用配置
│   ├── requirements.txt            # Python 依赖
│   └── Dockerfile                  # Docker 配置
├── src/                             # 📝 设备端源代码
│   └── main.cpp                    # ESP32 主程序
├── include/                         # 📚 头文件
│   └── camera_pins.h               # 摄像头引脚配置
├── data/                            # 📦 数据存储
│   ├── Images/                     # 图像存档
│   ├── Audio/                      # 音频缓存
│   ├── Logs/                       # 系统日志
│   └── ...                         # 其他数据目录
├── static/                          # 🎨 Web 静态资源
├── README.md                        # 项目说明文档
└── .gitignore                       # Git 忽略配置
```

## 配置说明

### 设备端配置 (main.cpp)

主要配置参数：

```cpp
// WiFi 配置
const char* ssid = "YourWiFiSSID";
const char* password = "YourWiFiPassword";

// 服务器配置
const char* server_host = "192.168.137.1";  // PC服务器IP地址
const uint16_t server_port = 8000;          // WebSocket服务器端口

// 音频配置
#define AUDIO_SAMPLE_RATE     16000
#define AUDIO_BUFFER_SIZE     512
#define AUDIO_CHANNELS        1

// 摄像头配置
config.frame_size = FRAMESIZE_VGA;    // 640x480
config.pixel_format = PIXFORMAT_JPEG; // JPEG 格式
config.jpeg_quality = 10;             // 质量设置 (0-31, 数值越小质量越高)
```

### 服务器端配置 (server.py)

主要配置参数：

```python
# 服务器配置
host = "0.0.0.0"  # 监听所有网络接口
port = 8000        # WebSocket 端口

# 存储路径
base_dir = Path("data")
images_dir = base_dir / "Images"  # 图像存储目录
audio_dir = base_dir / "Audio"    # 音频存储目录
logs_dir = base_dir / "Logs"      # 日志存储目录
```

## 故障排除

### 常见问题

1. **编译错误**
   - 确保安装了所有 PlatformIO 库依赖
   - 检查 `platformio.ini` 中的板型配置是否正确

2. **WiFi 连接失败**
   - 检查 SSID 和密码是否正确
   - 确认 WiFi 信号强度足够
   - 检查防火墙设置

3. **WebSocket 连接失败**
   - 确认服务器 IP 地址正确
   - 检查端口 8000 是否被占用
   - 确认防火墙允许该端口

4. **摄像头初始化失败**
   - 检查硬件连接
   - 确认 PSRAM 配置正确
   - 重新插拔摄像头模块

5. **音频采集失败**
   - 检查 PDM 麦克风连接
   - 确认引脚配置正确
   - 调整采样率参数

### 调试命令

```bash
# 查看详细编译信息
pio run -e seeed_xiao_esp32s3_sense -v

# 清理构建缓存
pio run -e seeed_xiao_esp32s3_sense -t clean

# 监控串口输出
pio device monitor -e seeed_xiao_esp32s3_sense --baud 115200

# 测试 WebSocket 连接
python -c "import websockets; print('websockets 库正常')"
```

## 性能优化

### 设备端优化

- 调整摄像头质量以平衡图像质量和传输速度
- 优化音频缓冲区大小以减少延迟
- 使用双核任务分离提高并发性能

### 服务器端优化

- 调整音频缓冲区大小避免内存溢出
- 使用异步处理提高并发性能
- 定期清理旧日志文件

## 扩展功能

### 未来计划

- **Whisper AI 集成**：完整语音识别和转录
- **图像识别**：基于 AI 的场景分析
- **数据可视化**：Web 界面查看 lifelog 数据
- **云端同步**：自动备份到云存储
- **移动应用**：手机端查看和控制

### 自定义开发

系统采用模块化设计，可以轻松扩展：

- 添加新的传感器支持
- 集成其他 AI 服务
- 自定义数据处理逻辑
- 开发用户界面

## 技术支持

如果遇到问题，请：

1. 查看 `autodiary_server.log` 日志文件
2. 检查设备串口输出
3. 确认网络连接状态
4. 验证硬件连接

## 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。

## 作者

自动开发代理 v1.0
