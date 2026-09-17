from app.tasks.ping import ping
from app.tasks.tools import run_tool

TASKS = [ping, run_tool]

__all__ = ["TASKS", "ping", "run_tool"]
