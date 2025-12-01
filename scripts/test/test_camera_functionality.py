#!/usr/bin/env python3
"""
AutoDiary 摄像头功能测试脚本

测试内容：
1. ESP32 连接测试
2. 摄像头初始化测试
3. 视频流获取测试
4. 拍照功能测试
5. 照片上传/保存测试
6. 性能测试

使用方法:
    python test_camera_functionality.py [esp32_ip]
    例如: python test_camera_functionality.py 192.168.1.11
"""

import sys
import time
import json
import requests
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CameraTestSuite:
    """摄像头测试套件"""
    
    def __init__(self, esp32_ip: str, esp32_port: int = 80, timeout: int = 10):
        """
        初始化测试套件
        
        Args:
            esp32_ip: ESP32 IP 地址
            esp32_port: ESP32 HTTP 服务器端口
            timeout: 请求超时时间（秒）
        """
        self.esp32_ip = esp32_ip
        self.esp32_port = esp32_port
        self.base_url = f"http://{esp32_ip}:{esp32_port}"
        self.timeout = timeout
        
        # 测试结果统计
        self.test_results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'details': []
        }
        
        # 创建 session
        self.session = requests.Session()
        self.session.timeout = timeout
        
        # 创建测试结果目录
        self.test_dir = Path("test_results")
        self.test_dir.mkdir(exist_ok=True)
        
        logger.info("=" * 60)
        logger.info("AutoDiary 摄像头功能测试")
        logger.info("=" * 60)
        logger.info(f"目标设备: {self.base_url}")
    
    def _print_section(self, title: str):
        """打印分隔符"""
        logger.info("\n" + "=" * 60)
        logger.info(f"🔍 {title}")
        logger.info("=" * 60)
    
    def _record_test(self, test_name: str, result: bool, message: str = ""):
        """记录测试结果"""
        self.test_results['total'] += 1
        if result:
            self.test_results['passed'] += 1
            status = "✅ 通过"
        else:
            self.test_results['failed'] += 1
            status = "❌ 失败"
        
        test_detail = {
            'name': test_name,
            'status': status,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results['details'].append(test_detail)
        
        if message:
            logger.info(f"{status} | {test_name}: {message}")
        else:
            logger.info(f"{status} | {test_name}")
    
    # ==================== 测试方法 ====================
    
    def test_connection(self) -> bool:
        """测试 ESP32 连接"""
        self._print_section("1. 连接测试")
        
        try:
            logger.info(f"正在连接到 {self.base_url}...")
            response = self.session.get(f"{self.base_url}/status", timeout=5)
            
            if response.status_code == 200:
                self._record_test("ESP32 连接测试", True, "连接成功")
                logger.info(f"HTTP 状态码: {response.status_code}")
                return True
            else:
                self._record_test(
                    "ESP32 连接测试", 
                    False, 
                    f"HTTP 状态码: {response.status_code}"
                )
                return False
                
        except requests.exceptions.ConnectionError as e:
            self._record_test(
                "ESP32 连接测试", 
                False, 
                f"连接错误: {e}"
            )
            logger.error(f"无法连接到 ESP32: {e}")
            return False
        except requests.exceptions.Timeout:
            self._record_test(
                "ESP32 连接测试", 
                False, 
                "连接超时"
            )
            logger.error("连接超时")
            return False
        except Exception as e:
            self._record_test(
                "ESP32 连接测试", 
                False, 
                f"未知错误: {e}"
            )
            logger.error(f"错误: {e}")
            return False
    
    def test_device_status(self) -> Optional[dict]:
        """测试获取设备状态"""
        self._print_section("2. 设备状态查询")
        
        try:
            logger.info("正在获取设备状态...")
            response = self.session.get(f"{self.base_url}/status", timeout=5)
            
            if response.status_code == 200:
                status_data = response.json()
                self._record_test("设备状态查询", True, "状态获取成功")
                
                # 打印设备信息
                logger.info("\n📊 设备信息:")
                logger.info(f"  • 设备: {status_data.get('device', 'N/A')}")
                logger.info(f"  • 固件版本: {status_data.get('firmware_version', 'N/A')}")
                logger.info(f"  • IP 地址: {status_data.get('ip_address', 'N/A')}")
                logger.info(f"  • WiFi 连接: {'✅' if status_data.get('wifi_connected') else '❌'}")
                logger.info(f"  • 摄像头初始化: {'✅' if status_data.get('camera_initialized') else '❌'}")
                logger.info(f"  • I2S 初始化: {'✅' if status_data.get('i2s_initialized') else '❌'}")
                logger.info(f"  • 捕获帧数: {status_data.get('frame_count', 'N/A')}")
                logger.info(f"  • 信号强度: {status_data.get('signal_strength', 'N/A')} dBm")
                
                # 验证摄像头状态
                camera_ok = status_data.get('camera_initialized', False)
                if not camera_ok:
                    self._record_test("摄像头初始化状态", False, "摄像头未初始化")
                else:
                    self._record_test("摄像头初始化状态", True)
                
                return status_data
            else:
                self._record_test(
                    "设备状态查询", 
                    False, 
                    f"HTTP 状态码: {response.status_code}"
                )
                return None
                
        except Exception as e:
            self._record_test("设备状态查询", False, f"错误: {e}")
            logger.error(f"获取设备状态失败: {e}")
            return None
    
    def test_video_frame_capture(self, count: int = 3) -> bool:
        """测试视频帧捕获"""
        self._print_section(f"3. 视频帧捕获测试 (共 {count} 帧)")
        
        success_count = 0
        frame_sizes = []
        
        for i in range(count):
            try:
                logger.info(f"正在捕获第 {i+1} 帧...")
                start_time = time.time()
                
                response = self.session.get(f"{self.base_url}/video.jpg", timeout=5)
                
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    frame_size = len(response.content)
                    frame_sizes.append(frame_size)
                    success_count += 1
                    
                    logger.info(f"  ✅ 帧 {i+1}: {frame_size} 字节 ({elapsed:.2f}s)")
                    
                    # 保存第一帧用于验证
                    if i == 0:
                        frame_path = self.test_dir / f"test_frame_{int(time.time())}.jpg"
                        with open(frame_path, 'wb') as f:
                            f.write(response.content)
                        logger.info(f"  📸 已保存到: {frame_path}")
                else:
                    logger.warning(f"  ❌ 帧 {i+1}: HTTP 状态码 {response.status_code}")
                
                time.sleep(0.5)  # 帧之间的延迟
                
            except Exception as e:
                logger.error(f"  ❌ 帧 {i+1}: 错误 - {e}")
        
        # 记录测试结果
        if success_count > 0:
            avg_size = sum(frame_sizes) / len(frame_sizes)
            self._record_test(
                "视频帧捕获",
                True,
                f"成功捕获 {success_count}/{count} 帧，平均大小: {avg_size:.0f} 字节"
            )
            logger.info(f"\n📊 视频帧统计:")
            logger.info(f"  • 成功帧数: {success_count}/{count}")
            logger.info(f"  • 平均大小: {avg_size:.0f} 字节")
            logger.info(f"  • 最小: {min(frame_sizes)} 字节")
            logger.info(f"  • 最大: {max(frame_sizes)} 字节")
            return True
        else:
            self._record_test("视频帧捕获", False, f"无法捕获任何帧")
            return False
    
    def test_capture_photo(self) -> Optional[bytes]:
        """测试拍照功能"""
        self._print_section("4. 拍照功能测试")
        
        try:
            logger.info("正在触发拍照指令...")
            response = self.session.get(f"{self.base_url}/capture", timeout=5)
            
            if response.status_code == 200:
                logger.info(f"✅ 拍照指令已发送")
                logger.info(f"响应: {response.text}")
                self._record_test("拍照功能", True, "拍照指令发送成功")
                
                # 等待处理
                time.sleep(1)
                
                # 获取保存的照片
                return self.test_get_saved_photo()
            else:
                self._record_test(
                    "拍照功能",
                    False,
                    f"HTTP 状态码: {response.status_code}"
                )
                return None
                
        except Exception as e:
            self._record_test("拍照功能", False, f"错误: {e}")
            logger.error(f"拍照失败: {e}")
            return None
    
    def test_get_saved_photo(self) -> Optional[bytes]:
        """获取已保存的照片"""
        self._print_section("5. 获取已保存的照片")
        
        try:
            logger.info("正在获取已保存的照片...")
            response = self.session.get(f"{self.base_url}/saved_photo", timeout=5)
            
            if response.status_code == 200:
                photo_data = response.content
                photo_size = len(photo_data)
                
                self._record_test("获取保存的照片", True, f"照片大小: {photo_size} 字节")
                logger.info(f"✅ 获取照片成功")
                logger.info(f"  • 大小: {photo_size} 字节")
                
                # 保存照片到本地
                photo_path = self.test_dir / f"saved_photo_{int(time.time())}.jpg"
                with open(photo_path, 'wb') as f:
                    f.write(photo_data)
                logger.info(f"  📸 已保存到: {photo_path}")
                
                return photo_data
            else:
                self._record_test(
                    "获取保存的照片",
                    False,
                    f"HTTP 状态码: {response.status_code}"
                )
                logger.warning(f"❌ 获取照片失败: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            self._record_test("获取保存的照片", False, f"错误: {e}")
            logger.error(f"获取保存的照片失败: {e}")
            return None
    
    def test_photo_upload_simulation(self) -> bool:
        """模拟照片上传（保存到本地）"""
        self._print_section("6. 照片上传模拟测试")
        
        try:
            # 获取一张新的照片
            logger.info("正在捕获照片用于上传测试...")
            response = self.session.get(f"{self.base_url}/video.jpg", timeout=5)
            
            if response.status_code == 200:
                photo_data = response.content
                photo_size = len(photo_data)
                
                # 模拟上传：保存到本地
                upload_dir = self.test_dir / "uploaded_photos"
                upload_dir.mkdir(exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                photo_path = upload_dir / f"uploaded_photo_{timestamp}.jpg"
                
                with open(photo_path, 'wb') as f:
                    f.write(photo_data)
                
                self._record_test(
                    "照片上传模拟",
                    True,
                    f"照片已上传，大小: {photo_size} 字节"
                )
                logger.info(f"✅ 照片上传成功")
                logger.info(f"  • 大小: {photo_size} 字节")
                logger.info(f"  📸 已保存到: {photo_path}")
                
                return True
            else:
                self._record_test(
                    "照片上传模拟",
                    False,
                    f"HTTP 状态码: {response.status_code}"
                )
                return False
                
        except Exception as e:
            self._record_test("照片上传模拟", False, f"错误: {e}")
            logger.error(f"照片上传失败: {e}")
            return False
    
    def test_continuous_capture(self, duration: int = 10, interval: float = 2.0) -> bool:
        """持续捕获测试"""
        self._print_section(f"7. 持续捕获测试 (持续时间: {duration}s, 间隔: {interval}s)")
        
        try:
            capture_count = 0
            start_time = time.time()
            capture_times = []
            
            logger.info("正在开始持续捕获...")
            
            while time.time() - start_time < duration:
                try:
                    frame_start = time.time()
                    response = self.session.get(f"{self.base_url}/video.jpg", timeout=5)
                    frame_time = time.time() - frame_start
                    
                    if response.status_code == 200:
                        capture_count += 1
                        capture_times.append(frame_time)
                        logger.info(f"  📸 第 {capture_count} 帧: {len(response.content)} 字节 ({frame_time:.3f}s)")
                    
                    remaining = duration - (time.time() - start_time)
                    time.sleep(min(interval, remaining))
                    
                except Exception as e:
                    logger.warning(f"  捕获失败: {e}")
            
            elapsed = time.time() - start_time
            
            if capture_count > 0:
                avg_time = sum(capture_times) / len(capture_times)
                fps = capture_count / elapsed
                
                self._record_test(
                    "持续捕获",
                    True,
                    f"捕获 {capture_count} 帧，FPS: {fps:.2f}，平均耗时: {avg_time:.3f}s"
                )
                logger.info(f"\n📊 持续捕获统计:")
                logger.info(f"  • 总帧数: {capture_count}")
                logger.info(f"  • 实际耗时: {elapsed:.2f}s")
                logger.info(f"  • 平均帧率: {fps:.2f} FPS")
                logger.info(f"  • 平均耗时: {avg_time:.3f}s")
                logger.info(f"  • 最小: {min(capture_times):.3f}s")
                logger.info(f"  • 最大: {max(capture_times):.3f}s")
                
                return True
            else:
                self._record_test("持续捕获", False, "无法捕获任何帧")
                return False
                
        except Exception as e:
            self._record_test("持续捕获", False, f"错误: {e}")
            logger.error(f"持续捕获失败: {e}")
            return False
    
    def generate_report(self):
        """生成测试报告"""
        self._print_section("测试报告总结")
        
        logger.info(f"\n📊 测试统计:")
        logger.info(f"  • 总测试数: {self.test_results['total']}")
        logger.info(f"  • 通过: {self.test_results['passed']} ✅")
        logger.info(f"  • 失败: {self.test_results['failed']} ❌")
        
        if self.test_results['total'] > 0:
            pass_rate = (self.test_results['passed'] / self.test_results['total']) * 100
            logger.info(f"  • 通过率: {pass_rate:.1f}%")
        
        logger.info(f"\n📝 详细结果:")
        for detail in self.test_results['details']:
            logger.info(f"  {detail['status']} | {detail['name']}")
            if detail['message']:
                logger.info(f"      {detail['message']}")
        
        # 保存报告到文件
        report_path = self.test_dir / f"test_report_{int(time.time())}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 报告已保存到: {report_path}")
        
        # 总体结论
        logger.info("\n" + "=" * 60)
        if self.test_results['failed'] == 0:
            logger.info("✅ 所有测试通过！摄像头功能正常。")
        else:
            logger.info(f"⚠️ 有 {self.test_results['failed']} 个测试失败。请检查设备连接。")
        logger.info("=" * 60 + "\n")
    
    def run_all_tests(self) -> bool:
        """运行所有测试"""
        try:
            # 1. 连接测试
            if not self.test_connection():
                logger.error("❌ 无法连接到设备，停止测试")
                self.generate_report()
                return False
            
            time.sleep(1)
            
            # 2. 设备状态查询
            device_status = self.test_device_status()
            time.sleep(1)
            
            # 3. 视频帧捕获
            self.test_video_frame_capture(count=3)
            time.sleep(1)
            
            # 4. 拍照功能
            self.test_capture_photo()
            time.sleep(1)
            
            # 5. 照片上传模拟
            self.test_photo_upload_simulation()
            time.sleep(1)
            
            # 6. 持续捕获测试
            self.test_continuous_capture(duration=10, interval=2.0)
            
            # 生成报告
            self.generate_report()
            
            return self.test_results['failed'] == 0
            
        except KeyboardInterrupt:
            logger.info("\n⚠️ 测试被中断")
            self.generate_report()
            return False
        except Exception as e:
            logger.error(f"❌ 测试出错: {e}")
            self.generate_report()
            return False


def main():
    """主函数"""
    # 获取 ESP32 IP 地址
    if len(sys.argv) > 1:
        esp32_ip = sys.argv[1]
    else:
        # 使用配置文件中的 IP
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                esp32_ip = config.get('esp32_ip', '192.168.1.11')
        except:
            esp32_ip = '192.168.1.11'
    
    logger.info(f"使用 ESP32 IP: {esp32_ip}")
    
    # 创建并运行测试
    test_suite = CameraTestSuite(esp32_ip)
    success = test_suite.run_all_tests()
    
    # 返回状态码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
