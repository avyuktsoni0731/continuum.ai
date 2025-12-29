# Delegation Engine - Smart Teammate Selection

## Overview

The Delegation Engine selects the best teammate(s) for task delegation based on intelligent scoring, then sends contextual notifications via Slack.

## What It Does

When the Policy Engine decides to **DELEGATE**, this engine:
1. **Scores teammates** based on ownership, workload, and availability
2. **Selects best candidate(s)** 
3. **Sends Slack notification** with context and reasoning

## Components

### 1. Teammate Selector (`app/delegation/selector.py`)

**Scoring Algorithm:**
- **Ownership Score (40% weight)**: Code/file ownership match
- **Workload Score (30% weight)**: Current workload (lower = better)
- **Availability Score (30% weight)**: Timezone, calendar, activity

**Selection:**
- Calculates total score for each teammate
- Returns best candidate(s)

### 2. Notifier (`app/delegation/notifier.py`)

**Slack Notifications:**
- Rich Block Kit formatting
- Includes task context, urgency, reasoning
- Direct message to selected teammate
- Fallback to channel notification

## How It Works

### Flow:
```
Policy Engine decides: DELEGATE
    ↓
Delegation Engine selects teammate
    ↓
Sends Slack DM to teammate
    ↓
Response shows: "✅ Delegated to [teammate]"
```

### Example:
```
User asks: "show me PR #42"
    ↓
Policy: CS=82, user unavailable → DELEGATE
    ↓
Delegation: Selects "aditya" (ownership: 80, workload: 30)
    ↓
Slack DM to aditya: "📋 Task Delegation: PR #42..."
    ↓
Response: "✅ Delegated to aditya: High ownership match (80.0)"
```

## Configuration

### Setup Teammates

Edit `app/delegation/config.py`:

```python
TEAMMATES_CONFIG = [
    {
        "username": "aditya",
        "github_username": "aditya",
        "slack_user_id": "U123456",  # Get from Slack
        "timezone": "Asia/Kolkata",
        "components": ["payments"],  # Jira components
        "file_patterns": ["src/payments/"]  # Code ownership
    },
]
```

### Get Slack User IDs

1. Go to Slack → User profile
2. Click "More" → "Copy member ID"
3. Or use Slack API: `users.list`

## Integration

Automatically triggered when:
- Policy Engine decides `Action.DELEGATE`
- Task is PR or Jira issue
- User is unavailable

## Future Enhancements

1. **Dynamic teammate loading**:
   - Fetch from GitHub contributors
   - Fetch from Jira project members
   - Fetch from Slack team

2. **Workload calculation**:
   - Count open PRs assigned
   - Count open Jira issues
   - Calculate from recent activity

3. **Ownership matching**:
   - Git blame analysis
   - File path matching
   - Component ownership

4. **Availability checking**:
   - Calendar integration
   - Timezone-aware
   - Recent activity tracking

## Testing

Test delegation:
```
@continuum.ai show me PR #42
```

If you're unavailable (in a meeting), the bot should:
1. Calculate CS/AFS
2. Decide DELEGATE
3. Select best teammate
4. Send Slack DM
5. Show in response: "✅ Delegated to [teammate]"

