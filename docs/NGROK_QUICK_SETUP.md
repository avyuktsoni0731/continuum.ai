# ngrok Quick Setup (No Domain Required)

## Why ngrok?

- ✅ **No domain needed** - Works immediately
- ✅ **Free HTTPS** - Perfect for webhooks
- ✅ **Quick setup** - 5 minutes

## Setup Steps

### 1. Sign up for ngrok (free)

Go to: https://dashboard.ngrok.com/signup

### 2. Get your auth token

After signing up, go to: https://dashboard.ngrok.com/get-started/your-authtoken

Copy your authtoken (looks like: `2abc123def456ghi789jkl012mno345pq_6r7s8t9u0v1w2x3y4z5`)

### 3. Install on EC2

```bash
# SSH into your EC2 instance
ssh -i "continuum-kp.pem" ubuntu@ec2-3-108-63-43.ap-south-1.compute.amazonaws.com

# Install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok
```

### 4. Configure ngrok

```bash
# Add your authtoken
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

### 5. Start tunnel

**Option A: Run in foreground (for testing)**

```bash
ngrok http 3000
```

This will show you a URL like:

```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:3000
```

**Option B: Run as systemd service (recommended)**

Create `/etc/systemd/system/ngrok.service`:

```ini
[Unit]
Description=ngrok tunnel
After=network.target

[Service]
Type=simple
User=ubuntu
ExecStart=/usr/bin/ngrok http 3000 --log=stdout
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ngrok
sudo systemctl start ngrok
sudo systemctl status ngrok
```

### 6. Get your HTTPS URL

```bash
# Check ngrok status
curl http://localhost:4040/api/tunnels
```

Or check the ngrok dashboard: https://dashboard.ngrok.com/tunnels

You'll get a URL like: `https://abc123.ngrok-free.app`

### 7. Update Webhook URLs

**Jira:**

- URL: `https://abc123.ngrok-free.app/webhooks/jira`

**GitHub:**

- URL: `https://abc123.ngrok-free.app/webhooks/github`

## Important Notes

⚠️ **The URL changes each time you restart ngrok** (unless you pay for a static domain)

✅ **For testing/hackathon:** This is perfect - just update webhook URLs when it changes

✅ **For production later:** Use Cloudflare Tunnel with your own domain

## Verify It Works

```bash
# Test the endpoint
curl https://abc123.ngrok-free.app/webhooks/jira
```

Should return a response (even if it's an error, that means HTTPS is working).

## Troubleshooting

**"ngrok: command not found"**

```bash
# Make sure it's installed
which ngrok
# If not found, reinstall
sudo apt install ngrok
```

**"authtoken not found"**

```bash
# Re-add your token
ngrok config add-authtoken YOUR_TOKEN
```

**"tunnel not starting"**

```bash
# Check if port 3000 is in use
sudo lsof -i :3000
# Make sure your Slack bot is running
```
