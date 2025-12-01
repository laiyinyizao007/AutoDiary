#!/usr/bin/env python3
"""
AutoDiary v3.0 固件部署工具
支持：固件烧录、设备检测、部署验证
"""

import subprocess
import sys
import json
import time
import os
from datetime import datetime
from pathlib import Path

class FirmwareDeployer:
    def __init__(self):
        self.project_dir = Path(__file__).parent
        self.pio_ini = self.project_dir / "platformio.ini"
        self.firmware_source = self.project_dir / "src" / "main_with_checkpoints.cpp"
        self.log_file = self.project_dir / "deployment_log.txt"
        self.device_port = None
        
    def log(self, message, level="INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        print(log_msg)
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    
    def detect_device(self):
        """检测连接的 ESP32 设备"""
        self.log("检测 ESP32 设备...")
        
        try:
            result = subprocess.run(
                ["platformio", "device", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout
                self.log(f"检测到的设备:\n{output}")
                
                # 查找 COM 端口
                for line in output.split("\n"):
                    if "COM" in line.upper() or "/dev/tty" in line:
                        self.device_port = line.split()[0]
                        self.log(f"✅ 检测到设备端口: {self.device_port}")
                        return True
                        
                self.log("⚠️  未找到可用的设备端口", "WARNING")
                return False
            else:
                self.log(f"检测失败: {result.stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"检测异常: {str(e)}", "ERROR")
            return False
    
    def build_firmware(self):
        """编译固件"""
        self.log("开始编译 v3.0 固件...")
        
        try:
            # 检查源文件
            if not self.firmware_source.exists():
                self.log(f"固件源文件不存在: {self.firmware_source}", "ERROR")
                return False
            
            # 编译
            result = subprocess.run(
                ["platformio", "run", "-e", "seeed_xiao_esp32s3"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.log("✅ 固件编译成功")
                self.log(f"编译输出:\n{result.stdout}")
                return True
            else:
                self.log(f"编译失败:\n{result.stderr}", "ERROR")
                return False
                
        except subprocess.TimeoutExpired:
            self.log("编译超时", "ERROR")
            return False
        except Exception as e:
            self.log(f"编译异常: {str(e)}", "ERROR")
            return False
    
    def upload_firmware(self):
        """烧录固件到设备"""
        if not self.device_port:
            self.log("没有可用的设备端口，跳过烧录", "WARNING")
            return False
        
        self.log(f"开始烧录固件到 {self.device_port}...")
        
        try:
            result = subprocess.run(
                [
                    "platformio", "run", "-e", "seeed_xiao_esp32s3",
                    "-t", "upload",
                    "--upload-port", self.device_port
                ],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.log("✅ 固件烧录成功")
                self.log(f"烧录输出:\n{result.stdout}")
                return True
            else:
                self.log(f"烧录失败:\n{result.stderr}", "ERROR")
                return False
                
        except subprocess.TimeoutExpired:
            self.log("烧录超时", "ERROR")
            return False
        except Exception as e:
            self.log(f"烧录异常: {str(e)}", "ERROR")
            return False
    
    def monitor_serial(self, duration=30):
        """监控串口输出"""
        if not self.device_port:
            self.log("没有可用的设备端口", "WARNING")
            return False
        
        self.log(f"监控串口输出 ({duration}s)...")
        
        try:
            result = subprocess.run(
                ["platformio", "device", "monitor", "--port", self.device_port],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=duration + 5
            )
            
            output = result.stdout + result.stderr
            self.log(f"串口输出:\n{output}")
            return True
            
        except subprocess.TimeoutExpired:
            self.log("串口监控超时（正常）")
            return True
        except Exception as e:
            self.log(f"监控异常: {str(e)}", "ERROR")
            return False
    
    def verify_deployment(self):
        """验证部署成功"""
        self.log("验证固件部署...")
        
        # 等待设备启动
        time.sleep(3)
        
        # 检查设备是否响应
        try:
            import requests
            
            # 从 config.json 读取 ESP32 IP
            config_file = self.project_dir / "config.json"
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    esp32_ip = config.get("esp32_ip", "192.168.1.11")
                    esp32_port = config.get("esp32_port", 80)
            else:
                esp32_ip = "192.168.1.11"
                esp32_port = 80
            
            url = f"http://{esp32_ip}:{esp32_port}/status"
            self.log(f"尝试连接设备: {url}")
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                status = response.json()
                self.log(f"✅ 设备响应正常")
                self.log(f"设备状态: {json.dumps(status, indent=2, ensure_ascii=False)}")
                return True
            else:
                self.log(f"设备响应异常: {response.status_code}", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"验证异常: {str(e)}", "WARNING")
            # 不中断部署流程
            return True
    
    def deploy(self, skip_upload=False):
        """执行完整的部署流程"""
        self.log("=" * 60)
        self.log("开始 AutoDiary v3.0 固件部署")
        self.log("=" * 60)
        
        # 步骤1: 检测设备
        if not self.detect_device():
            if not skip_upload:
                self.log("无法检测到设备，部署终止", "ERROR")
                return False
        
        # 步骤2: 编译固件
        if not self.build_firmware():
            self.log("固件编译失败，部署终止", "ERROR")
            return False
        
        # 步骤3: 烧录固件
        if not skip_upload and self.device_port:
            if not self.upload_firmware():
                self.log("固件烧录失败", "ERROR")
                return False
        else:
            self.log("跳过固件烧录（已编译完成）")
        
        # 步骤4: 验证部署
        if self.device_port:
            time.sleep(2)
            self.verify_deployment()
        
        self.log("=" * 60)
        self.log("✅ 部署流程完成")
        self.log("=" * 60)
        
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="AutoDiary v3.0 固件部署工具")
    parser.add_argument("--skip-upload", action="store_true", help="跳过烧录，仅编译")
    parser.add_argument("--monitor", action="store_true", help="烧录后监控串口")
    parser.add_argument("--duration", type=int, default=30, help="监控持续时间（秒）")
    
    args = parser.parse_args()
    
    deployer = FirmwareDeployer()
    
    # 执行部署
    success = deployer.deploy(skip_upload=args.skip_upload)
    
    if success and args.monitor:
        deployer.monitor_serial(duration=args.duration)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
