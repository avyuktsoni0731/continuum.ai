# Testing Slack Bot on EC2

## Current Setup

- **MCP Server**: Port 8000 → `http://3.108.63.43:8000/mcp/`
- **Slack Bot**: Port 3000 → `http://3.108.63.43:3000/slack/events`

---

## Step 1: Verify Both Servers Are Running

On your EC2 instance, check if both are running:

```bash
# Check if MCP server is running (port 8000)
curl http://localhost:8000/mcp/ || echo "MCP server not running"

# Check if Slack bot is running (port 3000)
curl http://localhost:3000/health || echo "Slack bot not running"
```

Expected responses:

- MCP server: May return 406 (normal for non-MCP clients)
- Slack bot: `{"status":"ok","service":"continuum.ai-slack-bot"}`

---

## Step 2: Check EC2 Security Group

Make sure port **3000** is open in your EC2 security group:

1. Go to EC2 Console → Security Groups
2. Find your instance's security group
3. Edit Inbound Rules
4. Add rule:
   - **Type**: Custom TCP
   - **Port**: 3000
   - **Source**: 0.0.0.0/0 (or restrict to Slack IPs if needed)
   - **Description**: Slack Bot Events

---

## Step 3: Test Slack Bot Endpoint from Your Machine

From your local machine, test if the endpoint is accessible:

```bash
# Test health endpoint
curl http://3.108.63.43:3000/health

# Test Slack events endpoint (should return error without proper payload, but should be reachable)
curl -X POST http://3.108.63.43:3000/slack/events \
  -H "Content-Type: application/json" \
  -d '{"type":"url_verification","challenge":"test123"}'
```

Expected response for challenge:

```json
{ "challenge": "test123" }
```

If you get connection refused or timeout:

- Check EC2 security group (port 3000)
- Check if Slack bot is running on EC2
- Check firewall rules on EC2

---

## Step 4: Update Slack Event Subscriptions

1. Go to https://api.slack.com/apps → Your App → Event Subscriptions
2. **Request URL**: `http://3.108.63.43:3000/slack/events`
   - ⚠️ **Important**: Use port **3000**, not 8000!
3. Click **"Retry"** or **"Save Changes"**
4. Slack will send a challenge request
5. Your bot should respond with the challenge value
6. You should see **"Verified ✓"** green checkmark

---

## Step 5: Run Both Servers on EC2

### Option A: Run in Separate Terminals (Testing)

**Terminal 1 (MCP Server):**

```bash
cd /path/to/continuum.ai
python -m app.server --transport http --host 0.0.0.0 --port 8000
```

**Terminal 2 (Slack Bot):**

```bash
cd /path/to/continuum.ai
uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000
```

### Option B: Run in Background (Production)

**MCP Server:**

```bash
nohup python -m app.server --transport http --host 0.0.0.0 --port 8000 > mcp.log 2>&1 &
```

**Slack Bot:**

```bash
nohup uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000 > slack_bot.log 2>&1 &
```

### Option C: Use systemd (Recommended for Production)

Create `/etc/systemd/system/continuum-slack-bot.service`:

```ini
[Unit]
Description=continuum.ai Slack Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/continuum.ai
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 -m uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable continuum-slack-bot
sudo systemctl start continuum-slack-bot
sudo systemctl status continuum-slack-bot
```

---

## Step 6: Test in Slack

### Test 1: Health Check

```bash
curl http://3.108.63.43:3000/health
```

### Test 2: URL Verification (Manual)

```bash
curl -X POST http://3.108.63.43:3000/slack/events \
  -H "Content-Type: application/json" \
  -d '{"type":"url_verification","challenge":"test_challenge_123"}'
```

Should return:

```json
{ "challenge": "test_challenge_123" }
```

### Test 3: In Slack

1. Add bot to a channel: `/invite @continuum.ai`
2. Mention the bot: `@continuum.ai show me open PRs`
3. Or use slash command: `/continuum what issues are in board 1?`

---

## Troubleshooting

### "URL didn't respond with challenge"

- ✅ Check if Slack bot is running: `curl http://localhost:3000/health`
- ✅ Check if port 3000 is open: `curl http://3.108.63.43:3000/health`
- ✅ Check bot logs for errors
- ✅ Verify URL is `http://3.108.63.43:3000/slack/events` (not 8000)

### "Connection refused" or "Timeout"

- ✅ Check EC2 security group (port 3000)
- ✅ Check if server is running: `ps aux | grep uvicorn`
- ✅ Check firewall: `sudo ufw status`

### Bot not responding in Slack

- ✅ Check if bot is added to channel
- ✅ Check bot logs: `tail -f slack_bot.log` or `journalctl -u continuum-slack-bot -f`
- ✅ Verify `SLACK_BOT_TOKEN` in `.env`
- ✅ Check Event Subscriptions shows "Verified ✓"

### Bot responds but errors occur

- ✅ Check `.env` has all required variables (Jira, GitHub, Calendar, GCP)
- ✅ Check GCP credentials: `gcloud auth application-default login`
- ✅ Check bot logs for specific error messages

---

## Quick Test Commands

```bash
# On EC2 - Check if both servers are running
ps aux | grep -E "(app.server|slack_bot)"

# On EC2 - Check ports
netstat -tuln | grep -E "(8000|3000)"

# From your machine - Test endpoints
curl http://3.108.63.43:3000/health
curl http://3.108.63.43:8000/mcp/

# Test Slack challenge
curl -X POST http://3.108.63.43:3000/slack/events \
  -H "Content-Type: application/json" \
  -d '{"type":"url_verification","challenge":"test"}'
```

---

## Next Steps

Once verified:

1. ✅ Slack Event Subscriptions shows "Verified ✓"
2. ✅ Bot responds to mentions in Slack
3. ✅ Bot can fetch data from Jira/GitHub/Calendar

Then you can:

- Set up systemd services for persistence
- Add HTTPS with Cloudflare Tunnel (optional)
- Test more complex queries
