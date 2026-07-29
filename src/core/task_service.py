"""
TaskService manages long-running tasks, progress, cancellation, and results.
Milestone 2: structure only.
"""

from src.core.results import TaskResult
from src.core.event_bus import EventBus

class TaskService:
    def __init__(self, events: EventBus):
        self.events = events
        self.tasks = {}

    def start_task(self, task_id: str, description: str):
        self.tasks[task_id] = {"status": "running", "description": description}
        self.events.emit("task.started", {"task_id": task_id})
        return TaskResult(task_id=task_id, status="running")

    def complete_task(self, task_id: str, output=None):
        self.tasks[task_id]["status"] = "completed"
        self.events.emit("task.completed", {"task_id": task_id})
        return TaskResult(task_id=task_id, status="completed", output=output)

    def cancel_task(self, task_id: str):
        self.tasks[task_id]["status"] = "cancelled"
        self.events.emit("task.cancelled", {"task_id": task_id})
        return TaskResult(task_id=task_id, status="cancelled")

