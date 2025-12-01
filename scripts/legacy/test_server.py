#!/usr/bin/env python3
"""
AutoDiary 端到端测试服务器

简化的测试服务器，用于验证硬件固件和服务器集成
"""

import asyncio
import websockets
import json
import time
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutoDiaryTestServer:
    """AutoDiary 测试服务器"""
    
    def __init__(self):
        self.video_clients = set()
        self.audio_clients = set()
        self.device_connected = False
        self.device_info = {}
        self.last_heartbeat = 0
        self.image_count = 0
        self.audio_data_count = 0
        
        # 创建数据目录
        Path("data").mkdir(exist_ok=True)
        Path("data/test_images").mkdir(exist_ok=True)
        Path("data/test_audio").mkdir(exist_ok=True)
        
        logger.info("AutoDiary测试服务器初始化完成")

    async def handle_video_client(self, websocket):
        """处理视频客户端连接"""
        self.video_clients.add(websocket)
        client_id = f"video_{id(websocket)}"
        logger.info(f"视频客户端连接: {client_id}")
        
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    # 处理图像数据
                    await self._process_video_data(message)
                elif isinstance(message, str):
                    # 处理文本消息
                    await self._process_device_message(message, "video")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"视频客户端断开: {client_id}")
        except Exception as e:
            logger.error(f"视频客户端处理错误: {e}")
        finally:
            self.video_clients.discard(websocket)

    async def handle_audio_client(self, websocket):
        """处理音频客户端连接"""
        self.audio_clients.add(websocket)
        client_id = f"audio_{id(websocket)}"
        logger.info(f"音频客户端连接: {client_id}")
        
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    # 处理音频数据
                    await self._process_audio_data(message)
                elif isinstance(message, str):
                    # 处理文本消息
                    await self._process_device_message(message, "audio")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"音频客户端断开: {client_id}")
        except Exception as e:
            logger.error(f"音频客户端处理错误: {e}")
        finally:
            self.audio_clients.discard(websocket)

    async def _process_video_data(self, image_data: bytes):
        """处理视频数据"""
        try:
            self.image_count += 1
            
            # 每隔10张图像保存一次
            if self.image_count % 10 == 0:
                timestamp = int(time.time())
                filename = f"data/test_images/test_image_{timestamp}.jpg"
                
                with open(filename, 'wb') as f:
                    f.write(image_data)
                
                logger.info(f"保存测试图像: {filename}, 大小: {len(image_data)} bytes")
            
            # 每30帧输出一次统计
            if self.image_count % 30 == 0:
                logger.info(f"视频流统计: {self.image_count} 帧, 当前图像大小: {len(image_data)} bytes")
            
        except Exception as e:
            logger.error(f"处理视频数据失败: {e}")

    async def _process_audio_data(self, audio_data: bytes):
        """处理音频数据"""
        try:
            self.audio_data_count += 1
            
            # 每隔100个音频包保存一次
            if self.audio_data_count % 100 == 0:
                timestamp = int(time.time())
                filename = f"data/test_audio/test_audio_{timestamp}.raw"
                
                with open(filename, 'wb') as f:
                    f.write(audio_data)
                
                logger.info(f"保存测试音频: {filename}, 大小: {len(audio_data)} bytes")
            
            # 每500个包输出一次统计
            if self.audio_data_count % 500 == 0:
                logger.info(f"音频流统计: {self.audio_data_count} 包, 当前包大小: {len(audio_data)} bytes")
            
        except Exception as e:
            logger.error(f"处理音频数据失败: {e}")

    async def _process_device_message(self, message: str, msg_type: str):
        """处理设备消息"""
        try:
            data = json.loads(message)
            
            if data.get("type") == "heartbeat":
                self.last_heartbeat = time.time()
                self.device_connected = True
                logger.debug(f"收到设备心跳 ({msg_type})")
                
            elif data.get("type") == "device_info":
                self.device_info = data
                logger.info(f"设备信息更新: {data}")
                
            elif data.get("type") == "audio_config":
                logger.info(f"音频配置: {data}")
                
            else:
                logger.debug(f"其他设备消息 ({msg_type}): {data}")
                
        except json.JSONDecodeError:
            logger.debug(f"非JSON设备消息 ({msg_type}): {message}")
        except Exception as e:
            logger.error(f"处理设备消息失败: {e}")

    async def start_servers(self):
        """启动服务器"""
        try:
            logger.info("正在启动AutoDiary测试服务器...")
            
            # 启动视频和音频服务器
            video_server = await websockets.serve(
                self.handle_video_client,
                "0.0.0.0",
                8000
            )
            
            audio_server = await websockets.serve(
                self.handle_audio_client,
                "0.0.0.0",
                8001
            )
            
            logger.info("AutoDiary测试服务器启动完成")
            logger.info("视频流: ws://0.0.0.0:8000/video")
            logger.info("音频流: ws://0.0.0.0:8001/audio")
            
            # 启动监控任务
            monitor_task = asyncio.create_task(self._monitor_system())
            
            # 等待服务器运行
            await asyncio.gather(
                video_server.wait_closed(),
                audio_server.wait_closed(),
                monitor_task
            )
            
        except Exception as e:
            logger.error(f"启动服务器失败: {e}")
            raise

    async def _monitor_system(self):
        """系统监控任务"""
        while True:
            try:
                # 检查设备连接状态
                if self.last_heartbeat > 0:
                    heartbeat_age = time.time() - self.last_heartbeat
                    if heartbeat_age > 60:  # 1分钟无心跳
                        self.device_connected = False
                        logger.warning(f"设备连接超时，最后心跳: {heartbeat_age:.1f}秒前")
                
                # 每30秒输出系统状态
                if int(time.time()) % 30 == 0:
                    status = {
                        'device_connected': self.device_connected,
                        'video_clients': len(self.video_clients),
                        'audio_clients': len(self.audio_clients),
                        'image_count': self.image_count,
                        'audio_data_count': self.audio_data_count,
                        'last_heartbeat': self.last_heartbeat
                    }
                    logger.info(f"系统状态: {json.dumps(status, indent=2)}")
                
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"系统监控错误: {e}")
                await asyncio.sleep(30)

async def main():
    """主函数"""
    try:
        server = AutoDiaryTestServer()
        await server.start_servers()
        
    except KeyboardInterrupt:
        logger.info("服务器被用户中断")
    except Exception as e:
        logger.error(f"服务器运行失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
