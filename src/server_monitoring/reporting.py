from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import smtplib
from typing import Any
from email.message import EmailMessage

from urllib import request


def format_text_report(report: dict[str, Any], warnings: list[str]) -> str:
    lines = []
    lines.append("Server Monitoring Report")
    lines.append("=" * 60)
    lines.append(f"Generated (UTC): {report['timestamp_utc']}")
    lines.append(f"Hostname: {report['hostname']}")
    lines.append(
        f"OS: {report['os']['system']} {report['os']['release']} ({report['os']['machine']})"
    )
    lines.append(f"Python: {report['os']['python_version']}")
    lines.append(f"Uptime (seconds): {report['uptime']['seconds']}")
    lines.append("")

    lines.append("CPU")
    lines.append("-" * 60)
    lines.append(f"Usage: {report['cpu']['usage_percent']}%")
    lines.append(
        f"Cores: logical={report['cpu']['logical_cores']}, physical={report['cpu']['physical_cores']}"
    )
    lines.append(f"Load average (1m/5m/15m): {report['cpu']['load_average']}")
    lines.append("")

    lines.append("Memory")
    lines.append("-" * 60)
    lines.append(f"Total: {report['memory']['total_gb']} GB")
    lines.append(f"Used: {report['memory']['used_gb']} GB ({report['memory']['usage_percent']}%)")
    lines.append(f"Available: {report['memory']['available_gb']} GB")
    lines.append(
        f"Swap: {report['memory']['swap_used_gb']} / {report['memory']['swap_total_gb']} GB ({report['memory']['swap_usage_percent']}%)"
    )
    lines.append("")

    lines.append("Disk")
    lines.append("-" * 60)
    lines.append(
        f"/: {report['disk']['root_used_gb']} / {report['disk']['root_total_gb']} GB ({report['disk']['root_usage_percent']}%)"
    )
    lines.append("")

    lines.append("Network")
    lines.append("-" * 60)
    lines.append(
        f"Sent/Recv: {report['network']['bytes_sent_gb']} GB / {report['network']['bytes_recv_gb']} GB"
    )
    lines.append("")

    lines.append("Top Processes (CPU/Memory)")
    lines.append("-" * 60)
    for process in report["top_processes"]:
        lines.append(
            f"PID {process['pid']:<7} CPU {process['cpu_percent']:<6}% MEM {process['memory_percent']:<6}% NAME {process['name']}"
        )
    lines.append("")

    lines.append("Warnings")
    lines.append("-" * 60)
    if warnings:
        lines.extend(f"- {item}" for item in warnings)
    else:
        lines.append("No threshold warnings.")

    return "\n".join(lines)


def to_json(report: dict[str, Any], warnings: list[str]) -> str:
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "warnings": warnings,
        "metrics": report,
    }
    return json.dumps(payload, indent=2)


def write_report(path: str, text_report: str, json_report: str | None = None) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text_report, encoding="utf-8")

    if json_report:
        json_path = output.with_suffix(".json")
        json_path.write_text(json_report, encoding="utf-8")


def send_webhook(webhook_url: str, json_report: str, timeout_seconds: int = 15) -> None:
    req = request.Request(
        webhook_url,
        data=json_report.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(req, timeout=timeout_seconds):
        pass


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_from: str,
    smtp_to: list[str],
    subject: str,
    text_report: str,
    use_starttls: bool = True,
) -> None:
    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = ", ".join(smtp_to)
    msg["Subject"] = subject
    msg.set_content(text_report)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as client:
        if use_starttls:
            client.starttls()
        if smtp_user:
            client.login(smtp_user, smtp_password)
        client.send_message(msg)
