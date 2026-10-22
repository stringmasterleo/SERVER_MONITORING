from __future__ import annotations

import argparse
from datetime import datetime, timezone
import sys
import time

from server_monitoring.config import load_config
from server_monitoring.collector import collect_metrics, evaluate_health
from server_monitoring.http_view import start_http_report_server
from server_monitoring.reporting import (
    format_text_report,
    send_email,
    send_webhook,
    to_json,
    write_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect Linux server metrics and send a report."
    )
    parser.add_argument(
        "--config",
        default="./config.toml",
        help="Path to TOML configuration file.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run exactly one iteration and exit (overrides run.loop).",
    )
    return parser


def _run_once(config: dict[str, object]) -> int:
    run_config = config["run"]
    report_config = config["report"]
    thresholds = config["thresholds"]
    delivery = config["delivery"]

    top_process_limit = int(run_config["top_process_limit"])
    report_path = str(report_config["path"])
    include_json_copy = bool(report_config["include_json_copy"])

    cpu_warn = float(thresholds["cpu_warn_threshold"])
    mem_warn = float(thresholds["mem_warn_threshold"])
    disk_warn = float(thresholds["disk_warn_threshold"])

    report = collect_metrics(top_process_limit=top_process_limit)
    warnings = evaluate_health(
        report,
        cpu_warn_threshold=cpu_warn,
        mem_warn_threshold=mem_warn,
        disk_warn_threshold=disk_warn,
    )

    text_report = format_text_report(report, warnings)
    json_report = to_json(report, warnings)

    write_report(
        report_path,
        text_report,
        json_report if include_json_copy else None,
    )

    webhook = delivery["webhook"]
    if bool(webhook["enabled"]) and str(webhook["url"]).strip():
        send_webhook(str(webhook["url"]), json_report)

    email = delivery["email"]
    smtp_host = str(email["smtp_host"]).strip()
    smtp_from = str(email["from_email"]).strip()
    smtp_to = str(email["to_email"]).strip()

    if bool(email["enabled"]) and smtp_host and smtp_from and smtp_to:
        send_email(
            smtp_host=smtp_host,
            smtp_port=int(email["smtp_port"]),
            smtp_user=str(email["smtp_user"]),
            smtp_password=str(email["smtp_password"]),
            smtp_from=smtp_from,
            smtp_to=[smtp_to],
            subject=(
                f"{email['subject_prefix']} {report['hostname']} @ "
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            ),
            text_report=text_report,
            use_starttls=bool(email["use_starttls"]),
        )

    print(text_report)
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    config = load_config(args.config)

    http_config = config["http"]
    loop = bool(config["run"]["loop"])
    if args.once:
        loop = False

    interval_seconds = int(config["run"]["interval_seconds"])

    if loop and interval_seconds <= 0:
        print("run.interval_seconds must be > 0 when run.loop is true.", file=sys.stderr)
        return 2

    if bool(http_config["enabled"]) and not loop and not args.once:
        print("http.enabled requires run.loop=true, unless --once is used.", file=sys.stderr)
        return 2

    if bool(http_config["enabled"]):
        start_http_report_server(http_config=http_config, report_path=str(config["report"]["path"]))
        print(
            f"HTTP report endpoint started at http://{http_config['host']}:{http_config['port']}{http_config['path']}"
        )

    if not loop:
        return _run_once(config)

    while True:
        try:
            _run_once(config)
        except Exception as exc:  # pragma: no cover
            print(f"Monitoring iteration failed: {exc}", file=sys.stderr)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
