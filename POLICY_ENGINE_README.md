# Policy Engine - Decision Intelligence Layer

## Overview

The Policy Engine is the core differentiator that makes Continuum.ai **adaptive and intelligent**, not just a reactive command router.

## What It Does

When you ask about a PR or Jira issue, the agent now:
1. **Calculates scores** (Criticality + Automation Feasibility)
2. **Makes decisions** (Execute/Delegate/Summarize/Reschedule/Automate)
3. **Shows reasoning** (explains why it chose that action)

## Components

### 1. Scoring System (`app/policy/scoring.py`)

**Criticality Score (CS)** - 0-100
- How urgent/important is this task?
- Factors: Priority, due date, age, size, labels, status

**Automation Feasibility Score (AFS)** - 0-100
- How safe is it to automate?
- Factors: CI status, approvals, blockers, mergeable status

### 2. Decision Engine (`app/policy/decision.py`)

Routes actions based on scores:

```
IF CS > 80 AND user_available:
    → EXECUTE (do it now)

ELIF CS > 60 AND user_unavailable:
    → DELEGATE (find best teammate)

ELIF CS > 60 AND AFS > 70 AND automation_enabled:
    → AUTOMATE (safe to auto-merge/assign)

ELIF CS < 40:
    → SUMMARIZE (low priority, batch for later)

ELIF 40 <= CS <= 60 AND user_unavailable:
    → RESCHEDULE (move to when user is free)

ELSE:
    → NOTIFY (just inform)
```

### 3. Guardrails (`app/policy/rules.py`)

Safety checks before automation:
- ✅ Automation opt-in required
- ✅ AFS must be ≥ 70
- ✅ Production changes need 2+ approvals
- ✅ CI must pass
- ✅ No blockers
- ✅ Business hours only

## Example Usage

### User asks: "Show me PR #42"

**Before (reactive):**
```
Bot: "PR #42: Add feature X - Status: Open - CI: Passing"
```

**After (intelligent):**
```
Bot: "PR #42: Add feature X - Status: Open - CI: Passing

💡 Decision for PR #42: DELEGATE | CS: 82.5 | AFS: 34.2
Why: High criticality (CS: 82.5). User is unavailable. Delegate to best teammate."
```

## Integration

The policy engine is automatically applied when:
- User asks about a specific PR (`get_github_pr_context`)
- User asks about a Jira issue (`get_jira_issue`)
- User asks about issues in a board (`get_jira_board_issues`)

## Decision Trace Format

Each decision includes:
- **Action**: What to do (EXECUTE/DELEGATE/etc.)
- **CS**: Criticality Score
- **AFS**: Automation Feasibility Score
- **Reasoning**: Why this action was chosen
- **Factors**: All inputs used (priority, status, etc.)
- **Guardrail checks**: Safety validation results

## Next Steps

1. ✅ **Policy Engine** - DONE
2. ⏭️ **Delegation Engine** - Select best teammate
3. ⏭️ **Trigger System** - Proactive detection
4. ⏭️ **Action Execution** - Actually delegate/reschedule

## Testing

Test with:
```
@continuum.ai show me PR #42
@continuum.ai what's the status of PROJ-123
@continuum.ai get issues from board 1
```

You should see decision intelligence in the response!

