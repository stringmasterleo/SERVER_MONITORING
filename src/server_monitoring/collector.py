from __future__ import annotations

from datetime import datetime, timezone
import os
import platform
import socket
import time
from typing import Any

import psutil


def _bytes_to_gb(num_bytes: int) -> float:
    return round(num_bytes / (1024 ** 3), 2)


def _safe_load_average() -> dict[str, float | None]:
    try:
        one, five, fifteen = os.getloadavg()
        return {
            "1m": round(one, 2),
            "5m": round(five, 2),
            "15m": round(fifteen, 2),
        }
    except (AttributeError, OSError):
        return {"1m": None, "5m": None, "15m": None}


def _collect_top_processes(limit: int) -> list[dict[str, Any]]:
    processes = []
    logical_cores = psutil.cpu_count(logical=True) or 1

    for process in psutil.process_iter(["pid", "name", "username", "memory_percent"]):
        try:
            process.cpu_percent(interval=None)
            processes.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(0.2)

    rows = []
    for process in processes:
        try:
            info = process.as_dict(attrs=["pid", "name", "username", "memory_percent"])
            name = info.get("name") or "unknown"
            if int(info.get("pid", -1)) <= 0 or name.lower() == "system idle process":
                continue

            cpu_total = process.cpu_percent(interval=None)
            cpu_normalized = cpu_total / logical_cores
            rows.append(
                {
                    "pid": info.get("pid"),
                    "name": name,
                    "username": info.get("username") or "unknown",
                    "cpu_percent": round(cpu_normalized, 2),
                    "memory_percent": round(float(info.get("memory_percent", 0.0)), 2),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    rows.sort(key=lambda row: (row["cpu_percent"], row["memory_percent"]), reverse=True)
    return rows[: max(limit, 1)]


def collect_metrics(top_process_limit: int = 5) -> dict[str, Any]:
    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
    now = datetime.now(tz=timezone.utc)

    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    cpu_freq = psutil.cpu_freq()
    disk_total = psutil.disk_usage("/")
    net_io = psutil.net_io_counters()
    disk_io = psutil.disk_io_counters()

    report = {
        "timestamp_utc": now.isoformat(),
        "hostname": socket.gethostname(),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
        },
        "uptime": {
            "seconds": int((now - boot_time).total_seconds()),
            "boot_time_utc": boot_time.isoformat(),
        },
        "cpu": {
            "usage_percent": round(psutil.cpu_percent(interval=1.0), 2),
            "logical_cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
            "frequency_mhz": {
                "current": round(cpu_freq.current, 2) if cpu_freq else None,
                "min": round(cpu_freq.min, 2) if cpu_freq else None,
                "max": round(cpu_freq.max, 2) if cpu_freq else None,
            },
            "load_average": _safe_load_average(),
        },
        "memory": {
            "total_gb": _bytes_to_gb(vm.total),
            "available_gb": _bytes_to_gb(vm.available),
            "used_gb": _bytes_to_gb(vm.used),
            "usage_percent": round(vm.percent, 2),
            "swap_total_gb": _bytes_to_gb(swap.total),
            "swap_used_gb": _bytes_to_gb(swap.used),
            "swap_usage_percent": round(swap.percent, 2),
        },
        "disk": {
            "root_total_gb": _bytes_to_gb(disk_total.total),
            "root_used_gb": _bytes_to_gb(disk_total.used),
            "root_free_gb": _bytes_to_gb(disk_total.free),
            "root_usage_percent": round(disk_total.percent, 2),
            "read_bytes_gb": _bytes_to_gb(disk_io.read_bytes) if disk_io else None,
            "write_bytes_gb": _bytes_to_gb(disk_io.write_bytes) if disk_io else None,
            "read_count": disk_io.read_count if disk_io else None,
            "write_count": disk_io.write_count if disk_io else None,
        },
        "network": {
            "bytes_sent_gb": _bytes_to_gb(net_io.bytes_sent) if net_io else None,
            "bytes_recv_gb": _bytes_to_gb(net_io.bytes_recv) if net_io else None,
            "packets_sent": net_io.packets_sent if net_io else None,
            "packets_recv": net_io.packets_recv if net_io else None,
            "errin": net_io.errin if net_io else None,
            "errout": net_io.errout if net_io else None,
            "dropin": net_io.dropin if net_io else None,
            "dropout": net_io.dropout if net_io else None,
        },
        "top_processes": _collect_top_processes(top_process_limit),
    }

    return report


def evaluate_health(
    report: dict[str, Any],
    cpu_warn_threshold: float,
    mem_warn_threshold: float,
    disk_warn_threshold: float,
) -> list[str]:
    warnings = []

    cpu = float(report["cpu"]["usage_percent"])
    mem = float(report["memory"]["usage_percent"])
    disk = float(report["disk"]["root_usage_percent"])

    if cpu >= cpu_warn_threshold:
        warnings.append(
            f"High CPU usage: {cpu}% >= {cpu_warn_threshold}%"
        )
    if mem >= mem_warn_threshold:
        warnings.append(
            f"High memory usage: {mem}% >= {mem_warn_threshold}%"
        )
    if disk >= disk_warn_threshold:
        warnings.append(
            f"High disk usage on /: {disk}% >= {disk_warn_threshold}%"
        )

    return warnings
