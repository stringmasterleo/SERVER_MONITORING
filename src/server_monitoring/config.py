from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


DEFAULT_CONFIG: dict[str, Any] = {
    "run": {
        "loop": True,
        "interval_seconds": 3600,
        "top_process_limit": 5,
    },
    "report": {
        "path": "./reports/latest_report.txt",
        "include_json_copy": True,
    },
    "thresholds": {
        "cpu_warn_threshold": 85,
        "mem_warn_threshold": 90,
        "disk_warn_threshold": 90,
    },
    "delivery": {
        "webhook": {
            "enabled": False,
            "url": "",
        },
        "email": {
            "enabled": False,
            "smtp_host": "",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_password": "",
            "from_email": "",
            "to_email": "",
            "use_starttls": True,
            "subject_prefix": "[ServerMonitor]",
        },
    },
    "http": {
        "enabled": False,
        "host": "0.0.0.0",
        "port": 9090,
        "path": "/serverReport",
    },
}


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: str) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. Copy config.toml.example to config.toml and update values."
        )

    loaded = tomllib.loads(path.read_text(encoding="utf-8"))
    config = _merge_dict(DEFAULT_CONFIG, loaded)

    interval = int(config["run"]["interval_seconds"])
    if interval <= 0:
        raise ValueError("run.interval_seconds must be > 0")

    top_limit = int(config["run"]["top_process_limit"])
    if top_limit <= 0:
        raise ValueError("run.top_process_limit must be > 0")

    smtp_port = int(config["delivery"]["email"]["smtp_port"])
    if smtp_port <= 0:
        raise ValueError("delivery.email.smtp_port must be > 0")

    http_port = int(config["http"]["port"])
    if http_port <= 0 or http_port > 65535:
        raise ValueError("http.port must be between 1 and 65535")

    http_path = str(config["http"]["path"]).strip()
    if not http_path:
        raise ValueError("http.path must not be empty")
    if not http_path.startswith("/"):
        http_path = "/" + http_path
    config["http"]["path"] = http_path

    return config
