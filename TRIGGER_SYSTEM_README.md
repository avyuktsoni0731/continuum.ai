# Trigger System - Proactive Context Detection

## Overview

The Trigger System makes continuum.ai **adaptive** rather than just reactive. It proactively detects when planned work can't be done and automatically takes action.

## What It Does

1. **Scheduled Monitoring**: Checks tasks every 15 minutes
2. **Context Mismatch Detection**: Detects conflicts (meetings, overdue, priority changes)
3. **Webhook Integration**: Responds to GitHub/Jira events in real-time
4. **Automatic Action**: Delegates/reschedules/notifies based on policy

## Components

### 1. Scheduler (`app/triggers/scheduler.py`)

**Periodic Task Monitoring:**

- Runs every 15 minutes
- Checks for due/overdue tasks
- Triggers processing when tasks need attention

**Usage:**

```python
from app.triggers.scheduler import schedule_pr_review, schedule_issue_work

# Schedule a PR review for tomorrow 2 PM
await schedule_pr_review(
    pr_number=42,
    scheduled_time=datetime(2025, 12, 30, 14, 0),
    user_id="soniavyukt"
)
```

### 2. Context Mismatch Detector (`app/triggers/detector.py`)

**Detects:**

- User in meeting at scheduled time
- Task overdue (>1 hour past due)
- Calendar conflicts
- Priority changes (urgent labels, high priority)

**Returns:**

- `ContextMismatch` with reason and severity
- Used to trigger appropriate action

### 3. Trigger Processor (`app/triggers/processor.py`)

**Processes trigger events:**

1. Gets task context (PR/issue data)
2. Checks user availability
3. Applies policy engine
4. Executes action (delegate/reschedule/notify)

### 4. Webhook Handlers (`app/triggers/webhooks.py`)

**GitHub Webhooks:**

- `pull_request.opened` → Schedule review
- `pull_request.synchronize` → Check if review needed
- `pull_request.labeled` → Detect priority change

**Jira Webhooks:**

- `jira:issue_created` → Schedule work
- `jira:issue_updated` → Check for priority/due date changes
- `jira:issue_assigned` → Schedule for assignee

## How It Works

### Flow:

```
1. Scheduled Task Due
   ↓
2. Detector checks context
   ↓
3. Mismatch detected? (user in meeting, overdue, etc.)
   ↓
4. Policy Engine decides action
   ↓
5. Execute: Delegate/Reschedule/Notify
   ↓
6. Slack notification sent
```

### Example:

```
1. PR #42 scheduled for review at 2 PM
   ↓
2. Scheduler checks at 1:45 PM
   ↓
3. Detector: User in meeting 2-3 PM
   ↓
4. Policy: CS=82, user unavailable → DELEGATE
   ↓
5. Delegation: Selects "aditya" (ownership: 80)
   ↓
6. Slack DM to aditya: "📋 Task Delegation: PR #42..."
```

## Setup

### 1. Start Scheduler

The scheduler starts automatically when the Slack bot starts (via `@app.on_event("startup")`).

### 2. Configure Webhooks

**GitHub:**

1. Go to repository → Settings → Webhooks
2. Add webhook URL: `http://your-server:3000/webhooks/github`
3. Select events: `Pull requests`
4. Save

**Jira:**

1. Go to project → Settings → Webhooks
2. Add webhook URL: `http://your-server:3000/webhooks/jira`
3. Select events: `Issue created`, `Issue updated`
4. Save

### 3. Schedule Tasks

Tasks can be scheduled:

- **Manually**: Via API or code
- **Automatically**: When PR/issue created (via webhook)
- **User-initiated**: "Schedule PR #42 review for tomorrow 2 PM"

## API Endpoints

### Webhooks

**POST `/webhooks/github`**

- Receives GitHub webhook events
- Processes PR events automatically

**POST `/webhooks/jira`**

- Receives Jira webhook events
- Processes issue events automatically

## Integration

### With Policy Engine

When trigger detects mismatch:

1. Policy Engine calculates CS/AFS
2. Decides action (delegate/reschedule/etc.)
3. Executes action

### With Delegation Engine

When action is DELEGATE:

1. Delegation Engine selects teammate
2. Sends Slack notification
3. Logs delegation

## Testing

### Test Scheduled Monitoring

```python
from app.triggers.scheduler import schedule_pr_review
from datetime import datetime, timedelta

# Schedule a task for 1 minute from now
await schedule_pr_review(
    pr_number=42,
    scheduled_time=datetime.now() + timedelta(minutes=1),
    user_id="soniavyukt"
)

# Wait 2 minutes, check logs for trigger processing
```

### Test Webhook

```bash
# Simulate GitHub webhook
curl -X POST http://localhost:3000/webhooks/github \
  -H "Content-Type: application/json" \
  -d '{
    "action": "opened",
    "pull_request": {
      "number": 42,
      "user": {"login": "soniavyukt"}
    }
  }'
```

## Future Enhancements

1. **Database persistence**: Store scheduled tasks in DB
2. **User preferences**: Allow users to set scheduling preferences
3. **Smart scheduling**: Auto-suggest best times based on calendar
4. **Batch processing**: Group similar tasks
5. **Recurring tasks**: Support recurring reviews/checks

## Architecture

```
Trigger System
├── Scheduler (periodic checks)
├── Detector (context mismatch)
├── Processor (action execution)
└── Webhooks (external events)
    ├── GitHub
    └── Jira
```

All components integrate with:

- Policy Engine (decision making)
- Delegation Engine (teammate selection)
- Slack Bot (notifications)
