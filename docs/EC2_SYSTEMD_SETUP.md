# EC2 Systemd Setup - Run Both Servers Automatically

This guide sets up both the MCP server and Slack bot to run automatically on EC2.

## Quick Setup

### Step 1: Create Systemd Service Files

SSH into your EC2 instance and create the service files:

```bash
# SSH into EC2
ssh -i "C:\Users\Avyukt\Downloads\continuum-kp.pem" \
    ubuntu@ec2-3-108-63-43.ap-south-1.compute.amazonaws.com

# Navigate to project
cd ~/continuum.ai
```

### Step 2: Create MCP Server Service

```bash
sudo nano /etc/systemd/system/continuum-mcp.service
```

Paste this content:

```ini
[Unit]
Description=continuum.ai MCP Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/continuum.ai
Environment="PATH=/home/ubuntu/continuum.ai/.venv/bin:/usr/bin:/usr/local/bin"
EnvironmentFile=/home/ubuntu/continuum.ai/.env
ExecStart=/home/ubuntu/continuum.ai/.venv/bin/python -m app.server --transport http --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Note:** This uses the Python from `.venv`. If your virtual environment is in a different location, update the path accordingly.

### Step 3: Create Slack Bot Service

```bash
sudo nano /etc/systemd/system/continuum-slack-bot.service
```

Paste this content:

```ini
[Unit]
Description=continuum.ai Slack Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/continuum.ai
Environment="PATH=/home/ubuntu/continuum.ai/.venv/bin:/usr/bin:/usr/local/bin"
EnvironmentFile=/home/ubuntu/continuum.ai/.env
ExecStart=/home/ubuntu/continuum.ai/.venv/bin/python -m uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Note:** This uses the Python from `.venv`. If your virtual environment is in a different location, update the path accordingly.

### Step 4: Reload systemd and Enable Services

```bash
# Reload systemd to recognize new services
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable continuum-mcp
sudo systemctl enable continuum-slack-bot

# Start both services
sudo systemctl start continuum-mcp
sudo systemctl start continuum-slack-bot
```

### Step 5: Verify Services Are Running

```bash
# Check status of both services
sudo systemctl status continuum-mcp
sudo systemctl status continuum-slack-bot

# Or check both at once
sudo systemctl status continuum-mcp continuum-slack-bot
```

You should see `active (running)` for both.

---

## Managing Services

### Start Services

```bash
sudo systemctl start continuum-mcp
sudo systemctl start continuum-slack-bot
```

### Stop Services

```bash
sudo systemctl stop continuum-mcp
sudo systemctl stop continuum-slack-bot
```

### Restart Services

```bash
sudo systemctl restart continuum-mcp
sudo systemctl restart continuum-slack-bot
```

### View Logs

```bash
# MCP Server logs
sudo journalctl -u continuum-mcp -f

# Slack Bot logs
sudo journalctl -u continuum-slack-bot -f

# Both logs
sudo journalctl -u continuum-mcp -u continuum-slack-bot -f
```

### View Recent Logs (last 100 lines)

```bash
sudo journalctl -u continuum-mcp -n 100
sudo journalctl -u continuum-slack-bot -n 100
```

---

## Single Command Script (Optional)

If you want a single command to manage both services, create a helper script:

```bash
nano ~/continuum.ai/manage_services.sh
```

Paste this:

```bash
#!/bin/bash

# Manage both continuum.ai services

case "$1" in
    start)
        echo "Starting continuum.ai services..."
        sudo systemctl start continuum-mcp
        sudo systemctl start continuum-slack-bot
        echo "Services started!"
        ;;
    stop)
        echo "Stopping continuum.ai services..."
        sudo systemctl stop continuum-mcp
        sudo systemctl stop continuum-slack-bot
        echo "Services stopped!"
        ;;
    restart)
        echo "Restarting continuum.ai services..."
        sudo systemctl restart continuum-mcp
        sudo systemctl restart continuum-slack-bot
        echo "Services restarted!"
        ;;
    status)
        echo "=== MCP Server Status ==="
        sudo systemctl status continuum-mcp --no-pager
        echo ""
        echo "=== Slack Bot Status ==="
        sudo systemctl status continuum-slack-bot --no-pager
        ;;
    logs)
        echo "Showing logs (Ctrl+C to exit)..."
        sudo journalctl -u continuum-mcp -u continuum-slack-bot -f
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
```

Make it executable:

```bash
chmod +x ~/continuum.ai/manage_services.sh
```

Now you can use:

```bash
# Start both
~/continuum.ai/manage_services.sh start

# Stop both
~/continuum.ai/manage_services.sh stop

# Restart both
~/continuum.ai/manage_services.sh restart

# Check status
~/continuum.ai/manage_services.sh status

# View logs
~/continuum.ai/manage_services.sh logs
```

---

## Troubleshooting

### Service won't start?

1. **Check if Python path is correct:**

   ```bash
   which python3
   # Should show: /usr/bin/python3 or /usr/local/bin/python3
   ```

2. **Check if .env file exists:**

   ```bash
   ls -la ~/continuum.ai/.env
   ```

3. **Check service logs:**

   ```bash
   sudo journalctl -u continuum-mcp -n 50
   sudo journalctl -u continuum-slack-bot -n 50
   ```

4. **Test running manually (with venv):**

   ```bash
   cd ~/continuum.ai
   source .venv/bin/activate
   python -m app.server --transport http --host 0.0.0.0 --port 8000
   # In another terminal:
   source .venv/bin/activate
   python -m uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000
   ```

   Or without activating (using venv Python directly):

   ```bash
   cd ~/continuum.ai
   .venv/bin/python -m app.server --transport http --host 0.0.0.0 --port 8000
   .venv/bin/python -m uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000
   ```

### Service keeps restarting?

Check the logs for errors:

```bash
sudo journalctl -u continuum-mcp -n 100 | grep -i error
sudo journalctl -u continuum-slack-bot -n 100 | grep -i error
```

Common issues:

- Missing environment variables in `.env`
- Wrong Python path
- Port already in use
- Missing dependencies

### Port already in use?

```bash
# Check what's using the ports
sudo lsof -i :8000
sudo lsof -i :3000

# Kill the process if needed
sudo kill -9 <PID>
```

---

## Verify Auto-Start on Reboot

Test that services start automatically:

```bash
# Reboot the instance
sudo reboot

# After reboot, SSH back in and check:
sudo systemctl status continuum-mcp
sudo systemctl status continuum-slack-bot
```

Both should show `active (running)`.

---

## Notes

- Services will automatically restart if they crash (RestartSec=10)
- Logs are stored in systemd journal (view with `journalctl`)
- Both services run as `ubuntu` user
- Environment variables are loaded from `/home/ubuntu/continuum.ai/.env`
- Services start after network is available
