# AutoDiary - PC 实时语音识别工具

基于 sherpa_onnx + Paraformer 的实时语音识别系统，自动生成每日日记和摘要。

## 功能特点

- **实时语音识别**: 使用 Paraformer 中文 ASR 模型
- **智能 VAD**: Silero VAD 自动检测语音片段
- **LLM 优化**: GPT-4o-mini 自动校正识别结果
- **段落总结**: 超过5分钟静默自动生成段落摘要
- **双输出**:
  - `Transcripts/`: 完整日记（含原文和总结）
  - `Summary/`: 仅包含时间和摘要

## 目录结构

```
tools/
├── realtime_paraformer.py   # 主程序
├── models/                  # 模型文件
│   ├── paraformer/         # Paraformer ASR 模型
│   │   ├── model.onnx
│   │   └── tokens.txt
│   └── silero_vad.onnx     # Silero VAD 模型
├── data/                   # 输出数据
│   ├── Transcripts/        # 完整日记
│   └── Summary/            # 段落摘要
└── _archived/              # 旧版本代码存档
```

## 使用方法

### 基本用法

```bash
python realtime_paraformer.py --openai-key "YOUR_KEY" --device 0
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--openai-key` | (必填) | OpenAI API Key |
| `--device` | 0 | 音频输入设备索引 |
| `--paragraph-gap` | 5.0 | 段落间隔（分钟），超过此时间触发总结 |
| `--min-speech` | 2500 | 最小语音长度（毫秒） |
| `--buffer-seconds` | 30.0 | 音频缓冲区大小（秒） |
| `--list-devices` | - | 列出可用音频设备 |

### 列出音频设备

```bash
python realtime_paraformer.py --list-devices
```

## 输出格式

### Transcripts (完整日记)

```
==================================================
[段落] 19:30:15 - 19:35:22 (5条语音)
==================================================

[19:30:15] 今天开了一个会议讨论项目进度
[19:31:20] 主要讨论了下周的发布计划
...

📝 段落总结: 用户参加了项目进度会议，讨论了下周发布计划。

--------------------------------------------------
```

### Summary (仅摘要)

```
[19:30:15 - 19:35:22] 用户参加了项目进度会议，讨论了下周发布计划。
[20:15:30 - 20:18:45] 用户提到了晚餐安排和明天的行程。
```

## 依赖安装

```bash
pip install sherpa-onnx onnxruntime numpy pyaudio openai
```

## 模型下载

### Paraformer ASR
```bash
# model.onnx (~823MB)
curl -L -o models/paraformer/model.onnx \
  https://huggingface.co/csukuangfj/sherpa-onnx-paraformer-zh-2023-03-28/resolve/main/model.onnx

# tokens.txt
curl -L -o models/paraformer/tokens.txt \
  https://huggingface.co/csukuangfj/sherpa-onnx-paraformer-zh-2023-03-28/resolve/main/tokens.txt
```

### Silero VAD
```bash
curl -L -o models/silero_vad.onnx \
  https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx
```
