#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoDiary: Real-time speech recognition using sherpa_onnx + Paraformer
Based on reference project: minutes

Pipeline: Microphone -> VAD (Silero) -> ASR (Paraformer) -> LLM Optimize -> LLM Summarize -> Diary File
"""

import argparse
import sys
import os
import io

# Force unbuffered output and fix Windows console encoding
os.environ['PYTHONUNBUFFERED'] = '1'
if sys.platform == 'win32':
    # Use reconfigure to avoid breaking unbuffered mode
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
import threading
import queue
import time
import datetime
import warnings
from pathlib import Path
from typing import Callable, List

import numpy as np
import pyaudio
import onnxruntime
import sherpa_onnx
from openai import OpenAI
from scipy import signal

# ==================== VAD (from reference project) ====================

class OnnxWrapper():
    """Silero VAD ONNX Wrapper - supports multiple model versions"""

    def __init__(self, path, force_onnx_cpu=False):
        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1

        if force_onnx_cpu and 'CPUExecutionProvider' in onnxruntime.get_available_providers():
            self.session = onnxruntime.InferenceSession(path, providers=['CPUExecutionProvider'], sess_options=opts)
        else:
            self.session = onnxruntime.InferenceSession(path, sess_options=opts)

        # Detect model version by checking input names
        self.input_names = [inp.name for inp in self.session.get_inputs()]
        print(f"  [VAD] 模型输入: {self.input_names}")

        # Determine version: v3.1 uses h0/c0, v4+ uses state or h/c
        if 'state' in self.input_names:
            self.version = 'v5'  # Newest version with state
        elif 'h0' in self.input_names:
            self.version = 'v3'  # v3.1 uses h0/c0 without sr
        elif 'h' in self.input_names:
            self.version = 'v4'  # v4.x uses h/c with sr
        else:
            self.version = 'unknown'
        print(f"  [VAD] 检测到版本: {self.version}")

        self.reset_states()
        self.sample_rates = [8000, 16000]

    def _validate_input(self, x, sr: int):
        if x.ndim == 1:
            x = np.expand_dims(x, 0)
        if x.ndim > 2:
            raise ValueError(f"Too many dimensions for input audio chunk {x.ndim}")

        if sr != 16000 and (sr % 16000 == 0):
            step = sr // 16000
            x = x[:,::step]
            sr = 16000

        if sr not in self.sample_rates:
            raise ValueError(f"Supported sampling rates: {self.sample_rates} (or multiply of 16000)")

        if sr / x.shape[1] > 31.25:
            raise ValueError("Input audio chunk is too short")

        return x, sr

    def reset_states(self, batch_size=1):
        if self.version == 'v5':
            self._state = np.zeros((2, batch_size, 128)).astype('float32')
        else:
            # v3 and v4 both use h/c with shape (2, batch_size, 64)
            self._h = np.zeros((2, batch_size, 64)).astype('float32')
            self._c = np.zeros((2, batch_size, 64)).astype('float32')
        self._last_sr = 0
        self._last_batch_size = 0

    def __call__(self, x, sr: int):
        x, sr = self._validate_input(x, sr)
        batch_size = x.shape[0]

        if not self._last_batch_size:
            self.reset_states(batch_size)
        if (self._last_sr) and (self._last_sr != sr):
            self.reset_states(batch_size)
        if (self._last_batch_size) and (self._last_batch_size != batch_size):
            self.reset_states(batch_size)

        if sr in [8000, 16000]:
            if self.version == 'v5':
                # v5: uses 'input', 'state', 'sr'
                ort_inputs = {
                    'input': x,
                    'state': self._state,
                    'sr': np.array(sr, dtype='int64')
                }
                ort_outs = self.session.run(None, ort_inputs)
                out, self._state = ort_outs
            elif self.version == 'v3':
                # v3.1: uses 'input', 'h0', 'c0' (no sr input)
                ort_inputs = {'input': x, 'h0': self._h, 'c0': self._c}
                ort_outs = self.session.run(None, ort_inputs)
                out, self._h, self._c = ort_outs
            else:
                # v4: uses 'input', 'h', 'c', 'sr'
                ort_inputs = {'input': x, 'h': self._h, 'c': self._c, 'sr': np.array(sr, dtype='int64')}
                ort_outs = self.session.run(None, ort_inputs)
                out, self._h, self._c = ort_outs
        else:
            raise ValueError()

        self._last_sr = sr
        self._last_batch_size = batch_size

        return out


def get_speech_timestamps(audio,
                          model,
                          threshold: float = 0.5,
                          sampling_rate: int = 16000,
                          min_speech_duration_ms: int = 2500,  # 参考项目使用2500ms，保证足够上下文
                          max_speech_duration_s: float = 20,
                          min_silence_duration_ms: int = 100,
                          window_size_samples: int = 512,
                          speech_pad_ms: int = 30,
                          return_seconds: bool = False,
                          visualize_probs: bool = False,
                          progress_tracking_callback: Callable[[float], None] = None):
    """
    Split audio into speech chunks using Silero VAD - copied from reference project
    """
    audio = audio.astype(np.float32)
    if len(audio.shape) > 1:
        for i in range(len(audio.shape)):
            audio = audio.squeeze(0)
        if len(audio.shape) > 1:
            raise ValueError("More than one dimension in audio. Are you trying to process audio with 2 channels?")

    if sampling_rate > 16000 and (sampling_rate % 16000 == 0):
        step = sampling_rate // 16000
        sampling_rate = 16000
        audio = audio[::step]
        warnings.warn('Sampling rate is a multiply of 16000, casting to 16000 manually!')
    else:
        step = 1

    if sampling_rate == 8000 and window_size_samples > 768:
        warnings.warn('window_size_samples is too big for 8000 sampling_rate!')
    if window_size_samples not in [256, 512, 768, 1024, 1536]:
        warnings.warn('Unusual window_size_samples!')

    model.reset_states()
    min_speech_samples = sampling_rate * min_speech_duration_ms / 1000
    speech_pad_samples = sampling_rate * speech_pad_ms / 1000
    max_speech_samples = sampling_rate * max_speech_duration_s - window_size_samples - 2 * speech_pad_samples
    min_silence_samples = sampling_rate * min_silence_duration_ms / 1000
    min_silence_samples_at_max_speech = sampling_rate * 98 / 1000

    audio_length_samples = len(audio)

    speech_probs = []
    for current_start_sample in range(0, audio_length_samples, window_size_samples):
        chunk = audio[current_start_sample: current_start_sample + window_size_samples]
        if len(chunk) < window_size_samples:
            chunk = np.pad(chunk, (0, int(window_size_samples - len(chunk))), mode='constant', constant_values=0)
        out = model(chunk, sampling_rate)
        # v4 output: [batch, 1] shape, use .item() directly like reference project
        speech_prob = out.item()
        speech_probs.append(float(speech_prob))
        if progress_tracking_callback:
            progress = min(current_start_sample + window_size_samples, audio_length_samples)
            progress_tracking_callback((progress / audio_length_samples) * 100)

    # Debug: print speech_probs statistics
    if speech_probs:
        print(f"  [VAD概率] 最大: {max(speech_probs):.4f}, 平均: {np.mean(speech_probs):.4f}, 超过阈值({threshold})的窗口数: {sum(1 for p in speech_probs if p >= threshold)}")

    triggered = False
    speeches = []
    current_speech = {}
    neg_threshold = threshold - 0.15
    temp_end = 0
    prev_end = next_start = 0

    for i, speech_prob in enumerate(speech_probs):
        if (speech_prob >= threshold) and temp_end:
            temp_end = 0
            if next_start < prev_end:
               next_start = window_size_samples * i

        if (speech_prob >= threshold) and not triggered:
            triggered = True
            current_speech['start'] = window_size_samples * i
            continue

        if triggered and (window_size_samples * i) - current_speech['start'] > max_speech_samples:
            if prev_end:
                current_speech['end'] = prev_end
                speeches.append(current_speech)
                current_speech = {}
                if next_start < prev_end:
                    triggered = False
                else:
                    current_speech['start'] = next_start
                prev_end = next_start = temp_end = 0
            else:
                current_speech['end'] = window_size_samples * i
                speeches.append(current_speech)
                current_speech = {}
                prev_end = next_start = temp_end = 0
                triggered = False
                continue

        if (speech_prob < neg_threshold) and triggered:
            if not temp_end:
                temp_end = window_size_samples * i
            if ((window_size_samples * i) - temp_end) > min_silence_samples_at_max_speech:
                prev_end = temp_end
            if (window_size_samples * i) - temp_end < min_silence_samples:
                continue
            else:
                current_speech['end'] = temp_end
                if (current_speech['end'] - current_speech['start']) > min_speech_samples:
                    speeches.append(current_speech)
                current_speech = {}
                prev_end = next_start = temp_end = 0
                triggered = False
                continue

    if current_speech and (audio_length_samples - current_speech['start']) > min_speech_samples:
        current_speech['end'] = audio_length_samples
        speeches.append(current_speech)

    for i, speech in enumerate(speeches):
        if i == 0:
            speech['start'] = int(max(0, speech['start'] - speech_pad_samples))
        if i != len(speeches) - 1:
            silence_duration = speeches[i+1]['start'] - speech['end']
            if silence_duration < 2 * speech_pad_samples:
                speech['end'] += int(silence_duration // 2)
                speeches[i+1]['start'] = int(max(0, speeches[i+1]['start'] - silence_duration // 2))
            else:
                speech['end'] = int(min(audio_length_samples, speech['end'] + speech_pad_samples))
                speeches[i+1]['start'] = int(max(0, speeches[i+1]['start'] - speech_pad_samples))
        else:
            speech['end'] = int(min(audio_length_samples, speech['end'] + speech_pad_samples))

    if return_seconds:
        for speech_dict in speeches:
            speech_dict['start'] = round(speech_dict['start'] / sampling_rate, 1)
            speech_dict['end'] = round(speech_dict['end'] / sampling_rate, 1)
    elif step > 1:
        for speech_dict in speeches:
            speech_dict['start'] *= step
            speech_dict['end'] *= step

    return speeches


# ==================== ASR with VAD (from reference project) ====================

def process_time(milliseconds):
    delta = datetime.timedelta(milliseconds=milliseconds)
    time_str = str(delta)
    time_parts = time_str.split(".")[0].split(":")
    time_hms = "{:02d}:{:02d}:{:02d}".format(int(time_parts[0]), int(time_parts[1]), int(time_parts[2]))
    return time_hms


def transcribe_audio(recognizer, audio: np.ndarray, sample_rate: int = 16000) -> str:
    """Transcribe audio using Paraformer"""
    s = recognizer.create_stream()
    s.accept_waveform(sample_rate, audio)
    recognizer.decode_streams([s])
    return s.result.text


# ==================== LLM Processing ====================

def optimize_text(client: OpenAI, text: str) -> str:
    """Use LLM to optimize/correct ASR output"""
    if not client or not text or len(text.strip()) < 2:
        return text

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个文字校对助手。请修正语音识别结果中的错误，保持原意。只输出修正后的文字，不要添加任何解释。如果文字已经正确，直接输出原文。"},
                {"role": "user", "content": text}
            ],
            max_tokens=500,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM优化错误] {e}")
        return text


def summarize_text(client: OpenAI, text: str) -> str:
    """Use LLM to summarize text"""
    if not client or not text or len(text.strip()) < 10:
        return ""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "请用一句简短的话总结以下内容的主旨。只输出总结，不要任何前缀或解释。"},
                {"role": "user", "content": text}
            ],
            max_tokens=100,
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM总结错误] {e}")
        return ""


# ==================== Real-time Recording ====================

class RealtimeRecorder:
    """Real-time audio recorder with VAD-triggered processing

    优化策略（参考项目方式）：
    1. 使用滑动窗口 + 重叠区域，避免语音被截断
    2. 实时 VAD 检测：当检测到语音开始时开始累积，语音结束时触发处理
    3. 保留音频上下文，确保完整的语音片段
    """

    def __init__(self,
                 recognizer,
                 vad_model: OnnxWrapper,
                 openai_client: OpenAI,
                 device_index: int = 0,
                 sample_rate: int = 16000,
                 buffer_seconds: float = 30.0,
                 min_speech_ms: int = 500,  # 降低最小语音长度，让VAD自己判断
                 silence_threshold_ms: int = 2000,  # 静默阈值：增加到2秒，积累更多上下文
                 paragraph_gap_minutes: float = 1.0,  # 段落间隔：1分钟无语音视为新段落
                 save_audio: bool = False):  # 新增：是否保存音频

        self.recognizer = recognizer
        self.vad_model = vad_model
        self.openai_client = openai_client
        self.device_index = device_index
        self.target_sample_rate = sample_rate  # 目标采样率（VAD/ASR需要16kHz）
        self.device_sample_rate = sample_rate  # 设备实际采样率（启动时更新）
        self.buffer_seconds = buffer_seconds
        self.min_speech_ms = min_speech_ms
        self.silence_threshold_ms = silence_threshold_ms  # 静默阈值
        self.paragraph_gap_seconds = paragraph_gap_minutes * 60  # 转换为秒
        self.save_audio = save_audio  # 新增：是否保存音频

        self.chunk_size = 1024
        self.audio_buffer = []
        self.buffer_lock = threading.Lock()
        self.is_recording = False
        self.stream = None
        self.audio = None

        # VAD 状态追踪
        self.vad_window_samples = 512  # VAD 窗口大小
        self.is_speaking = False  # 当前是否在说话
        self.speech_start_time = None  # 语音开始时间
        self.last_speech_end_time = None  # 上次语音结束时间
        self.speech_audio_buffer = []  # 当前语音片段的音频

        # 累积的文本段落（用于批量总结）
        self.pending_texts = []  # [(timestamp, raw_text, optimized_text), ...]
        self.last_speech_time = None  # 上次语音的时间
        self.pending_lock = threading.Lock()

        # Output directories
        self.output_dir = Path(__file__).parent / "data" / "Transcripts"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.summary_dir = Path(__file__).parent / "data" / "Summary"
        self.summary_dir.mkdir(parents=True, exist_ok=True)

        # 音频保存相关（新增）
        self.wav_file = None
        self.audio_save_path = None
        self.audio_dir = Path(__file__).parent / "data" / "Audio"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.paragraph_start_time = None  # 当前段落开始时间

    def get_diary_path(self) -> Path:
        """Get today's diary file path"""
        today = datetime.date.today().strftime("%Y%m%d")
        return self.output_dir / f"diary_{today}.txt"

    def get_summary_path(self) -> Path:
        """Get today's summary file path"""
        today = datetime.date.today().strftime("%Y%m%d")
        return self.summary_dir / f"summary_{today}.txt"

    def start_paragraph_audio(self):
        """开始新段落的音频文件

        注意：在打开新文件前，先关闭并重命名旧文件。
        这样可以保证音频录制不会中断（在段落之间持续录制）。
        """
        if not self.save_audio:
            return

        # 先关闭上一个段落的音频文件（如果存在）
        if self.wav_file is not None:
            self.close_paragraph_audio()

        # 记录新段落开始时间
        self.paragraph_start_time = datetime.datetime.now()

        # 生成文件名: paragraph_YYYYMMDD_HHMMSS_HHMMSS.wav (第二个时间戳在关闭时更新)
        date_str = self.paragraph_start_time.strftime("%Y%m%d")
        start_time_str = self.paragraph_start_time.strftime("%H%M%S")

        # 临时文件名（段落结束时重命名）
        temp_filename = f"paragraph_{date_str}_{start_time_str}_temp.wav"
        self.audio_save_path = self.audio_dir / temp_filename

        # 打开 WAV 文件
        import wave
        self.wav_file = wave.open(str(self.audio_save_path), 'wb')
        self.wav_file.setnchannels(1)  # 单声道
        self.wav_file.setsampwidth(2)  # 16-bit
        self.wav_file.setframerate(self.device_sample_rate)  # 设备原始采样率

        print(f"[段落音频] 开始: {temp_filename}")

    def close_paragraph_audio(self):
        """关闭当前段落的音频文件并重命名"""
        if not self.save_audio or not self.wav_file:
            return

        # 关闭文件
        self.wav_file.close()
        self.wav_file = None

        # 生成最终文件名（包含起止时间戳）
        end_time = datetime.datetime.now()
        date_str = self.paragraph_start_time.strftime("%Y%m%d")
        start_time_str = self.paragraph_start_time.strftime("%H%M%S")
        end_time_str = end_time.strftime("%H%M%S")

        final_filename = f"paragraph_{date_str}_{start_time_str}_{end_time_str}.wav"
        final_path = self.audio_dir / final_filename

        # 重命名临时文件
        if self.audio_save_path.exists():
            self.audio_save_path.rename(final_path)
            print(f"[段落音频] 完成: {final_filename}")

        self.audio_save_path = None
        self.paragraph_start_time = None

    def append_single_entry(self, timestamp: str, raw_text: str, optimized_text: str):
        """实时写入单条识别结果到日记文件"""
        diary_path = self.get_diary_path()
        with open(diary_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}]\n")
            f.write(f"原文: {raw_text}\n")
            if optimized_text != raw_text:
                f.write(f"修正: {optimized_text}\n")
            f.write(f"{'-'*50}\n")

    def append_summary(self, entries: list, summary: str):
        """写入段落总结到 Summary 文件

        Args:
            entries: list of (timestamp, raw_text, optimized_text) tuples
            summary: summary of the whole paragraph
        """
        if not entries or not summary:
            return

        first_ts = entries[0][0]
        last_ts = entries[-1][0]

        summary_path = self.get_summary_path()
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(f"[{first_ts} - {last_ts}] {summary}\n")

    def flush_pending_texts(self):
        """Flush pending texts and generate summary for the paragraph"""
        with self.pending_lock:
            if not self.pending_texts:
                return

            entries = self.pending_texts.copy()
            self.pending_texts = []

        # 合并所有优化后的文本用于总结
        all_optimized = " ".join([e[2] for e in entries])

        print(f"\n[段落总结] 合并 {len(entries)} 条语音进行总结...")
        print(f"  合并文本: {all_optimized[:100]}..." if len(all_optimized) > 100 else f"  合并文本: {all_optimized}")

        # 生成段落总结
        summary = summarize_text(self.openai_client, all_optimized)
        if summary:
            print(f"  段落摘要: {summary}")

        # 写入 Summary 文件（只包含时间和总结）
        self.append_summary(entries, summary)
        print(f"  -> 摘要已保存到 Summary 文件")

        # 注意：不在这里关闭音频文件
        # 音频录制持续进行，文件会在下一段落开始时自动关闭并重命名

    def check_paragraph_gap(self):
        """Check if we should flush pending texts due to time gap"""
        with self.pending_lock:
            if not self.pending_texts or not self.last_speech_time:
                return False

            time_since_last = time.time() - self.last_speech_time
            return time_since_last >= self.paragraph_gap_seconds

    def process_buffer(self):
        """Process accumulated audio buffer

        关键：参考项目直接使用原始音频，不做增益调整！
        过度的预处理（如AGC）会导致识别准确性下降。
        """
        with self.buffer_lock:
            if not self.audio_buffer:
                return
            audio_data = np.concatenate(self.audio_buffer)
            self.audio_buffer = []

        # Audio statistics before processing
        max_amp = np.max(np.abs(audio_data))
        mean_amp = np.mean(np.abs(audio_data))
        print(f"  [音频统计] 样本数: {len(audio_data)} ({self.device_sample_rate}Hz), 最大值: {max_amp:.4f}, 平均: {mean_amp:.6f}")

        # Resample to target rate if needed (VAD/ASR requires 16kHz)
        if self.device_sample_rate != self.target_sample_rate:
            audio_data = signal.resample_poly(
                audio_data,
                self.target_sample_rate,
                self.device_sample_rate
            ).astype(np.float32)
            print(f"  [重采样] {self.device_sample_rate}Hz -> {self.target_sample_rate}Hz, 样本数: {len(audio_data)}")

        # 参考项目不做任何增益调整，直接使用原始音频
        # 只确保音频在合理范围内（-1.0 到 1.0）
        max_amp = np.max(np.abs(audio_data))
        if max_amp > 1.0:
            # 如果超出范围，进行归一化
            audio_data = audio_data / max_amp
            print(f"  [归一化] 原始最大值 {max_amp:.4f} 超出范围，已归一化")

        # Get speech timestamps using VAD (always at target_sample_rate = 16kHz)
        # 关键优化：增加 min_silence_duration_ms 以合并相邻片段，提供更多上下文给 ASR
        timestamps = get_speech_timestamps(
            audio_data,
            self.vad_model,
            threshold=0.5,
            sampling_rate=self.target_sample_rate,
            min_speech_duration_ms=1000,  # 最小 1 秒，与 ASR 最小长度一致
            min_silence_duration_ms=500,  # 增加静默容忍到 500ms，更好地合并片段
            window_size_samples=512,
            max_speech_duration_s=20,
            speech_pad_ms=200  # 增加前后填充到 200ms，获取更多上下文
        )

        print(f"  [VAD结果] 检测到 {len(timestamps)} 个语音片段")

        if not timestamps:
            return

        # Process each speech segment (参考项目的处理方式)
        for ts in timestamps:
            segment = audio_data[ts['start']:ts['end']]
            duration_ms = (ts['end'] - ts['start']) / self.target_sample_rate * 1000

            print(f"\n[处理语音片段] 时长: {duration_ms/1000:.1f}秒, 样本数: {len(segment)}")

            # Ensure minimum audio length for Paraformer (at least 1 second)
            # 太短的片段会导致 ONNX Runtime "negative tensor shape" 错误
            min_samples = int(self.target_sample_rate * 1.0)  # 增加到 1 秒
            if len(segment) < min_samples:
                print(f"  -> 音频太短 ({duration_ms:.0f}ms < 1000ms)，跳过")
                continue

            # 参考项目直接使用原始音频数据，不做额外处理
            # 只确保是 float32 类型
            segment = segment.astype(np.float32)

            # Transcribe with Paraformer (参考项目方式)
            try:
                # 参考项目: s.accept_waveform(sample_rate, samples)
                s = self.recognizer.create_stream()
                s.accept_waveform(self.target_sample_rate, segment)
                self.recognizer.decode_streams([s])
                raw_text = s.result.text
            except Exception as e:
                # 捕获 ONNX Runtime 错误（通常是片段太短导致的 tensor shape 错误）
                error_msg = str(e)
                if "negative value" in error_msg or "tensor shape" in error_msg.lower():
                    print(f"  -> 片段可能太短，ONNX 错误，跳过")
                else:
                    print(f"  -> ASR 错误: {e}")
                continue

            if not raw_text or len(raw_text.strip()) < 2:
                print("  -> 无有效内容")
                continue

            print(f"  原始识别: {raw_text}")

            # LLM optimize
            optimized_text = optimize_text(self.openai_client, raw_text)
            if optimized_text != raw_text:
                print(f"  优化结果: {optimized_text}")

            # 实时写入日记
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.append_single_entry(timestamp, raw_text, optimized_text)
            print(f"  -> 已写入日记")

            # 累积到待处理列表（用于后续生成 Summary）
            with self.pending_lock:
                # 如果是新段落的第一条语音，开始新的音频文件
                is_first_text = len(self.pending_texts) == 0

                self.pending_texts.append((timestamp, raw_text, optimized_text))
                self.last_speech_time = time.time()
                pending_count = len(self.pending_texts)

                # 开始新段落的音频文件
                if is_first_text and self.wav_file is None:
                    self.start_paragraph_audio()

            print(f"  -> 已累积 (当前段落共 {pending_count} 条语音，等待静默后生成摘要)")

    def process_speech_segment(self, audio_chunks: list):
        """处理检测到的语音片段（VAD 触发后调用）

        这个方法在 VAD 检测到语音结束后被调用，处理累积的完整语音片段。
        与 process_buffer 不同，这里的音频是 VAD 确认的完整语音。
        """
        if not audio_chunks:
            return

        # 合并音频
        audio_data = np.concatenate(audio_chunks)
        duration_sec = len(audio_data) / self.device_sample_rate

        print(f"\n[处理语音] 时长: {duration_sec:.1f}秒, 样本数: {len(audio_data)}")

        # 重采样到16kHz
        if self.device_sample_rate != self.target_sample_rate:
            audio_data = signal.resample_poly(
                audio_data,
                self.target_sample_rate,
                self.device_sample_rate
            ).astype(np.float32)

        # 确保音频在合理范围内
        max_amp = np.max(np.abs(audio_data))
        if max_amp > 1.0:
            audio_data = audio_data / max_amp

        # 使用完整的 VAD 再次确认语音片段
        # 关键优化：增加 min_silence_duration_ms 以合并相邻片段，提供更多上下文给 ASR
        # 这样可以减少碎片化，提高识别准确率
        self.vad_model.reset_states()
        timestamps = get_speech_timestamps(
            audio_data,
            self.vad_model,
            threshold=0.5,
            sampling_rate=self.target_sample_rate,
            min_speech_duration_ms=1000,  # 最小 1 秒，与 ASR 最小长度一致
            min_silence_duration_ms=500,  # 增加静默容忍到 500ms，更好地合并片段
            window_size_samples=512,
            max_speech_duration_s=20,
            speech_pad_ms=200  # 增加前后填充到 200ms，获取更多上下文
        )

        if not timestamps:
            print("  -> VAD 未检测到有效语音片段")
            return

        print(f"  [VAD] 确认 {len(timestamps)} 个语音片段")

        # 处理每个语音片段
        for ts in timestamps:
            segment = audio_data[ts['start']:ts['end']]
            segment_duration_ms = (ts['end'] - ts['start']) / self.target_sample_rate * 1000

            # 确保最小长度（Paraformer 模型需要至少 1 秒的音频才能正常工作）
            # 太短的片段会导致 ONNX Runtime "negative tensor shape" 错误
            min_samples = int(self.target_sample_rate * 1.0)  # 增加到 1 秒
            if len(segment) < min_samples:
                print(f"  -> 片段太短 ({segment_duration_ms:.0f}ms < 1000ms)，跳过")
                continue

            # ASR 识别
            try:
                segment = segment.astype(np.float32)
                s = self.recognizer.create_stream()
                s.accept_waveform(self.target_sample_rate, segment)
                self.recognizer.decode_streams([s])
                raw_text = s.result.text
            except Exception as e:
                # 捕获 ONNX Runtime 错误（通常是片段太短导致的 tensor shape 错误）
                error_msg = str(e)
                if "negative value" in error_msg or "tensor shape" in error_msg.lower():
                    print(f"  -> 片段可能太短，ONNX 错误，跳过")
                else:
                    print(f"  -> ASR 错误: {e}")
                continue

            if not raw_text or len(raw_text.strip()) < 2:
                print("  -> 无有效内容")
                continue

            print(f"  原始识别: {raw_text}")

            # LLM 优化
            optimized_text = optimize_text(self.openai_client, raw_text)
            if optimized_text != raw_text:
                print(f"  优化结果: {optimized_text}")

            # 实时写入日记
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.append_single_entry(timestamp, raw_text, optimized_text)
            print(f"  -> 已写入日记")

            # 累积到待处理列表
            with self.pending_lock:
                # 如果是新段落的第一条语音，开始新的音频文件
                is_first_text = len(self.pending_texts) == 0

                self.pending_texts.append((timestamp, raw_text, optimized_text))
                self.last_speech_time = time.time()
                pending_count = len(self.pending_texts)

                # 开始新段落的音频文件
                if is_first_text and self.wav_file is None:
                    self.start_paragraph_audio()

            print(f"  -> 已累积 (当前段落共 {pending_count} 条)")

    def audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for recording - VAD 驱动的智能处理"""
        audio_chunk = np.frombuffer(in_data, dtype=np.float32)

        # 先保存到 WAV 文件（如果启用）
        if self.save_audio and self.wav_file:
            # 转换 float32 [-1.0, 1.0] 到 int16 [-32768, 32767]
            audio_int16 = (audio_chunk * 32767).astype(np.int16)
            self.wav_file.writeframes(audio_int16.tobytes())

        # 然后再进行 VAD 和识别处理
        with self.buffer_lock:
            self.audio_buffer.append(audio_chunk)

            # 累积足够的音频后进行 VAD 检测
            total_samples = sum(len(chunk) for chunk in self.audio_buffer)

            # 每秒检测一次 VAD 状态
            if total_samples >= self.device_sample_rate:
                # 获取最近1秒的音频进行VAD检测
                recent_audio = np.concatenate(self.audio_buffer)

                # 重采样到16kHz用于VAD
                if self.device_sample_rate != self.target_sample_rate:
                    recent_audio_16k = signal.resample_poly(
                        recent_audio,
                        self.target_sample_rate,
                        self.device_sample_rate
                    ).astype(np.float32)
                else:
                    recent_audio_16k = recent_audio.astype(np.float32)

                # 检测VAD（取最后一个窗口的概率）
                if len(recent_audio_16k) >= self.vad_window_samples:
                    chunk_for_vad = recent_audio_16k[-self.vad_window_samples:]
                    try:
                        vad_prob = self.vad_model(chunk_for_vad, self.target_sample_rate).item()
                    except:
                        vad_prob = 0.0

                    current_time = time.time()

                    # 状态机：检测语音开始和结束
                    if vad_prob >= 0.5:  # 检测到语音
                        if not self.is_speaking:
                            # 语音开始
                            self.is_speaking = True
                            self.speech_start_time = current_time
                            print(f"\n[VAD] 检测到语音开始 (prob={vad_prob:.2f})")
                        self.last_speech_end_time = current_time
                        # 累积语音音频
                        self.speech_audio_buffer.extend(self.audio_buffer)
                        self.audio_buffer = []
                    else:  # 静默
                        if self.is_speaking:
                            # 检查静默持续时间
                            silence_duration = (current_time - self.last_speech_end_time) * 1000
                            if silence_duration >= self.silence_threshold_ms:
                                # 语音结束，触发处理
                                print(f"\n[VAD] 检测到语音结束 (静默 {silence_duration:.0f}ms)")
                                self.is_speaking = False
                                # 把剩余音频也加入
                                self.speech_audio_buffer.extend(self.audio_buffer)
                                self.audio_buffer = []
                                # 后台处理
                                audio_to_process = self.speech_audio_buffer.copy()
                                self.speech_audio_buffer = []
                                threading.Thread(
                                    target=self.process_speech_segment,
                                    args=(audio_to_process,),
                                    daemon=True
                                ).start()
                            else:
                                # 短暂静默，继续累积
                                self.speech_audio_buffer.extend(self.audio_buffer)
                                self.audio_buffer = []
                        else:
                            # 持续静默，只保留最近的音频作为上下文
                            max_context = int(self.device_sample_rate * 2)  # 保留2秒上下文
                            if total_samples > max_context:
                                # 只保留最后2秒
                                all_audio = np.concatenate(self.audio_buffer)
                                self.audio_buffer = [all_audio[-max_context:]]

            # 防止缓冲区过大（安全阀）
            if total_samples >= self.device_sample_rate * self.buffer_seconds:
                print(f"\n[安全阀] 缓冲区已满 ({total_samples/self.device_sample_rate:.1f}秒)，强制处理")
                if self.speech_audio_buffer:
                    self.speech_audio_buffer.extend(self.audio_buffer)
                    audio_to_process = self.speech_audio_buffer.copy()
                    self.speech_audio_buffer = []
                else:
                    audio_to_process = self.audio_buffer.copy()
                self.audio_buffer = []
                self.is_speaking = False
                threading.Thread(
                    target=self.process_speech_segment,
                    args=(audio_to_process,),
                    daemon=True
                ).start()

        return (None, pyaudio.paContinue)

    def paragraph_monitor_thread(self):
        """Background thread to monitor paragraph gap and trigger summarization"""
        while self.is_recording:
            time.sleep(10)  # 每10秒检查一次

            if self.check_paragraph_gap():
                print(f"\n[检测到静默] 超过 {self.paragraph_gap_seconds/60:.1f} 分钟无新语音，触发段落总结...")
                self.flush_pending_texts()

    def start(self):
        """Start recording"""
        self.audio = pyaudio.PyAudio()

        # Get device info and determine actual sample rate to use
        device_info = self.audio.get_device_info_by_index(self.device_index)
        device_default_rate = int(device_info['defaultSampleRate'])

        # Use device's default sample rate (will resample to target_sample_rate later)
        self.device_sample_rate = device_default_rate

        print(f"\n[使用设备] {device_info['name']}")
        print(f"[设备采样率] {self.device_sample_rate} Hz")
        if self.device_sample_rate != self.target_sample_rate:
            print(f"[目标采样率] {self.target_sample_rate} Hz (将自动重采样)")
        print(f"[缓冲区上限] {self.buffer_seconds} 秒")
        print(f"[最小语音长度] {self.min_speech_ms} ms")
        print(f"[静默阈值] {self.silence_threshold_ms} ms (超过此时间触发处理)")
        print(f"[段落间隔] {self.paragraph_gap_seconds/60:.1f} 分钟 (超过此时间视为新段落)")
        print(f"[模式] VAD 驱动的智能触发（语音结束后自动处理）")

        if self.save_audio:
            print(f"[音频保存] 按段落分段保存到 {self.audio_dir}")

        print(f"\n开始录音... 按 Ctrl+C 停止\n")

        self.stream = self.audio.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.device_sample_rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk_size,
            stream_callback=self.audio_callback
        )

        self.is_recording = True
        self.stream.start_stream()

        # 启动段落监控线程
        monitor_thread = threading.Thread(target=self.paragraph_monitor_thread, daemon=True)
        monitor_thread.start()

        try:
            while self.is_recording and self.stream.is_active():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n停止录音...")
        finally:
            self.stop()

    def stop(self):
        """Stop recording"""
        self.is_recording = False

        # Process remaining speech audio buffer
        if self.speech_audio_buffer or self.audio_buffer:
            print("处理剩余音频...")
            all_remaining = self.speech_audio_buffer + self.audio_buffer
            if all_remaining:
                self.process_speech_segment(all_remaining)
            self.speech_audio_buffer = []
            self.audio_buffer = []

        # Flush any pending texts (final paragraph)
        if self.pending_texts:
            print("处理剩余累积文本...")
            self.flush_pending_texts()

        # 关闭最后一个段落的音频文件（如果有）
        if self.wav_file:
            self.close_paragraph_audio()

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if self.audio:
            self.audio.terminate()

        print(f"\n日记已保存到: {self.get_diary_path()}")


def list_audio_devices():
    """List available audio input devices"""
    audio = pyaudio.PyAudio()
    print("\n可用的音频输入设备:")
    print("-" * 50)
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f"  [{i}] {info['name']}")
    print("-" * 50)
    audio.terminate()


def get_args():
    parser = argparse.ArgumentParser(description="AutoDiary: Real-time speech recognition with Paraformer")

    parser.add_argument("--paraformer", type=str,
                        default="./models/paraformer",
                        help="Path to paraformer model directory")
    parser.add_argument("--vad", type=str,
                        default="./models/silero_vad_v4.onnx",
                        help="Path to silero_vad.onnx (v4.0 is recommended)")
    parser.add_argument("--openai-key", type=str, default=os.environ.get("OPENAI_API_KEY", ""),
                        help="OpenAI API key (or set OPENAI_API_KEY env var)")
    parser.add_argument("--device", type=int, default=0,
                        help="Audio input device index")
    parser.add_argument("--buffer-seconds", type=float, default=30.0,
                        help="Maximum audio buffer size in seconds (safety valve)")
    parser.add_argument("--min-speech", type=int, default=500,
                        help="Minimum speech duration in ms (default: 500)")
    parser.add_argument("--silence-threshold", type=int, default=2000,
                        help="Silence threshold in ms to trigger processing (default: 2000). "
                             "Higher value = more context for better accuracy.")
    parser.add_argument("--paragraph-gap", type=float, default=5.0,
                        help="Paragraph gap in minutes (default: 5.0). "
                             "If no speech for this duration, trigger paragraph summarization.")
    parser.add_argument("--save-audio", action="store_true",
                        help="Save raw audio to WAV file while recognizing (default: False)")
    parser.add_argument("--list-devices", action="store_true",
                        help="List audio devices and exit")

    return parser.parse_args()


def main():
    args = get_args()

    if args.list_devices:
        list_audio_devices()
        return

    # Resolve paths
    script_dir = Path(__file__).parent
    paraformer_dir = script_dir / args.paraformer
    vad_path = script_dir / args.vad

    token_file = str(paraformer_dir / "tokens.txt")
    model_file = str(paraformer_dir / "model.onnx")

    # Check model files
    if not Path(model_file).exists():
        print(f"错误: Paraformer模型不存在: {model_file}")
        print("请运行以下命令下载模型:")
        print(f"  curl -L -o {model_file} https://huggingface.co/csukuangfj/sherpa-onnx-paraformer-zh-2023-03-28/resolve/main/model.onnx")
        sys.exit(1)

    if not Path(token_file).exists():
        print(f"错误: tokens.txt 不存在: {token_file}")
        sys.exit(1)

    if not Path(vad_path).exists():
        print(f"错误: VAD模型不存在: {vad_path}")
        sys.exit(1)

    print("加载模型...")

    # Load Paraformer ASR
    print("  - 加载 Paraformer ASR...")
    recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
        paraformer=model_file,
        tokens=token_file,
        num_threads=2,
        sample_rate=16000,
        feature_dim=80,
        decoding_method="greedy_search",
        debug=False,
    )

    # Load VAD
    print("  - 加载 Silero VAD...")
    vad_model = OnnxWrapper(str(vad_path))

    # Initialize OpenAI client (optional)
    openai_client = None
    if args.openai_key:
        print("  - 初始化 OpenAI 客户端...")
        openai_client = OpenAI(api_key=args.openai_key)
    else:
        print("  - 跳过 OpenAI 客户端 (未提供 API Key，将跳过 LLM 优化)")

    print("模型加载完成!")

    # List devices
    list_audio_devices()

    # Start recorder
    recorder = RealtimeRecorder(
        recognizer=recognizer,
        vad_model=vad_model,
        openai_client=openai_client,
        device_index=args.device,
        buffer_seconds=args.buffer_seconds,
        min_speech_ms=args.min_speech,
        silence_threshold_ms=args.silence_threshold,
        paragraph_gap_minutes=args.paragraph_gap,
        save_audio=args.save_audio  # 新增：传递音频保存参数
    )

    recorder.start()


if __name__ == "__main__":
    main()
