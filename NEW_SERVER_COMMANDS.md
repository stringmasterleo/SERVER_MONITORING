# New Server Setup: Exact Commands

Use this on a fresh Linux server to set up the monitoring binary with TWMS/WildFly integration.

For strict step-by-step execution order, use `HOW_TO_SETUP.md` first.

## 0) Set Variables

Run this first and adjust values for your server.

```bash
MONITOR_HOME=/home/btprojusr01/apps/server-monitoring
WILDFLY_HOME=/home/btprojusr01/apps/wildfly-10.1.0.Final
SERVER_IP=10.132.201.47
MGMT_PORT=10090
APP_PORT=8180
MONITOR_PORT=9090
MONITOR_PATH=/monitorReport

mkdir -p "$MONITOR_HOME"/bin "$MONITOR_HOME"/logs "$MONITOR_HOME"/reports
```

## 1) Copy Binary

Copy the built Linux binary to:

- $MONITOR_HOME/bin/server-monitoring

Then run:

```bash
chmod +x "$MONITOR_HOME/bin/server-monitoring"
```

## 2) Create Config

```bash
cat > "$MONITOR_HOME/config.toml" <<'EOF'
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
EOF
```

## 3) Create Start Script

```bash
cat > "$MONITOR_HOME/start_monitoring.sh" <<'EOF'
#!/bin/sh
APP_HOME=/home/btprojusr01/apps/server-monitoring
PID_FILE=$APP_HOME/monitor.pid
LOG_FILE=$APP_HOME/logs/monitor.out
BIN_FILE=$APP_HOME/bin/server-monitoring
CONFIG_FILE=$APP_HOME/config.toml

mkdir -p "$APP_HOME/logs" "$APP_HOME/reports"

if [ ! -x "$BIN_FILE" ]; then
  echo "Monitor binary is missing or not executable: $BIN_FILE"
  exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Monitor config file not found: $CONFIG_FILE"
  exit 1
fi

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Monitor already running with PID $(cat "$PID_FILE")"
  exit 0
fi

nohup "$BIN_FILE" --config "$CONFIG_FILE" >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 2

if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Monitor failed to stay up. Check log: $LOG_FILE"
  tail -n 80 "$LOG_FILE" 2>/dev/null || true
  rm -f "$PID_FILE"
  exit 1
fi

echo "Monitor started with PID $(cat "$PID_FILE")"
EOF

chmod +x "$MONITOR_HOME/start_monitoring.sh"
```

## 4) Create Stop Script

```bash
cat > "$MONITOR_HOME/stop_monitoring.sh" <<'EOF'
#!/bin/sh
APP_HOME=/home/btprojusr01/apps/server-monitoring
PID_FILE=$APP_HOME/monitor.pid

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    sleep 2
    kill -9 "$PID" 2>/dev/null || true
    echo "Monitor stopped (PID $PID)"
  else
    echo "PID file found but process not running"
  fi
  rm -f "$PID_FILE"
else
  pkill -f "$APP_HOME/bin/server-monitoring" && echo "Monitor was not tracked by PID file, sent pkill fallback" || echo "Monitor not running"
fi
EOF

chmod +x "$MONITOR_HOME/stop_monitoring.sh"
```

## 5) Quick Binary Sanity Check

```bash
"$MONITOR_HOME/bin/server-monitoring" --config "$MONITOR_HOME/config.toml" --once
curl -i -sS "http://127.0.0.1:${MONITOR_PORT}${MONITOR_PATH}" | head -n 20
curl -i -sS "http://127.0.0.1:${MONITOR_PORT}${MONITOR_PATH}/json" | head -n 20
```

## 6) Hook Into twms_jboss

Edit your twms_jboss file and add:

- Before starting TWMS: `$MONITOR_HOME/start_monitoring.sh`
- During stop flow: `$MONITOR_HOME/stop_monitoring.sh`

If your twms_jboss already has this hook, skip this step.

Automated option (recommended):

```bash
chmod +x ./patch_twms_hooks.sh
MONITOR_HOME="$MONITOR_HOME" WILDFLY_HOME="$WILDFLY_HOME" ./patch_twms_hooks.sh
```

Verify hooks:

```bash
grep -n 'start_monitoring.sh\|stop_monitoring.sh' "$WILDFLY_HOME/bin/twms_jboss"
```

## 7) Configure WildFly Reverse Proxy (one-time)

```bash
cd "$WILDFLY_HOME/bin"

./jboss-cli.sh --connect --controller=${SERVER_IP}:${MGMT_PORT} <<EOF
/socket-binding-group=standard-sockets/remote-destination-outbound-socket-binding=serverReportProxySocket:add(host=127.0.0.1,port=${MONITOR_PORT})
/subsystem=undertow/configuration=handler/reverse-proxy=serverReportProxy:add
/subsystem=undertow/configuration=handler/reverse-proxy=serverReportProxy/host=monitor:add(outbound-socket-binding=serverReportProxySocket,scheme=http)
/subsystem=undertow/server=default-server/host=default-host/location="${MONITOR_PATH}":add(handler=serverReportProxy)
/subsystem=undertow/configuration=handler/reverse-proxy=serverReportProxy/host=monitor:write-attribute(name=path,value=${MONITOR_PATH})
:reload
EOF
```

If you get already-exists errors, keep going. They are harmless for repeat runs.

## 8) Restart Full Stack

```bash
cd "$WILDFLY_HOME/bin"
./twms_jboss restart
sleep 8
```

## 9) Validate Final URLs

```bash
ps -ef | grep server-monitoring | grep -v grep
curl -i -sS "http://127.0.0.1:${MONITOR_PORT}${MONITOR_PATH}" | head -n 20
curl -i -sS "http://127.0.0.1:${MONITOR_PORT}${MONITOR_PATH}/json" | head -n 20
curl -i -sS "http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}" | head -n 25
curl -i -sS "http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}/json" | head -n 25
```

Expected:

- All four curls return HTTP 200
- Browser URL works:
  - http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}

## 10) Daily Operations

```bash
cd "$WILDFLY_HOME/bin"
./twms_jboss restart
./twms_jboss status
```

No need to rerun CLI proxy commands every restart.

## 11) Log Commands

```bash
tail -n 100 "$MONITOR_HOME/logs/monitor.out"
tail -n 150 "$WILDFLY_HOME/standalone/log/server.log"
```

## 12) Recovery Commands

Clear old monitor logs:

```bash
: > "$MONITOR_HOME/logs/monitor.out"
```

Check glibc compatibility:

```bash
strings "$MONITOR_HOME/bin/server-monitoring" | grep -o 'GLIBC_[0-9.]*' | sort -Vu | tail -n 5
ldd --version | head -n 1
```
