#!/usr/bin/env python3
"""
AutoDiary - HTTP 集成服务器

改造为 HTTP 模式（基于参考项目）:
- ESP32 作为 HTTP 服务器，PC 作为客户端
- PC 通过 HTTP API 与 ESP32 通信
- 支持实时视频流、音频采集、智能分析

功能：
- 从 ESP32 获取实时视频流
- 从 ESP32 采集音频数据
- FunASR 语音识别
- 智能分析和总结
- Web 管理界面

作者: AutoDiary 开发团队
版本: v2.0 (HTTP 模式)
"""

import asyncio
import threading
import json
import time
import logging
import requests
from pathlib import Path
from typing import Dict, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import io

# 导入自定义模块
try:
    from funasr_client import FunASRClient
    from intelligent_analyzer import IntelligentAnalyzer
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("某些功能可能不可用")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('http_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ESPDevice:
    """ESP32 设备管理"""
    
    def __init__(self, ip: str, port: int = 80):
        """
        初始化 ESP32 设备
        
        Args:
            ip: ESP32 IP 地址
            port: ESP32 HTTP 服务器端口（默认80）
        """
        self.ip = ip
        self.port = port
        self.base_url = f"http://{ip}:{port}"
        self.last_seen = time.time()
        self.device_info = {}
        self.session = requests.Session()
        self.session.timeout = 5
    
    def is_alive(self, timeout: int = 60) -> bool:
        """检查设备是否在线"""
        return time.time() - self.last_seen < timeout
    
    def ping(self) -> bool:
        """Ping 设备"""
        try:
            response = self.session.get(f"{self.base_url}/status", timeout=2)
            if response.status_code == 200:
                self.last_seen = time.time()
                self.device_info = response.json()
                logger.info(f"✅ 设备在线: {self.ip}")
                return True
        except Exception as e:
            logger.warning(f"❌ 设备离线: {self.ip} ({e})")
        return False
    
    def get_video_frame(self) -> Optional[bytes]:
        """获取一帧视频"""
        try:
            response = self.session.get(f"{self.base_url}/video.jpg", timeout=3)
            if response.status_code == 200:
                self.last_seen = time.time()
                return response.content
        except Exception as e:
            logger.warning(f"获取视频帧失败: {e}")
        return None
    
    def get_status(self) -> Optional[Dict]:
        """获取设备状态"""
        try:
            response = self.session.get(f"{self.base_url}/status", timeout=2)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"获取状态失败: {e}")
        return None


class AutoDiaryHTTPServer:
    """AutoDiary HTTP 服务器"""
    
    def __init__(self, config_file: str = "config.json", esp32_ip: str = None):
        """
        初始化 HTTP 服务器
        
        Args:
            config_file: 配置文件路径
            esp32_ip: ESP32 IP 地址（可选）
        """
        self.config = self._load_config(config_file)
        self.esp32_ip = esp32_ip or self.config.get("esp32_ip", "192.168.1.11")
        
        # 初始化 ESP32 设备
        self.device = ESPDevice(self.esp32_ip)
        
        # 服务器组件
        self.funasr_client: Optional[FunASRClient] = None
        self.intelligent_analyzer: Optional[IntelligentAnalyzer] = None
        
        # 数据存储
        self.data_dir = Path("data")
        self.audio_buffer = []
        self.current_image = None
        
        # 状态变量
        self.running = False
        self.device_connected = False
        
        logger.info("AutoDiary HTTP 服务器初始化完成")
    
    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info("配置文件加载成功")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            logger.info("使用默认配置")
            return {
                "server": {"host": "0.0.0.0", "port": 8080},
                "esp32_ip": "192.168.1.11",
                "features": {
                    "funasr_enabled": True,
                    "intelligent_analysis": True
                }
            }
    
    async def initialize(self) -> bool:
        """初始化所有组件"""
        try:
            logger.info("正在初始化 AutoDiary HTTP 服务器...")
            
            # 检查 ESP32 连接
            logger.info(f"检查 ESP32 连接: {self.esp32_ip}...")
            if self.device.ping():
                self.device_connected = True
                logger.info(f"✅ ESP32 已连接")
                logger.info(f"设备信息: {self.device.device_info}")
            else:
                logger.warning(f"❌ 无法连接到 ESP32，请检查 IP 地址")
            
            # 初始化 FunASR
            if self.config["features"].get("funasr_enabled"):
                logger.info("初始化 FunASR 客户端...")
                try:
                    self.funasr_client = FunASRClient(
                        model_name=self.config.get("funasr", {}).get("model_name", "paraformer-zh"),
                        device=self.config.get("funasr", {}).get("device", "cpu"),
                        sample_rate=self.config.get("funasr", {}).get("sample_rate", 16000)
                    )
                    if await self.funasr_client.initialize():
                        logger.info("✅ FunASR 客户端初始化成功")
                    else:
                        logger.warning("⚠️ FunASR 客户端初始化失败")
                        self.funasr_client = None
                except Exception as e:
                    logger.warning(f"⚠️ FunASR 初始化异常: {e}")
                    self.funasr_client = None
            
            # 初始化智能分析器
            if self.config["features"].get("intelligent_analysis"):
                logger.info("初始化智能分析器...")
                self.intelligent_analyzer = IntelligentAnalyzer(
                    funasr_client=self.funasr_client,
                    llm_client=None,
                    data_dir="data"
                )
            
            # 创建数据目录
            await self._create_data_directories()
            
            logger.info("✅ 服务器初始化完成")
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
    
    async def capture_video_stream(self, duration: int = None):
        """
        连续捕获视频流
        
        Args:
            duration: 捕获持续时间（秒），None 表示无限
        """
        logger.info(f"开始视频捕获流 (持续时间: {duration}s)")
        
        start_time = time.time()
        frame_count = 0
        
        while self.running:
            if duration and time.time() - start_time > duration:
                break
            
            frame_data = self.device.get_video_frame()
            if frame_data:
                self.current_image = frame_data
                frame_count += 1
                
                # 定期保存图像
                if frame_count % 30 == 0:
                    await self._save_image(frame_data)
                    logger.info(f"📸 已捕获 {frame_count} 帧")
            else:
                logger.warning("⚠️ 视频帧获取失败")
            
            await asyncio.sleep(0.1)  # 控制帧率
    
    async def _save_image(self, image_data: bytes):
        """保存图像"""
        try:
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"autodiary_{timestamp}.jpg"
            filepath = self.data_dir / "Images" / filename
            
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"💾 图像已保存: {filename}")
            
        except Exception as e:
            logger.error(f"保存图像失败: {e}")
    
    async def start_http_server(self):
        """启动 HTTP 服务器"""
        try:
            logger.info(f"启动 HTTP 服务器: {self.config['server']['host']}:{self.config['server']['port']}")
            
            # 创建 HTTP 处理器类
            server_instance = self
            
            class RequestHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    """处理 GET 请求"""
                    path = urlparse(self.path).path
                    
                    if path == '/':
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(self._get_html_page().encode('utf-8'))
                    
                    elif path == '/status':
                        # 获取服务器和设备状态
                        status = {
                            'server_running': server_instance.running,
                            'device_connected': server_instance.device_connected,
                            'device_info': server_instance.device.device_info,
                            'current_time': time.time()
                        }
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(json.dumps(status, ensure_ascii=False, indent=2).encode('utf-8'))
                    
                    elif path == '/video.jpg':
                        # 获取最新的视频帧
                        if server_instance.current_image:
                            self.send_response(200)
                            self.send_header('Content-Type', 'image/jpeg')
                            self.send_header('Cache-Control', 'no-cache')
                            self.end_headers()
                            self.wfile.write(server_instance.current_image)
                        else:
                            self.send_response(503)
                            self.send_header('Content-Type', 'text/plain')
                            self.end_headers()
                            self.wfile.write(b'No video data available')
                    
                    else:
                        self.send_response(404)
                        self.send_header('Content-Type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b'404 - Not Found')
                
                def log_message(self, format, *args):
                    """禁用默认的日志输出"""
                    pass
                
                def _get_html_page(self) -> str:
                    """返回管理界面"""
                    return """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>AutoDiary - HTTP 服务器</title>
                        <style>
                            * { margin: 0; padding: 0; box-sizing: border-box; }
                            body { 
                                font-family: Arial, sans-serif;
                                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                min-height: 100vh;
                                display: flex;
                                justify-content: center;
                                align-items: center;
                                padding: 20px;
                            }
                            .container {
                                background: white;
                                border-radius: 15px;
                                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                                max-width: 800px;
                                width: 100%;
                                padding: 30px;
                            }
                            h1 { color: #333; text-align: center; margin-bottom: 30px; }
                            .status-section {
                                background: #f8f9fa;
                                border-left: 4px solid #667eea;
                                padding: 20px;
                                border-radius: 5px;
                                margin-bottom: 20px;
                            }
                            .status-item {
                                display: flex;
                                justify-content: space-between;
                                padding: 10px 0;
                                border-bottom: 1px solid #e0e0e0;
                            }
                            .status-item:last-child { border-bottom: none; }
                            .status-label { color: #666; font-weight: 500; }
                            .status-value { color: #333; font-family: monospace; }
                            .status-value.success { color: #22863a; }
                            .status-value.error { color: #cb2431; }
                            .info-text { color: #666; font-size: 14px; margin-top: 20px; }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>🎥 AutoDiary HTTP 服务器</h1>
                            
                            <div class="status-section">
                                <h2>📊 系统状态</h2>
                                <div class="status-item">
                                    <span class="status-label">服务器状态</span>
                                    <span class="status-value success" id="serverStatus">运行中</span>
                                </div>
                                <div class="status-item">
                                    <span class="status-label">ESP32 连接</span>
                                    <span class="status-value" id="deviceStatus">检查中...</span>
                                </div>
                                <div class="status-item">
                                    <span class="status-label">设备 IP</span>
                                    <span class="status-value" id="deviceIP">-</span>
                                </div>
                                <div class="status-item">
                                    <span class="status-label">设备固件版本</span>
                                    <span class="status-value" id="fwVersion">-</span>
                                </div>
                            </div>
                            
                            <div class="info-text">
                                <p>✅ HTTP 服务器已启动</p>
                                <p>📡 API 接口:</p>
                                <ul style="margin-left: 20px; margin-top: 10px;">
                                    <li>GET /status - 获取系统状态</li>
                                    <li>GET /video.jpg - 获取实时视频帧</li>
                                </ul>
                            </div>
                        </div>
                        
                        <script>
                            function updateStatus() {
                                fetch('/status')
                                    .then(r => r.json())
                                    .then(data => {
                                        if (data.device_connected) {
                                            document.getElementById('deviceStatus').textContent = '✅ 已连接';
                                            document.getElementById('deviceStatus').className = 'status-value success';
                                        } else {
                                            document.getElementById('deviceStatus').textContent = '❌ 未连接';
                                            document.getElementById('deviceStatus').className = 'status-value error';
                                        }
                                        
                                        if (data.device_info) {
                                            document.getElementById('deviceIP').textContent = data.device_info.ip_address || '-';
                                            document.getElementById('fwVersion').textContent = data.device_info.firmware_version || '-';
                                        }
                                    })
                                    .catch(e => console.log('Status update failed'));
                            }
                            
                            setInterval(updateStatus, 5000);
                            updateStatus();
                        </script>
                    </body>
                    </html>
                    """
            
            # 启动 HTTP 服务器
            server = HTTPServer(
                (self.config['server']['host'], self.config['server']['port']),
                RequestHandler
            )
            
            # 在线程中运行服务器
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            logger.info(f"✅ HTTP 服务器启动成功")
            logger.info(f"🌐 访问地址: http://localhost:{self.config['server']['port']}/")
            
        except Exception as e:
            logger.error(f"启动 HTTP 服务器失败: {e}")
    
    async def monitor_device(self):
        """监控设备连接状态"""
        logger.info("设备监控任务已启动")
        
        while self.running:
            try:
                if self.device.ping():
                    if not self.device_connected:
                        logger.info("✅ ESP32 已连接")
                        self.device_connected = True
                else:
                    if self.device_connected:
                        logger.warning("❌ ESP32 已断开连接")
                        self.device_connected = False
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"设备监控错误: {e}")
                await asyncio.sleep(10)
    
    async def run(self):
        """运行服务器"""
        try:
            self.running = True
            
            # 启动 HTTP 服务器
            await self.start_http_server()
            
            # 启动监控任务
            monitor_task = asyncio.create_task(self.monitor_device())
            
            # 启动视频捕获（如果设备已连接）
            if self.device_connected:
                capture_task = asyncio.create_task(self.capture_video_stream())
            
            logger.info("📡 服务器运行中...")
            
            # 保持运行
            while self.running:
                await asyncio.sleep(1)
            
        except KeyboardInterrupt:
            logger.info("收到中断信号")
        except Exception as e:
            logger.error(f"服务器运行错误: {e}")
        finally:
            self.running = False
            logger.info("服务器已停止")


async def main():
    """主函数"""
    import sys
    
    # 从命令行参数获取 ESP32 IP（可选）
    esp32_ip = sys.argv[1] if len(sys.argv) > 1 else None
    
    # 创建并启动服务器
    server = AutoDiaryHTTPServer(esp32_ip=esp32_ip)
    
    if await server.initialize():
        await server.run()
    else:
        logger.error("服务器初始化失败")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已停止")
    except Exception as e:
        logger.error(f"程序异常: {e}")
