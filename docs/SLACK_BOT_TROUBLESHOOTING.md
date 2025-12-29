# Slack Bot Troubleshooting Guide

## Issue: Bot Receives Requests But Doesn't Respond

If you see 200 status codes in logs but no response in Slack, follow these steps:

---

## Step 1: Check Logs

The bot now has detailed logging. Look for:

```bash
# If running with uvicorn directly
# You should see logs like:
INFO - Received Slack event: event_callback
INFO - Event type: app_mention, Channel: C123456
INFO - User message: show me open PRs
INFO - Processing message with agent: show me open PRs
```

**Common log patterns:**

✅ **Good:**
```
INFO - Received Slack event: event_callback
INFO - Processing message with agent: ...
INFO - Agent response: ...
INFO - Posting to Slack channel C123456: ...
INFO - Successfully posted to Slack: 1234567890.123456
```

❌ **Error patterns:**
```
ERROR - Failed to initialize agent: ...
ERROR - Error processing message: ...
ERROR - Slack API error: channel_not_found
ERROR - Slack API error: not_authed
```

---

## Step 2: Check Common Issues

### Issue A: Agent Initialization Fails

**Symptoms:**
- Logs show: `ERROR - Failed to initialize agent`
- Bot doesn't respond

**Fix:**
1. Check `.env` has all required variables:
   ```bash
   GCP_PROJECT_ID=your-project-id
   GCP_LOCATION=global
   JIRA_BASE_URL=...
   GITHUB_TOKEN=...
   SLACK_BOT_TOKEN=...
   ```

2. Verify GCP credentials:
   ```bash
   gcloud auth application-default login
   ```

3. Test agent initialization:
   ```python
   python -c "from app.agent.conversation import ConversationalAgent; agent = ConversationalAgent(); print('OK')"
   ```

---

### Issue B: Slack API Errors

**Symptoms:**
- Logs show: `ERROR - Slack API error: ...`
- Common errors:
  - `channel_not_found` - Bot not in channel
  - `not_authed` - Invalid token
  - `missing_scope` - Missing permissions

**Fix:**

1. **Channel not found:**
   - Add bot to channel: `/invite @continuum.ai`
   - Or use channel ID instead of name

2. **Not authenticated:**
   - Verify `SLACK_BOT_TOKEN` in `.env`
   - Token should start with `xoxb-`
   - Regenerate token in Slack App settings

3. **Missing scope:**
   - Go to Slack App → OAuth & Permissions
   - Add required scopes:
     - `chat:write`
     - `app_mentions:read`
     - `channels:read` (if posting to channels)

---

### Issue C: Agent Processing Errors

**Symptoms:**
- Logs show: `ERROR - Error processing message: ...`
- Bot might post error message or nothing

**Fix:**

1. Check tool execution:
   - Verify Jira/GitHub/Calendar credentials
   - Test tools manually:
     ```python
     from app.tools.jira import get_boards
     import asyncio
     asyncio.run(get_boards())
     ```

2. Check Gemini API:
   - Verify GCP project has Vertex AI enabled
   - Check quota limits
   - Test Gemini connection:
     ```python
     python app/vertexai.py
     ```

---

## Step 3: Test Endpoints Manually

### Test 1: Health Check
```bash
curl http://3.108.63.43:3000/health
```

Expected: `{"status":"ok","service":"continuum.ai-slack-bot"}`

### Test 2: Test Slack Posting
```bash
# First, get your channel ID from Slack (right-click channel → View channel details)
# Then test:
curl http://3.108.63.43:3000/test-slack
```

This will try to post a test message (you need to set `SLACK_TEST_CHANNEL_ID` in `.env`).

### Test 3: Simulate Slack Event
```bash
curl -X POST http://3.108.63.43:3000/slack/events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "event_callback",
    "event": {
      "type": "app_mention",
      "channel": "C1234567890",
      "text": "<@U123456> show me open PRs",
      "ts": "1234567890.123456"
    }
  }'
```

Check logs to see what happens.

---

## Step 4: Enable Debug Logging

To see even more details, change logging level:

```python
# In app/slack_bot.py, change:
logging.basicConfig(level=logging.DEBUG)  # Instead of INFO
```

This will show:
- Full request/response bodies
- HTTP client details
- All function calls

---

## Step 5: Common Fixes

### Fix 1: Restart Bot with Logging

```bash
# Stop current bot (Ctrl+C)
# Restart with visible logs:
uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000 --log-level debug
```

### Fix 2: Check Event Subscriptions

1. Go to Slack App → Event Subscriptions
2. Verify Request URL shows "Verified ✓"
3. Check subscribed events:
   - `app_mention` ✅
   - `message.channels` ✅ (if bot in channels)
   - `message.im` ✅ (for DMs)

### Fix 3: Verify Bot Permissions

1. Go to Slack App → OAuth & Permissions
2. Check "Bot Token Scopes":
   - `app_mentions:read` ✅
   - `chat:write` ✅
   - `channels:read` ✅ (optional)
   - `users:read` ✅ (optional)

### Fix 4: Test in Direct Message

Sometimes channel permissions are tricky. Try:
1. Open DM with bot
2. Send: `show me open PRs`
3. Check logs

---

## Quick Debug Checklist

- [ ] Bot is running (check `ps aux | grep uvicorn`)
- [ ] Port 3000 is accessible (`curl http://localhost:3000/health`)
- [ ] `.env` file has all required variables
- [ ] `SLACK_BOT_TOKEN` is valid (starts with `xoxb-`)
- [ ] Bot is added to channel (`/invite @continuum.ai`)
- [ ] Event Subscriptions shows "Verified ✓"
- [ ] Logs show events being received
- [ ] No errors in logs when processing
- [ ] GCP credentials are set (`gcloud auth application-default login`)

---

## Still Not Working?

1. **Share logs** - Copy the full log output when you mention the bot
2. **Check Slack API response** - Look for `Slack API error:` in logs
3. **Test agent separately** - Try running the agent code directly:
   ```python
   from app.agent.conversation import ConversationalAgent
   import asyncio
   
   agent = ConversationalAgent()
   result = asyncio.run(agent.chat("show me open PRs"))
   print(result)
   ```

---

## Next Steps

Once you see the logs, you'll know exactly where it's failing:
- **Agent init fails** → Check GCP credentials
- **Tool execution fails** → Check Jira/GitHub/Calendar credentials
- **Slack API fails** → Check token and permissions
- **No errors but no response** → Check channel permissions

