#!/usr/bin/env python3
"""
兼容的 WebSocket 服务器 - 专为 ESP32 WebSocket 客户端优化

该服务器使用 websocket-server 库，完全兼容 Arduino WebSockets 库
"""

import asyncio
import json
import time
import logging
import threading
from pathlib import Path
from datetime import datetime
from websocket_server import WebsocketServer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('websocket_compatible_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CompatibleWebSocketServer:
    """兼容的 WebSocket 服务器"""
    
    def __init__(self, host="0.0.0.0", video_port=8000, audio_port=8001):
        self.host = host
        self.video_port = video_port
        self.audio_port = audio_port
        
        self.video_server = None
        self.audio_server = None
        
        self.video_clients = {}
        self.audio_clients = {}
        
        self.device_info = {}
        self.last_heartbeat = 0
        self.device_connected = False
        
        self.data_dir = Path("data")
        self._ensure_data_dirs()
        
        self.image_save_interval = 30
        self.last_image_save = 0
        self.current_image = None
        
        self.audio_buffer = []
        
    def _ensure_data_dirs(self):
        """创建数据目录"""
        dirs = ["data/Images", "data/Audio", "data/Transcriptions", "data/Logs"]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
            
    def start_video_server(self):
        """启动视频 WebSocket 服务器"""
        def on_video_message(client, server, message):
            try:
                # 如果是二进制数据（图像）
                if isinstance(message, bytes):
                    self.current_image = message
                    current_time = time.time()
                    if current_time - self.last_image_save >= self.image_save_interval:
                        self._save_image(message)
                        self.last_image_save = current_time
                # 如果是文本消息
                elif isinstance(message, str):
                    try:
                        data = json.loads(message)
                        logger.info(f"📨 视频消息: {data.get('type', 'unknown')}")
                        
                        if data.get("type") == "device_info":
                            self.device_info = data
                            logger.info(f"📱 设备信息: {data.get('device', 'unknown')}")
                        elif data.get("type") == "heartbeat":
                            self.device_connected = True
                            self.last_heartbeat = time.time()
                            logger.debug("💓 收到视频心跳")
                    except json.JSONDecodeError:
                        logger.debug(f"非JSON文本: {message}")
            except Exception as e:
                logger.error(f"处理视频消息错误: {e}")
        
        def on_video_connect(client, server):
            logger.info(f"🎥 视频客户端已连接: {client['address']}")
            self.video_clients[client['id']] = client
            
        def on_video_close(client, server):
            logger.info(f"🎥 视频客户端已断开: {client['address']}")
            self.video_clients.pop(client['id'], None)
        
        self.video_server = WebsocketServer(
            host=self.host,
            port=self.video_port,
            loglevel=logging.INFO
        )
        
        self.video_server.set_fn_message_received(on_video_message)
        self.video_server.set_fn_client_left(on_video_close)
        self.video_server.set_fn_new_client(on_video_connect)
        
        logger.info(f"🎥 视频服务器启动: ws://{self.host}:{self.video_port}/video")
        
        # 在单独的线程中运行
        thread = threading.Thread(target=self.video_server.serve_forever)
        thread.daemon = True
        thread.start()
        
        return thread
    
    def start_audio_server(self):
        """启动音频 WebSocket 服务器"""
        def on_audio_message(client, server, message):
            try:
                # 如果是二进制数据（音频）
                if isinstance(message, bytes):
                    self.audio_buffer.append(message)
                    logger.debug(f"🎵 收到音频数据: {len(message)} bytes")
                    
                    # 限制缓冲区大小
                    if len(self.audio_buffer) > 100:
                        self.audio_buffer = self.audio_buffer[-50:]
                
                # 如果是文本消息
                elif isinstance(message, str):
                    try:
                        data = json.loads(message)
                        logger.info(f"📨 音频消息: {data.get('type', 'unknown')}")
                        
                        if data.get("type") == "audio_config":
                            logger.info(f"🎤 音频配置: {data.get('sample_rate')}Hz, {data.get('channels')}ch")
                        elif data.get("type") == "heartbeat":
                            self.device_connected = True
                            self.last_heartbeat = time.time()
                            logger.debug("💓 收到音频心跳")
                    except json.JSONDecodeError:
                        logger.debug(f"非JSON文本: {message}")
            except Exception as e:
                logger.error(f"处理音频消息错误: {e}")
        
        def on_audio_connect(client, server):
            logger.info(f"🎤 音频客户端已连接: {client['address']}")
            self.audio_clients[client['id']] = client
            
        def on_audio_close(client, server):
            logger.info(f"🎤 音频客户端已断开: {client['address']}")
            self.audio_clients.pop(client['id'], None)
        
        self.audio_server = WebsocketServer(
            host=self.host,
            port=self.audio_port,
            loglevel=logging.INFO
        )
        
        self.audio_server.set_fn_message_received(on_audio_message)
        self.audio_server.set_fn_client_left(on_audio_close)
        self.audio_server.set_fn_new_client(on_audio_connect)
        
        logger.info(f"🎤 音频服务器启动: ws://{self.host}:{self.audio_port}/audio")
        
        # 在单独的线程中运行
        thread = threading.Thread(target=self.audio_server.serve_forever)
        thread.daemon = True
        thread.start()
        
        return thread
    
    def _save_image(self, image_data: bytes):
        """保存图像"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"autodiary_{timestamp}.jpg"
            filepath = self.data_dir / "Images" / filename
            
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"📸 图像已保存: {filename} ({len(image_data)} bytes)")
            
        except Exception as e:
            logger.error(f"保存图像失败: {e}")
    
    def start_monitor(self):
        """启动监控线程"""
        def monitor():
            while True:
                try:
                    # 检查设备连接
                    if self.device_connected:
                        heartbeat_age = time.time() - self.last_heartbeat
                        if heartbeat_age > 60:
                            self.device_connected = False
                            logger.warning(f"⚠️ 设备连接超时 ({heartbeat_age:.1f}s)")
                    
                    # 输出状态
                    if int(time.time()) % 30 == 0:
                        status = {
                            'device_connected': self.device_connected,
                            'video_clients': len(self.video_clients),
                            'audio_clients': len(self.audio_clients),
                            'audio_buffer_size': len(self.audio_buffer),
                            'image_size': len(self.current_image) if self.current_image else 0
                        }
                        logger.info(f"📊 系统状态: {json.dumps(status)}")
                    
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"监控错误: {e}")
                    time.sleep(5)
        
        thread = threading.Thread(target=monitor)
        thread.daemon = True
        thread.start()
        
        return thread
    
    def run(self):
        """运行服务器"""
        logger.info("=" * 60)
        logger.info("🚀 AutoDiary 兼容 WebSocket 服务器启动")
        logger.info("=" * 60)
        
        # 启动各个服务器
        self.start_video_server()
        self.start_audio_server()
        self.start_monitor()
        
        logger.info("✅ 所有服务器已启动，等待设备连接...")
        logger.info(f"📍 视频端点: ws://0.0.0.0:{self.video_port}/video")
        logger.info(f"📍 音频端点: ws://0.0.0.0:{self.audio_port}/audio")
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n🛑 服务器停止")
            if self.video_server:
                self.video_server.shutdown()
            if self.audio_server:
                self.audio_server.shutdown()

def main():
    """主函数"""
    server = CompatibleWebSocketServer(
        host="0.0.0.0",
        video_port=8000,
        audio_port=8001
    )
    
    server.run()

if __name__ == "__main__":
    main()
