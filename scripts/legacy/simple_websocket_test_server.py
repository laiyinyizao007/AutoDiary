#!/usr/bin/env python3
"""
简单的WebSocket测试服务器
专门用于ESP32设备连接测试
基于XIAO-ESP32S3-Sense的实践经验
"""

import asyncio
import websockets
import json
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_connection():
    """测试WebSocket连接到不同的路径"""
    servers_to_test = [
        # 尝试不同的路径
        "ws://localhost:8888/video",
        "ws://localhost:8888/audio",
        # 尝试根路径
        "ws://localhost:8888/",
    ]
    
    for server_uri in servers_to_test:
        try:
            print(f"\n🔌 正在测试连接: {server_uri}")
            
            async with websockets.connect(server_uri) as websocket:
                print("✅ WebSocket连接成功！")
                # 发送测试消息
                test_msg = {
                    "type": "test",
                    "server": "simple_test",
                    "message": f"连接时间: {time.time()}"
                }
                await websocket.send(json.dumps(test_msg))
                
                # 尝试接收响应
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    print(f"📥 收到服务器响应: {response}")
                except asyncio.TimeoutError:
                    print("⏰️ 服务器响应超时（这在正常范围内）")
                
        except Exception as e:
                print(f"❌ 连接失败: {e}")
                print(f"   可能的原因: 网络配置或服务器未启动")
                
        except Exception as e:
            print(f"❌ 严重错误: {e}")
            
        print(f"\n📊 连接测试完成")

if __name__ == "__main__":
    asyncio.run(test_connection())
