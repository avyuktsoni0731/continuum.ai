# continuum.ai Slack Bot

A conversational AI bot for Slack that uses your MCP tools (Jira, GitHub, Calendar) to answer questions and help your team.

## What Makes It Unique?

Unlike Cursor Chat (which is personal), this bot:
- **Team-focused**: Works in Slack channels for collaboration
- **Proactive**: Can detect context mismatches and notify teams
- **Decision-making**: Uses Gemini to reason and make intelligent decisions
- **Action-oriented**: Executes actions (notify, summarize, delegate) not just fetch data

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Slack App

Follow the detailed guide in `SLACK_BOT_SETUP.md` to:
- Create a Slack app
- Get bot token
- Configure event subscriptions
- Set up slash commands (optional)

### 3. Configure Environment

Add to your `.env` file:

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=global
# ... other configs (Jira, GitHub, Calendar)
```

### 4. Run the Bot

```bash
# Development
python -m app.slack_bot

# Or with uvicorn
uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000
```

### 5. Test It

**Option 1: Mention the bot**
```
@continuum.ai show me open PRs
```

**Option 2: Use slash command**
```
/continuum what issues are in board 1?
```

**Option 3: Direct message**
Send a DM to the bot:
```
show me my calendar availability
```

## How It Works

```
User in Slack → Bot receives message
    ↓
Gemini parses intent → Selects MCP tools
    ↓
Executes tools (Jira/GitHub/Calendar)
    ↓
Gemini formats response → Posts to Slack
```

## Example Interactions

### Jira
- "Show me issues in board 1"
- "What's the status of PROJ-123?"
- "List all high priority tasks"

### GitHub
- "Show me open PRs"
- "What's the status of PR #42?"
- "Check if PR #10 has approvals"

### Calendar
- "Am I free this week?"
- "Show me today's events"
- "When can I schedule a meeting?"

## Architecture

```
app/
├── slack_bot.py          # FastAPI server for Slack events
├── agent/
│   └── conversation.py   # Conversational agent (Gemini + MCP tools)
└── tools/
    ├── jira.py          # Jira API integration
    ├── github.py        # GitHub API integration
    └── calendar.py      # Google Calendar integration
```

## Deployment

### Local Testing (ngrok)

```bash
# Terminal 1: Run bot
python -m app.slack_bot

# Terminal 2: Start ngrok
ngrok http 3000

# Use ngrok URL in Slack Event Subscriptions
```

### Production (EC2)

1. Deploy bot to EC2 (same as MCP server)
2. Use systemd to keep it running
3. Configure Slack Event Subscriptions with EC2 public IP
4. Or use Cloudflare Tunnel for HTTPS

See `EC2_SETUP_SIMPLE.md` for details.

## Next Steps

- [ ] Add proactive notifications (detect unavailable user → notify team)
- [ ] Implement decision-making logic (scoring, policy)
- [ ] Add self-reflection loop
- [ ] Integrate with LangGraph for multi-step reasoning

## Troubleshooting

**Bot not responding?**
- Check if bot is added to channel
- Verify `SLACK_BOT_TOKEN` is set
- Check bot logs for errors

**Events not working?**
- Verify Request URL is accessible
- Check Slack Event Subscriptions shows "Verified ✓"
- Ensure ngrok/tunnel is running (for testing)

**Getting errors?**
- Check all environment variables are set
- Verify GCP credentials: `gcloud auth application-default login`
- Check Jira/GitHub/Calendar credentials

