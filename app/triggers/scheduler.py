"""
Scheduled task monitoring.

Periodically checks for:
- Tasks due soon
- Overdue tasks
- Context mismatches
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from app.triggers.models import ScheduledTask, TriggerEvent, TriggerType

logger = logging.getLogger(__name__)

# In-memory task store (in production, use database)
_scheduled_tasks: List[ScheduledTask] = []
_scheduler_running = False
_scheduler_task: Optional[asyncio.Task] = None


def add_scheduled_task(task: ScheduledTask):
    """Add a task to monitor."""
    _scheduled_tasks.append(task)
    logger.info(f"Added scheduled task: {task.task_type} {task.task_key} at {task.scheduled_time}")


def remove_scheduled_task(task_id: str):
    """Remove a scheduled task."""
    global _scheduled_tasks
    _scheduled_tasks = [t for t in _scheduled_tasks if t.task_id != task_id]
    logger.info(f"Removed scheduled task: {task_id}")


def get_scheduled_tasks(user_id: Optional[str] = None) -> List[ScheduledTask]:
    """Get scheduled tasks, optionally filtered by user."""
    if user_id:
        return [t for t in _scheduled_tasks if t.user_id == user_id]
    return _scheduled_tasks.copy()


async def _check_scheduled_tasks():
    """Check scheduled tasks for due/overdue items."""
    now = datetime.now()
    due_soon_threshold = now + timedelta(hours=1)  # Tasks due in next hour
    
    events = []
    
    for task in _scheduled_tasks:
        # Check if task is due soon or overdue
        if task.scheduled_time <= due_soon_threshold:
            events.append(TriggerEvent(
                trigger_type=TriggerType.SCHEDULED,
                event_data={
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "task_key": task.task_key,
                    "scheduled_time": task.scheduled_time.isoformat(),
                    "user_id": task.user_id,
                    "metadata": task.metadata
                },
                timestamp=now,
                source="scheduler"
            ))
    
    return events


async def _scheduler_loop():
    """Main scheduler loop - runs every 15 minutes."""
    logger.info("Scheduler started")
    
    while _scheduler_running:
        try:
            # Check scheduled tasks
            events = await _check_scheduled_tasks()
            
            if events:
                logger.info(f"Scheduler detected {len(events)} due/upcoming tasks")
                # Process events (will be handled by trigger processor)
                for event in events:
                    try:
                        await _process_trigger_event(event)
                    except Exception as e:
                        logger.error(f"Error processing event {event.event_data.get('task_key')}: {e}", exc_info=True)
            
            # Wait 15 minutes before next check
            await asyncio.sleep(15 * 60)
            
        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)
            await asyncio.sleep(60)  # Wait 1 minute on error
    
    logger.info("Scheduler stopped")


async def _process_trigger_event(event: TriggerEvent):
    """
    Process a trigger event.
    
    This will:
    1. Detect context mismatch
    2. Apply policy engine
    3. Execute action (delegate/reschedule/etc.)
    """
    try:
        from app.triggers.detector import detect_context_mismatch
        from app.triggers.processor import process_trigger
        
        # Detect if there's a context mismatch
        mismatch = await detect_context_mismatch(event)
        
        if mismatch:
            logger.info(f"Context mismatch detected: {mismatch.reason}")
            # Process the mismatch
            await process_trigger(event, mismatch)
        else:
            # No mismatch, but task is due - just notify
            await process_trigger(event, None)
            
    except Exception as e:
        logger.error(f"Error processing trigger event: {e}", exc_info=True)


def start_scheduler():
    """Start the background scheduler."""
    global _scheduler_running, _scheduler_task
    
    if _scheduler_running:
        logger.warning("Scheduler already running")
        return
    
    _scheduler_running = True
    
    # Create task in current event loop
    try:
        loop = asyncio.get_running_loop()
        _scheduler_task = loop.create_task(_scheduler_loop())
    except RuntimeError:
        # No event loop running, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _scheduler_task = loop.create_task(_scheduler_loop())
    
    logger.info("Scheduler started")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running, _scheduler_task
    
    if not _scheduler_running:
        return
    
    _scheduler_running = False
    if _scheduler_task:
        _scheduler_task.cancel()
    logger.info("Scheduler stopped")


async def schedule_pr_review(pr_number: int, scheduled_time: datetime, user_id: str):
    """Schedule a PR review task."""
    task = ScheduledTask(
        task_id=f"pr_review_{pr_number}_{int(scheduled_time.timestamp())}",
        task_type="pr_review",
        task_key=str(pr_number),
        scheduled_time=scheduled_time,
        user_id=user_id,
        metadata={"pr_number": pr_number}
    )
    add_scheduled_task(task)
    return task


async def schedule_issue_work(issue_key: str, scheduled_time: datetime, user_id: str):
    """Schedule a Jira issue work task."""
    task = ScheduledTask(
        task_id=f"issue_work_{issue_key}_{int(scheduled_time.timestamp())}",
        task_type="issue_work",
        task_key=issue_key,
        scheduled_time=scheduled_time,
        user_id=user_id,
        metadata={"issue_key": issue_key}
    )
    add_scheduled_task(task)
    return task

