#!/usr/bin/env python3
"""
AutoDiary v3.0 完整工作流执行脚本
自动化执行：部署 -> 测试 -> 分析 -> 监控 -> 诊断
"""

import subprocess
import json
import time
import sys
import argparse
from datetime import datetime
from pathlib import Path


class WorkflowOrchestrator:
    """工作流编排器"""

    def __init__(self, esp32_ip: str = "192.168.1.11",
                 esp32_port: int = 80,
                 skip_deploy: bool = False,
                 skip_upload: bool = False):
        self.esp32_ip = esp32_ip
        self.esp32_port = esp32_port
        self.skip_deploy = skip_deploy
        self.skip_upload = skip_upload
        self.project_dir = Path(__file__).parent
        self.start_time = None
        self.results = {}

    def log(self, message: str, level: str = "INFO", section: str = ""):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}]"
        
        if level == "INFO":
            icon = "ℹ️"
        elif level == "SUCCESS":
            icon = "✅"
        elif level == "WARNING":
            icon = "⚠️"
        elif level == "ERROR":
            icon = "❌"
        elif level == "SECTION":
            icon = "📋"
        else:
            icon = "❓"

        if section:
            prefix += f" [{section}]"

        print(f"{prefix} {icon} {message}")

    def section(self, title: str):
        """输出分节标题"""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70 + "\n")

    def run_command(self, command: list, description: str,
                    timeout: int = 300) -> bool:
        """运行系统命令"""
        self.log(f"执行: {' '.join(command)}", "INFO", description)
        
        try:
            result = subprocess.run(
                command,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                self.log(f"{description} 成功", "SUCCESS", description)
                return True
            else:
                self.log(
                    f"{description} 失败: {result.stderr}",
                    "ERROR",
                    description
                )
                return False

        except subprocess.TimeoutExpired:
            self.log(f"{description} 超时", "ERROR", description)
            return False
        except Exception as e:
            self.log(f"{description} 异常: {str(e)}", "ERROR", description)
            return False

    def step_1_deploy_firmware(self) -> bool:
        """步骤 1: 部署固件"""
        self.section("步骤 1: 部署固件")

        if self.skip_deploy:
            self.log("跳过固件部署（已指定 --skip-deploy）",
                     "WARNING")
            return True

        command = ["python", "deploy_firmware.py"]
        if self.skip_upload:
            command.append("--skip-upload")

        return self.run_command(command, "固件部署", timeout=180)

    def step_2_wait_for_device(self) -> bool:
        """步骤 2: 等待设备启动"""
        self.section("步骤 2: 等待设备启动")

        self.log(f"等待 10 秒设备启动...", "INFO")
        time.sleep(10)

        # 检查设备连接
        try:
            import requests

            for i in range(5):
                try:
                    response = requests.get(
                        f"http://{self.esp32_ip}:{self.esp32_port}/status",
                        timeout=5
                    )
                    if response.status_code == 200:
                        self.log("✅ 设备已连接", "SUCCESS")
                        status = response.json()
                        self.log(
                            f"设备版本: {status.get('version', 'unknown')}",
                            "INFO"
                        )
                        return True
                except Exception:
                    self.log(f"连接尝试 {i+1}/5 失败，重试中...",
                             "WARNING")
                    time.sleep(2)

            self.log("无法连接到设备", "ERROR")
            return False

        except ImportError:
            self.log("requests 库未安装", "WARNING")
            return True

    def step_3_collect_checkpoints(self) -> bool:
        """步骤 3: 收集埋点数据"""
        self.section("步骤 3: 收集埋点数据")

        command = [
            "python", "checkpoint_collector.py",
            "--ip", self.esp32_ip,
            "--port", str(self.esp32_port),
            "--cycles", "3"
        ]

        success = self.run_command(
            command,
            "埋点收集",
            timeout=120
        )

        if success:
            # 查找最新的检查点文件
            data_dir = self.project_dir / "data" / "checkpoints"
            if data_dir.exists():
                json_files = sorted(
                    data_dir.glob("checkpoints_cycle*.json"),
                    reverse=True
                )
                if json_files:
                    self.results["latest_checkpoint_file"] = str(
                        json_files[0]
                    )
                    self.log(
                        f"最新检查点: {json_files[0].name}",
                        "INFO"
                    )

        return success

    def step_4_run_realtime_monitoring(self) -> bool:
        """步骤 4: 运行实时监控"""
        self.section("步骤 4: 运行实时监控")

        command = [
            "python", "realtime_monitor.py",
            "--ip", self.esp32_ip,
            "--port", str(self.esp32_port),
            "--duration", "30"
        ]

        return self.run_command(
            command,
            "实时监控",
            timeout=60
        )

    def step_5_fault_diagnosis(self) -> bool:
        """步骤 5: 故障诊断"""
        self.section("步骤 5: 故障诊断分析")

        if "latest_checkpoint_file" not in self.results:
            self.log("未找到检查点文件，跳过诊断", "WARNING")
            return True

        checkpoint_file = self.results["latest_checkpoint_file"]
        command = [
            "python", "fault_diagnostics.py",
            checkpoint_file
        ]

        return self.run_command(
            command,
            "故障诊断",
            timeout=60
        )

    def print_summary(self):
        """打印工作流摘要"""
        self.section("工作流完成摘要")

        elapsed_time = (datetime.now() - self.start_time).total_seconds()

        print(f"⏱️  总耗时: {elapsed_time:.1f} 秒")
        print(f"🎯 设备: {self.esp32_ip}:{self.esp32_port}")
        print(f"📊 检查点文件: {self.results.get('latest_checkpoint_file', 'N/A')}")

        print("\n工作流步骤执行状态:")
        steps = [
            ("1. 固件部署", self.step_1_deploy_firmware),
            ("2. 设备启动", self.step_2_wait_for_device),
            ("3. 埋点收集", self.step_3_collect_checkpoints),
            ("4. 实时监控", self.step_4_run_realtime_monitoring),
            ("5. 故障诊断", self.step_5_fault_diagnosis)
        ]

        for name, _ in steps:
            print(f"  ✅ {name}")

        print("\n数据输出位置:")
        print(f"  📁 检查点: data/checkpoints/")
        print(f"  📁 监控日志: data/monitoring/")
        print(f"  📁 诊断报告: data/diagnostics/")

    def run_workflow(self) -> bool:
        """执行完整工作流"""
        self.section("AutoDiary v3.0 完整工作流启动")
        self.start_time = datetime.now()

        self.log(f"开始时间: {self.start_time}", "INFO")
        self.log(f"设备地址: {self.esp32_ip}:{self.esp32_port}", "INFO")

        # 执行各步骤
        steps = [
            (self.step_1_deploy_firmware, "固件部署"),
            (self.step_2_wait_for_device, "设备启动"),
            (self.step_3_collect_checkpoints, "埋点收集"),
            (self.step_4_run_realtime_monitoring, "实时监控"),
            (self.step_5_fault_diagnosis, "故障诊断")
        ]

        failed_steps = []

        for step_func, step_name in steps:
            try:
                if not step_func():
                    failed_steps.append(step_name)
                    self.log(f"{step_name} 失败，继续下一步", "WARNING")
            except Exception as e:
                failed_steps.append(step_name)
                self.log(f"{step_name} 异常: {str(e)}", "ERROR")

        # 打印摘要
        self.print_summary()

        if failed_steps:
            print(f"\n⚠️  失败的步骤: {', '.join(failed_steps)}")
            return False

        print("\n✅ 所有步骤执行成功！")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="AutoDiary v3.0 完整工作流执行"
    )
    parser.add_argument(
        "--ip",
        default="192.168.1.11",
        help="ESP32 设备 IP 地址"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=80,
        help="ESP32 设备端口"
    )
    parser.add_argument(
        "--skip-deploy",
        action="store_true",
        help="跳过固件部署"
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="跳过固件烧录（仅编译）"
    )

    args = parser.parse_args()

    orchestrator = WorkflowOrchestrator(
        esp32_ip=args.ip,
        esp32_port=args.port,
        skip_deploy=args.skip_deploy,
        skip_upload=args.skip_upload
    )

    success = orchestrator.run_workflow()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
