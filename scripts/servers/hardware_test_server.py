#!/usr/bin/env python3
"""
硬件测试服务器 - 使用不同端口避免冲突
"""

import asyncio
import websockets
import json
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HardwareTestServer:
    def __init__(self):
        self.video_clients = set()
        self.audio_clients = set()
        self.device_info = {}
        self.last_heartbeat = 0
        Path("data/real_test").mkdir(parents=True, exist_ok=True)
        logger.info("硬件测试服务器初始化完成")

    async def handle_video_client(self, websocket):
        self.video_clients.add(websocket)
        client_id = f"video_{id(websocket)}"
        logger.info(f"🎥 视频客户端连接: {client_id}")
        
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    await self._process_video_data(message, client_id)
                elif isinstance(message, str):
                    await self._process_device_message(message, "video", client_id)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🎥 视频客户端断开: {client_id}")
        finally:
            self.video_clients.discard(websocket)

    async def handle_audio_client(self, websocket):
        self.audio_clients.add(websocket)
        client_id = f"audio_{id(websocket)}"
        logger.info(f"🎤 音频客户端连接: {client_id}")
        
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    await self._process_audio_data(message, client_id)
                elif isinstance(message, str):
                    await self._process_device_message(message, "audio", client_id)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🎤 音频客户端断开: {client_id}")
        finally:
            self.audio_clients.discard(websocket)

    async def _process_video_data(self, image_data: bytes, client_id):
        try:
            if not hasattr(self, 'image_count'):
                self.image_count = 0
            self.image_count += 1
            
            if self.image_count % 10 == 0:
                timestamp = int(time.time())
                filename = f"data/real_test/hardware_image_{timestamp}.jpg"
                with open(filename, 'wb') as f:
                    f.write(image_data)
                logger.info(f"📸 硬件图像保存: {filename}, 大小: {len(image_data)} bytes")
            
            if self.image_count % 30 == 0:
                logger.info(f"🎥 硬件视频流: {self.image_count} 帧, 大小: {len(image_data)} bytes")
        except Exception as e:
            logger.error(f"处理视频数据失败: {e}")

    async def _process_audio_data(self, audio_data: bytes, client_id):
        try:
            if not hasattr(self, 'audio_count'):
                self.audio_count = 0
            self.audio_count += 1
            
            if self.audio_count % 100 == 0:
                timestamp = int(time.time())
                filename = f"data/real_test/hardware_audio_{timestamp}.raw"
                with open(filename, 'wb') as f:
                    f.write(audio_data)
                logger.info(f"🎤 硬件音频保存: {filename}, 大小: {len(audio_data)} bytes")
            
            if self.audio_count % 500 == 0:
                logger.info(f"🎤 硬件音频流: {self.audio_count} 包, 大小: {len(audio_data)} bytes")
        except Exception as e:
            logger.error(f"处理音频数据失败: {e}")

    async def _process_device_message(self, message: str, msg_type: str, client_id):
        try:
            data = json.loads(message)
            
            if data.get("type") == "heartbeat":
                self.last_heartbeat = time.time()
                logger.info(f"💓 收到硬件心跳 ({msg_type}): {client_id}")
                
            elif data.get("type") == "device_info":
                self.device_info = data
                logger.info(f"📱 硬件设备信息: {data}")
                
            elif data.get("type") == "audio_config":
                logger.info(f"🎵 硬件音频配置: {data}")
                
        except Exception as e:
            logger.error(f"处理硬件消息失败: {e}")

    async def start_servers(self):
        try:
            logger.info("🚀 启动硬件测试服务器...")
            
            # 使用不同端口避免冲突
            video_server = await websockets.serve(
                self.handle_video_client,
                "0.0.0.0",
                9000  # 使用9000端口
            )
            
            audio_server = await websockets.serve(
                self.handle_audio_client,
                "0.0.0.0",
                9001  # 使用9001端口
            )
            
            logger.info("✅ 硬件测试服务器启动完成")
            logger.info("🎥 视频流: ws://0.0.0.0:9000/video")
            logger.info("🎤 音频流: ws://0.0.0.0:9001/audio")
            logger.info("📡 等待ESP32硬件设备连接...")
            
            monitor_task = asyncio.create_task(self._monitor_system())
            
            await asyncio.gather(
                video_server.wait_closed(),
                audio_server.wait_closed(),
                monitor_task
            )
            
        except Exception as e:
            logger.error(f"启动服务器失败: {e}")
            raise

    async def _monitor_system(self):
        while True:
            try:
                if int(time.time()) % 30 == 0:
                    status = {
                        'video_clients': len(self.video_clients),
                        'audio_clients': len(self.audio_clients),
                        'device_connected': len(self.video_clients) > 0 or len(self.audio_clients) > 0,
                        'device_info': self.device_info
                    }
                    logger.info(f"📊 硬件测试状态: {json.dumps(status, indent=2)}")
                
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"监控错误: {e}")
                await asyncio.sleep(30)

async def main():
    try:
        server = HardwareTestServer()
        await server.start_servers()
    except KeyboardInterrupt:
        logger.info("👋 测试服务器被用户中断")
    except Exception as e:
        logger.error(f"服务器运行失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
