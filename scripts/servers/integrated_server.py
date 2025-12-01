#!/usr/bin/env python3
"""
AutoDiary 集成服务器

整合 FunASR 语音识别、摄像头Web管理、智能分析等功能模块，
提供完整的 AutoDiary 系统服务。

功能：
- WebSocket 音视频流处理
- FunASR 语音识别集成
- 摄像头 Web 管理界面
- 智能音频分析
- 数据存储和管理
- 系统监控和日志

作者：AutoDiary开发团队
版本：v1.0
"""

import asyncio
import websockets
import json
import time
import logging
import signal
import sys
from pathlib import Path
from typing import Dict, Set, Optional
import threading

# 导入自定义模块
try:
    from funasr_client import FunASRClient
    from camera_web_server import CameraWebServer
    from intelligent_analyzer import IntelligentAnalyzer
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有模块文件都在同一目录下")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('integrated_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoDiaryIntegratedServer:
    """AutoDiary 集成服务器主类"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        初始化集成服务器
        
        Args:
            config_file: 配置文件路径
        """
        self.config = self._load_config(config_file)
        
        # 服务器组件
        self.funasr_client: Optional[FunASRClient] = None
        self.camera_web_server: Optional[CameraWebServer] = None
        self.intelligent_analyzer: Optional[IntelligentAnalyzer] = None
        
        # WebSocket 连接管理
        self.video_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.audio_clients: Set[websockets.WebSocketServerProtocol] = set()
        
        # 设备连接状态
        self.device_connected = False
        self.device_info = {}
        self.last_heartbeat = 0
        
        # 数据存储
        self.data_dir = Path("data")
        self.audio_buffer = []
        self.current_image = None
        
        # 运行状态
        self.running = False
        
        logger.info("AutoDiary集成服务器初始化完成")

    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 设置默认值
            default_config = {
                "server": {
                    "host": "0.0.0.0",
                    "video_port": 8000,
                    "audio_port": 8001,
                    "web_port": 8080
                },
                "features": {
                    "funasr_enabled": True,
                    "camera_web_enabled": True,
                    "intelligent_analysis": True
                },
                "funasr": {
                    "model_name": "paraformer-zh",
                    "device": "cuda",
                    "sample_rate": 16000
                },
                "camera": {
                    "auto_capture_interval": 30,
                    "image_quality": 95
                },
                "analysis": {
                    "min_segment_duration": 2.0,
                    "max_segment_duration": 30.0
                }
            }
            
            # 合并配置
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if sub_key not in config[key]:
                            config[key][sub_key] = sub_value
            
            logger.info("配置文件加载成功")
            return config
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            logger.info("使用默认配置")
            return {
                "server": {"host": "0.0.0.0", "video_port": 8000, "audio_port": 8001, "web_port": 8080},
                "features": {"funasr_enabled": True, "camera_web_enabled": True, "intelligent_analysis": True},
                "funasr": {"model_name": "paraformer-zh", "device": "cuda", "sample_rate": 16000},
                "camera": {"auto_capture_interval": 30, "image_quality": 95},
                "analysis": {"min_segment_duration": 2.0, "max_segment_duration": 30.0}
            }

    async def initialize(self) -> bool:
        """初始化所有组件"""
        try:
            logger.info("正在初始化AutoDiary集成服务器...")
            
            # 1. 初始化 FunASR 客户端
            if self.config["features"]["funasr_enabled"]:
                logger.info("初始化FunASR客户端...")
                self.funasr_client = FunASRClient(
                    model_name=self.config["funasr"]["model_name"],
                    device=self.config["funasr"]["device"],
                    sample_rate=self.config["funasr"]["sample_rate"]
                )
                
                if await self.funasr_client.initialize():
                    logger.info("FunASR客户端初始化成功")
                else:
                    logger.warning("FunASR客户端初始化失败，将禁用语音识别功能")
                    self.funasr_client = None
            
            # 2. 初始化摄像头Web服务器
            if self.config["features"]["camera_web_enabled"]:
                logger.info("初始化摄像头Web服务器...")
                self.camera_web_server = CameraWebServer(
                    host=self.config["server"]["host"],
                    web_port=self.config["server"]["web_port"],
                    websocket_port=self.config["server"]["audio_port"] + 1
                )
                logger.info("摄像头Web服务器初始化成功")
            
            # 3. 初始化智能分析器
            if self.config["features"]["intelligent_analysis"]:
                logger.info("初始化智能分析器...")
                self.intelligent_analyzer = IntelligentAnalyzer(
                    funasr_client=self.funasr_client,
                    llm_client=None,  # 可以在这里集成LLM客户端
                    data_dir="data"
                )
                logger.info("智能分析器初始化成功")
            
            # 4. 创建数据目录
            await self._create_data_directories()
            
            logger.info("AutoDiary集成服务器初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    async def _create_data_directories(self):
        """创建数据存储目录"""
        try:
            directories = [
                "data/Images",
                "data/Audio", 
                "data/Transcriptions",
                "data/Summaries",
                "data/Analysis",
                "data/Logs"
            ]
            
            for dir_path in directories:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
            
            logger.info("数据目录创建完成")
            
        except Exception as e:
            logger.error(f"创建数据目录失败: {e}")

    async def start_video_server(self):
        """启动视频WebSocket服务器"""
        async def handle_video_client(websocket, path):
            if path != "/video":
                await websocket.close(1003, "Invalid path")
                return
            
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
        
        # 启动服务器
        server = await websockets.serve(
            handle_video_client,
            self.config["server"]["host"],
            self.config["server"]["video_port"]
        )
        
        logger.info(f"视频服务器启动: ws://{self.config['server']['host']}:{self.config['server']['video_port']}/video")
        return server

    async def start_audio_server(self):
        """启动音频WebSocket服务器"""
        async def handle_audio_client(websocket, path):
            if path != "/audio":
                await websocket.close(1003, "Invalid path")
                return
            
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
        
        # 启动服务器
        server = await websockets.serve(
            handle_audio_client,
            self.config["server"]["host"],
            self.config["server"]["audio_port"]
        )
        
        logger.info(f"音频服务器启动: ws://{self.config['server']['host']}:{self.config['server']['audio_port']}/audio")
        return server

    async def _process_video_data(self, image_data: bytes):
        """处理视频数据"""
        try:
            # 保存当前图像
            self.current_image = image_data
            
            # 如果启用了摄像头Web服务器，转发图像数据
            if self.camera_web_server:
                await self.camera_web_server._process_camera_image(image_data)
            
            # 定期保存图像
            current_time = time.time()
            if current_time - getattr(self, '_last_image_save', 0) >= self.config["camera"]["auto_capture_interval"]:
                await self._save_image(image_data)
                self._last_image_save = current_time
            
        except Exception as e:
            logger.error(f"处理视频数据失败: {e}")

    async def _process_audio_data(self, audio_data: bytes):
        """处理音频数据"""
        try:
            # 添加到音频缓冲区
            import numpy as np
            
            # 转换为numpy数组
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            self.audio_buffer.append(audio_array)
            
            # 限制缓冲区大小
            max_buffer_duration = 300  # 5分钟
            current_duration = sum(len(chunk) for chunk in self.audio_buffer) / 16000
            if current_duration > max_buffer_duration:
                # 保留最新的4分钟
                target_duration = 240
                while current_duration > target_duration and self.audio_buffer:
                    removed_chunk = self.audio_buffer.pop(0)
                    current_duration -= len(removed_chunk) / 16000
            
            # 如果启用了智能分析器，进行实时处理
            if self.intelligent_analyzer and self.funasr_client:
                # 检查是否有足够的音频数据进行处理
                total_samples = sum(len(chunk) for chunk in self.audio_buffer)
                if total_samples >= 16000 * 10:  # 10秒音频
                    await self._process_realtime_audio()
            
        except Exception as e:
            logger.error(f"处理音频数据失败: {e}")

    async def _process_realtime_audio(self):
        """处理实时音频"""
        try:
            if not self.audio_buffer:
                return
            
            # 合并音频数据
            import numpy as np
            full_audio = np.concatenate(self.audio_buffer[-10:])  # 使用最近10个块
            
            # 使用智能分析器进行实时处理
            session_id = f"device_{int(time.time())}"
            result = await self.intelligent_analyzer.process_real_time_audio(
                full_audio, 
                session_id
            )
            
            if result:
                logger.info(f"实时音频处理结果: {result['transcription']['text'][:50]}...")
                
                # 保存实时转录结果
                await self._save_realtime_transcription(result)
                
                # 清空部分缓冲区
                self.audio_buffer = self.audio_buffer[-5:]  # 保留最后5个块
            
        except Exception as e:
            logger.error(f"实时音频处理失败: {e}")

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
                
            elif data.get("type") == "status":
                logger.debug(f"设备状态: {data}")
                
            else:
                logger.debug(f"其他设备消息 ({msg_type}): {data}")
                
        except json.JSONDecodeError:
            logger.debug(f"非JSON设备消息 ({msg_type}): {message}")
        except Exception as e:
            logger.error(f"处理设备消息失败: {e}")

    async def _save_image(self, image_data: bytes):
        """保存图像"""
        try:
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"autodiary_{timestamp}.jpg"
            filepath = self.data_dir / "Images" / filename
            
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"图像已保存: {filename}")
            
        except Exception as e:
            logger.error(f"保存图像失败: {e}")

    async def _save_realtime_transcription(self, result: Dict):
        """保存实时转录结果"""
        try:
            from datetime import datetime
            import json
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"realtime_{timestamp}.json"
            filepath = self.data_dir / "Transcriptions" / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            logger.error(f"保存实时转录失败: {e}")

    async def start_servers(self):
        """启动所有服务器"""
        try:
            logger.info("正在启动AutoDiary集成服务器...")
            
            # 启动WebSocket服务器
            video_server = await self.start_video_server()
            audio_server = await self.start_audio_server()
            
            # 启动摄像头Web服务器
            web_server_task = None
            if self.camera_web_server:
                web_server_task = asyncio.create_task(
                    self.camera_web_server.start_servers()
                )
            
            # 启动监控任务
            monitor_task = asyncio.create_task(self._monitor_system())
            
            self.running = True
            logger.info("AutoDiary集成服务器启动完成")
            logger.info(f"视频流: ws://{self.config['server']['host']}:{self.config['server']['video_port']}/video")
            logger.info(f"音频流: ws://{self.config['server']['host']}:{self.config['server']['audio_port']}/audio")
            if self.camera_web_server:
                logger.info(f"Web界面: http://{self.config['server']['host']}:{self.config['server']['web_port']}")
            
            # 等待所有任务
            tasks = [monitor_task]
            if web_server_task:
                tasks.append(web_server_task)
            
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"启动服务器失败: {e}")
            raise

    async def _monitor_system(self):
        """系统监控任务"""
        while self.running:
            try:
                # 检查设备连接状态
                if self.last_heartbeat > 0:
                    heartbeat_age = time.time() - self.last_heartbeat
                    if heartbeat_age > 60:  # 1分钟无心跳
                        self.device_connected = False
                        logger.warning(f"设备连接超时，最后心跳: {heartbeat_age:.1f}秒前")
                
                # 清理音频缓冲区
                if len(self.audio_buffer) > 100:
                    self.audio_buffer = self.audio_buffer[-50:]  # 保留最后50个块
                    logger.info("音频缓冲区已清理")
                
                # 记录系统状态
                if int(time.time()) % 300 == 0:  # 每5分钟记录一次
                    await self._log_system_status()
                
                await asyncio.sleep(10)  # 每10秒检查一次
                
            except Exception as e:
                logger.error(f"系统监控错误: {e}")
                await asyncio.sleep(30)

    async def _log_system_status(self):
        """记录系统状态"""
        try:
            status = {
                'timestamp': time.time(),
                'device_connected': self.device_connected,
                'video_clients': len(self.video_clients),
                'audio_clients': len(self.audio_clients),
                'audio_buffer_size': len(self.audio_buffer),
                'funasr_available': self.funasr_client is not None,
                'camera_web_available': self.camera_web_server is not None,
                'intelligent_analyzer_available': self.intelligent_analyzer is not None,
                'last_heartbeat': self.last_heartbeat
            }
            
            logger.info(f"系统状态: {json.dumps(status, indent=2)}")
            
        except Exception as e:
            logger.error(f"记录系统状态失败: {e}")

    async def stop(self):
        """停止服务器"""
        try:
            logger.info("正在停止AutoDiary集成服务器...")
            
            self.running = False
            
            # 关闭WebSocket连接
            for client in self.video_clients.copy():
                await client.close()
            for client in self.audio_clients.copy():
                await client.close()
            
            # 清理组件资源
            if self.funasr_client:
                await self.funasr_client.cleanup()
            
            if self.camera_web_server:
                await self.camera_web_server.cleanup()
            
            if self.intelligent_analyzer:
                await self.intelligent_analyzer.cleanup_cache()
            
            logger.info("AutoDiary集成服务器已停止")
            
        except Exception as e:
            logger.error(f"停止服务器失败: {e}")

    def setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，正在停止服务器...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


# 主函数
async def main():
    """主函数"""
    try:
        # 创建集成服务器
        server = AutoDiaryIntegratedServer("config.json")
        
        # 设置信号处理器
        server.setup_signal_handlers()
        
        # 初始化服务器
        if await server.initialize():
            logger.info("服务器初始化成功")
            
            # 启动服务器
            await server.start_servers()
        else:
            logger.error("服务器初始化失败")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("服务器被用户中断")
    except Exception as e:
        logger.error(f"服务器运行失败: {e}")
        sys.exit(1)
    finally:
        logger.info("程序退出")


if __name__ == "__main__":
    asyncio.run(main())
