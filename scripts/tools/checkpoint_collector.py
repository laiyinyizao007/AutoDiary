#!/usr/bin/env python3
"""
AutoDiary v3.0 埋点数据收集系统
功能：
- 从设备收集埋点数据
- 存储和分析埋点数据
- 生成性能报告
- 实时监控设备状态
"""

import requests
import json
import time
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import statistics


class CheckpointCollector:
    """埋点数据收集器"""

    def __init__(self, esp32_ip: str = "192.168.1.11",
                 esp32_port: int = 80):
        self.esp32_ip = esp32_ip
        self.esp32_port = esp32_port
        self.base_url = f"http://{esp32_ip}:{esp32_port}"
        self.project_dir = Path(__file__).parent
        self.data_dir = self.project_dir / "data" / "checkpoints"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.checkpoints: List[Dict] = []
        self.sessions: List[Dict] = []

    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def connect_device(self) -> bool:
        """检查设备连接"""
        try:
            response = requests.get(
                f"{self.base_url}/status",
                timeout=5
            )
            if response.status_code == 200:
                self.log(f"✅ 设备已连接: {self.base_url}")
                return True
            else:
                self.log(f"❌ 设备响应异常: {response.status_code}", "ERROR")
                return False
        except requests.exceptions.ConnectionError:
            self.log(f"❌ 无法连接到设备: {self.base_url}", "ERROR")
            return False
        except Exception as e:
            self.log(f"❌ 连接异常: {str(e)}", "ERROR")
            return False

    def trigger_full_cycle(self) -> bool:
        """触发设备执行完整周期"""
        try:
            self.log("触发设备执行完整周期...")
            response = requests.get(
                f"{self.base_url}/fullcycle",
                timeout=60
            )
            if response.status_code == 200:
                self.log(f"✅ 完整周期已启动: {response.text}")
                return True
            else:
                self.log(f"❌ 启动失败: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ 触发异常: {str(e)}", "ERROR")
            return False

    def collect_checkpoints(self) -> bool:
        """从设备收集埋点数据"""
        try:
            self.log("收集设备埋点数据...")
            response = requests.get(
                f"{self.base_url}/checkpoints",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                self.checkpoints = data.get("checkpoints", [])
                self.log(f"✅ 成功收集 {len(self.checkpoints)} 个埋点")
                return True
            else:
                self.log(f"❌ 收集失败: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ 收集异常: {str(e)}", "ERROR")
            return False

    def save_checkpoints(self, session_name: Optional[str] = None) -> Path:
        """保存埋点数据"""
        if not self.checkpoints:
            self.log("❌ 没有埋点数据可保存", "WARNING")
            return None

        # 生成文件名
        if not session_name:
            session_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        json_file = self.data_dir / f"checkpoints_{session_name}.json"
        csv_file = self.data_dir / f"checkpoints_{session_name}.csv"

        # 保存 JSON
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "device": f"{self.esp32_ip}:{self.esp32_port}",
                "checkpoints": self.checkpoints
            }, f, indent=2, ensure_ascii=False)
        
        self.log(f"✅ 埋点数据已保存: {json_file}")

        # 保存 CSV
        if self.checkpoints:
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=self.checkpoints[0].keys()
                )
                writer.writeheader()
                writer.writerows(self.checkpoints)
            
            self.log(f"✅ CSV 数据已保存: {csv_file}")

        return json_file

    def analyze_checkpoints(self) -> Dict:
        """分析埋点数据"""
        if not self.checkpoints:
            self.log("❌ 没有埋点数据可分析", "WARNING")
            return {}

        analysis = {
            "total_checkpoints": len(self.checkpoints),
            "total_time_ms": 0,
            "phases": {},
            "memory": {
                "initial_heap": 0,
                "final_heap": 0,
                "delta": 0
            },
            "performance": {}
        }

        # 总时间
        if self.checkpoints:
            first_cp = self.checkpoints[0]
            last_cp = self.checkpoints[-1]
            analysis["total_time_ms"] = (
                last_cp.get("elapsed_ms", 0) - 
                first_cp.get("elapsed_ms", 0)
            )

            # 内存分析
            analysis["memory"]["initial_heap"] = first_cp.get("heap_free", 0)
            analysis["memory"]["final_heap"] = last_cp.get("heap_free", 0)
            analysis["memory"]["delta"] = (
                analysis["memory"]["final_heap"] - 
                analysis["memory"]["initial_heap"]
            )

        # 按阶段分析
        phases_data = {}
        for cp in self.checkpoints:
            phase = cp.get("phase", "unknown")
            if phase not in phases_data:
                phases_data[phase] = []
            
            phase_duration = cp.get("phase_duration_ms", 0)
            if phase_duration > 0:
                phases_data[phase].append(phase_duration)

        for phase, durations in phases_data.items():
            if durations:
                analysis["phases"][str(phase)] = {
                    "count": len(durations),
                    "avg_ms": statistics.mean(durations),
                    "min_ms": min(durations),
                    "max_ms": max(durations),
                    "total_ms": sum(durations)
                }

        # 性能指标
        heap_values = [cp.get("heap_free", 0) for cp in self.checkpoints]
        if heap_values:
            analysis["performance"]["avg_heap_free"] = (
                statistics.mean(heap_values)
            )
            analysis["performance"]["min_heap_free"] = min(heap_values)
            analysis["performance"]["max_heap_free"] = max(heap_values)

        return analysis

    def print_analysis(self, analysis: Dict):
        """打印分析结果"""
        print("\n" + "=" * 60)
        print("埋点数据分析报告")
        print("=" * 60)

        print(f"\n总埋点数: {analysis.get('total_checkpoints', 0)}")
        print(f"总耗时: {analysis.get('total_time_ms', 0)} ms")

        # 内存分析
        memory = analysis.get("memory", {})
        print(f"\n内存分析:")
        print(f"  初始堆: {memory.get('initial_heap', 0)} bytes")
        print(f"  最终堆: {memory.get('final_heap', 0)} bytes")
        print(f"  变化: {memory.get('delta', 0)} bytes")

        # 阶段分析
        phases = analysis.get("phases", {})
        if phases:
            print(f"\n阶段分析:")
            for phase, stats in phases.items():
                print(f"  阶段 {phase}:")
                print(f"    计数: {stats.get('count', 0)}")
                print(f"    平均耗时: {stats.get('avg_ms', 0):.2f} ms")
                print(f"    最小耗时: {stats.get('min_ms', 0)} ms")
                print(f"    最大耗时: {stats.get('max_ms', 0)} ms")

        # 性能指标
        perf = analysis.get("performance", {})
        if perf:
            print(f"\n性能指标:")
            print(f"  平均堆空闲: {perf.get('avg_heap_free', 0):.0f} bytes")
            print(f"  最小堆空闲: {perf.get('min_heap_free', 0)} bytes")
            print(f"  最大堆空闲: {perf.get('max_heap_free', 0)} bytes")

        print("\n" + "=" * 60 + "\n")

    def run_full_collection(self, cycles: int = 1) -> bool:
        """执行完整的埋点收集流程"""
        self.log("=" * 60)
        self.log(f"开始埋点数据收集 ({cycles} 个周期)")
        self.log("=" * 60)

        # 检查连接
        if not self.connect_device():
            return False

        for cycle in range(1, cycles + 1):
            self.log(f"\n--- 周期 {cycle}/{cycles} ---")

            # 触发完整周期
            if not self.trigger_full_cycle():
                self.log(f"周期 {cycle} 启动失败", "ERROR")
                continue

            # 等待执行
            self.log("等待设备执行完整周期...")
            time.sleep(10)

            # 收集数据
            if not self.collect_checkpoints():
                self.log(f"周期 {cycle} 数据收集失败", "ERROR")
                continue

            # 分析数据
            analysis = self.analyze_checkpoints()
            
            # 保存数据
            session_name = f"cycle{cycle}_{datetime.now().strftime('%H%M%S')}"
            saved_file = self.save_checkpoints(session_name)

            # 打印分析
            self.print_analysis(analysis)

            # 记录会话
            self.sessions.append({
                "cycle": cycle,
                "file": str(saved_file),
                "analysis": analysis,
                "timestamp": datetime.now().isoformat()
            })

            if cycle < cycles:
                self.log(f"等待 {5} 秒后继续下一个周期...")
                time.sleep(5)

        # 保存会话汇总
        self.save_sessions_summary()

        self.log("=" * 60)
        self.log("✅ 埋点收集完成")
        self.log("=" * 60)

        return True

    def save_sessions_summary(self):
        """保存会话汇总"""
        if not self.sessions:
            return

        summary_file = (
            self.data_dir / 
            f"sessions_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(self.sessions, f, indent=2, ensure_ascii=False)

        self.log(f"✅ 会话汇总已保存: {summary_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="AutoDiary v3.0 埋点收集工具"
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
        "--cycles",
        type=int,
        default=3,
        help="运行周期数"
    )

    args = parser.parse_args()

    collector = CheckpointCollector(
        esp32_ip=args.ip,
        esp32_port=args.port
    )

    collector.run_full_collection(cycles=args.cycles)


if __name__ == "__main__":
    main()
