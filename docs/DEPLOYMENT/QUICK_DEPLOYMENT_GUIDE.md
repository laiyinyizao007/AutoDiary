# AutoDiary v3.0 快速部署指南

## 🚀 5分钟快速开始

### 前置条件检查清单

- [ ] XIAO ESP32-S3 开发板已连接
- [ ] OV2640 摄像头已正确接线
- [ ] 电脑和设备在同一 WiFi 网络
- [ ] Python 3.8+ 已安装
- [ ] PlatformIO 已安装

### 快速命令

```bash
# 1. 一键执行完整工作流（推荐）
python run_complete_workflow.py --ip 192.168.1.11

# 2. 仅部署固件
python deploy_firmware.py

# 3. 仅收集埋点数据
python checkpoint_collector.py --ip 192.168.1.11 --cycles 3

# 4. 运行实时监控
python realtime_monitor.py --ip 192.168.1.11 --duration 60

# 5. 分析诊断报告
python fault_diagnostics.py data/checkpoints/checkpoints_cycle1_*.json
```

## 📊 工作流步骤

```
┌─────────────────┐
│  1. 部署固件    │ ← 编译并烧录到设备
└────────┬────────┘
         ↓
┌─────────────────────────┐
│  2. 等待设备启动        │ ← 自动检测设备在线
└────────┬────────────────┘
         ↓
┌──────────────────────────┐
│  3. 收集埋点数据         │ ← 执行 3 个完整周期
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│  4. 实时监控             │ ← 监控 30 秒性能指标
└────────┬─────────────────┘
         ↓
┌──────────────────────────┐
│  5. 故障诊断             │ ← 自动分析问题并给出建议
└──────────────────────────┘
```

## 🔧 常见问题快速解决

### Q: 设备无法连接？
A: 
```bash
# 检查设备 IP
curl http://192.168.1.11/status

# 或修改固件中的 WiFi 凭证
# src/main_with_checkpoints.cpp 第 35-36 行
const char* ssid = "你的WiFi名称";
const char* password = "你的密码";
```

### Q: 固件编译失败？
A:
```bash
# 清理后重新编译
pio run -e seeed_xiao_esp32s3 --target clean
pio run -e seeed_xiao_esp32s3
```

### Q: 摄像头不工作？
A:
```bash
# 检查引脚配置
cat include/camera_pins.h

# 检查 PSRAM 是否启用
# platformio.ini 应包含：
# board_build.arduino.memory_type = qio_opi
```

## 📈 性能基准

| 操作 | 耗时 | 内存消耗 |
|------|------|---------|
| 拍摄 | 200-300 ms | 变化 ±2MB |
| 存储 | 100-200 ms | 变化 ±1MB |
| 上传 | 1-3 秒 | 变化 ±10MB |
| 完整周期 | 2-4 秒 | 恢复到初始值 |

## 🎯 输出数据位置

```
data/
├── checkpoints/          # 埋点数据
│   ├── checkpoints_cycle1_*.json
│   └── checkpoints_cycle1_*.csv
├── monitoring/           # 监控日志
│   ├── monitor.log
│   └── metrics_*.json
└── diagnostics/          # 诊断报告
    └── diagnostic_*.json
```

## 🔍 读取埋点数据

### JSON 格式示例

```json
{
  "checkpoints": [
    {
      "id": 1,
      "phase": 1,
      "elapsed_ms": 125,
      "heap_free": 245000,
      "message": "Photo capture started"
    }
  ]
}
```

### CSV 格式

直接用 Excel 或任何电子表格软件打开：
```
id,phase,elapsed_ms,heap_free,message,...
1,1,125,245000,Photo capture started,...
```

## ⚙️ 配置调整

### 提高上传速度

编辑 `src/main_with_checkpoints.cpp`：

```cpp
// 降低图像质量（文件更小，上传更快）
config.jpeg_quality = 15;  // 1-63，越小越快

// 使用 QVGA 分辨率（减小帧）
config.frame_size = FRAMESIZE_QVGA;  // 320x240
```

### 保存更高质量的图像

```cpp
// 提高图像质量
config.jpeg_quality = 10;  // 10 = 最高质量

// 使用 XGA 分辨率
config.frame_size = FRAMESIZE_XGA;  // 1024x768
```

### 降低功耗

```cpp
// 在 platformio.ini 中添加
build_flags = 
    -DCAMERA_MODEL_XIAO_ESP32S3
    -DBOARD_HAS_PSRAM
    -mfix-esp32-psram-cache-issue
    -DPSRAM_CACHE_DISABLED  # 禁用 PSRAM 缓存
```

## 🧪 测试验证步骤

### 1. 检查固件版本

```bash
curl http://192.168.1.11/status

# 应返回：
# {
#   "device": "XIAO-ESP32S3-Sense",
#   "version": "v3.0",
#   "mode": "Full Cycle with Checkpoints"
# }
```

### 2. 手动触发拍摄

```bash
curl http://192.168.1.11/capture
```

### 3. 获取埋点数据

```bash
curl http://192.168.1.11/checkpoints

# 应返回 JSON 格式的埋点数据
```

## 📋 工作流常用命令速查表

| 任务 | 命令 |
|------|------|
| 完整工作流 | `python run_complete_workflow.py` |
| 仅编译 | `python deploy_firmware.py --skip-upload` |
| 编译并烧录 | `python deploy_firmware.py` |
| 收集数据 | `python checkpoint_collector.py` |
| 监控 | `python realtime_monitor.py` |
| 诊断 | `python fault_diagnostics.py <文件>` |
| 串口监控 | `platformio device monitor` |

## 🆘 获取帮助

### 查看详细文档

- 完整部署指南：`DEPLOYMENT_AND_TESTING_GUIDE.md`
- 固件源代码：`src/main_with_checkpoints.cpp`
- 配置文件：`config.json`

### 调试步骤

1. 检查日志文件：`deployment_log.txt`
2. 查看监控日志：`data/monitoring/monitor.log`
3. 阅读诊断报告：`data/diagnostics/diagnostic_*.json`

## 🎓 学习资源

- esp32-camera：https://github.com/espressif/esp32-camera
- XIAO ESP32-S3：https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/
- PlatformIO 文档：https://docs.platformio.org/

## 📝 版本信息

- **版本**：v3.0
- **发布日期**：2025-11-30
- **状态**：生产就绪 ✅

---

**提示**：需要更多帮助？查看 `DEPLOYMENT_AND_TESTING_GUIDE.md` 获取完整文档。
