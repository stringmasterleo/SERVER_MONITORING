# Server Monitoring Tool

This project collects Linux server metrics and sends a report every hour.

## What it monitors

- CPU usage (%), core count, frequency, load average
- Memory usage: used, available, total memory and swap
- Disk usage on `/` and disk I/O counters
- Network I/O counters (sent/received/packet/error/drop)
- Uptime and host/OS details
- Top processes by CPU and memory
- Threshold-based warnings for CPU, memory, and disk usage

## 1) Start with venv (local development)

From project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Windows (for local development):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 2) Configure everything from one file

Copy `config.toml.example` to `config.toml`:

```bash
cp config.toml.example config.toml
```

Important settings in `config.toml`:

- `delivery.email.to_email` specific recipient email ID
- `delivery.email.enabled` set `true` to send mail
- `delivery.email.smtp_*` SMTP server credentials
- `report.path` local report path
- `thresholds.*` warning thresholds
- `run.interval_seconds` hourly schedule interval (3600 by default)
- `http.enabled` enable browser report view
- `http.host`, `http.port`, `http.path` HTTP endpoint settings

## 3) Run once

```bash
PYTHONPATH=src python -m server_monitoring --config ./config.toml
```

## 4) Run in loop mode from config

```bash
PYTHONPATH=src python -m server_monitoring --config ./config.toml
```

`run.loop=true` and `run.interval_seconds=3600` will run every hour.

Run exactly one iteration (useful for cron/timer testing):

```bash
PYTHONPATH=src python -m server_monitoring --config ./config.toml --once
```

## 5) Linux deployment path A: server has Python

1. Copy project to `/opt/server-monitoring`.
2. Create service user:

```bash
sudo useradd -r -s /usr/sbin/nologin monitor || true
```

3. Prepare directories and permissions:

```bash
sudo mkdir -p /var/log/server-monitoring
sudo chown -R monitor:monitor /var/log/server-monitoring /opt/server-monitoring
```

4. Setup venv and dependencies:

```bash
cd /opt/server-monitoring
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

5. Create `/opt/server-monitoring/config.toml` from example and set SMTP/email values.
6. Install systemd unit/timer:

```bash
sudo cp deploy/systemd/server-monitor.service /etc/systemd/system/
sudo cp deploy/systemd/server-monitor.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now server-monitor.timer
```

## 6) Linux deployment path B: server has NO Python (no Docker required)

You can still deploy this by shipping a standalone Linux binary.

1. Build binary on a Linux machine similar to target server (same CPU family and close distro/glibc):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
PYTHONPATH=src pyinstaller --onefile --name server-monitoring src/server_monitoring/__main__.py
```

Binary output will be at `dist/server-monitoring`.

2. Copy these to target server:
- `dist/server-monitoring` to `/opt/server-monitoring/bin/server-monitoring`
- `config.toml` to `/opt/server-monitoring/config.toml`
- systemd files from `deploy/systemd/server-monitor-binary.*`

3. On target server:

```bash
sudo useradd -r -s /usr/sbin/nologin monitor || true
sudo mkdir -p /opt/server-monitoring/bin /var/log/server-monitoring
sudo chown -R monitor:monitor /opt/server-monitoring /var/log/server-monitoring
sudo chmod +x /opt/server-monitoring/bin/server-monitoring

sudo cp deploy/systemd/server-monitor-binary.service /etc/systemd/system/
sudo cp deploy/systemd/server-monitor-binary.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now server-monitor-binary.timer
```

## 7) Verify on Linux

```bash
systemctl status server-monitor.timer
systemctl status server-monitor-binary.timer
systemctl list-timers --all | grep server-monitor
journalctl -u server-monitor.service -n 100 --no-pager
journalctl -u server-monitor-binary.service -n 100 --no-pager
```

## Browser view for QA (no SMTP required)

Enable this in `config.toml`:

```toml
[http]
enabled = true
host = "0.0.0.0"
port = 9090
path = "/serverReport"
```

Then open:

```text
http://<server-ip>:9090/serverReport
```

JSON view is also available at:

```text
http://<server-ip>:9090/serverReport/json
```

Important: if WildFly is already using `:8180`, this monitor cannot bind to the same port directly.
To use `http://10.132.201.47:8180/serverReport`, configure WildFly (or another reverse proxy) to forward `/serverReport` to this monitor endpoint on `:9090`.

## 8) Start monitor automatically with WildFly (your use case)

Yes, this is supported. In this mode:

- WildFly start triggers monitor start
- WildFly stop triggers monitor stop
- Report frequency comes from `config.toml` (`run.interval_seconds`)
- Browser endpoint remains available while monitor service is running

Use one of these options (do not enable timer at the same time):

### Option A: WildFly + Python runtime

```bash
sudo cp deploy/systemd/server-monitor-wildfly.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable server-monitor-wildfly.service
sudo systemctl restart wildfly.service
```

### Option B: WildFly + standalone binary (no Python on server)

```bash
sudo cp deploy/systemd/server-monitor-binary-wildfly.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable server-monitor-binary-wildfly.service
sudo systemctl restart wildfly.service
```

Check linkage and logs:

```bash
systemctl status wildfly.service
systemctl status server-monitor-wildfly.service
systemctl status server-monitor-binary-wildfly.service
journalctl -u server-monitor-wildfly.service -n 100 --no-pager
journalctl -u server-monitor-binary-wildfly.service -n 100 --no-pager
```

If your WildFly unit name is not `wildfly.service`, replace that name in the service file before enabling.

## Notes

- If email is enabled, report is sent to exactly one recipient: `delivery.email.to_email`.
- If email/webhook are disabled, the tool still writes local reports.
- Do not enable both timer-based and WildFly-coupled units simultaneously.

## Build Linux binary with GitHub Actions (no WSL needed)

This repository includes workflow `Build Linux Binary`:

- Workflow file: `.github/workflows/build-linux-binary.yml`
- Runner: `ubuntu-22.04`
- Output artifact: `server-monitoring-linux-x86_64`

How to run:

1. Push this repository to GitHub.
2. Open GitHub repo -> Actions -> **Build Linux Binary**.
3. Click **Run workflow**.
4. Download artifact `server-monitoring-linux-x86_64`.

Artifact contents:

- `bin/server-monitoring` (standalone Linux binary)
- `config.toml` (from example)
- `deploy/systemd/server-monitor-binary-wildfly.service`
- `deploy/systemd/server-monitor-binary.service`
- `deploy/systemd/server-monitor-binary.timer`
- `README.md`

Deploy from artifact to QA server:

```bash
sudo useradd -r -s /usr/sbin/nologin monitor || true
sudo mkdir -p /opt/server-monitoring/bin /opt/server-monitoring/reports /var/log/server-monitoring
sudo chown -R monitor:monitor /opt/server-monitoring /var/log/server-monitoring

sudo cp bin/server-monitoring /opt/server-monitoring/bin/server-monitoring
sudo chmod +x /opt/server-monitoring/bin/server-monitoring
sudo cp config.toml /opt/server-monitoring/config.toml
sudo cp deploy/systemd/server-monitor-binary-wildfly.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable server-monitor-binary-wildfly.service
sudo systemctl restart wildfly.service
```
