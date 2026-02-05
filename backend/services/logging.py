"""
Logging Service for Workflow

Provides:
- Log storage with clear on workflow start
- Real-time log streaming via SSE
- Log level filtering
"""

import asyncio
from datetime import datetime
from typing import List, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum


class LogLevel(str, Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    STEP = "STEP"


@dataclass
class LogEntry:
    timestamp: str
    level: LogLevel
    message: str
    step: str = ""
    
    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "level": self.level.value,
            "message": self.message,
            "step": self.step
        }


class WorkflowLogger:
    """Singleton logger for workflow execution."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_logger()
        return cls._instance
    
    def _init_logger(self):
        self.logs: List[LogEntry] = []
        self.subscribers: List[asyncio.Queue] = []
        self.is_running = False
        self.current_step = ""
    
    def clear(self):
        """Clear all logs (called when workflow starts)."""
        self.logs = []
        self.current_step = ""
        # Notify subscribers of clear
        self._notify_clear()
    
    def set_step(self, step: str):
        """Set current workflow step."""
        self.current_step = step
        self.log(LogLevel.STEP, f"Starting: {step}", step=step)
    
    def log(self, level: LogLevel, message: str, step: str = None):
        """Add a log entry."""
        entry = LogEntry(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            level=level,
            message=message,
            step=step or self.current_step
        )
        self.logs.append(entry)
        
        # Print to console as well (use errors='replace' to handle unicode on Windows)
        msg = f"[{entry.timestamp}] [{entry.level.value}] {entry.message}"
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
        
        # Notify subscribers
        self._notify_subscribers(entry)
    
    def info(self, message: str):
        self.log(LogLevel.INFO, message)
    
    def success(self, message: str):
        self.log(LogLevel.SUCCESS, message)
    
    def warning(self, message: str):
        self.log(LogLevel.WARNING, message)
    
    def error(self, message: str):
        self.log(LogLevel.ERROR, message)
    
    def get_logs(self) -> List[dict]:
        """Get all logs as dicts."""
        return [log.to_dict() for log in self.logs]
    
    def subscribe(self) -> asyncio.Queue:
        """Subscribe to log updates."""
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        return queue
    
    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from log updates."""
        if queue in self.subscribers:
            self.subscribers.remove(queue)
    
    def _notify_subscribers(self, entry: LogEntry):
        """Send log entry to all subscribers."""
        for queue in self.subscribers:
            try:
                queue.put_nowait({"type": "log", "data": entry.to_dict()})
            except asyncio.QueueFull:
                pass
    
    def _notify_clear(self):
        """Notify subscribers that logs were cleared."""
        for queue in self.subscribers:
            try:
                queue.put_nowait({"type": "clear"})
            except asyncio.QueueFull:
                pass


# Global logger instance
logger = WorkflowLogger()
