"""
TaskService manages long-running tasks, progress, cancellation, and results.
Milestone 6: simple in-memory orchestration with progress events.
"""

from src.core.results import TaskResult
from src.core.event_bus import EventBus

class TaskService:
    def __init__(self, events: EventBus):
        self.events = events
        self.tasks = {}

    def start_task(self, task_id: str, description: str):
        self.tasks[task_id] = {"status": "running", "description": description, "progress": 0}
        self.events.emit("task.started", {"task_id": task_id, "description": description})
        return TaskResult(task_id=task_id, status="running")

    def update_progress(self, task_id: str, progress: int):
        if task_id not in self.tasks:
            return
        self.tasks[task_id]["progress"] = progress
        self.events.emit("task.progress", {"task_id": task_id, "progress": progress})

    def complete_task(self, task_id: str, output=None):
        if task_id not in self.tasks:
            return TaskResult(task_id=task_id, status="unknown")
        self.tasks[task_id]["status"] = "completed"
        self.events.emit("task.completed", {"task_id": task_id})
        return TaskResult(task_id=task_id, status="completed", output=output)

    def cancel_task(self, task_id: str):
        if task_id not in self.tasks:
            return TaskResult(task_id=task_id, status="unknown")
        self.tasks[task_id]["status"] = "cancelled"
        self.events.emit("task.cancelled", {"task_id": task_id})
        return TaskResult(task_id=task_id, status="cancelled")

    def fail_task(self, task_id: str, error: str):
        if task_id not in self.tasks:
            return TaskResult(task_id=task_id, status="unknown")
        self.tasks[task_id]["status"] = "failed"
        self.events.emit("task.failed", {"task_id": task_id, "error": error})
        return TaskResult(task_id=task_id, status="failed", metadata={"error": error})
