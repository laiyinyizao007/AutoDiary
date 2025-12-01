#!/usr/bin/env python3
"""
兼容ESP32的WebSocket测试服务器
使用更简单的WebSocket实现来解决协议兼容性问题
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

class CompatibleWebSocketServer:
    """兼容ESP32的WebSocket服务器"""
    
    def __init__(self):
        self.video_clients = set()
        self.audio_clients = set()
        self.device_info = {}
        self.last_heartbeat = 0
        self.connection_count = 0
        
        # 创建数据目录
        Path("data").mkdir(exist_ok=True)
        Path("data/real_test").mkdir(exist_ok=True)
        
        logger.info("兼容WebSocket服务器初始化完成")

    async def handle_client(self, websocket, path):
        """处理客户端连接"""
        client_id = f"client_{self.connection_count}_{id(websocket)}"
        self.connection_count += 1
        
        # 根据路径确定客户端类型
        if "/video" in path:
            client_type = "video"
            self.video_clients.add(websocket)
            logger.info(f"🎥 视频客户端连接: {client_id}, 路径: {path}")
        elif "/audio" in path:
            client_type = "audio"
            self.audio_clients.add(websocket)
            logger.info(f"🎤 音频客户端连接: {client_id}, 路径: {path}")
        else:
            client_type = "unknown"
            logger.info(f"❓ 未知客户端连接: {client_id}, 路径: {path}")
        
        try:
            # 发送欢迎消息
            welcome_msg = {
                "type": "welcome",
                "server": "CompatibleWebSocketServer",
                "client_id": client_id,
                "timestamp": time.time()
            }
            await websocket.send(json.dumps(welcome_msg))
            
            # 处理消息
            async for message in websocket:
                try:
                    if isinstance(message, bytes):
                        # 处理二进制数据
                        await self._process_binary_data(message, client_type, client_id)
                    elif isinstance(message, str):
                        # 处理文本消息
                        await self._process_text_message(message, client_type, client_id)
                except Exception as e:
                    logger.error(f"处理消息错误 ({client_id}): {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 客户端断开连接: {client_id} ({client_type})")
        except websockets.exceptions.ConnectionClosedOK:
            logger.info(f"🔌 客户端正常关闭连接: {client_id} ({client_type})")
        except Exception as e:
            logger.error(f"客户端连接错误 ({client_id}): {e}")
        finally:
            # 清理客户端连接
            if client_type == "video":
                self.video_clients.discard(websocket)
            elif client_type == "audio":
                self.audio_clients.discard(websocket)

    async def _process_binary_data(self, data: bytes, client_type: str, client_id: str):
        """处理二进制数据"""
        try:
            if client_type == "video":
                await self._process_video_data(data, client_id)
            elif client_type == "audio":
                await self._process_audio_data(data, client_id)
        except Exception as e:
            logger.error(f"处理二进制数据错误 ({client_type}): {e}")

    async def _process_video_data(self, image_data: bytes, client_id: str):
        """处理视频数据"""
        try:
            # 每10张图像保存一张用于验证
            if not hasattr(self, 'image_count'):
                self.image_count = 0
            self.image_count += 1
            
            if self.image_count % 10 == 0:
                timestamp = int(time.time())
                filename = f"data/real_test/hardware_image_{timestamp}.jpg"
                
                with open(filename, 'wb') as f:
                    f.write(image_data)
                
                logger.info(f"📸 硬件图像保存: {filename}, 大小: {len(image_data)} bytes, 客户端: {client_id}")
            
            # 每30帧输出一次统计
            if self.image_count % 30 == 0:
                logger.info(f"🎥 硬件视频流: {self.image_count} 帧, 当前图像大小: {len(image_data)} bytes")
            
        except Exception as e:
            logger.error(f"处理视频数据失败: {e}")

    async def _process_audio_data(self, audio_data: bytes, client_id: str):
        """处理音频数据"""
        try:
            # 每100个音频包保存一次用于验证
            if not hasattr(self, 'audio_count'):
                self.audio_count = 0
            self.audio_count += 1
            
            if self.audio_count % 100 == 0:
                timestamp = int(time.time())
                filename = f"data/real_test/hardware_audio_{timestamp}.raw"
                
                with open(filename, 'wb') as f:
                    f.write(audio_data)
                
                logger.info(f"🎤 硬件音频保存: {filename}, 大小: {len(audio_data)} bytes, 客户端: {client_id}")
            
            # 每500个包输出一次统计
            if self.audio_count % 500 == 0:
                logger.info(f"🎤 硬件音频流: {self.audio_count} 包, 当前包大小: {len(audio_data)} bytes")
            
        except Exception as e:
            logger.error(f"处理音频数据失败: {e}")

    async def _process_text_message(self, message: str, client_type: str, client_id: str):
        """处理文本消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            
            if msg_type == "heartbeat":
                self.last_heartbeat = time.time()
                logger.info(f"💓 收到设备心跳 ({client_type}): {client_id}")
                
                # 回复心跳
                response = {
                    "type": "heartbeat_response",
                    "timestamp": time.time(),
                    "client_id": client_id
                }
                # 注意：这里我们需要找到对应的websocket来发送响应
                
            elif msg_type == "device_info":
                self.device_info = data
                logger.info(f"📱 硬件设备信息更新: {data}")
                
            elif msg_type == "audio_config":
                logger.info(f"🎵 硬件音频配置: {data}")
                
            else:
                logger.debug(f"📨 其他硬件消息 ({client_type}): {data}")
                
        except json.JSONDecodeError:
            logger.debug(f"非JSON硬件消息 ({client_type}): {message}")
        except Exception as e:
            logger.error(f"处理硬件消息失败: {e}")

    async def start_servers(self):
        """启动服务器"""
        try:
            logger.info("🚀 启动兼容WebSocket服务器...")
            
            # 启动服务器 - 使用更宽松的配置
            server = await websockets.serve(
                self.handle_client,
                "0.0.0.0",
                8888,
                ping_interval=None,  # 禁用ping
                ping_timeout=None,
                close_timeout=1,
                max_size=10**7,  # 10MB max message size
                compression=None  # 禁用压缩
            )
            
            logger.info("✅ 兼容WebSocket服务器启动完成")
            logger.info("🎥 视频流: ws://0.0.0.0:8888/video")
            logger.info("🎤 音频流: ws://0.0.0.0:8888/audio")
            logger.info("📡 等待ESP32设备连接...")
            
            # 启动监控任务
            monitor_task = asyncio.create_task(self._monitor_system())
            
            # 等待服务器运行
            await server.wait_closed()
            
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
                        logger.warning(f"⚠️ 硬件设备连接超时，最后心跳: {heartbeat_age:.1f}秒前")
                
                # 每30秒输出系统状态
                if int(time.time()) % 30 == 0:
                    status = {
                        'video_clients': len(self.video_clients),
                        'audio_clients': len(self.audio_clients),
                        'device_connected': len(self.video_clients) > 0 or len(self.audio_clients) > 0,
                        'last_heartbeat': self.last_heartbeat,
                        'device_info': self.device_info
                    }
                    logger.info(f"📊 系统状态: {json.dumps(status, indent=2)}")
                
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"系统监控错误: {e}")
                await asyncio.sleep(30)

async def main():
    """主函数"""
    try:
        server = CompatibleWebSocketServer()
        await server.start_servers()
        
    except KeyboardInterrupt:
        logger.info("👋 服务器被用户中断")
    except Exception as e:
        logger.error(f"服务器运行失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
