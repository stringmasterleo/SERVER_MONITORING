#!/usr/bin/env bash
set -euo pipefail

# Patches twms_jboss to include monitor start/stop hooks when missing.
# Safe to run multiple times (idempotent).

MONITOR_HOME="${MONITOR_HOME:-/home/btprojusr01/apps/server-monitoring}"
WILDFLY_HOME="${WILDFLY_HOME:-/home/btprojusr01/apps/wildfly-10.1.0.Final}"
TWMS_SCRIPT="${TWMS_SCRIPT:-$WILDFLY_HOME/bin/twms_jboss}"

START_HOOK="\"$MONITOR_HOME/start_monitoring.sh\""
STOP_HOOK="\"$MONITOR_HOME/stop_monitoring.sh\""

if [ ! -f "$TWMS_SCRIPT" ]; then
  echo "[error] twms_jboss not found: $TWMS_SCRIPT" >&2
  exit 1
fi

if [ ! -w "$TWMS_SCRIPT" ]; then
  echo "[error] twms_jboss is not writable: $TWMS_SCRIPT" >&2
  exit 1
fi

backup="$TWMS_SCRIPT.bak.$(date +%Y%m%d_%H%M%S)"
cp "$TWMS_SCRIPT" "$backup"
echo "[info] Backup created: $backup"

has_start=0
has_stop=0

if grep -q "start_monitoring.sh" "$TWMS_SCRIPT"; then
  has_start=1
fi
if grep -q "stop_monitoring.sh" "$TWMS_SCRIPT"; then
  has_stop=1
fi

if [ "$has_start" -eq 1 ] && [ "$has_stop" -eq 1 ]; then
  echo "[info] Hooks already exist. No changes made."
  exit 0
fi

tmp_file="$(mktemp)"

awk -v has_start="$has_start" -v has_stop="$has_stop" -v start_hook="$START_HOOK" -v stop_hook="$STOP_HOOK" '
BEGIN {
  inserted_start = (has_start == 1)
  inserted_stop = (has_stop == 1)
}
{
  if (!inserted_stop && $0 ~ /Stopping TWMS Application/) {
    print "# server-monitoring stop hook"
    print stop_hook
    inserted_stop = 1
  }

  if (!inserted_start && $0 ~ /Starting TWMS Application/) {
    print "# server-monitoring start hook"
    print start_hook
    inserted_start = 1
  }

  print $0
}
END {
  if (!inserted_stop) {
    print ""
    print "# server-monitoring stop hook (appended)"
    print stop_hook
  }
  if (!inserted_start) {
    print ""
    print "# server-monitoring start hook (appended)"
    print start_hook
  }
}
' "$TWMS_SCRIPT" > "$tmp_file"

mv "$tmp_file" "$TWMS_SCRIPT"
chmod +x "$TWMS_SCRIPT"

echo "[ok] twms_jboss patched: $TWMS_SCRIPT"
echo "[next] Verify with: grep -n 'monitoring.*hook\|start_monitoring.sh\|stop_monitoring.sh' \"$TWMS_SCRIPT\""
