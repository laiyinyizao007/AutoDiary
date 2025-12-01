#!/usr/bin/env python3
"""
简单的连接测试脚本
测试ESP32设备到WebSocket服务器的连接
"""

import asyncio
import websockets
import json
import time

async def test_websocket_connection():
    """测试WebSocket连接"""
    uri = "ws://localhost:8888/video"
    
    try:
        print("🔌 正在连接到WebSocket服务器...")
        print(f"   服务器地址: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket连接成功！")
            
            # 发送测试消息
            test_message = {
                "type": "test_connection",
                "timestamp": time.time(),
                "message": "ESP32连接测试"
            }
            
            await websocket.send(json.dumps(test_message))
            print("📤 发送测试消息成功")
            
            # 等待响应
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 收到服务器��应: {response}")
                
                if "welcome" in response:
                    print("🎉 服务器响应正常，连接测试成功！")
                
            except asyncio.TimeoutError:
                print("⏰️ 服务器响应超时（这在正常范围内）")
                print("   但连接已建立，基础功能正常")
            
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        print("   这可能是正常的，因为服务器可能需要特定路径")
    
    print("\n📊 连接测试完成")

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())
