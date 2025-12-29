# Simple EC2 Setup for continuum.ai MCP Server

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up `.env` file:**
   ```bash
   cp env.example .env
   nano .env  # Add your API keys
   ```

3. **Run with HTTP transport:**
   ```bash
   python -m app.server --transport http --host 0.0.0.0 --port 8000
   ```

4. **Access at:**
   ```
   http://YOUR_EC2_IP:8000/mcp/
   ```

---

## Keep It Running (systemd)

Create `/etc/systemd/system/continuum-ai.service`:

```ini
[Unit]
Description=continuum.ai MCP Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/continuum.ai
Environment="PATH=/home/ubuntu/continuum.ai/venv/bin"
ExecStart=/home/ubuntu/continuum.ai/venv/bin/python -m app.server --transport http --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable continuum-ai
sudo systemctl start continuum-ai
sudo systemctl status continuum-ai
```

---

## Security Group

In AWS Console, open port 8000:
- Type: Custom TCP
- Port: 8000
- Source: 0.0.0.0/0 (or restrict to your IP)

---

## Optional: Cloudflare Tunnel (Free HTTPS)

If you want HTTPS without setting up certificates:

```bash
# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# Run tunnel (creates permanent HTTPS URL)
cloudflared tunnel --url http://localhost:8000
```

This gives you a permanent `https://xxx.trycloudflare.com` URL!

---

## That's It!

No extra files needed. Just:
- `app/server.py` (your MCP server)
- systemd service (to keep it running)
- Optional: Cloudflare Tunnel (for HTTPS)

Simple and clean! 🚀

