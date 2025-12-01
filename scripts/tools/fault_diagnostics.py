#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AutoDiary v3.0 故障诊断系统
功能：
- 基于埋点数据进行故障诊断
- 性能瓶颈识别
- 内存泄漏检测
- 自动化故障排查建议
"""

import json
import sys
import io
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from enum import Enum

# 设置 stdout 编码为 UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class FaultLevel(Enum):
    """故障级别"""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class FaultDiagnostics:
    """故障诊断系统"""

    def __init__(self, checkpoint_file: Optional[Path] = None):
        self.checkpoint_file = checkpoint_file
        self.checkpoints: List[Dict] = []
        self.project_dir = Path(__file__).parent
        self.report_dir = self.project_dir / "data" / "diagnostics"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        self.faults: List[Dict] = []
        self.recommendations: List[str] = []

    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def load_checkpoints(self) -> bool:
        """加载埋点数据"""
        if not self.checkpoint_file:
            self.log("未指定检查点文件", "ERROR")
            return False

        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.checkpoints = data.get("checkpoints", [])
                self.log(f"✅ 加载 {len(self.checkpoints)} 个检查点")
                return True
        except Exception as e:
            self.log(f"加载失败: {str(e)}", "ERROR")
            return False

    def diagnose_memory_leaks(self) -> Tuple[FaultLevel, List[str]]:
        """诊断内存泄漏"""
        if len(self.checkpoints) < 2:
            return FaultLevel.OK, []

        issues = []
        
        # 获取初始和最终的堆内存
        first_heap = self.checkpoints[0].get("heap_free", 0)
        last_heap = self.checkpoints[-1].get("heap_free", 0)
        memory_delta = last_heap - first_heap

        # 计算堆内存趋势
        heap_trend = [cp.get("heap_free", 0) for cp in self.checkpoints]

        # 检查是否单调递减
        decreasing_count = 0
        for i in range(1, len(heap_trend)):
            if heap_trend[i] < heap_trend[i-1]:
                decreasing_count += 1

        decrease_ratio = decreasing_count / (len(heap_trend) - 1)

        if memory_delta < -10000:  # 内存减少超过 10KB
            issues.append(
                f"检测到明显的内存泄漏: "
                f"{abs(memory_delta)/1024:.1f}KB"
            )
            self.recommendations.append(
                "检查是否存在未释放的缓冲区或文件句柄"
            )
            self.recommendations.append(
                "检查 esp_camera_fb_return() 是否被正确调用"
            )
            return FaultLevel.CRITICAL, issues

        if decrease_ratio > 0.5 and memory_delta < -5000:
            issues.append(
                f"检测到可能的内存泄漏: "
                f"内存呈下降趋势，"
                f"总减少 {abs(memory_delta)/1024:.1f}KB"
            )
            self.recommendations.append(
                "逐步检查各阶段的内存释放"
            )
            return FaultLevel.WARNING, issues

        return FaultLevel.OK, issues

    def diagnose_performance_bottleneck(
            self
    ) -> Tuple[FaultLevel, List[str]]:
        """诊断性能瓶颈"""
        if not self.checkpoints:
            return FaultLevel.OK, []

        issues = []
        
        # 按阶段分析耗时
        phases_durations = {}
        for cp in self.checkpoints:
            phase = cp.get("phase", "unknown")
            duration = cp.get("phase_duration_ms", 0)
            
            if phase not in phases_durations:
                phases_durations[phase] = []
            if duration > 0:
                phases_durations[phase].append(duration)

        # 找出最慢的阶段
        slowest_phase = None
        slowest_time = 0
        
        for phase, durations in phases_durations.items():
            if durations:
                avg_duration = sum(durations) / len(durations)
                if avg_duration > slowest_time:
                    slowest_time = avg_duration
                    slowest_phase = phase

        if slowest_time > 5000:  # 超过 5 秒
            issues.append(
                f"阶段 {slowest_phase} 耗时过长: "
                f"{slowest_time:.0f}ms"
            )
            self.recommendations.append(
                f"优化阶段 {slowest_phase} 的处理逻辑"
            )
            return FaultLevel.ERROR, issues

        if slowest_time > 3000:  # 超过 3 秒
            issues.append(
                f"阶段 {slowest_phase} 耗时较长: "
                f"{slowest_time:.0f}ms"
            )
            self.recommendations.append(
                f"考虑缓存或批处理优化阶段 {slowest_phase}"
            )
            return FaultLevel.WARNING, issues

        return FaultLevel.OK, issues

    def diagnose_heap_fragmentation(self) -> Tuple[FaultLevel, List[str]]:
        """诊断堆碎片化"""
        if len(self.checkpoints) < 2:
            return FaultLevel.OK, []

        issues = []
        heap_values = [cp.get("heap_free", 0) for cp in self.checkpoints]

        # 计算堆波动
        variance = 0
        if len(heap_values) > 1:
            mean = sum(heap_values) / len(heap_values)
            variance = sum(
                (x - mean) ** 2 for x in heap_values
            ) / len(heap_values)
            std_dev = variance ** 0.5

            # 高波动表示可能的碎片化
            if std_dev > 50000:  # 标准差超过 50KB
                issues.append(
                    f"检测到堆碎片化迹象: "
                    f"标准差 {std_dev/1024:.1f}KB"
                )
                self.recommendations.append(
                    "考虑添加堆整理或使用内存池"
                )
                return FaultLevel.WARNING, issues

        return FaultLevel.OK, issues

    def diagnose_network_issues(self) -> Tuple[FaultLevel, List[str]]:
        """诊断网络问题"""
        if not self.checkpoints:
            return FaultLevel.OK, []

        issues = []
        
        # 检查上传阶段 (phase=3)
        upload_checkpoints = [
            cp for cp in self.checkpoints if cp.get("phase") == 3
        ]

        if not upload_checkpoints:
            return FaultLevel.OK, []

        # 检查上传耗时
        upload_duration = 0
        if len(upload_checkpoints) > 1:
            first_time = upload_checkpoints[0].get("elapsed_ms", 0)
            last_time = upload_checkpoints[-1].get("elapsed_ms", 0)
            upload_duration = last_time - first_time

        if upload_duration > 30000:  # 上传超过 30 秒
            issues.append(
                f"上传耗时过长: {upload_duration}ms"
            )
            self.recommendations.append(
                "检查网络连接速度和 WiFi 信号强度"
            )
            self.recommendations.append(
                "考虑减小图像质量或分块上传"
            )
            return FaultLevel.ERROR, issues

        if upload_duration > 15000:  # 上传超过 15 秒
            issues.append(
                f"上传耗时较长: {upload_duration}ms"
            )
            self.recommendations.append(
                "考虑优化网络设置或服务器性能"
            )
            return FaultLevel.WARNING, issues

        return FaultLevel.OK, issues

    def diagnose_camera_issues(self) -> Tuple[FaultLevel, List[str]]:
        """诊断摄像头问题"""
        if not self.checkpoints:
            return FaultLevel.OK, []

        issues = []
        
        # 检查拍摄阶段 (phase=1)
        capture_checkpoints = [
            cp for cp in self.checkpoints if cp.get("phase") == 1
        ]

        if not capture_checkpoints:
            # 没有拍摄阶段的检查点
            issues.append("未检测到摄像头初始化")
            self.recommendations.append(
                "检查摄像头硬件连接和驱动"
            )
            return FaultLevel.ERROR, issues

        # 检查帧大小
        frame_sizes = [
            cp.get("frame_size", 0) 
            for cp in capture_checkpoints 
            if cp.get("frame_size", 0) > 0
        ]

        if frame_sizes:
            avg_frame_size = sum(frame_sizes) / len(frame_sizes)
            
            if avg_frame_size < 1000:  # 帧大小小于 1KB
                issues.append(
                    f"摄像头帧大小异常小: "
                    f"{avg_frame_size/1024:.1f}KB"
                )
                self.recommendations.append(
                    "检查摄像头配置和 JPEG 质量设置"
                )
                return FaultLevel.WARNING, issues

        return FaultLevel.OK, issues

    def diagnose_storage_issues(self) -> Tuple[FaultLevel, List[str]]:
        """诊断存储问题"""
        if not self.checkpoints:
            return FaultLevel.OK, []

        issues = []
        
        # 检查存储阶段 (phase=2)
        storage_checkpoints = [
            cp for cp in self.checkpoints if cp.get("phase") == 2
        ]

        if not storage_checkpoints:
            return FaultLevel.OK, []

        # 检查文件大小
        file_sizes = [
            cp.get("file_size", 0) 
            for cp in storage_checkpoints 
            if cp.get("file_size", 0) > 0
        ]

        if not file_sizes:
            issues.append("未检测到保存的文件")
            self.recommendations.append(
                "检查 SPIFFS 初始化和文件系统权限"
            )
            return FaultLevel.ERROR, issues

        # 检查存储耗时
        storage_duration = 0
        if len(storage_checkpoints) > 1:
            first_time = storage_checkpoints[0].get("elapsed_ms", 0)
            last_time = storage_checkpoints[-1].get("elapsed_ms", 0)
            storage_duration = last_time - first_time

        if storage_duration > 5000:  # 存储超过 5 秒
            issues.append(
                f"文件存储耗时过长: {storage_duration}ms"
            )
            self.recommendations.append(
                "检查 SPIFFS 性能或使用 SD 卡"
            )
            return FaultLevel.WARNING, issues

        return FaultLevel.OK, issues

    def run_diagnostics(self) -> bool:
        """执行完整诊断"""
        self.log("=" * 60)
        self.log("开始故障诊断")
        self.log("=" * 60)

        if not self.load_checkpoints():
            return False

        # 执行各项诊断
        diagnostics = [
            ("内存泄漏检测", self.diagnose_memory_leaks),
            ("性能瓶颈诊断", self.diagnose_performance_bottleneck),
            ("堆碎片化诊断", self.diagnose_heap_fragmentation),
            ("网络问题诊断", self.diagnose_network_issues),
            ("摄像头诊断", self.diagnose_camera_issues),
            ("存储诊断", self.diagnose_storage_issues),
        ]

        for name, diagnose_func in diagnostics:
            level, issues = diagnose_func()
            
            if issues:
                self.faults.append({
                    "name": name,
                    "level": level.value,
                    "issues": issues
                })

        # 生成报告
        self.generate_report()

        return True

    def generate_report(self):
        """生成诊断报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "checkpoint_file": str(self.checkpoint_file),
            "total_checkpoints": len(self.checkpoints),
            "faults": self.faults,
            "recommendations": self.recommendations
        }

        # 打印报告
        self.print_report(report)

        # 保存报告
        report_file = (
            self.report_dir / 
            f"diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        self.log(f"✅ 诊断报告已保存: {report_file}")

    def print_report(self, report: Dict):
        """打印诊断报告"""
        print("\n" + "=" * 60)
        print("诊断报告")
        print("=" * 60)

        print(f"\n检查点文件: {report['checkpoint_file']}")
        print(f"总检查点数: {report['total_checkpoints']}")

        # 故障汇总
        faults = report.get("faults", [])
        if faults:
            print(f"\n检测到 {len(faults)} 个潜在问题:")
            print()
            for fault in faults:
                level = fault.get("level", "unknown")
                level_icon = {
                    "ok": "✅",
                    "warning": "⚠️",
                    "error": "❌",
                    "critical": "🔴"
                }.get(level, "❓")
                
                print(f"{level_icon} {fault['name']}")
                for issue in fault.get("issues", []):
                    print(f"   - {issue}")

        # 建议
        recommendations = report.get("recommendations", [])
        if recommendations:
            print(f"\n优化建议:")
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec}")

        print("\n" + "=" * 60 + "\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="AutoDiary v3.0 故障诊断工具"
    )
    parser.add_argument(
        "checkpoint_file",
        help="检查点数据文件路径"
    )

    args = parser.parse_args()

    checkpoint_file = Path(args.checkpoint_file)
    if not checkpoint_file.exists():
        print(f"❌ 文件不存在: {checkpoint_file}")
        return 1

    diagnostics = FaultDiagnostics(checkpoint_file)
    success = diagnostics.run_diagnostics()

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
