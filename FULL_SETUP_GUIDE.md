# Server Monitoring Tool: Full Setup Guide

## 1) Overview

This guide covers complete setup for the SERVER_MONITORING tool in your TWMS/WildFly environment:

- Build Linux-compatible binary via GitHub Actions
- Deploy on Linux host without Python installation
- Auto-start monitor with `twms_jboss restart`
- Expose report via WildFly URL
- Validate runtime behavior
- Troubleshoot common failures

Final working report URLs:

- HTML: `http://10.132.201.47:8180/monitorReport`
- JSON: `http://10.132.201.47:8180/monitorReport/json`

## 2) Prerequisites

On Linux server:

- TWMS/WildFly installed and runnable via `./twms_jboss`
- Access to deployment path:
  - `/home/btprojusr01/apps/server-monitoring`
- WildFly CLI available:
  - `/home/btprojusr01/apps/wildfly-10.1.0.Final/bin/jboss-cli.sh`

On development side:

- GitHub repository: `https://github.com/stringmasterleo/SERVER_MONITORING.git`
- GitHub Actions enabled for builds

## 3) Build Linux Binary (GitHub Actions)

Workflow file:

- `.github/workflows/build-linux-binary.yml`

What it does:

- Uses `manylinux2014` container for broad glibc compatibility
- Builds OpenSSL + shared CPython in container
- Builds one-file executable with PyInstaller
- Publishes tar.gz artifact

Trigger build:

1. Push to `main` (or run workflow manually).
2. Download artifact named `server-monitoring-linux-x86_64`.

## 4) Deploy Binary on Server

Example target layout:

- `/home/btprojusr01/apps/server-monitoring/bin/server-monitoring`
- `/home/btprojusr01/apps/server-monitoring/config.toml`
- `/home/btprojusr01/apps/server-monitoring/logs/`
- `/home/btprojusr01/apps/server-monitoring/reports/`

Deploy steps:

1. Copy binary to `bin/server-monitoring`
2. Make executable:
   - `chmod +x /home/btprojusr01/apps/server-monitoring/bin/server-monitoring`
3. Ensure logs/reports directories exist:
   - `mkdir -p /home/btprojusr01/apps/server-monitoring/logs /home/btprojusr01/apps/server-monitoring/reports`

## 5) Working Config File

Use this working config at:

- `/home/btprojusr01/apps/server-monitoring/config.toml`

```toml
[run]
loop = true
interval_seconds = 300
top_process_limit = 5

[report]
path = "/home/btprojusr01/apps/server-monitoring/reports/latest_report.txt"
include_json_copy = true

[thresholds]
cpu_warn_threshold = 85
mem_warn_threshold = 90
disk_warn_threshold = 90

[delivery.webhook]
enabled = false
url = ""

[delivery.email]
enabled = false
smtp_host = ""
smtp_port = 587
smtp_user = ""
smtp_password = ""
from_email = ""
to_email = ""
use_starttls = true
subject_prefix = "[ServerMonitor]"

[http]
enabled = true
host = "0.0.0.0"
port = 9090
path = "/monitorReport"
```

## 6) Validate Binary + Config Before Integration

Run once manually:

```bash
/home/btprojusr01/apps/server-monitoring/bin/server-monitoring \
  --config /home/btprojusr01/apps/server-monitoring/config.toml \
  --once
```

Expected:

- Prints monitoring report to console
- No TOML parse errors
- No GLIBC-related runtime errors

## 7) TWMS Startup Integration

`start_monitoring.sh` starts monitor and writes PID/logs.
`twms_jboss restart` should:

1. Stop monitor/TWMS
2. Start monitor
3. Start TWMS

Expected status output example:

- `Monitor started with PID ...`
- `running: PID:...`

## 8) WildFly Proxy Setup (Runtime)

Because `serverReport` path conflicted in this environment, use `monitorReport`.

Management port used in this setup:

- `10.132.201.47:10090`

Apply reverse proxy configuration:

```bash
cd /home/btprojusr01/apps/wildfly-10.1.0.Final/bin

./jboss-cli.sh --connect --controller=10.132.201.47:10090 <<'EOF'
/socket-binding-group=standard-sockets/remote-destination-outbound-socket-binding=serverReportProxySocket:add(host=127.0.0.1,port=9090)
/subsystem=undertow/configuration=handler/reverse-proxy=serverReportProxy:add
/subsystem=undertow/configuration=handler/reverse-proxy=serverReportProxy/host=monitor:add(outbound-socket-binding=serverReportProxySocket,scheme=http)
/subsystem=undertow/server=default-server/host=default-host/location="/monitorReport":add(handler=serverReportProxy)
:reload
EOF
```

Set backend path so `/monitorReport/json` forwards correctly:

```bash
./jboss-cli.sh --connect --controller=10.132.201.47:10090 \
  --commands="/subsystem=undertow/configuration=handler/reverse-proxy=serverReportProxy/host=monitor:write-attribute(name=path,value=/monitorReport)"

./jboss-cli.sh --connect --controller=10.132.201.47:10090 --commands=":reload"
```

## 9) Verification Commands

Monitor process:

```bash
ps -ef | grep server-monitoring | grep -v grep
```

Direct monitor endpoints:

```bash
curl -i -sS "http://127.0.0.1:9090/monitorReport" | head -n 20
curl -i -sS "http://127.0.0.1:9090/monitorReport/json" | head -n 20
```

WildFly proxied endpoints:

```bash
curl -i -sS "http://10.132.201.47:8180/monitorReport" | head -n 25
curl -i -sS "http://10.132.201.47:8180/monitorReport/json" | head -n 25
```

Expected:

- Both return `200 OK`
- HTML on `/monitorReport`
- JSON on `/monitorReport/json`

## 10) Operations

Normal operation:

- Use `./twms_jboss restart` for restart cycles
- No need to re-run CLI setup commands unless config is reset

Freshness behavior:

- Page auto-refreshes every 30s
- Data refresh cadence follows `run.interval_seconds` (currently 300 seconds)

## 11) Troubleshooting

### A) `GLIBC_2.35 not found`

Cause:

- Old incompatible binary artifact deployed

Fix:

- Replace binary with latest manylinux-built artifact
- Verify symbols:

```bash
strings /home/btprojusr01/apps/server-monitoring/bin/server-monitoring | grep -o 'GLIBC_[0-9.]*' | sort -Vu | tail -n 5
ldd --version | head -n 1
```

### B) `tomllib.TOMLDecodeError`

Cause:

- Corrupt `config.toml`

Fix:

- Restore a valid TOML file (section 5)

### C) CLI `Connection refused` on `localhost:9990`

Cause:

- Management interface is not on default port

Fix:

- Use active controller from this environment: `10.132.201.47:10090`

### D) 500 on proxied URL

Cause:

- Proxy handler/path mismatch

Fix:

- Set reverse-proxy host `path=/monitorReport`
- Reload WildFly

### E) Direct shell URL command error (`No such file or directory`)

Cause:

- URL typed directly in shell

Fix:

- Use `curl "http://..."` or open URL in browser

## 12) Backup Recommendations

Keep backups of:

- `twms_jboss`
- `/home/btprojusr01/apps/server-monitoring/config.toml`
- WildFly active config (`standalone.xml`)

## 13) Quick Runbook

1. Update binary + config
2. `./twms_jboss restart`
3. Validate process + endpoints
4. Open browser URL:
   - `http://10.132.201.47:8180/monitorReport`

If endpoint fails:

1. Check monitor logs:
   - `tail -n 100 /home/btprojusr01/apps/server-monitoring/logs/monitor.out`
2. Check WildFly logs:
   - `tail -n 150 /home/btprojusr01/apps/wildfly-10.1.0.Final/standalone/log/server.log`
3. Re-validate direct backend:
   - `curl -i -sS "http://127.0.0.1:9090/monitorReport" | head -n 20`
