#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./bootstrap_new_server.sh
#   MONITOR_HOME=/custom/path ./bootstrap_new_server.sh
#
# Optional environment overrides:
#   MONITOR_HOME, WILDFLY_HOME, SERVER_IP, MGMT_PORT, APP_PORT, MONITOR_PORT, MONITOR_PATH

MONITOR_HOME="${MONITOR_HOME:-/home/btprojusr01/apps/server-monitoring}"
WILDFLY_HOME="${WILDFLY_HOME:-/home/btprojusr01/apps/wildfly-10.1.0.Final}"
SERVER_IP="${SERVER_IP:-10.132.201.47}"
MGMT_PORT="${MGMT_PORT:-10090}"
APP_PORT="${APP_PORT:-8180}"
MONITOR_PORT="${MONITOR_PORT:-9090}"
MONITOR_PATH="${MONITOR_PATH:-/monitorReport}"

BIN_FILE="$MONITOR_HOME/bin/server-monitoring"
CONFIG_FILE="$MONITOR_HOME/config.toml"
START_SCRIPT="$MONITOR_HOME/start_monitoring.sh"
STOP_SCRIPT="$MONITOR_HOME/stop_monitoring.sh"
TWMS_SCRIPT="$WILDFLY_HOME/bin/twms_jboss"
CLI="$WILDFLY_HOME/bin/jboss-cli.sh"

log() {
  printf '[setup] %s\n' "$*"
}

warn() {
  printf '[warn] %s\n' "$*"
}

need_file() {
  if [ ! -f "$1" ]; then
    printf '[error] Missing file: %s\n' "$1" >&2
    exit 1
  fi
}

need_exec() {
  if [ ! -x "$1" ]; then
    printf '[error] Missing executable: %s\n' "$1" >&2
    exit 1
  fi
}

run_cli() {
  "$CLI" --connect --controller="${SERVER_IP}:${MGMT_PORT}" --commands="$1"
}

safe_add_cli() {
  set +e
  local out
  out=$(run_cli "$1" 2>&1)
  local rc=$?
  set -e
  if [ $rc -ne 0 ]; then
    if printf '%s' "$out" | grep -qi 'already exists'; then
      log "Already exists: $1"
      return 0
    fi
    printf '%s\n' "$out" >&2
    return $rc
  fi
  printf '%s\n' "$out"
}

log "Validating required paths"
need_file "$BIN_FILE"
need_exec "$CLI"
need_exec "$TWMS_SCRIPT"

log "Creating monitor directories"
mkdir -p "$MONITOR_HOME/bin" "$MONITOR_HOME/logs" "$MONITOR_HOME/reports"
chmod +x "$BIN_FILE"

log "Writing monitor config"
cat > "$CONFIG_FILE" <<EOF
[run]
loop = true
interval_seconds = 300
top_process_limit = 5

[report]
path = "${MONITOR_HOME}/reports/latest_report.txt"
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
port = ${MONITOR_PORT}
path = "${MONITOR_PATH}"
EOF

log "Writing start script"
cat > "$START_SCRIPT" <<'EOF'
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
chmod +x "$START_SCRIPT"

log "Writing stop script"
cat > "$STOP_SCRIPT" <<'EOF'
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
chmod +x "$STOP_SCRIPT"

log "Running one-time binary smoke test"
"$BIN_FILE" --config "$CONFIG_FILE" --once >/tmp/server-monitor-once.out 2>&1 || {
  cat /tmp/server-monitor-once.out >&2
  exit 1
}

log "Checking direct monitor endpoint"
if ! curl -fsS "http://127.0.0.1:${MONITOR_PORT}${MONITOR_PATH}" >/dev/null; then
  warn "Direct endpoint not responding yet. This can happen if monitor is not running continuously."
fi

log "Configuring WildFly reverse proxy"
safe_add_cli "/socket-binding-group=standard-sockets/remote-destination-outbound-socket-binding=serverReportProxySocket:add(host=127.0.0.1,port=${MONITOR_PORT})"
safe_add_cli "/subsystem=undertow/configuration=handler/reverse-proxy=serverReportProxy:add"
safe_add_cli "/subsystem=undertow/configuration=handler/reverse-proxy=serverReportProxy/host=monitor:add(outbound-socket-binding=serverReportProxySocket,scheme=http)"
safe_add_cli "/subsystem=undertow/server=default-server/host=default-host/location=\"${MONITOR_PATH}\":add(handler=serverReportProxy)"
run_cli "/subsystem=undertow/configuration=handler/reverse-proxy=serverReportProxy/host=monitor:write-attribute(name=path,value=${MONITOR_PATH})"
run_cli ":reload"

log "Restarting TWMS stack"
"$TWMS_SCRIPT" restart
sleep 8

log "Verifying processes"
ps -ef | grep server-monitoring | grep -v grep || true

log "Verifying endpoints"
set +e
curl -i -sS "http://127.0.0.1:${MONITOR_PORT}${MONITOR_PATH}" | head -n 15
curl -i -sS "http://127.0.0.1:${MONITOR_PORT}${MONITOR_PATH}/json" | head -n 15
curl -i -sS "http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}" | head -n 20
curl -i -sS "http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}/json" | head -n 20
set -e

log "Setup complete"
log "Primary URL: http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}"
log "JSON URL:    http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}/json"

cat <<'EOF'

NOTE:
- This script assumes twms_jboss already starts/stops monitor hooks.
- If hooks are missing in twms_jboss, add calls to:
  /home/btprojusr01/apps/server-monitoring/start_monitoring.sh
  /home/btprojusr01/apps/server-monitoring/stop_monitoring.sh
EOF
