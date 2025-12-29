# Slack Bot Setup Guide

## Step 1: Create Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name: `continuum.ai`
4. Workspace: Select your workspace
5. Click **"Create App"**

---

## Step 2: Configure Bot Token Scopes

1. Go to **"OAuth & Permissions"** in sidebar
2. Scroll to **"Scopes"** → **"Bot Token Scopes"**
3. Add these scopes:
   - `app_mentions:read` - Listen for @mentions
   - `chat:write` - Send messages
   - `commands` - Handle slash commands
   - `channels:read` - Read channel info (optional)
   - `users:read` - Read user info (optional)

---

## Step 3: Install App to Workspace

1. Still in **"OAuth & Permissions"**
2. Scroll to top
3. Click **"Install to Workspace"**
4. Authorize the app
5. **Copy the "Bot User OAuth Token"** (starts with `xoxb-`)

---

## Step 4: Configure Event Subscriptions

1. Go to **"Event Subscriptions"** in sidebar
2. Enable Events: **ON**
3. Request URL: `https://your-domain.com/slack/events`
   - For testing: Use ngrok/cloudflare tunnel
   - For production: Your EC2 public URL
4. Subscribe to bot events:

   - `app_mention` - When bot is mentioned
   - `message.channels` - Messages in channels (if bot is member)
   - `message.im` - Direct messages

5. Click **"Save Changes"**

---

## Step 5: Create Slash Command (Optional)

1. Go to **"Slash Commands"** in sidebar
2. Click **"Create New Command"**
3. Command: `/continuum`
4. Request URL: `https://your-domain.com/slack/commands`
5. Short description: `Ask continuum.ai anything`
6. Click **"Save"**

---

## Step 6: Add Environment Variables

Add to your `.env` file:

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_SIGNING_SECRET=your-signing-secret  # Optional, for verification
```

---

## Step 7: Run the Bot

```bash
# Development
python -m app.slack_bot

# Production (with systemd)
# See EC2_SETUP_SIMPLE.md for systemd service setup
```

---

## Step 8: Test It

### Option 1: Mention the bot

In any channel where the bot is added:

```
@continuum.ai show me open PRs
```

### Option 2: Use slash command

```
/continuum what issues are in board 1?
```

### Option 3: Direct message

Send a DM to the bot:

```
show me my calendar availability
```

---

## Example Interactions

**User:** "Show me open PRs"
**Bot:** _Fetches PRs → Formats with Gemini → Posts to Slack_

**User:** "What issues are in Jira board 1?"
**Bot:** _Fetches board issues → Formats nicely → Posts to Slack_

**User:** "Am I free this week?"
**Bot:** _Checks calendar → Shows free slots → Posts to Slack_

---

## Troubleshooting

### Bot not responding?

- Check if bot is added to the channel
- Verify `SLACK_BOT_TOKEN` is set correctly
- Check bot logs for errors

### Events not working?

- Verify Request URL is accessible
- Check Slack Event Subscriptions shows "Verified ✓"
- Ensure ngrok/tunnel is running (for testing)

### Getting 401 errors?

- Regenerate Bot Token
- Verify token starts with `xoxb-`
- Check token hasn't expired

---

## Security Note

For production, add request verification using `SLACK_SIGNING_SECRET` to verify requests are from Slack.
