#!/usr/bin/env python3
"""
FunASR客户端 - 为AutoDiary集成的语音识别模块

基于阿里巴巴FunASR框架，提供高精度的中文语音识别功能。
支持实时流式识别、VAD语音活动检测、标点恢复等功能。

作者：AutoDiary开发团队
版本：v1.0
"""

import asyncio
import logging
import numpy as np
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, AsyncGenerator
from datetime import datetime

# FunASR imports
try:
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess
    FUNASR_AVAILABLE = True
except ImportError:
    print("警告: FunASR未安装，请运行: pip install -U funasr")
    FUNASR_AVAILABLE = False

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FunASRClient:
    """FunASR语音识别客户端"""
    
    def __init__(self, 
                 model_name: str = "paraformer-zh",
                 vad_model: str = "fsmn-vad",
                 punc_model: str = "ct-punc",
                 device: str = "cuda",
                 sample_rate: int = 16000):
        """
        初始化FunASR客户端
        
        Args:
            model_name: ASR模型名称 (paraformer-zh, paraformer-zh-streaming, SenseVoiceSmall)
            vad_model: VAD模型名称 (fsmn-vad)
            punc_model: 标点恢复模型名称 (ct-punc)
            device: 计算设备 (cuda, cpu)
            sample_rate: 音频采样率
        """
        self.model_name = model_name
        self.vad_model_name = vad_model
        self.punc_model_name = punc_model
        self.device = device
        self.sample_rate = sample_rate
        
        # 模型实例
        self.asr_model = None
        self.vad_model = None
        self.punc_model = None
        
        # 统计信息
        self.stats = {
            'total_processed_seconds': 0,
            'total_characters': 0,
            'processing_time': 0,
            'error_count': 0
        }
        
        logger.info(f"FunASR客户端初始化完成 - 模型: {model_name}, 设备: {device}")

    async def initialize(self) -> bool:
        """异步初始化模型"""
        try:
            if not FUNASR_AVAILABLE:
                raise ImportError("FunASR未安装")
            
            logger.info("正在加载FunASR模型...")
            
            # 初始化ASR模型
            if self.model_name == "paraformer-zh-streaming":
                # 流式模型配置
                self.asr_model = AutoModel(
                    model=self.model_name,
                    device=self.device
                )
                logger.info("流式ASR模型加载完成")
            else:
                # 非流式模型配置
                self.asr_model = AutoModel(
                    model=self.model_name,
                    vad_model=self.vad_model_name,
                    punc_model=self.punc_model_name,
                    device=self.device
                )
                logger.info("ASR模型加载完成")
            
            # 如果需要单独的VAD和标点模型
            if self.vad_model_name and self.model_name != "paraformer-zh":
                self.vad_model = AutoModel(model=self.vad_model_name)
                logger.info("VAD模型加载完成")
                
            if self.punc_model_name and self.model_name != "paraformer-zh":
                self.punc_model = AutoModel(model=self.punc_model_name)
                logger.info("标点恢复模型加载完成")
            
            logger.info("所有FunASR模型初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"FunASR模型初始化失败: {e}")
            return False

    async def transcribe_file(self, audio_file: str, **kwargs) -> Optional[str]:
        """
        转录音频文件
        
        Args:
            audio_file: 音频文件路径
            **kwargs: 额外参数 (language, use_itn, batch_size_s等)
            
        Returns:
            转录文本结果
        """
        try:
            if not self.asr_model:
                raise RuntimeError("ASR模型未初始化")
            
            start_time = time.time()
            
            # 读取音频文件
            import soundfile
            audio_data, sr = soundfile.read(audio_file)
            
            # 重采样到目标采样率
            if sr != self.sample_rate:
                import librosa
                audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=self.sample_rate)
            
            # 调用FunASR进行转录
            result = self.asr_model.generate(
                input=audio_data,
                **kwargs
            )
            
            # 提取文本结果
            if result and len(result) > 0:
                text = result[0].get("text", "")
                
                # 如果启用富文本后处理
                if kwargs.get("use_itn", False):
                    text = rich_transcription_postprocess(text)
                
                # 更新统计信息
                processing_time = time.time() - start_time
                audio_duration = len(audio_data) / self.sample_rate
                
                self.stats['total_processed_seconds'] += audio_duration
                self.stats['total_characters'] += len(text)
                self.stats['processing_time'] += processing_time
                
                logger.info(f"文件转录完成: {audio_file}, 耗时: {processing_time:.2f}s, "
                          f"音频时长: {audio_duration:.2f}s, RTF: {processing_time/audio_duration:.2f}")
                
                return text
            else:
                logger.warning(f"转录结果为空: {audio_file}")
                return None
                
        except Exception as e:
            logger.error(f"音频文件转录失败: {e}")
            self.stats['error_count'] += 1
            return None

    async def transcribe_audio_data(self, audio_data: np.ndarray, **kwargs) -> Optional[str]:
        """
        转录音频数据
        
        Args:
            audio_data: 音频数据numpy数组
            **kwargs: 额外参数
            
        Returns:
            转录文本结果
        """
        try:
            if not self.asr_model:
                raise RuntimeError("ASR模型未初始化")
            
            start_time = time.time()
            
            # 确保音频数据格式正确
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # 调用FunASR进行转录
            result = self.asr_model.generate(
                input=audio_data,
                **kwargs
            )
            
            # 提取文本结果
            if result and len(result) > 0:
                text = result[0].get("text", "")
                
                # 富文本后处理
                if kwargs.get("use_itn", False):
                    text = rich_transcription_postprocess(text)
                
                # 更新统计信息
                processing_time = time.time() - start_time
                audio_duration = len(audio_data) / self.sample_rate
                
                self.stats['total_processed_seconds'] += audio_duration
                self.stats['total_characters'] += len(text)
                self.stats['processing_time'] += processing_time
                
                return text
            else:
                return None
                
        except Exception as e:
            logger.error(f"音频数据转录失败: {e}")
            self.stats['error_count'] += 1
            return None

    async def stream_transcribe(self, audio_generator: AsyncGenerator[np.ndarray, None]) -> AsyncGenerator[Dict, None]:
        """
        流式转录音频数据
        
        Args:
            audio_generator: 音频数据生成器
            
        Yields:
            转录结果字典
        """
        if not self.asr_model:
            raise RuntimeError("ASR模型未初始化")
        
        if self.model_name != "paraformer-zh-streaming":
            logger.warning("当前模型不支持流式转录，建议使用 paraformer-zh-streaming")
        
        try:
            cache = {}
            chunk_size = [0, 10, 5]  # 600ms延迟配置
            encoder_chunk_look_back = 4
            decoder_chunk_look_back = 1
            
            async for audio_chunk in audio_generator:
                # 确保音频数据格式
                if audio_chunk.dtype != np.float32:
                    audio_chunk = audio_chunk.astype(np.float32)
                
                # 流式识别
                result = self.asr_model.generate(
                    input=audio_chunk,
                    cache=cache,
                    is_final=False,
                    chunk_size=chunk_size,
                    encoder_chunk_look_back=encoder_chunk_look_back,
                    decoder_chunk_look_back=decoder_chunk_look_back
                )
                
                if result and len(result) > 0:
                    yield {
                        'text': result[0].get("text", ""),
                        'timestamp': time.time(),
                        'is_final': False
                    }
            
            # 强制输出最后一个结果
            final_result = self.asr_model.generate(
                input=[],
                cache=cache,
                is_final=True,
                chunk_size=chunk_size,
                encoder_chunk_look_back=encoder_chunk_look_back,
                decoder_chunk_look_back=decoder_chunk_look_back
            )
            
            if final_result and len(final_result) > 0:
                yield {
                    'text': final_result[0].get("text", ""),
                    'timestamp': time.time(),
                    'is_final': True
                }
                
        except Exception as e:
            logger.error(f"流式转录失败: {e}")
            yield {
                'text': "",
                'timestamp': time.time(),
                'is_final': True,
                'error': str(e)
            }

    async def vad_segment_audio(self, audio_data: np.ndarray) -> List[Dict]:
        """
        使用VAD对音频进行分段
        
        Args:
            audio_data: 音频数据
            
        Returns:
            分段结果列表
        """
        try:
            if not self.vad_model:
                # 如果没有单独的VAD模型，使用ASR模型的VAD功能
                logger.info("使用ASR模型的VAD功能进行分段")
                
                # 调用ASR模型的VAD功能
                result = self.asr_model.generate(
                    input=audio_data,
                    return_segments=True
                )
                
                if result and len(result) > 0:
                    segments = result[0].get("segments", [])
                    return segments
                else:
                    return []
            else:
                # 使用单独的VAD模型
                from funasr.runtime.python.onnxruntime.vad import OnnxWrapper
                vad_model = OnnxWrapper(self.vad_model)
                
                # 获取语音时间戳
                timestamps = vad_model.get_speech_timestamps(audio_data)
                
                segments = []
                for idx, timestamp in enumerate(timestamps):
                    segment = {
                        'id': idx,
                        'start': timestamp['start'],
                        'end': timestamp['end'],
                        'start_time': self._format_timestamp(timestamp['start']/self.sample_rate*1000),
                        'end_time': self._format_timestamp(timestamp['end']/self.sample_rate*1000)
                    }
                    segments.append(segment)
                
                return segments
                
        except Exception as e:
            logger.error(f"VAD分段失败: {e}")
            return []

    def _format_timestamp(self, milliseconds: int) -> str:
        """格式化时间戳"""
        delta = datetime.timedelta(milliseconds=milliseconds)
        time_str = str(delta)
        time_parts = time_str.split(".")[0].split(":")
        return "{:02d}:{:02d}:{:02d}".format(
            int(time_parts[0]), int(time_parts[1]), int(time_parts[2])
        )

    def get_stats(self) -> Dict:
        """获取统计信息"""
        if self.stats['total_processed_seconds'] > 0:
            avg_rtf = self.stats['processing_time'] / self.stats['total_processed_seconds']
        else:
            avg_rtf = 0
            
        return {
            **self.stats,
            'avg_rtf': avg_rtf,
            'model_name': self.model_name,
            'device': self.device
        }

    async def save_transcription(self, text: str, metadata: Optional[Dict] = None):
        """保存转录结果"""
        try:
            # 创建转录数据目录
            transcriptions_dir = Path("data/Transcriptions")
            transcriptions_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transcription_{timestamp}.json"
            filepath = transcriptions_dir / filename
            
            # 保存转录数据
            transcription_data = {
                'text': text,
                'timestamp': timestamp,
                'model': self.model_name,
                'metadata': metadata or {},
                'stats': self.get_stats()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(transcription_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"转录结果已保存: {filename}")
            
        except Exception as e:
            logger.error(f"保存转录结果失败: {e}")

    async def cleanup(self):
        """清理资源"""
        try:
            # 清理模型资源
            if self.asr_model:
                del self.asr_model
                self.asr_model = None
                
            if self.vad_model:
                del self.vad_model
                self.vad_model = None
                
            if self.punc_model:
                del self.punc_model
                self.punc_model = None
            
            logger.info("FunASR客户端资源清理完成")
            
        except Exception as e:
            logger.error(f"资源清理失败: {e}")


# 使用示例
async def main():
    """主函数示例"""
    # 创建FunASR客户端
    client = FunASRClient(
        model_name="paraformer-zh",
        device="cuda"  # 或 "cpu"
    )
    
    # 初始化模型
    if await client.initialize():
        logger.info("FunASR客户端初始化成功")
        
        # 示例：转录音频文件
        # result = await client.transcribe_file("test_audio.wav")
        # print(f"转录结果: {result}")
        
        # 获取统计信息
        stats = client.get_stats()
        print(f"统计信息: {stats}")
    else:
        logger.error("FunASR客户端初始化失败")


if __name__ == "__main__":
    asyncio.run(main())
