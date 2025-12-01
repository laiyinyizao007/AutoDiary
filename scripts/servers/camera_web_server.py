#!/usr/bin/env python3
"""
AutoDiary 摄像头Web服务器

基于 XIAO ESP32S3 Sense Camera_HTTP_Server_STA 项目，
为AutoDiary提供Web界面管理功能。

功能：
- 实时摄像头预览
- 图像捕获和保存
- 图像旋转控制
- SD卡存储管理
- 设备状态监控

作者：AutoDiary开发团队
版本：v1.0
"""

import asyncio
import websockets
import json
import base64
import io
import time
import datetime
from pathlib import Path
from typing import Dict, Optional, Set
import logging
from PIL import Image, ImageOps
import aiohttp
from aiohttp import web, WSMsgType
import aiofiles

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CameraWebServer:
    """摄像头Web服务器"""
    
    def __init__(self, 
                 host: str = "0.0.0.0", 
                 web_port: int = 8080,
                 websocket_port: int = 8001):
        """
        初始化摄像头Web服务器
        
        Args:
            host: 服务器主机地址
            web_port: Web界面端口
            websocket_port: WebSocket端口（用于实时视频流）
        """
        self.host = host
        self.web_port = web_port
        self.websocket_port = websocket_port
        
        # 数据存储路径
        self.base_dir = Path("data")
        self.images_dir = self.base_dir / "Images"
        self.temp_dir = self.base_dir / "Temp"
        
        # 创建目录
        self._create_directories()
        
        # 状态变量
        self.current_image = None
        self.image_rotation = 0
        self.auto_capture_enabled = True
        self.auto_capture_interval = 30  # 秒
        self.last_capture_time = 0
        self.image_count = 0
        
        # WebSocket连接管理
        self.websocket_clients: Set[websockets.WebSocketServerProtocol] = set()
        
        # 设备连接状态
        self.device_connected = False
        self.last_heartbeat = 0
        
        logger.info(f"摄像头Web服务器初始化完成")
        logger.info(f"Web界面: http://{host}:{web_port}")
        logger.info(f"WebSocket: ws://{host}:{websocket_port}")

    def _create_directories(self):
        """创建必要的目录结构"""
        try:
            self.base_dir.mkdir(exist_ok=True)
            self.images_dir.mkdir(exist_ok=True)
            self.temp_dir.mkdir(exist_ok=True)
            logger.info("目录结构创建成功")
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            raise

    async def start_web_server(self):
        """启动Web服务器"""
        app = web.Application()
        
        # 设置路由
        app.router.add_get('/', self.handle_index)
        app.router.add_get('/api/status', self.handle_status)
        app.router.add_post('/api/capture', self.handle_capture)
        app.router.add_post('/api/save', self.handle_save)
        app.router.add_post('/api/rotate', self.handle_rotate)
        app.router.add_get('/api/image/latest', self.handle_latest_image)
        app.router.add_get('/api/images', self.handle_image_list)
        app.router.add_static('/static/', path='static', name='static')
        
        # 启动服务器
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.web_port)
        await site.start()
        
        logger.info(f"Web服务器启动成功: http://{self.host}:{self.web_port}")

    async def start_websocket_server(self):
        """启动WebSocket服务器（用于实时视频流）"""
        async def handle_client(websocket, path):
            self.websocket_clients.add(websocket)
            self.device_connected = True
            logger.info(f"设备WebSocket连接建立: {websocket.remote_address}")
            
            try:
                async for message in websocket:
                    if isinstance(message, bytes):
                        # 接收到图像数据
                        await self._process_camera_image(message)
                    elif isinstance(message, str):
                        # 接收到文本消息（心跳、状态等）
                        await self._process_device_message(message)
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"设备WebSocket连接断开: {websocket.remote_address}")
            except Exception as e:
                logger.error(f"WebSocket处理错误: {e}")
            finally:
                self.websocket_clients.discard(websocket)
                self.device_connected = False
        
        # 启动WebSocket服务器
        server = await websockets.serve(
            handle_client,
            self.host,
            self.websocket_port
        )
        
        logger.info(f"WebSocket服务器启动成功: ws://{self.host}:{self.websocket_port}")
        return server

    async def handle_index(self, request):
        """处理主页请求"""
        html_content = self._generate_html_interface()
        return web.Response(text=html_content, content_type='text/html')

    async def handle_status(self, request):
        """处理状态查询请求"""
        status = {
            'device_connected': self.device_connected,
            'last_heartbeat': self.last_heartbeat,
            'current_image_count': self.image_count,
            'auto_capture_enabled': self.auto_capture_enabled,
            'auto_capture_interval': self.auto_capture_interval,
            'image_rotation': self.image_rotation,
            'last_capture_time': self.last_capture_time,
            'server_time': time.time()
        }
        return web.json_response(status)

    async def handle_capture(self, request):
        """处理图像捕获请求"""
        try:
            if not self.device_connected:
                return web.json_response(
                    {'success': False, 'error': '设备未连接'}, 
                    status=503
                )
            
            # 向设备发送捕获命令
            capture_command = {
                'command': 'capture',
                'timestamp': time.time()
            }
            
            # 广播捕获命令到所有连接的设备
            if self.websocket_clients:
                await self._broadcast_to_devices(capture_command)
                return web.json_response({'success': True, 'message': '捕获命令已发送'})
            else:
                return web.json_response(
                    {'success': False, 'error': '没有可用的设备'}, 
                    status=503
                )
                
        except Exception as e:
            logger.error(f"处理捕获请求失败: {e}")
            return web.json_response(
                {'success': False, 'error': str(e)}, 
                status=500
            )

    async def handle_save(self, request):
        """处理图像保存请求"""
        try:
            if not self.current_image:
                return web.json_response(
                    {'success': False, 'error': '没有可保存的图像'}, 
                    status=400
                )
            
            # 生成文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"autodiary_{timestamp}.jpg"
            filepath = self.images_dir / filename
            
            # 应用旋转并保存
            image = Image.open(io.BytesIO(self.current_image))
            if self.image_rotation % 360 != 0:
                image = image.rotate(self.image_rotation, expand=True)
            
            # 保存图像
            image.save(filepath, 'JPEG', quality=95)
            
            self.image_count += 1
            self.last_capture_time = time.time()
            
            logger.info(f"图像已保存: {filename}")
            
            return web.json_response({
                'success': True,
                'filename': filename,
                'filepath': str(filepath),
                'size': len(self.current_image),
                'dimensions': image.size,
                'timestamp': timestamp
            })
            
        except Exception as e:
            logger.error(f"保存图像失败: {e}")
            return web.json_response(
                {'success': False, 'error': str(e)}, 
                status=500
            )

    async def handle_rotate(self, request):
        """处理图像旋转请求"""
        try:
            data = await request.json()
            rotation = data.get('rotation', 90)
            
            # 验证旋转角度
            if rotation not in [90, 180, 270, -90, -180, -270]:
                return web.json_response(
                    {'success': False, 'error': '无效的旋转角度'}, 
                    status=400
                )
            
            self.image_rotation = (self.image_rotation + rotation) % 360
            
            return web.json_response({
                'success': True,
                'current_rotation': self.image_rotation
            })
            
        except Exception as e:
            logger.error(f"旋转图像失败: {e}")
            return web.json_response(
                {'success': False, 'error': str(e)}, 
                status=500
            )

    async def handle_latest_image(self, request):
        """处理获取最新图像请求"""
        try:
            if not self.current_image:
                return web.Response(
                    text='没有可用的图像', 
                    status=404
                )
            
            # 应用旋转
            image = Image.open(io.BytesIO(self.current_image))
            if self.image_rotation % 360 != 0:
                image = image.rotate(self.image_rotation, expand=True)
            
            # 转换为JPEG字节流
            img_buffer = io.BytesIO()
            image.save(img_buffer, 'JPEG', quality=95)
            img_buffer.seek(0)
            
            return web.Response(
                body=img_buffer.getvalue(),
                content_type='image/jpeg',
                headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            )
            
        except Exception as e:
            logger.error(f"获取最新图像失败: {e}")
            return web.Response(
                text=f'获取图像失败: {str(e)}', 
                status=500
            )

    async def handle_image_list(self, request):
        """处理图像列表请求"""
        try:
            # 获取图像文件列表
            image_files = []
            if self.images_dir.exists():
                for file_path in sorted(self.images_dir.glob("*.jpg"), reverse=True):
                    stat = file_path.stat()
                    image_files.append({
                        'filename': file_path.name,
                        'filepath': str(file_path),
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'url': f"/static/images/{file_path.name}"
                    })
            
            return web.json_response({
                'success': True,
                'images': image_files,
                'total_count': len(image_files)
            })
            
        except Exception as e:
            logger.error(f"获取图像列表失败: {e}")
            return web.json_response(
                {'success': False, 'error': str(e)}, 
                status=500
            )

    async def _process_camera_image(self, image_data: bytes):
        """处理摄像头图像数据"""
        try:
            # 验证图像数据
            image = Image.open(io.BytesIO(image_data))
            
            # 保存当前图像
            self.current_image = image_data
            
            # 自动保存检查
            current_time = time.time()
            if (self.auto_capture_enabled and 
                current_time - self.last_capture_time >= self.auto_capture_interval):
                
                # 自动保存图像
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"auto_{timestamp}.jpg"
                filepath = self.images_dir / filename
                
                # 保存原始图像
                with open(filepath, 'wb') as f:
                    f.write(image_data)
                
                self.image_count += 1
                self.last_capture_time = current_time
                
                logger.info(f"自动保存图像: {filename}")
            
        except Exception as e:
            logger.error(f"处理摄像头图像失败: {e}")

    async def _process_device_message(self, message: str):
        """处理设备消息"""
        try:
            data = json.loads(message)
            
            if data.get('type') == 'heartbeat':
                self.last_heartbeat = time.time()
                logger.debug("收到设备心跳")
            elif data.get('type') == 'status':
                logger.info(f"设备状态更新: {data}")
            else:
                logger.debug(f"设备消息: {data}")
                
        except json.JSONDecodeError:
            logger.debug(f"非JSON设备消息: {message}")
        except Exception as e:
            logger.error(f"处理设备消息失败: {e}")

    async def _broadcast_to_devices(self, message: dict):
        """向所有设备广播消息"""
        if self.websocket_clients:
            message_str = json.dumps(message)
            disconnected_clients = set()
            
            for client in self.websocket_clients:
                try:
                    await client.send(message_str)
                except websockets.exceptions.ConnectionClosed:
                    disconnected_clients.add(client)
                except Exception as e:
                    logger.error(f"发送消息到设备失败: {e}")
                    disconnected_clients.add(client)
            
            # 清理断开的连接
            self.websocket_clients -= disconnected_clients

    def _generate_html_interface(self) -> str:
        """生成HTML界面"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoDiary 摄像头控制台</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            color: #333;
        }
        .camera-section {
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
        }
        .image-container {
            flex: 1;
            text-align: center;
        }
        .controls {
            flex: 0 0 300px;
        }
        .image-preview {
            max-width: 100%;
            height: auto;
            border: 2px solid #ddd;
            border-radius: 5px;
            min-height: 300px;
            background-color: #f8f8f8;
        }
        .button {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            margin: 5px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }
        .button:hover {
            background-color: #0056b3;
        }
        .button:disabled {
            background-color: #6c757d;
            cursor: not-allowed;
        }
        .status {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-top: 20px;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
        }
        .connected { color: #28a745; }
        .disconnected { color: #dc3545; }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #3498db;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📷 AutoDiary 摄像头控制台</h1>
            <p>实时摄像头控制和图像管理</p>
        </div>
        
        <div class="camera-section">
            <div class="image-container">
                <h3>实时预览</h3>
                <img id="imagePreview" class="image-preview" 
                     src="/api/image/latest" alt="摄像头预览">
                <div id="imageInfo" style="margin-top: 10px; color: #666; font-size: 14px;"></div>
            </div>
            
            <div class="controls">
                <h3>控制面板</h3>
                <button id="captureBtn" class="button">📸 拍照</button>
                <button id="saveBtn" class="button">💾 保存图像</button>
                <button id="rotateBtn" class="button">🔄 旋转90°</button>
                
                <div style="margin-top: 20px;">
                    <h4>自动捕获设置</h4>
                    <label>
                        <input type="checkbox" id="autoCapture" checked> 启用自动捕获
                    </label>
                    <br>
                    <label>
                        间隔(秒): 
                        <input type="number" id="captureInterval" value="30" min="5" max="300" style="width: 60px;">
                    </label>
                </div>
            </div>
        </div>
        
        <div class="status">
            <h3>系统状态</h3>
            <div class="status-item">
                <span>设备连接状态:</span>
                <span id="deviceStatus" class="disconnected">未连接</span>
            </div>
            <div class="status-item">
                <span>最后心跳:</span>
                <span id="lastHeartbeat">-</span>
            </div>
            <div class="status-item">
                <span>图像数量:</span>
                <span id="imageCount">0</span>
            </div>
            <div class="status-item">
                <span>当前旋转角度:</span>
                <span id="currentRotation">0°</span>
            </div>
            <div class="status-item">
                <span>最后捕获时间:</span>
                <span id="lastCaptureTime">-</span>
            </div>
        </div>
    </div>

    <script>
        // 全局变量
        let currentRotation = 0;
        
        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            // 绑定按钮事件
            document.getElementById('captureBtn').addEventListener('click', captureImage);
            document.getElementById('saveBtn').addEventListener('click', saveImage);
            document.getElementById('rotateBtn').addEventListener('click', rotateImage);
            document.getElementById('autoCapture').addEventListener('change', toggleAutoCapture);
            document.getElementById('captureInterval').addEventListener('change', updateCaptureInterval);
            
            // 定期更新状态
            setInterval(updateStatus, 5000);
            
            // 定期刷新图像
            setInterval(refreshImage, 3000);
            
            // 初始化状态
            updateStatus();
        });
        
        // 拍照功能
        async function captureImage() {
            const btn = document.getElementById('captureBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> 拍照中...';
            
            try {
                const response = await fetch('/api/capture', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const result = await response.json();
                if (result.success) {
                    setTimeout(refreshImage, 1000); // 1秒后刷新图像
                } else {
                    alert('拍照失败: ' + result.error);
                }
            } catch (error) {
                alert('拍照请求失败: ' + error.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '📸 拍照';
            }
        }
        
        // 保存图像
        async function saveImage() {
            const btn = document.getElementById('saveBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> 保存中...';
            
            try {
                const response = await fetch('/api/save', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const result = await response.json();
                if (result.success) {
                    alert(`图像已保存: ${result.filename}\\n尺寸: ${result.dimensions[0]}x${result.dimensions[1]}`);
                    updateStatus();
                } else {
                    alert('保存失败: ' + result.error);
                }
            } catch (error) {
                alert('保存请求失败: ' + error.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '💾 保存图像';
            }
        }
        
        // 旋转图像
        async function rotateImage() {
            try {
                const response = await fetch('/api/rotate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ rotation: 90 })
                });
                
                const result = await response.json();
                if (result.success) {
                    currentRotation = result.current_rotation;
                    document.getElementById('currentRotation').textContent = currentRotation + '°';
                    refreshImage();
                } else {
                    alert('旋转失败: ' + result.error);
                }
            } catch (error) {
                alert('旋转请求失败: ' + error.message);
            }
        }
        
        // 切换自动捕获
        async function toggleAutoCapture() {
            const enabled = document.getElementById('autoCapture').checked;
            // 这里可以添加设置自动捕获的API调用
            console.log('自动捕获:', enabled);
        }
        
        // 更新捕获间隔
        async function updateCaptureInterval() {
            const interval = document.getElementById('captureInterval').value;
            // 这里可以添加设置捕获间隔的API调用
            console.log('捕获间隔:', interval);
        }
        
        // 刷新图像
        function refreshImage() {
            const img = document.getElementById('imagePreview');
            img.src = '/api/image/latest?t=' + Date.now();
        }
        
        // 更新状态
        async function updateStatus() {
            try {
                const response = await fetch('/api/status');
                const status = await response.json();
                
                // 更新设备状态
                const deviceStatus = document.getElementById('deviceStatus');
                if (status.device_connected) {
                    deviceStatus.textContent = '已连接';
                    deviceStatus.className = 'connected';
                } else {
                    deviceStatus.textContent = '未连接';
                    deviceStatus.className = 'disconnected';
                }
                
                // 更新其他状态
                document.getElementById('imageCount').textContent = status.current_image_count;
                document.getElementById('currentRotation').textContent = status.image_rotation + '°';
                
                if (status.last_capture_time > 0) {
                    const date = new Date(status.last_capture_time * 1000);
                    document.getElementById('lastCaptureTime').textContent = 
                        date.toLocaleString('zh-CN');
                }
                
                if (status.last_heartbeat > 0) {
                    const date = new Date(status.last_heartbeat * 1000);
                    document.getElementById('lastHeartbeat').textContent = 
                        date.toLocaleTimeString('zh-CN');
                }
                
            } catch (error) {
                console.error('获取状态失败:', error);
            }
        }
    </script>
</body>
</html>
        """

    async def start_servers(self):
        """启动所有服务器"""
        logger.info("正在启动AutoDiary摄像头Web服务器...")
        
        # 启动Web服务器和WebSocket服务器
        await asyncio.gather(
            self.start_web_server(),
            self.start_websocket_server()
        )

    async def cleanup(self):
        """清理资源"""
        try:
            # 关闭所有WebSocket连接
            for client in self.websocket_clients.copy():
                try:
                    await client.close()
                except:
                    pass
            self.websocket_clients.clear()
            
            logger.info("摄像头Web服务器资源清理完成")
            
        except Exception as e:
            logger.error(f"资源清理失败: {e}")


# 主函数
async def main():
    """主函数"""
    try:
        # 创建并启动摄像头Web服务器
        server = CameraWebServer(
            host="0.0.0.0",
            web_port=8080,
            websocket_port=8001
        )
        
        # 启动服务器
        await server.start_servers()
        
        logger.info("摄像头Web服务器启动完成")
        logger.info("访问 http://localhost:8080 查看控制台")
        
        # 保持运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("服务器被用户中断")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
    finally:
        logger.info("服务器已停止")


if __name__ == "__main__":
    asyncio.run(main())
