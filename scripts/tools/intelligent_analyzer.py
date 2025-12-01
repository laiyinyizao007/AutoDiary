#!/usr/bin/env python3
"""
AutoDiary 智能分析模块

基于 minutes 项目的语音处理和智能总结功能，
为AutoDiary提供音频分段、语音识别、智能总结等高级分析能力。

功能：
- VAD语音活动检测和分段
- 语音转文字转录
- 时间戳对齐
- 智能内容总结
- 关键信息提取
- 多模态数据融合

作者：AutoDiary开发团队
版本：v1.0
"""

import asyncio
import json
import time
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import re
from collections import defaultdict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IntelligentAnalyzer:
    """智能分析器"""
    
    def __init__(self, 
                 funasr_client=None,
                 llm_client=None,
                 data_dir: str = "data"):
        """
        初始化智能分析器
        
        Args:
            funasr_client: FunASR语音识别客户端
            llm_client: 大语言模型客户端
            data_dir: 数据存储目录
        """
        self.funasr_client = funasr_client
        self.llm_client = llm_client
        self.data_dir = Path(data_dir)
        
        # 子目录
        self.transcriptions_dir = self.data_dir / "Transcriptions"
        self.summaries_dir = self.data_dir / "Summaries"
        self.segments_dir = self.data_dir / "AudioSegments"
        self.analysis_dir = self.data_dir / "Analysis"
        
        # 创建目录
        self._create_directories()
        
        # 分析配置
        self.config = {
            'vad_threshold': 0.5,          # VAD阈值
            'min_segment_duration': 2.0,   # 最小分段时长(秒)
            'max_segment_duration': 30.0,  # 最大分段时长(秒)
            'merge_silence_gap': 1.0,      # 合并静音间隔(秒)
            'summary_max_length': 500,     # 总结最大长度
            'keyword_extraction': True,    # 关键词提取
            'emotion_analysis': True       # 情感分析
        }
        
        # 缓存
        self.analysis_cache = {}
        
        logger.info("智能分析器初始化完成")

    def _create_directories(self):
        """创建必要的目录结构"""
        try:
            self.transcriptions_dir.mkdir(parents=True, exist_ok=True)
            self.summaries_dir.mkdir(parents=True, exist_ok=True)
            self.segments_dir.mkdir(parents=True, exist_ok=True)
            self.analysis_dir.mkdir(parents=True, exist_ok=True)
            logger.info("分析目录结构创建成功")
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            raise

    async def process_audio_file(self, 
                               audio_file: str, 
                               metadata: Optional[Dict] = None) -> Dict:
        """
        处理音频文件，进行完整分析流程
        
        Args:
            audio_file: 音频文件路径
            metadata: 音频元数据
            
        Returns:
            分析结果字典
        """
        try:
            logger.info(f"开始处理音频文件: {audio_file}")
            start_time = time.time()
            
            # 1. 读取音频文件
            audio_data = await self._load_audio_file(audio_file)
            
            # 2. VAD分段
            segments = await self._vad_segmentation(audio_data)
            logger.info(f"VAD分段完成，共{len(segments)}个片段")
            
            # 3. 语音识别转录
            transcriptions = []
            for i, segment in enumerate(segments):
                transcription = await self._transcribe_segment(segment, i)
                if transcription:
                    transcriptions.append(transcription)
            
            logger.info(f"语音识别完成，共{len(transcriptions)}个转录结果")
            
            # 4. 合并和优化转录结果
            full_transcription = await self._merge_transcriptions(transcriptions)
            
            # 5. 智能总结
            summary = await self._generate_summary(full_transcription)
            
            # 6. 关键信息提取
            keywords = await self._extract_keywords(full_transcription)
            
            # 7. 保存分析结果
            analysis_result = {
                'audio_file': audio_file,
                'metadata': metadata or {},
                'segments': segments,
                'transcriptions': transcriptions,
                'full_transcription': full_transcription,
                'summary': summary,
                'keywords': keywords,
                'processing_time': time.time() - start_time,
                'timestamp': datetime.now().isoformat()
            }
            
            await self._save_analysis_result(analysis_result)
            
            logger.info(f"音频处理完成，耗时: {analysis_result['processing_time']:.2f}秒")
            return analysis_result
            
        except Exception as e:
            logger.error(f"音频处理失败: {e}")
            raise

    async def process_real_time_audio(self, 
                                    audio_chunk: np.ndarray,
                                    session_id: str) -> Optional[Dict]:
        """
        处理实时音频流
        
        Args:
            audio_chunk: 音频数据块
            session_id: 会话ID
            
        Returns:
            实时分析结果
        """
        try:
            # 获取或创建会话缓存
            if session_id not in self.analysis_cache:
                self.analysis_cache[session_id] = {
                    'audio_buffer': [],
                    'segments': [],
                    'transcriptions': [],
                    'last_process_time': time.time()
                }
            
            session = self.analysis_cache[session_id]
            
            # 添加音频数据到缓冲区
            session['audio_buffer'].append(audio_chunk)
            
            # 检查是否需要处理
            current_time = time.time()
            if current_time - session['last_process_time'] < self.config['min_segment_duration']:
                return None
            
            # 合并音频数据
            full_audio = np.concatenate(session['audio_buffer'])
            
            # VAD检测
            if await self._has_speech(full_audio):
                # 转录音频
                transcription = await self._transcribe_segment({
                    'audio_data': full_audio,
                    'start_time': session['last_process_time'],
                    'end_time': current_time
                }, len(session['transcriptions']))
                
                if transcription and transcription['text'].strip():
                    session['transcriptions'].append(transcription)
                    
                    # 清空缓冲区
                    session['audio_buffer'] = []
                    session['last_process_time'] = current_time
                    
                    return {
                        'session_id': session_id,
                        'transcription': transcription,
                        'timestamp': current_time
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"实时音频处理失败: {e}")
            return None

    async def _load_audio_file(self, audio_file: str) -> np.ndarray:
        """加载音频文件"""
        try:
            import soundfile
            
            audio_data, sample_rate = soundfile.read(audio_file)
            
            # 确保是单声道
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
            
            # 重采样到16kHz
            if sample_rate != 16000:
                import librosa
                audio_data = librosa.resample(
                    audio_data, 
                    orig_sr=sample_rate, 
                    target_sr=16000
                )
            
            return audio_data.astype(np.float32)
            
        except Exception as e:
            logger.error(f"加载音频文件失败: {e}")
            raise

    async def _vad_segmentation(self, audio_data: np.ndarray) -> List[Dict]:
        """VAD语音活动检测和分段"""
        try:
            if self.funasr_client:
                # 使用FunASR的VAD功能
                segments = await self.funasr_client.vad_segment_audio(audio_data)
            else:
                # 简单的能量阈值VAD
                segments = await self._simple_vad(audio_data)
            
            # 后处理：合并过短的片段，分割过长的片段
            processed_segments = await self._post_process_segments(segments)
            
            return processed_segments
            
        except Exception as e:
            logger.error(f"VAD分段失败: {e}")
            # 返回整个音频作为一个片段
            return [{
                'id': 0,
                'start': 0,
                'end': len(audio_data),
                'start_time': "00:00:00",
                'end_time': self._format_duration(len(audio_data) / 16000),
                'audio_data': audio_data
            }]

    async def _simple_vad(self, audio_data: np.ndarray) -> List[Dict]:
        """简单的能量阈值VAD"""
        try:
            # 计算音频能量
            frame_length = int(0.025 * 16000)  # 25ms帧
            hop_length = int(0.010 * 16000)    # 10ms跳跃
            
            frames = []
            for i in range(0, len(audio_data) - frame_length, hop_length):
                frame = audio_data[i:i + frame_length]
                energy = np.sum(frame ** 2)
                frames.append({
                    'start': i,
                    'end': i + frame_length,
                    'energy': energy
                })
            
            # 计算能量阈值
            energies = [f['energy'] for f in frames]
            threshold = np.mean(energies) * 0.1
            
            # 找到语音片段
            segments = []
            in_speech = False
            segment_start = 0
            
            for i, frame in enumerate(frames):
                is_speech = frame['energy'] > threshold
                
                if is_speech and not in_speech:
                    # 开始语音片段
                    segment_start = frame['start']
                    in_speech = True
                elif not is_speech and in_speech:
                    # 结束语音片段
                    segment_end = frame['end']
                    segments.append({
                        'start': segment_start,
                        'end': segment_end
                    })
                    in_speech = False
            
            # 处理最后一个片段
            if in_speech:
                segments.append({
                    'start': segment_start,
                    'end': len(audio_data)
                })
            
            return segments
            
        except Exception as e:
            logger.error(f"简单VAD处理失败: {e}")
            return []

    async def _post_process_segments(self, segments: List[Dict]) -> List[Dict]:
        """后处理VAD分段结果"""
        try:
            if not segments:
                return []
            
            processed_segments = []
            
            for i, segment in enumerate(segments):
                duration = (segment['end'] - segment['start']) / 16000
                
                # 跳过过短的片段
                if duration < self.config['min_segment_duration']:
                    continue
                
                # 分割过长的片段
                if duration > self.config['max_segment_duration']:
                    max_samples = int(self.config['max_segment_duration'] * 16000)
                    segment_samples = segment['end'] - segment['start']
                    
                    num_sub_segments = int(np.ceil(segment_samples / max_samples))
                    for j in range(num_sub_segments):
                        sub_start = segment['start'] + j * max_samples
                        sub_end = min(sub_start + max_samples, segment['end'])
                        
                        processed_segments.append({
                            'id': len(processed_segments),
                            'start': sub_start,
                            'end': sub_end,
                            'start_time': self._format_duration(sub_start / 16000),
                            'end_time': self._format_duration(sub_end / 16000)
                        })
                else:
                    segment['id'] = len(processed_segments)
                    segment['start_time'] = self._format_duration(segment['start'] / 16000)
                    segment['end_time'] = self._format_duration(segment['end'] / 16000)
                    processed_segments.append(segment)
            
            return processed_segments
            
        except Exception as e:
            logger.error(f"分段后处理失败: {e}")
            return segments

    async def _transcribe_segment(self, segment: Dict, segment_id: int) -> Optional[Dict]:
        """转录单个音频片段"""
        try:
            if 'audio_data' not in segment:
                logger.warning(f"片段{segment_id}缺少音频数据")
                return None
            
            if self.funasr_client:
                # 使用FunASR进行转录
                text = await self.funasr_client.transcribe_audio_data(
                    segment['audio_data'],
                    use_itn=True
                )
            else:
                # 模拟转录（实际使用时需要替换为真实的ASR）
                text = f"[模拟转录] 片段{segment_id}的语音内容"
            
            if text and text.strip():
                return {
                    'segment_id': segment_id,
                    'start_time': segment['start_time'],
                    'end_time': segment['end_time'],
                    'duration': self._calculate_duration(
                        segment['start_time'], 
                        segment['end_time']
                    ),
                    'text': text.strip(),
                    'confidence': 0.95  # 模拟置信度
                }
            
            return None
            
        except Exception as e:
            logger.error(f"转录片段{segment_id}失败: {e}")
            return None

    async def _merge_transcriptions(self, transcriptions: List[Dict]) -> str:
        """合并和优化转录结果"""
        try:
            if not transcriptions:
                return ""
            
            # 按时间排序
            transcriptions.sort(key=lambda x: x['start_time'])
            
            # 合并文本
            merged_text = ""
            for trans in transcriptions:
                if merged_text:
                    merged_text += " " + trans['text']
                else:
                    merged_text = trans['text']
            
            # 文本清理和优化
            merged_text = self._clean_transcription_text(merged_text)
            
            return merged_text
            
        except Exception as e:
            logger.error(f"合并转录结果失败: {e}")
            return ""

    def _clean_transcription_text(self, text: str) -> str:
        """清理转录文本"""
        try:
            # 移除重复的空格
            text = re.sub(r'\s+', ' ', text)
            
            # 移除开头和结尾的空格
            text = text.strip()
            
            # 修复常见的标点问题
            text = re.sub(r'\s+([，。！？；：])', r'\1', text)
            text = re.sub(r'([，。！？；：])\s+', r'\1 ', text)
            
            return text
            
        except Exception as e:
            logger.error(f"清理转录文本失败: {e}")
            return text

    async def _generate_summary(self, transcription: str) -> Dict:
        """生成智能总结"""
        try:
            if not transcription or not transcription.strip():
                return {
                    'summary': "",
                    'key_points': [],
                    'action_items': []
                }
            
            if self.llm_client:
                # 使用LLM生成总结
                summary_prompt = f"""
                请为以下语音转录内容生成简洁的总结：

                转录内容：
                {transcription}

                请提供：
                1. 主要内容总结（不超过200字）
                2. 关键要点（3-5个）
                3. 行动���目（如有）
                """
                
                # 这里应该调用实际的LLM API
                # llm_response = await self.llm_client.generate(summary_prompt)
                # 暂时使用模拟响应
                llm_response = self._mock_llm_response(transcription)
                
            else:
                # 简单的文本分析总结
                llm_response = self._simple_text_summary(transcription)
            
            return llm_response
            
        except Exception as e:
            logger.error(f"生成总结失败: {e}")
            return {
                'summary': "总结生成失败",
                'key_points': [],
                'action_items': []
            }

    def _mock_llm_response(self, transcription: str) -> Dict:
        """模拟LLM响应（实际使用时需要替换为真实的LLM调用）"""
        # 简单的关键词提取
        words = transcription.split()
        word_freq = defaultdict(int)
        for word in words:
            if len(word) > 2:  # 忽略太短的词
                word_freq[word] += 1
        
        # 获取高频词作为关键词
        keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        key_points = [f"关键词: {word}" for word, _ in keywords[:5]]
        
        # 生成简单的总结
        summary_length = min(200, len(transcription) // 4)
        summary = transcription[:summary_length] + "..." if len(transcription) > summary_length else transcription
        
        return {
            'summary': summary,
            'key_points': key_points,
            'action_items': []
        }

    def _simple_text_summary(self, transcription: str) -> Dict:
        """简单的文本分析总结"""
        try:
            # 分句
            sentences = re.split(r'[。！？]', transcription)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            # 提取关键句子（包含重要词汇的句子）
            important_words = ['重要', '关键', '需要', '必须', '记得', '注意', '问题', '解决']
            key_sentences = []
            
            for sentence in sentences:
                for word in important_words:
                    if word in sentence:
                        key_sentences.append(sentence)
                        break
            
            # 如果没有找到关键句子，使用前几句
            if not key_sentences:
                key_sentences = sentences[:3]
            
            summary = "。".join(key_sentences[:3]) + "。"
            
            # 提取关键词
            words = transcription.split()
            word_freq = defaultdict(int)
            for word in words:
                if len(word) > 2:
                    word_freq[word] += 1
            
            keywords = [word for word, _ in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:8]]
            
            return {
                'summary': summary,
                'key_points': [f"要点{i+1}: {point}" for i, point in enumerate(key_sentences[:5])],
                'action_items': []
            }
            
        except Exception as e:
            logger.error(f"简单文本总结失败: {e}")
            return {
                'summary': transcription[:100] + "..." if len(transcription) > 100 else transcription,
                'key_points': [],
                'action_items': []
            }

    async def _extract_keywords(self, transcription: str) -> List[str]:
        """提取关键词"""
        try:
            if not self.config['keyword_extraction']:
                return []
            
            # 简单的关键词提取
            words = transcription.split()
            word_freq = defaultdict(int)
            
            # 过滤停用词
            stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
            
            for word in words:
                if len(word) > 2 and word not in stop_words:
                    word_freq[word] += 1
            
            # 获取高频关键词
            keywords = [word for word, _ in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]]
            
            return keywords
            
        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return []

    async def _has_speech(self, audio_data: np.ndarray) -> bool:
        """检测音频中是否包含语音"""
        try:
            # 简单的能量检测
            energy = np.sum(audio_data ** 2) / len(audio_data)
            threshold = 0.001  # 能量阈值
            
            return energy > threshold
            
        except Exception as e:
            logger.error(f"语音检测失败: {e}")
            return False

    def _format_duration(self, seconds: float) -> str:
        """格式化时长为HH:MM:SS格式"""
        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            
        except Exception as e:
            logger.error(f"格式化时长失败: {e}")
            return "00:00:00"

    def _calculate_duration(self, start_time: str, end_time: str) -> str:
        """计算两个时间点之间的时长"""
        try:
            start_parts = start_time.split(':')
            end_parts = end_time.split(':')
            
            start_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(start_parts)))
            end_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(end_parts)))
            
            duration_seconds = end_seconds - start_seconds
            return self._format_duration(duration_seconds)
            
        except Exception as e:
            logger.error(f"计算时长失败: {e}")
            return "00:00:00"

    async def _save_analysis_result(self, result: Dict):
        """保存分析结果"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_{timestamp}.json"
            filepath = self.analysis_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"分析结果已保存: {filename}")
            
            # 同时保存转录和总结到各自的目录
            await self._save_transcription(result)
            await self._save_summary(result)
            
        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")

    async def _save_transcription(self, result: Dict):
        """保存转录结果"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"transcription_{timestamp}.json"
            filepath = self.transcriptions_dir / filename
            
            transcription_data = {
                'audio_file': result.get('audio_file', ''),
                'full_transcription': result.get('full_transcription', ''),
                'segments': result.get('transcriptions', []),
                'timestamp': result.get('timestamp', ''),
                'processing_time': result.get('processing_time', 0)
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(transcription_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存转录结果失败: {e}")

    async def _save_summary(self, result: Dict):
        """保存总结结果"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"summary_{timestamp}.json"
            filepath = self.summaries_dir / filename
            
            summary_data = {
                'audio_file': result.get('audio_file', ''),
                'summary': result.get('summary', {}),
                'keywords': result.get('keywords', []),
                'timestamp': result.get('timestamp', '')
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存总结结果失败: {e}")

    async def get_analysis_history(self, days: int = 7) -> List[Dict]:
        """获取分析历史"""
        try:
            history = []
            cutoff_time = datetime.now() - timedelta(days=days)
            
            for file_path in self.analysis_dir.glob("analysis_*.json"):
                stat = file_path.stat()
                if stat.st_mtime >= cutoff_time.timestamp():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        analysis_data = json.load(f)
                        history.append({
                            'filename': file_path.name,
                            'modified': stat.st_mtime,
                            'data': analysis_data
                        })
            
            # 按时间排序
            history.sort(key=lambda x: x['modified'], reverse=True)
            
            return history
            
        except Exception as e:
            logger.error(f"获取分析历史失败: {e}")
            return []

    async def cleanup_cache(self):
        """清理缓存"""
        try:
            self.analysis_cache.clear()
            logger.info("分析缓存已清理")
            
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")


# 使用示例
async def main():
    """主函数示例"""
    # 创建智能分析器
    analyzer = IntelligentAnalyzer(
        funasr_client=None,  # 实际使用时需要传入FunASR客户端
        llm_client=None      # 实际使用时需要传入LLM客户端
    )
    
    # 示例：处理音频文件
    # result = await analyzer.process_audio_file("test_audio.wav")
    # print(f"分析结果: {result}")
    
    # 获取分析历史
    history = await analyzer.get_analysis_history(days=7)
    print(f"最近7天的分析记录: {len(history)}条")


if __name__ == "__main__":
    asyncio.run(main())
