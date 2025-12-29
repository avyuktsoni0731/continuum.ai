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
   # Make sure you're in the project root directory
   cd /path/to/continuum.ai
   python -m app.server --transport http --host 0.0.0.0 --port 8000
   ```

   **Important:** Always run from the project root directory where `.env` and `token.json` are located.

4. **MCP Endpoint:**

   ```
   http://YOUR_EC2_IP:8000/mcp/
   ```

   **Note:** This endpoint is for MCP clients only. Browsers will get a 406 error (this is normal).
   To test if the server is running, check the logs - you should see "Uvicorn running on http://0.0.0.0:8000"

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

## Cloudflare Tunnel (Recommended - Free HTTPS URL)

This gives you a **permanent HTTPS URL** that MCP clients can easily connect to!

### Setup

1. **Install cloudflared on EC2:**

   ```bash
   wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
   chmod +x cloudflared
   sudo mv cloudflared /usr/local/bin/
   ```

2. **Run tunnel:**

   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```

   This will output something like:

   ```
   +--------------------------------------------------------------------------------------------+
   |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
   |  https://random-name-1234.trycloudflare.com                                                |
   +--------------------------------------------------------------------------------------------+
   ```

3. **Use this URL for MCP clients:**
   ```
   https://random-name-1234.trycloudflare.com/mcp/
   ```

### Keep Tunnel Running (systemd)

Create `/etc/systemd/system/cloudflare-tunnel.service`:

```ini
[Unit]
Description=Cloudflare Tunnel for continuum.ai
After=network.target

[Service]
Type=simple
User=ubuntu
ExecStart=/usr/local/bin/cloudflared tunnel --url http://localhost:8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cloudflare-tunnel
sudo systemctl start cloudflare-tunnel
```

**Note:** The free tunnel URL changes each time you restart. For a permanent URL, you'd need to set up a named tunnel (more complex but free).

---

## Alternative: ngrok (Simpler, but URL changes)

```bash
# Install ngrok
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar -xzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# Run (requires free ngrok account + auth token)
ngrok http 8000
```

Gives you: `https://xxxx-xx-xx-xx-xx.ngrok-free.app`

---

## Connecting to the MCP Server

### From an MCP Client

The `/mcp/` endpoint uses the MCP protocol. Connect using:

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "continuum-ai": {
      "url": "http://YOUR_EC2_IP:8000/mcp/",
      "transport": "sse"
    }
  }
}
```

### Testing Server Status

**Quick test with curl:**

```bash
curl -v http://YOUR_EC2_IP:8000/mcp/
```

**Expected:** `406 Not Acceptable` = Server is working! ✅  
(Browsers/curl don't send MCP protocol headers, so 406 is expected)

### Using MCP Inspector

**Note:** MCP Inspector may not support direct remote HTTP connections from Windows.

**Option 1: Test on EC2 locally**

```bash
# SSH into EC2, then:
mcp-inspector http://localhost:8000/mcp/
```

**Option 2: SSH Tunnel** (if remote inspector doesn't work)

```bash
# On your local Windows machine:
ssh -L 8000:localhost:8000 user@YOUR_EC2_IP

# Then in another terminal:
mcp-inspector http://localhost:8000/mcp/
```

This creates a tunnel so the inspector thinks it's connecting locally.

---

## That's It!

No extra files needed. Just:

- `app/server.py` (your MCP server)
- systemd service (to keep it running)
- Optional: Cloudflare Tunnel (for HTTPS)

Simple and clean! 🚀
