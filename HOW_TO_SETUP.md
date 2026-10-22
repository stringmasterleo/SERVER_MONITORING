# How To Setup On A New Server (Ordered Commands)

This is the exact sequence to run on a fresh Linux server.

## 1) Define Environment Variables

```bash
MONITOR_HOME=/home/btprojusr01/apps/server-monitoring
WILDFLY_HOME=/home/btprojusr01/apps/wildfly-10.1.0.Final
SERVER_IP=10.132.201.47
MGMT_PORT=10090
APP_PORT=8180
MONITOR_PORT=9090
MONITOR_PATH=/monitorReport
```

## 2) Create Folders

```bash
mkdir -p "$MONITOR_HOME/bin" "$MONITOR_HOME/logs" "$MONITOR_HOME/reports"
```

## 3) Copy Required Files To Server

Copy these files into your server deployment folder:

- `server-monitoring` binary -> `$MONITOR_HOME/bin/server-monitoring`
- `bootstrap_new_server.sh` -> preferred one-shot setup runner
- `patch_twms_hooks.sh` -> hook patcher for `twms_jboss`

## 4) Add Execute Permission (Required)

```bash
chmod +x "$MONITOR_HOME/bin/server-monitoring"
chmod +x ./bootstrap_new_server.sh
chmod +x ./patch_twms_hooks.sh
chmod +x "$WILDFLY_HOME/bin/twms_jboss"
chmod +x "$WILDFLY_HOME/bin/jboss-cli.sh"
```

## 5) Run One-Shot Setup Script

edit and Run from folder where `bootstrap_new_server.sh` is present:

```bash
MONITOR_HOME="$MONITOR_HOME" \
WILDFLY_HOME="$WILDFLY_HOME" \
SERVER_IP="$SERVER_IP" \
MGMT_PORT="$MGMT_PORT" \
APP_PORT="$APP_PORT" \
MONITOR_PORT="$MONITOR_PORT" \
MONITOR_PATH="$MONITOR_PATH" \
./bootstrap_new_server.sh
```

What it does:

- Writes `config.toml`
- Writes start/stop monitoring scripts
- Runs binary smoke test
- Configures WildFly reverse proxy
- Reloads WildFly config
- Restarts TWMS stack
- Prints verification outputs

## 6) Patch twms_jboss Hooks (If Missing)

Run this if monitor start/stop is not already integrated in `twms_jboss`:

```bash
MONITOR_HOME="$MONITOR_HOME" WILDFLY_HOME="$WILDFLY_HOME" ./patch_twms_hooks.sh
```

Verify hook lines:

```bash
grep -n 'start_monitoring.sh\|stop_monitoring.sh' "$WILDFLY_HOME/bin/twms_jboss"
```

## 7) Restart Application Stack

```bash
cd "$WILDFLY_HOME/bin"
./twms_jboss restart
sleep 8
./twms_jboss status
```

## 8) Verify Process + Endpoints

```bash
ps -ef | grep server-monitoring | grep -v grep

curl -i -sS "http://127.0.0.1:${MONITOR_PORT}${MONITOR_PATH}" | head -n 20
curl -i -sS "http://127.0.0.1:${MONITOR_PORT}${MONITOR_PATH}/json" | head -n 20

curl -i -sS "http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}" | head -n 25
curl -i -sS "http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}/json" | head -n 25
```

Expected:

- HTTP `200 OK` on all monitor endpoints
- HTML on `${MONITOR_PATH}`
- JSON on `${MONITOR_PATH}/json`

## 9) Final URLs

- HTML: `http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}`
- JSON: `http://${SERVER_IP}:${APP_PORT}${MONITOR_PATH}/json`

## 10) Daily Use Commands

```bash
cd "$WILDFLY_HOME/bin"
./twms_jboss status
./twms_jboss restart
```

## 11) Troubleshooting Commands

```bash
tail -n 120 "$MONITOR_HOME/logs/monitor.out"
tail -n 200 "$WILDFLY_HOME/standalone/log/server.log"
```

If old errors clutter logs:

```bash
: > "$MONITOR_HOME/logs/monitor.out"
```
