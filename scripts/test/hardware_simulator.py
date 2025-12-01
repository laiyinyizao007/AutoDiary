#!/usr/bin/env python3
"""
AutoDiary 硬件模拟器

模拟ESP32设备连接到测试服务器，用于端到端测试
"""

import asyncio
import websockets
import json
import time
import random
import numpy as np
from PIL import Image
import io
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HardwareSimulator:
    """硬件设备模拟器"""
    
    def __init__(self, server_host="localhost", video_port=8000, audio_port=8001):
        self.server_host = server_host
        self.video_port = video_port
        self.audio_port = audio_port
        self.running = False
        
        logger.info(f"硬件模拟器初始化完成，目标服务器: {server_host}")

    def generate_test_image(self):
        """生成测试图像"""
        # 创建一个640x480的彩色测试图像
        width, height = 640, 480
        
        # 生成随机颜色的测试图像
        image = Image.new('RGB', (width, height))
        pixels = image.load()
        
        # 创建渐变背景和一些随机矩形
        for y in range(height):
            for x in range(width):
                # 渐变背景
                r = int(255 * (x / width))
                g = int(255 * (y / height))
                b = int(255 * ((x + y) / (width + height)))
                pixels[x, y] = (r, g, b)
        
        # 添加一些随机矩形
        for _ in range(5):
            x1 = random.randint(0, width-50)
            y1 = random.randint(0, height-50)
            x2 = x1 + random.randint(20, 50)
            y2 = y1 + random.randint(20, 50)
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            for x in range(x1, min(x2, width)):
                for y in range(y1, min(y2, height)):
                    pixels[x, y] = color
        
        # 添加时间戳
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 转换为JPEG字节流
        img_buffer = io.BytesIO()
        image.save(img_buffer, 'JPEG', quality=85)
        img_buffer.seek(0)
        
        return img_buffer.getvalue()

    def generate_test_audio(self):
        """生成测试音频数据"""
        # 生成1秒的16kHz 16位单声道音频
        sample_rate = 16000
        duration = 0.1  # 100ms
        num_samples = int(sample_rate * duration)
        
        # 生成包含多个频率的测试音频
        t = np.linspace(0, duration, num_samples)
        
        # 混合多个频率的正弦波
        frequencies = [440, 880, 1320]  # A4, A5, E6
        audio_data = np.zeros(num_samples)
        
        for freq in frequencies:
            amplitude = random.uniform(0.1, 0.3)
            audio_data += amplitude * np.sin(2 * np.pi * freq * t)
        
        # 添加一些噪声
        noise = np.random.normal(0, 0.02, num_samples)
        audio_data += noise
        
        # 归一化到16位整数范围
        audio_data = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
        
        return audio_data.tobytes()

    async def send_device_info(self, websocket):
        """发送设备信息"""
        device_info = {
            "type": "device_info",
            "device": "XIAO_ESP32S3_SENSE_SIMULATOR",
            "camera": "OV2640",
            "resolution": "640x480",
            "format": "JPEG",
            "firmware_version": "1.0.0",
            "mac_address": "AA:BB:CC:DD:EE:FF"
        }
        
        await websocket.send(json.dumps(device_info))
        logger.info("设备信息已发送")

    async def send_audio_config(self, websocket):
        """发送音频配置"""
        audio_config = {
            "type": "audio_config",
            "sample_rate": 16000,
            "channels": 1,
            "format": "PCM16",
            "buffer_size": 512
        }
        
        await websocket.send(json.dumps(audio_config))
        logger.info("音频配置已发送")

    async def send_heartbeat(self, websocket):
        """发送心跳包"""
        heartbeat = {
            "type": "heartbeat",
            "timestamp": int(time.time() * 1000),
            "device": "XIAO_ESP32S3_SENSE_SIMULATOR"
        }
        
        await websocket.send(json.dumps(heartbeat))

    async def video_stream_task(self):
        """视频流任务"""
        retry_count = 0
        max_retries = 5
        
        while retry_count < max_retries and self.running:
            try:
                uri = f"ws://{self.server_host}:{self.video_port}/video"
                logger.info(f"连接视频服务器: {uri}")
                
                async with websockets.connect(uri) as websocket:
                    logger.info("视频服务器连接成功")
                    retry_count = 0  # 重置重试计数
                    
                    # 发送设备信息
                    await self.send_device_info(websocket)
                    
                    frame_count = 0
                    
                    while self.running:
                        # 生成并发送测试图像
                        image_data = self.generate_test_image()
                        await websocket.send(image_data)
                        
                        frame_count += 1
                        
                        # 每30帧输出一次统计
                        if frame_count % 30 == 0:
                            logger.info(f"发送视频帧: {frame_count}, 大小: {len(image_data)} bytes")
                        
                        # 控制帧率 (约15fps)
                        await asyncio.sleep(0.066)
                        
                        # 每10秒发送一次心跳
                        if frame_count % 150 == 0:
                            await self.send_heartbeat(websocket)
                        
            except Exception as e:
                retry_count += 1
                logger.error(f"视频流错误 (重试 {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(5)  # 等待5秒后重试
                else:
                    logger.error("视频流连接失败，已达到最大重试次数")

    async def audio_stream_task(self):
        """音频流任务"""
        retry_count = 0
        max_retries = 5
        
        while retry_count < max_retries and self.running:
            try:
                uri = f"ws://{self.server_host}:{self.audio_port}/audio"
                logger.info(f"连接音频服务器: {uri}")
                
                async with websockets.connect(uri) as websocket:
                    logger.info("音频服务器连接成功")
                    retry_count = 0  # 重置重试计数
                    
                    # 发送音频配置
                    await self.send_audio_config(websocket)
                    
                    packet_count = 0
                    
                    while self.running:
                        # 生成并发送测试音频
                        audio_data = self.generate_test_audio()
                        await websocket.send(audio_data)
                        
                        packet_count += 1
                        
                        # 每500个包输出一次统计
                        if packet_count % 500 == 0:
                            logger.info(f"发送音频包: {packet_count}, 大小: {len(audio_data)} bytes")
                        
                        # 控制音频包发送频率 (每100ms一个包)
                        await asyncio.sleep(0.1)
                        
                        # 每20秒发送一次心跳
                        if packet_count % 200 == 0:
                            await self.send_heartbeat(websocket)
                        
            except Exception as e:
                retry_count += 1
                logger.error(f"音频流错误 (重试 {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(5)  # 等待5秒后重试
                else:
                    logger.error("音频流连接失败，已达到最大重试次数")

    async def start_simulation(self):
        """启动模拟"""
        logger.info("启动硬件模拟器...")
        self.running = True
        
        try:
            # 同时启动视频和音频流任务
            await asyncio.gather(
                self.video_stream_task(),
                self.audio_stream_task()
            )
        except KeyboardInterrupt:
            logger.info("模拟器被用户中断")
        finally:
            self.running = False
            logger.info("硬件模拟器已停止")

async def main():
    """主函数"""
    try:
        simulator = HardwareSimulator(
            server_host="localhost",
            video_port=8000,
            audio_port=8001
        )
        
        await simulator.start_simulation()
        
    except Exception as e:
        logger.error(f"模拟器启动失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
