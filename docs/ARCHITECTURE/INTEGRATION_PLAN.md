# AutoDiary Reference 资源集成计划

## 📋 项目概述

基于 `C:\Dev\projects\AutoDiary\reference` 目录中的可复用资源，为AutoDiary项目制定详细的集成升级计划。

## 🎯 集成目标

1. **摄像头功能增强**：集成 Camera_HTTP_Server_STA 的Web管理界面
2. **语音识别升级**：采用 FunASR 替代 Whisper，提供更精准的中文识别
3. **智能分析能力**：集成 minutes 项目的语音转文字+智能总结功能

## 📁 Reference 资源分析

### 1. Camera_HTTP_Server_STA
- **位置**：`reference/XIAO-ESP32S3-Sense/Camera_HTTP_Server_STA/`
- **核心功能**：
  - Web界面控制：实时预览、旋转、保存图像
  - SD卡存储：自动命名和序列化存储
  - SPIFFS缓存：临时图像缓存机制
  - 稳定性优化：摄像头初始化和错误处理

### 2. FunASR 语音识别框架
- **位置**：`reference/FunASR/`
- **核心模型**：
  - **Paraformer-zh**：60,000小时中文训练，220M参数
  - **SenseVoiceSmall**：多语言理解，330M参数
  - **VAD模型**：语音活动检测，实时分割
  - **标点恢复**：CT-Transformer，290M参数

### 3. Minutes 会议记录工具
- **位置**：`reference/minutes/`
- **技术栈**：Sherpa-ONNX + VAD + LLM总结
- **核心功能**：长音频分段、时间戳对齐、智能摘要

## 🚀 集成实施方案

## 阶段一：摄像头功能增强（立即执行）

### 1.1 集成Web界面管理
```cpp
// 从 Camera_HTTP_Server_STA.ino 复制核心Web服务器代码
#include <WebServer.h>
#include "webpage.h"

WebServer server(80);

// 路由配置
server.on("/", handle_OnConnect);
server.on("/capture", handle_capture);
server.on("/save", handle_save);
server.on("/saved_photo", []() {getSpiffImg(FILE_PHOTO, "image/jpg"); });
```

### 1.2 图像处理优化
- **JPEG质量控制**：参考 `config.jpeg_quality = 12`
- **SPIFFS缓存机制**：临时存储预览图像
- **SD卡备份**：`photo_save()` 函数实现

### 1.3 实时预览功能
- 集成 `camera_index.h` 的HTML界面
- 支持浏览器实时查看摄像头画面
- 添加图像旋转和保存控制

## 阶段二：语音识别升级（高优先级）

### 2.1 FunASR服务部署
```bash
# 使用Docker部署FunASR服务
docker run -d --name funasr-server \
  -p 10095:10095 \
  -v ./models:/workspace/models \
  registry.cn-hangzhou.aliyuncs.com/funasr/funasr-runtime-sdk:0.1.10
```

### 2.2 Python客户端集成
```python
# 新增 funasr_client.py
from funasr import AutoModel

class FunASRClient:
    def __init__(self):
        self.model = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad", 
            punc_model="ct-punc",
            device="cuda"
        )
    
    async def transcribe_audio(self, audio_data):
        result = self.model.generate(input=audio_data)
        return result[0]["text"]
```

### 2.3 服务器端集成
```python
# 在 server.py 中集成FunASR
async def _process_audio_with_funasr(self, pcm_data):
    """使用FunASR处理音频数据"""
    try:
        # 转换音频格式
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
        audio_array = audio_array.astype(np.float32) / 32768.0
        
        # FunASR识别
        result = await self.funasr_client.transcribe_audio(audio_array)
        
        # 保存转录结果
        await self._save_transcription(result)
        
    except Exception as e:
        logger.error(f"FunASR处理错误: {e}")
```

## 阶段三：智能分析能力（扩展功能）

### 3.1 语音分段处理
```python
# 参考 minutes/pipeline.py
from models.vad import OnnxWrapper, get_speech_timestamps

def segment_audio_with_vad(self, audio_data, sample_rate=16000):
    """使用VAD对音频进行智能分段"""
    timestamps = get_speech_timestamps(audio_data, self.vad_model)
    
    segments = []
    for idx, timestamp in enumerate(timestamps):
        segment = {
            'id': idx,
            'start': timestamp['start'],
            'end': timestamp['end'],
            'start_time': self._format_time(timestamp['start']/sample_rate*1000),
            'end_time': self._format_time(timestamp['end']/sample_rate*1000),
            'audio_data': audio_data[timestamp['start']:timestamp['end']]
        }
        segments.append(segment)
    
    return segments
```

### 3.2 智能总结集成
```python
# 参考 minutes/summarize.py
async def generate_daily_summary(self, transcriptions):
    """生成每日智能总结"""
    # 合并所有转录文本
    full_text = "\n".join([t['text'] for t in transcriptions])
    
    # 调用LLM进行总结
    summary = await self.llm_client.summarize(full_text)
    
    # 保存总结结果
    summary_data = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'total_segments': len(transcriptions),
        'full_text': full_text,
        'summary': summary,
        'generated_at': datetime.now().isoformat()
    }
    
    await self._save_daily_summary(summary_data)
```

## 📊 技术实现细节

### 摄像头配置优化
```cpp
// 参考 Camera_HTTP_Server_STA 的最佳配置
camera_config_t config = {
    .xclk_freq_hz = 20000000,
    .frame_size = FRAMESIZE_UXGA,  // 1600x1200
    .pixel_format = PIXFORMAT_JPEG,
    .jpeg_quality = 12,            // 高质量JPEG
    .fb_count = 1,
    .fb_location = CAMERA_FB_IN_PSRAM
};
```

### 音频处理管道
```python
# 完整的音频处理流程
class AudioPipeline:
    def __init__(self):
        self.vad_model = OnnxWrapper("silero_vad.onnx")
        self.asr_model = AutoModel(model="paraformer-zh")
        self.punc_model = AutoModel(model="ct-punc")
    
    async def process_audio_stream(self, audio_data):
        # 1. VAD分段
        segments = self.segment_audio_with_vad(audio_data)
        
        # 2. 语音识别
        transcriptions = []
        for segment in segments:
            text = self.asr_model.generate(input=segment['audio_data'])
            transcriptions.append({
                'segment': segment,
                'text': text[0]["text"]
            })
        
        # 3. 标点恢复
        for trans in transcriptions:
            trans['text_with_punc'] = self.punc_model.generate(
                input=trans['text']
            )[0]["text"]
        
        return transcriptions
```

## 🔧 部署配置

### Docker Compose 配置
```yaml
# docker-compose.yml
version: '3.8'
services:
  funasr-server:
    image: registry.cn-hangzhou.aliyuncs.com/funasr/funasr-runtime-sdk:0.1.10
    ports:
      - "10095:10095"
    volumes:
      - ./models:/workspace/models
    environment:
      - MODEL_NAME=paraformer-zh
    
  autodiary-server:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    depends_on:
      - funasr-server
```

### 系统要求
- **硬件**：NVIDIA GPU（推荐）或高性能CPU
- **内存**：至少8GB RAM
- **存储**：50GB可用空间（模型+数据）
- **网络**：稳定的WiFi连接

## 📈 预期性能提升

| 指标 | 当前实现 | 集成后 | 提升幅度 |
|------|----------|--------|----------|
| 中文识别准确率 | ~85% (Whisper) | ~95% (Paraformer) | +10% |
| 实时响应延迟 | 2-3秒 | 0.5-1秒 | 3倍提升 |
| 并发处理能力 | 单线程 | 多线程+异步 | 5倍提升 |
| 管理便利性 | 命令行 | Web界面 | 显著改善 |

## 🗓️ 实施时间表

### 第1周：摄像头Web界面集成
- [ ] 复制Camera_HTTP_Server_STA核心代码
- [ ] 集成Web管理界面
- [ ] 测试图像捕获和预览功能

### 第2-3周：FunASR语音识别集成
- [ ] 部署FunASR服务
- [ ] 集成Python客户端
- [ ] 替换现有音频处理逻辑
- [ ] 性能测试和优化

### 第4周：智能分析功能
- [ ] 集成VAD分段处理
- [ ] 添加智能总结功能
- [ ] 完善数据存储和检索

## 🚨 注意事项

1. **模型下载**：FunASR模型较大（~2GB），需要稳定的网络连接
2. **GPU支持**：建议使用NVIDIA GPU以获得最佳性能
3. **存储管理**：需要定期清理旧数据，避免磁盘空间不足
4. **网络稳定性**：确保ESP32与服务器之间的网络连接稳定

## 📚 相关文档

- [FunASR官方文档](https://github.com/alibaba-damo-academy/FunASR)
- [Camera_HTTP_Server_STA源码](reference/XIAO-ESP32S3-Sense/Camera_HTTP_Server_STA/)
- [Minutes项目说明](reference/minutes/README.md)

---

*此集成计划将显著提升AutoDiary的功能性和实用性，建议按阶段逐步实施。*
