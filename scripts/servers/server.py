#!/usr/bin/env python3
"""
AutoDiary - 全自动音视频 Lifelog 服务器端程序

功能说明：
1. 接收并处理来自 XIAO ESP32S3 Sense 的视频流和音频流
2. 每30秒自动抓取一帧图片并保存到 data/Images/ 目录
3. 缓存音频数据，为 Whisper AI 语音识别做准备
4. 提供实时状态监控和统计信息

技术栈：
- WebSocket 服务器 (websockets 库)
- 异步处理 (asyncio)
- 图像处理 (PIL/Pillow)
- 音频处理准备 (future Whisper integration)

作者：自动开发代理
版本：v1.0
"""

import asyncio
import websockets
import json
import os
import time
import datetime
import base64
from pathlib import Path
import logging
from PIL import Image
import io
import threading
from typing import Dict, Optional, Set

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('autodiary_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoDiaryServer:
    """AutoDiary WebSocket 服务器主类"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.device_info = {}
        self.audio_config = {}
        
        # 数据存储路径
        self.base_dir = Path("data")
        self.images_dir = self.base_dir / "Images"
        self.audio_dir = self.base_dir / "Audio"
        self.logs_dir = self.base_dir / "Logs"
        
        # 创建目录
        self._create_directories()
        
        # 状态变量
        self.video_connected = False
        self.audio_connected = False
        self.last_image_time = 0
        self.image_count = 0
        self.audio_buffer = []
        self.total_audio_samples = 0
        
        # 统计信息
        self.stats = {
            'total_frames': 0,
            'total_audio_samples': 0,
            'images_saved': 0,
            'start_time': time.time(),
            'last_heartbeat': 0
        }
        
        logger.info(f"AutoDiary 服务器初始化完成")
        logger.info(f"监听地址: {host}:{port}")
        logger.info(f"图像存储目录: {self.images_dir.absolute()}")
        logger.info(f"音频存储目录: {self.audio_dir.absolute()}")

    def _create_directories(self):
        """创建必要的目录结构"""
        try:
            self.base_dir.mkdir(exist_ok=True)
            self.images_dir.mkdir(exist_ok=True)
            self.audio_dir.mkdir(exist_ok=True)
            self.logs_dir.mkdir(exist_ok=True)
            logger.info("目录结构创建成功")
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            raise

    async def handle_video_connection(self, websocket, path):
        """处理视频 WebSocket 连接"""
        if path != "/video":
            logger.warning(f"无效的视频路径: {path}")
            await websocket.close(1003, "Invalid path")
            return

        client_id = f"video_{id(websocket)}"
        self.clients[client_id] = websocket
        self.video_connected = True
        
        logger.info(f"视频客户端连接: {client_id}")
        
        try:
            async for message in websocket:
                await self._handle_video_message(websocket, message, client_id)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"视频客户端断开连接: {client_id}")
        except Exception as e:
            logger.error(f"视频连接处理错误: {e}")
        finally:
            if client_id in self.clients:
                del self.clients[client_id]
            self.video_connected = False

    async def handle_audio_connection(self, websocket, path):
        """处理音频 WebSocket 连接"""
        if path != "/audio":
            logger.warning(f"无效的音频路径: {path}")
            await websocket.close(1003, "Invalid path")
            return

        client_id = f"audio_{id(websocket)}"
        self.clients[client_id] = websocket
        self.audio_connected = True
        
        logger.info(f"音频客户端连接: {client_id}")
        
        try:
            async for message in websocket:
                await self._handle_audio_message(websocket, message, client_id)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"音频客户端断开连接: {client_id}")
        except Exception as e:
            logger.error(f"音频连接处理错误: {e}")
        finally:
            if client_id in self.clients:
                del self.clients[client_id]
            self.audio_connected = False

    async def _handle_video_message(self, websocket, message, client_id):
        """处理视频消息"""
        try:
            if isinstance(message, str):
                # 文本消息（设备信息、心跳等）
                await self._handle_text_message(message, "video")
            else:
                # 二进制消息（JPEG图像数据）
                await self._process_image_data(message)
                self.stats['total_frames'] += 1
                
        except Exception as e:
            logger.error(f"处理视频消息错误: {e}")

    async def _handle_audio_message(self, websocket, message, client_id):
        """处理音频消息"""
        try:
            if isinstance(message, str):
                # 文本消息（音频配置、心跳等）
                await self._handle_text_message(message, "audio")
            else:
                # 二进制消息（PCM音频数据）
                await self._process_audio_data(message)
                
        except Exception as e:
            logger.error(f"处理音频消息错误: {e}")

    async def _handle_text_message(self, message: str, msg_type: str):
        """处理文本消息"""
        try:
            if message == "heartbeat":
                self.stats['last_heartbeat'] = time.time()
                logger.debug(f"收到 {msg_type} 心跳")
                return

            # 尝试解析 JSON
            data = json.loads(message)
            msg_type_from_data = data.get("type", "")
            
            if msg_type_from_data == "device_info":
                self.device_info = data
                logger.info(f"收到设备信息: {data}")
                
            elif msg_type_from_data == "audio_config":
                self.audio_config = data
                logger.info(f"收到音频配置: {data}")
                
            elif msg_type_from_data == "heartbeat":
                self.stats['last_heartbeat'] = time.time()
                logger.debug(f"收到设备心跳: {data}")
                
            else:
                logger.debug(f"未处理的文本消息 ({msg_type}): {data}")
                
        except json.JSONDecodeError:
            logger.debug(f"非JSON文本消息 ({msg_type}): {message}")
        except Exception as e:
            logger.error(f"处理文本消息错误: {e}")

    async def _process_image_data(self, jpeg_data: bytes):
        """处理JPEG图像数据"""
        try:
            current_time = time.time()
            
            # 每30秒保存一张图片
            if current_time - self.last_image_time >= 30:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"autodiary_{timestamp}.jpg"
                filepath = self.images_dir / filename
                
                # 验证并保存图像
                try:
                    # 使用PIL验证图像数据
                    image = Image.open(io.BytesIO(jpeg_data))
                    
                    # 保存图像
                    with open(filepath, 'wb') as f:
                        f.write(jpeg_data)
                    
                    self.image_count += 1
                    self.stats['images_saved'] += 1
                    self.last_image_time = current_time
                    
                    # 生成图像信息
                    image_info = {
                        'filename': filename,
                        'filepath': str(filepath),
                        'size': len(jpeg_data),
                        'dimensions': image.size,
                        'format': image.format,
                        'timestamp': timestamp
                    }
                    
                    logger.info(f"图像已保存: {filename} ({image.size[0]}x{image.size[1]}, {len(jpeg_data)} bytes)")
                    
                    # 异步处理图像元数据
                    asyncio.create_task(self._process_image_metadata(image_info))
                    
                except Exception as e:
                    logger.error(f"图像处理失败: {e}")
                    # 即使处理失败，也更新时间戳以避免重复尝试
                    self.last_image_time = current_time
                    
        except Exception as e:
            logger.error(f"处理图像数据错误: {e}")

    async def _process_audio_data(self, pcm_data: bytes):
        """处理PCM音频数据"""
        try:
            # 将音频数据添加到缓冲区
            self.audio_buffer.append(pcm_data)
            self.total_audio_samples += len(pcm_data) // 2  # 16位音频，每样本2字节
            self.stats['total_audio_samples'] = self.total_audio_samples
            
            # 限制缓冲区大小，避免内存溢出
            max_buffer_size = 10 * 1024 * 1024  # 10MB
            if len(self.audio_buffer) > 0:
                total_size = sum(len(chunk) for chunk in self.audio_buffer)
                if total_size > max_buffer_size:
                    # 保留最新的数据
                    while total_size > max_buffer_size * 0.8 and len(self.audio_buffer) > 0:
                        total_size -= len(self.audio_buffer.pop(0))
            
            # 定期保存音频数据（每分钟）
            static_audio_counter = getattr(self, '_audio_save_counter', 0)
            static_audio_counter += len(pcm_data)
            
            if static_audio_counter >= self.audio_config.get('sample_rate', 16000) * 2 * 60:  # 1分钟数据
                await self._save_audio_chunk()
                static_audio_counter = 0
                
            setattr(self, '_audio_save_counter', static_audio_counter)
            
        except Exception as e:
            logger.error(f"处理音频数据错误: {e}")

    async def _process_image_metadata(self, image_info: dict):
        """处理图像元数据"""
        try:
            # 保存图像元数据到日志文件
            metadata_file = self.logs_dir / "image_metadata.jsonl"
            
            with open(metadata_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(image_info, ensure_ascii=False) + '\n')
                
        except Exception as e:
            logger.error(f"保存图像元数据错误: {e}")

    async def _save_audio_chunk(self):
        """保存音频数据块"""
        if not self.audio_buffer:
            return
            
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audio_chunk_{timestamp}.pcm"
            filepath = self.audio_dir / filename
            
            # 合并所有音频数据
            all_audio_data = b''.join(self.audio_buffer)
            
            with open(filepath, 'wb') as f:
                f.write(all_audio_data)
            
            logger.info(f"音频块已保存: {filename} ({len(all_audio_data)} bytes)")
            
            # 清空缓冲区
            self.audio_buffer.clear()
            
        except Exception as e:
            logger.error(f"保存音频块错误: {e}")

    async def _broadcast_status(self):
        """广播服务器状态"""
        while True:
            try:
                status = {
                    'type': 'server_status',
                    'timestamp': time.time(),
                    'uptime': time.time() - self.stats['start_time'],
                    'video_connected': self.video_connected,
                    'audio_connected': self.audio_connected,
                    'stats': {
                        'total_frames': self.stats['total_frames'],
                        'total_audio_samples': self.stats['total_audio_samples'],
                        'images_saved': self.stats['images_saved']
                    }
                }
                
                # 向所有连接的客户端广播状态
                for client_id, websocket in self.clients.items():
                    try:
                        await websocket.send(json.dumps(status))
                    except websockets.exceptions.ConnectionClosed:
                        continue
                        
            except Exception as e:
                logger.error(f"广播状态错误: {e}")
                
            await asyncio.sleep(10)  # 每10秒广播一次状态

    def start_whisper_processing_skeleton(self):
        """启动 Whisper 语音处理的骨架代码（待完善）"""
        logger.info("Whisper 语音处理骨架已启动（待集成）")
        
        def whisper_worker():
            """Whisper 处理工作线程"""
            while True:
                try:
                    if len(self.audio_buffer) > 0:
                        # TODO: 集成 Whisper AI 进行语音识别
                        # 1. 从缓冲区获取音频数据
                        # 2. 转换为 Whisper 所需格式
                        # 3. 调用 Whisper 进行转录
                        # 4. 处理转录结果（保存、优化、总结）
                        
                        logger.debug("Whisper 处理：音频数据可用（待实现）")
                        
                    time.sleep(1)  # 避免过度占用CPU
                    
                except Exception as e:
                    logger.error(f"Whisper 处理错误: {e}")
                    time.sleep(5)
        
        # 启动 Whisper 处理线程
        whisper_thread = threading.Thread(target=whisper_worker, daemon=True)
        whisper_thread.start()

    async def start_server(self):
        """启动服务器"""
        logger.info("正在启动 AutoDiary WebSocket 服务器...")
        
        # 启动 Whisper 处理骨架
        self.start_whisper_processing_skeleton()
        
        # 创建 WebSocket 服务器
        video_server = websockets.serve(
            self.handle_video_connection,
            self.host,
            self.port,
            subprotocols=["video-stream"]
        )
        
        audio_server = websockets.serve(
            self.handle_audio_connection,
            self.host,
            self.port,
            subprotocols=["audio-stream"]
        )
        
        # 启动服务器
        await asyncio.gather(
            video_server,
            audio_server,
            self._broadcast_status()
        )

def main():
    """主函数"""
    try:
        # 检查依赖
        try:
            import websockets
            import PIL
        except ImportError as e:
            logger.error(f"缺少必要的依赖库: {e}")
            logger.info("请安装依赖: pip install websockets pillow")
            return
        
        # 创建并启动服务器
        server = AutoDiaryServer(host="0.0.0.0", port=8000)
        
        # 运行服务器
        asyncio.run(server.start_server())
        
    except KeyboardInterrupt:
        logger.info("服务器被用户中断")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
    finally:
        logger.info("服务器已停止")

if __name__ == "__main__":
    main()
