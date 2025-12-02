#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoDiary: Streaming speech recognition with character-by-character output
Uses sherpa_onnx OnlineRecognizer for real-time streaming ASR

Key Features:
1. Character-by-character output (逐字输出)
2. Dynamic text correction based on context (上下文修正)
3. Text can be revised as more audio arrives (已显示的文字可被后续修改)

Pipeline: Microphone -> Streaming ASR (Paraformer) -> Dynamic Display -> LLM Correction -> Diary File
"""

import argparse
import sys
import os
import io

# Force unbuffered output and fix Windows console encoding
os.environ['PYTHONUNBUFFERED'] = '1'
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

import threading
import time
import datetime
from pathlib import Path

import numpy as np
import pyaudio
import sherpa_onnx
from openai import OpenAI
from scipy import signal


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
        print(f"\n[LLM优化错误] {e}")
        return text


# ==================== Streaming Display ====================

class StreamingDisplay:
    """Handle character-by-character display with revision support

    Key Features:
    1. Shows text progressively as it's being recognized
    2. Can revise previously displayed text when context changes
    3. Uses ANSI escape codes to update display in-place
    """

    def __init__(self):
        self.current_text = ""
        self.finalized_text = ""
        self.display_lock = threading.Lock()

    def update_partial(self, text: str):
        """Update the current partial result (can be revised)"""
        with self.display_lock:
            # Clear the current partial display and show new text
            if self.current_text:
                # Move cursor back and clear
                clear_len = len(self.current_text.encode('utf-8'))
                sys.stdout.write('\r' + ' ' * (clear_len + 20) + '\r')

            self.current_text = text
            # Show partial result in different color/style
            sys.stdout.write(f"\r[识别中] {text}")
            sys.stdout.flush()

    def finalize(self, text: str):
        """Finalize the current text (no more revisions)"""
        with self.display_lock:
            # Clear partial display
            if self.current_text:
                clear_len = len(self.current_text.encode('utf-8'))
                sys.stdout.write('\r' + ' ' * (clear_len + 20) + '\r')

            self.finalized_text += text + " "
            self.current_text = ""
            # Show finalized result
            sys.stdout.write(f"\n[完成] {text}\n")
            sys.stdout.flush()

    def get_finalized_text(self) -> str:
        """Get all finalized text"""
        with self.display_lock:
            return self.finalized_text.strip()


# ==================== Streaming Recorder ====================

class StreamingRecorder:
    """Real-time streaming speech recognition with character-by-character output

    Uses sherpa_onnx OnlineRecognizer for streaming ASR.

    Key Behavior:
    1. Audio is fed to the recognizer in small chunks (streaming)
    2. get_result() returns partial results that grow as more audio arrives
    3. When is_endpoint() returns True, the current utterance is complete
    4. Previous partial results may be revised based on new context
    """

    def __init__(self,
                 recognizer: sherpa_onnx.OnlineRecognizer,
                 openai_client: OpenAI,
                 device_index: int = 0,
                 sample_rate: int = 16000):

        self.recognizer = recognizer
        self.openai_client = openai_client
        self.device_index = device_index
        self.target_sample_rate = sample_rate
        self.device_sample_rate = sample_rate

        self.chunk_size = 1600  # 100ms at 16kHz
        self.is_recording = False
        self.stream = None
        self.audio = None

        # Streaming ASR state
        self.online_stream = None
        self.last_result = ""
        self.segment_id = 0

        # Display handler
        self.display = StreamingDisplay()

        # Pending finalized segments for LLM processing
        self.pending_segments = []
        self.pending_lock = threading.Lock()

        # Output directories
        self.output_dir = Path(__file__).parent / "data" / "Transcripts"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_diary_path(self) -> Path:
        """Get today's diary file path"""
        today = datetime.date.today().strftime("%Y%m%d")
        return self.output_dir / f"diary_{today}.txt"

    def append_entry(self, timestamp: str, raw_text: str, optimized_text: str):
        """Write a single entry to diary file"""
        diary_path = self.get_diary_path()
        with open(diary_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}]\n")
            f.write(f"原文: {raw_text}\n")
            if optimized_text != raw_text:
                f.write(f"修正: {optimized_text}\n")
            f.write(f"{'-'*50}\n")

    def process_segment(self, text: str):
        """Process a finalized segment: LLM optimize and save"""
        if not text or len(text.strip()) < 2:
            return

        # LLM optimize
        optimized = optimize_text(self.openai_client, text)

        # Save to diary
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.append_entry(timestamp, text, optimized)

        if optimized != text:
            print(f"[LLM修正] {optimized}")

    def audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback - feed audio to streaming recognizer"""
        audio_chunk = np.frombuffer(in_data, dtype=np.float32)

        # Resample if needed
        if self.device_sample_rate != self.target_sample_rate:
            audio_chunk = signal.resample_poly(
                audio_chunk,
                self.target_sample_rate,
                self.device_sample_rate
            ).astype(np.float32)

        # Ensure audio is in valid range
        max_amp = np.max(np.abs(audio_chunk))
        if max_amp > 1.0:
            audio_chunk = audio_chunk / max_amp

        # Feed to streaming recognizer
        self.online_stream.accept_waveform(self.target_sample_rate, audio_chunk)

        # Decode and get result
        while self.recognizer.is_ready(self.online_stream):
            self.recognizer.decode_stream(self.online_stream)

        # Get current result (may revise previous partial result)
        result = self.recognizer.get_result(self.online_stream)

        # Only update display if result changed (avoid redundant refreshes)
        if result and result != self.last_result:
            # Update display with current partial result
            # This may revise what was shown before!
            self.display.update_partial(result)
            self.last_result = result

        # Check if endpoint detected (utterance complete)
        if self.recognizer.is_endpoint(self.online_stream):
            if result and len(result.strip()) > 0:
                # Finalize this segment
                self.display.finalize(result)

                # Process in background (LLM + save)
                segment_text = result
                threading.Thread(
                    target=self.process_segment,
                    args=(segment_text,),
                    daemon=True
                ).start()

            # Reset stream for next utterance
            self.recognizer.reset(self.online_stream)
            self.last_result = ""  # Reset for next segment

        return (None, pyaudio.paContinue)

    def start(self):
        """Start streaming recording"""
        self.audio = pyaudio.PyAudio()

        # Get device info
        device_info = self.audio.get_device_info_by_index(self.device_index)
        self.device_sample_rate = int(device_info['defaultSampleRate'])

        print(f"\n{'='*60}")
        print(f"[流式识别模式] 实时逐字输出 + 动态修正")
        print(f"{'='*60}")
        print(f"[设备] {device_info['name']}")
        print(f"[采样率] {self.device_sample_rate} Hz -> {self.target_sample_rate} Hz")
        print(f"\n[说明]")
        print(f"  - 文字会随着你说话实时显示")
        print(f"  - 已显示的文字可能会被修正（根据后续上下文）")
        print(f"  - 语句结束后会进行 LLM 优化并保存")
        print(f"\n按 Ctrl+C 停止\n")
        print(f"{'='*60}\n")

        # Create online stream
        self.online_stream = self.recognizer.create_stream()

        # Open audio stream
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

        # Process any remaining result
        if self.online_stream:
            result = self.recognizer.get_result(self.online_stream)
            if result and len(result.strip()) > 0:
                self.display.finalize(result)
                self.process_segment(result)

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
    parser = argparse.ArgumentParser(
        description="AutoDiary: Streaming speech recognition with character-by-character output"
    )

    parser.add_argument("--model-dir", type=str,
                        default="./models/sherpa-onnx-streaming-paraformer-bilingual-zh-en",
                        help="Path to streaming paraformer model directory")
    parser.add_argument("--use-int8", action="store_true",
                        help="Use int8 quantized model for faster inference")
    parser.add_argument("--openai-key", type=str, default=os.environ.get("OPENAI_API_KEY", ""),
                        help="OpenAI API key for LLM correction (or set OPENAI_API_KEY env var)")
    parser.add_argument("--device", type=int, default=0,
                        help="Audio input device index")
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
    model_dir = script_dir / args.model_dir

    if args.use_int8:
        encoder_file = str(model_dir / "encoder.int8.onnx")
        decoder_file = str(model_dir / "decoder.int8.onnx")
    else:
        encoder_file = str(model_dir / "encoder.onnx")
        decoder_file = str(model_dir / "decoder.onnx")

    tokens_file = str(model_dir / "tokens.txt")

    # Check model files
    for f in [encoder_file, decoder_file, tokens_file]:
        if not Path(f).exists():
            print(f"错误: 模型文件不存在: {f}")
            print("\n请确保已下载流式 Paraformer 模型:")
            print("  https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/")
            print("  sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2")
            sys.exit(1)

    print("加载模型...")

    # Create Online Recognizer for streaming ASR
    print("  - 加载流式 Paraformer ASR...")
    recognizer = sherpa_onnx.OnlineRecognizer.from_paraformer(
        encoder=encoder_file,
        decoder=decoder_file,
        tokens=tokens_file,
        num_threads=2,
        sample_rate=16000,
        feature_dim=80,
        enable_endpoint_detection=True,
        rule1_min_trailing_silence=2.4,  # Endpoint rule 1: silence after speech
        rule2_min_trailing_silence=1.2,  # Endpoint rule 2: shorter silence
        rule3_min_utterance_length=20.0, # Endpoint rule 3: max utterance length
    )

    # Initialize OpenAI client
    openai_client = None
    if args.openai_key:
        print("  - 初始化 OpenAI 客户端...")
        openai_client = OpenAI(api_key=args.openai_key)
    else:
        print("  - 跳过 OpenAI 客户端 (将跳过 LLM 优化)")

    print("模型加载完成!")

    # List devices
    list_audio_devices()

    # Start streaming recorder
    recorder = StreamingRecorder(
        recognizer=recognizer,
        openai_client=openai_client,
        device_index=args.device,
    )

    recorder.start()


if __name__ == "__main__":
    main()
