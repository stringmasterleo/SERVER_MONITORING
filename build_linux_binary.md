# Build Standalone Linux Binary (No Python on Server)

Build on a Linux machine that is close to target server OS.

```bash
cd /path/to/server-monitoring
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
PYTHONPATH=src pyinstaller --onefile --name server-monitoring src/server_monitoring/__main__.py
```

Output binary:

- `dist/server-monitoring`

Copy it to target server path:

- `/opt/server-monitoring/bin/server-monitoring`

Then use:

- `deploy/systemd/server-monitor-binary.service`
- `deploy/systemd/server-monitor-binary.timer`
