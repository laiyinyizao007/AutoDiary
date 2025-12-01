#!/usr/bin/env python3
"""
AutoDiary v3.0 实时监控系统
功能：
- 实时监控设备状态和埋点数据
- WebSocket 实时推送
- 性能告警
- 设备健康度检测
"""

import requests
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HealthMetrics:
    """健康指标"""
    device_ip: str
    device_port: int
    is_connected: bool
    cpu_load: float
    memory_usage: float
    memory_free: int
    network_latency: float
    last_checkpoint_age: int
    total_checkpoints: int
    status: HealthStatus


class RealtimeMonitor:
    """实时监控系统"""

    def __init__(self, esp32_ip: str = "192.168.1.11",
                 esp32_port: int = 80,
                 check_interval: int = 5):
        self.esp32_ip = esp32_ip
        self.esp32_port = esp32_port
        self.base_url = f"http://{esp32_ip}:{esp32_port}"
        self.check_interval = check_interval
        self.project_dir = Path(__file__).parent
        self.log_dir = self.project_dir / "data" / "monitoring"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.is_running = False
        self.monitor_thread = None
        self.metrics_history: List[HealthMetrics] = []
        self.alert_callbacks: List[Callable] = []
        self.last_checkpoint_count = 0

    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        print(log_msg)
        
        log_file = self.log_dir / "monitor.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")

    def register_alert(self, callback: Callable):
        """注册告警回调"""
        self.alert_callbacks.append(callback)

    def fetch_device_status(self) -> Optional[Dict]:
        """获取设备状态"""
        try:
            response = requests.get(
                f"{self.base_url}/status",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    def fetch_checkpoints(self) -> Optional[List[Dict]]:
        """获取埋点数据"""
        try:
            response = requests.get(
                f"{self.base_url}/checkpoints",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("checkpoints", [])
            return None
        except Exception:
            return None

    def calculate_metrics(self) -> Optional[HealthMetrics]:
        """计算健康指标"""
        status_data = self.fetch_device_status()
        checkpoints = self.fetch_checkpoints()
        
        if not status_data:
            return HealthMetrics(
                device_ip=self.esp32_ip,
                device_port=self.esp32_port,
                is_connected=False,
                cpu_load=0.0,
                memory_usage=0.0,
                memory_free=0,
                network_latency=0.0,
                last_checkpoint_age=-1,
                total_checkpoints=0,
                status=HealthStatus.CRITICAL
            )

        # 计算内存使用
        memory_free = 0
        if checkpoints and len(checkpoints) > 0:
            memory_free = checkpoints[-1].get("heap_free", 0)

        # 计算内存使用率 (假设总内存为 512KB)
        total_memory = 512 * 1024
        memory_usage = (
            (total_memory - memory_free) / total_memory * 100 
            if memory_free > 0 else 0
        )

        # 计算检查点年龄
        checkpoint_count = len(checkpoints) if checkpoints else 0
        last_checkpoint_age = 0
        if checkpoints and checkpoint_count > self.last_checkpoint_count:
            last_checkpoint_age = 0
            self.last_checkpoint_count = checkpoint_count
        else:
            last_checkpoint_age = -1

        # 判断健康状态
        health_status = HealthStatus.HEALTHY
        if memory_usage > 80:
            health_status = HealthStatus.CRITICAL
        elif memory_usage > 60:
            health_status = HealthStatus.WARNING

        metrics = HealthMetrics(
            device_ip=self.esp32_ip,
            device_port=self.esp32_port,
            is_connected=True,
            cpu_load=0.0,
            memory_usage=memory_usage,
            memory_free=memory_free,
            network_latency=0.0,
            last_checkpoint_age=last_checkpoint_age,
            total_checkpoints=checkpoint_count,
            status=health_status
        )

        return metrics

    def check_alerts(self, metrics: HealthMetrics):
        """检查告警条件"""
        alerts = []

        if not metrics.is_connected:
            alerts.append({
                "level": "CRITICAL",
                "message": "设备离线"
            })

        if metrics.memory_usage > 90:
            alerts.append({
                "level": "CRITICAL",
                "message": f"内存使用率过高: {metrics.memory_usage:.1f}%"
            })
        elif metrics.memory_usage > 75:
            alerts.append({
                "level": "WARNING",
                "message": f"内存使用率较高: {metrics.memory_usage:.1f}%"
            })

        # 触发告警
        for alert in alerts:
            self.log(
                f"{alert['level']}: {alert['message']}",
                alert['level']
            )
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self.log(f"告警回调异常: {str(e)}", "ERROR")

    def monitor_loop(self):
        """监控循环"""
        self.log("启动实时监控...")

        while self.is_running:
            try:
                # 计算指标
                metrics = self.calculate_metrics()
                if metrics:
                    # 保存历史
                    self.metrics_history.append(metrics)
                    
                    # 检查告警
                    self.check_alerts(metrics)
                    
                    # 打印状态
                    self.print_metrics(metrics)

            except Exception as e:
                self.log(f"监控异常: {str(e)}", "ERROR")

            time.sleep(self.check_interval)

    def print_metrics(self, metrics: HealthMetrics):
        """打印指标"""
        status_str = {
            HealthStatus.HEALTHY: "✅ 正常",
            HealthStatus.WARNING: "⚠️  警告",
            HealthStatus.CRITICAL: "❌ 异常"
        }.get(metrics.status, "未知")

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 设备状态 {status_str}")
        print(f"  连接: {'✅ 已连接' if metrics.is_connected else '❌ 离线'}")
        print(f"  内存: {metrics.memory_usage:.1f}% "
              f"({metrics.memory_free} bytes 空闲)")
        print(f"  埋点: {metrics.total_checkpoints} 个")

    def start(self):
        """启动监控"""
        if self.is_running:
            self.log("监控已在运行中", "WARNING")
            return

        self.is_running = True
        self.monitor_thread = threading.Thread(
            target=self.monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        self.log(f"✅ 实时监控已启动 (间隔 {self.check_interval}s)")

    def stop(self):
        """停止监控"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.log("✅ 实时监控已停止")

    def save_metrics(self):
        """保存监控数据"""
        if not self.metrics_history:
            return

        metrics_file = (
            self.log_dir / 
            f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        # 转换为可序列化格式
        data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": [
                {
                    "time": m.device_ip,
                    "is_connected": m.is_connected,
                    "memory_usage": m.memory_usage,
                    "memory_free": m.memory_free,
                    "total_checkpoints": m.total_checkpoints,
                    "status": m.status.value
                }
                for m in self.metrics_history
            ]
        }

        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.log(f"✅ 监控数据已保存: {metrics_file}")

    def get_summary(self) -> Dict:
        """获取监控摘要"""
        if not self.metrics_history:
            return {}

        memory_usage_list = [
            m.memory_usage for m in self.metrics_history
        ]
        checkpoint_counts = [
            m.total_checkpoints for m in self.metrics_history
        ]

        import statistics

        return {
            "total_checks": len(self.metrics_history),
            "uptime_percent": (
                sum(1 for m in self.metrics_history if m.is_connected) /
                len(self.metrics_history) * 100
            ),
            "avg_memory_usage": statistics.mean(memory_usage_list),
            "max_memory_usage": max(memory_usage_list),
            "min_memory_usage": min(memory_usage_list),
            "max_checkpoints": max(checkpoint_counts) if checkpoint_counts else 0,
            "critical_alerts": sum(
                1 for m in self.metrics_history
                if m.status == HealthStatus.CRITICAL
            ),
            "warning_alerts": sum(
                1 for m in self.metrics_history
                if m.status == HealthStatus.WARNING
            )
        }


def default_alert_handler(alert: Dict):
    """默认告警处理器"""
    print(f"🚨 告警: [{alert['level']}] {alert['message']}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="AutoDiary v3.0 实时监控系统"
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
        "--interval",
        type=int,
        default=5,
        help="检查间隔（秒）"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="监控持续时间（秒）"
    )

    args = parser.parse_args()

    monitor = RealtimeMonitor(
        esp32_ip=args.ip,
        esp32_port=args.port,
        check_interval=args.interval
    )

    # 注册告警处理器
    monitor.register_alert(default_alert_handler)

    # 启动监控
    monitor.start()

    try:
        print(f"监控运行中...（将在 {args.duration} 秒后停止）")
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\n手动停止监控")
    finally:
        monitor.stop()
        monitor.save_metrics()

        # 打印摘要
        summary = monitor.get_summary()
        print("\n" + "=" * 60)
        print("监控摘要")
        print("=" * 60)
        for key, value in summary.items():
            print(f"{key}: {value}")
        print("=" * 60)


if __name__ == "__main__":
    main()
