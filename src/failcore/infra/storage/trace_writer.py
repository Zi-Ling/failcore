# failcore/infra/storage/trace_writer.py
"""
Trace writer abstraction for concurrent-safe, buffered trace recording.

Provides:
- Buffered writes with configurable flush policy
- Thread-safe/async-safe event queuing
- Schema validation and versioning
- Graceful shutdown with flush guarantee
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional, Protocol


class TraceWriter(Protocol):
    """Protocol for trace writers."""
    
    def write_event(self, event: Any) -> None:
        """Write a single event to trace."""
        ...
    
    def flush(self) -> None:
        """Flush buffered events to storage."""
        ...
    
    def close(self) -> None:
        """Close writer and flush remaining events."""
        ...


class SyncTraceWriter:
    """
    Synchronous trace writer with buffering.
    
    Features:
    - Buffered writes (configurable batch size)
    - Auto-flush on time interval or buffer size
    - Thread-safe for concurrent writes
    - JSON-L format
    - Optional file locking for multi-process safety (reserved for future)
    """
    
    def __init__(
        self,
        trace_path: Path | str,
        *,
        buffer_size: int = 100,
        flush_interval_s: float = 1.0,
        schema_version: str = "v0.1.2",
        use_file_lock: bool = False,  # Reserved: enable for multi-process/daemon mode
    ):
        self.trace_path = Path(trace_path)
        self.buffer_size = buffer_size
        self.flush_interval_s = flush_interval_s
        self.schema_version = schema_version
        self.use_file_lock = use_file_lock
        
        if use_file_lock:
            raise NotImplementedError(
                "File locking not yet implemented. "
                "This parameter is reserved for future multi-process/daemon support. "
                "For now, ensure only one writer per trace file."
            )
        
        # Ensure parent directory exists
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Open file in append mode (create if not exists)
        self._file = open(self.trace_path, 'a', encoding='utf-8')
        
        # Buffer and lock
        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._closed = False
        
        # Write schema header
        self._write_header()
    
    def _write_header(self) -> None:
        """Write trace file header with schema version."""
        header = {
            "type": "trace_header",
            "schema_version": self.schema_version,
            "created_at": time.time(),
        }
        self._file.write(json.dumps(header, ensure_ascii=False) + "\n")
        self._file.flush()
    
    def write_event(self, event: Any) -> None:
        """
        Write event to buffer.
        
        Auto-flushes if:
        - Buffer reaches buffer_size
        - Time since last flush exceeds flush_interval_s
        """
        if self._closed:
            raise RuntimeError("TraceWriter is closed")
        
        # Convert event to dict
        if is_dataclass(event):
            event_dict = asdict(event)
        elif hasattr(event, "to_dict"):
            event_dict = event.to_dict()
        elif isinstance(event, dict):
            event_dict = event
        else:
            raise TypeError(f"Event must be dict, dataclass, or have to_dict(): {type(event)}")
        
        with self._lock:
            self._buffer.append(event_dict)
            
            # Auto-flush conditions
            should_flush = (
                len(self._buffer) >= self.buffer_size
                or (time.time() - self._last_flush) >= self.flush_interval_s
            )
            
            if should_flush:
                self._flush_unlocked()
    
    def flush(self) -> None:
        """Explicitly flush buffer to disk."""
        with self._lock:
            self._flush_unlocked()
    
    def _flush_unlocked(self) -> None:
        """Internal flush (caller must hold lock)."""
        if not self._buffer:
            return
        
        # Write all buffered events
        for event_dict in self._buffer:
            self._file.write(json.dumps(event_dict, ensure_ascii=False) + "\n")
        
        # Flush file handle
        self._file.flush()
        
        # Clear buffer
        self._buffer.clear()
        self._last_flush = time.time()
    
    def close(self) -> None:
        """Close writer and flush remaining events."""
        if self._closed:
            return
        
        with self._lock:
            self._flush_unlocked()
            self._file.close()
            self._closed = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AsyncTraceWriter:
    """
    Async trace writer with background queue processing.
    
    Features:
    - Non-blocking writes (events queued to background thread)
    - Batch flush from queue
    - Graceful shutdown with queue drain
    - Optional file locking for multi-process safety (reserved for future)
    """
    
    def __init__(
        self,
        trace_path: Path | str,
        *,
        buffer_size: int = 100,
        flush_interval_s: float = 1.0,
        schema_version: str = "v0.1.2",
        use_file_lock: bool = False,  # Reserved: enable for multi-process/daemon mode
    ):
        self.trace_path = Path(trace_path)
        self.buffer_size = buffer_size
        self.flush_interval_s = flush_interval_s
        self.schema_version = schema_version
        self.use_file_lock = use_file_lock
        
        if use_file_lock:
            raise NotImplementedError(
                "File locking not yet implemented. "
                "This parameter is reserved for future multi-process/daemon support. "
                "For now, ensure only one writer per trace file."
            )
        
        # Event queue and worker thread
        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        
        # Start worker thread
        self._start_worker()
    
    def _start_worker(self) -> None:
        """Start background worker thread."""
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=False,  # Ensure proper shutdown
        )
        self._worker_thread.start()
    
    def _worker_loop(self) -> None:
        """Background worker that processes event queue."""
        # Ensure parent directory exists
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.trace_path, 'a', encoding='utf-8') as f:
            # Write header
            header = {
                "type": "trace_header",
                "schema_version": self.schema_version,
                "created_at": time.time(),
            }
            f.write(json.dumps(header, ensure_ascii=False) + "\n")
            f.flush()
            
            buffer = []
            last_flush = time.time()
            
            while not self._stop_event.is_set() or not self._queue.empty():
                try:
                    # Block for flush_interval_s, then check flush conditions
                    event_dict = self._queue.get(timeout=self.flush_interval_s)
                    buffer.append(event_dict)
                    self._queue.task_done()
                except queue.Empty:
                    pass  # Timeout, check flush conditions
                
                # Flush conditions
                should_flush = (
                    len(buffer) >= self.buffer_size
                    or (time.time() - last_flush) >= self.flush_interval_s
                )
                
                if should_flush and buffer:
                    for event_dict in buffer:
                        f.write(json.dumps(event_dict, ensure_ascii=False) + "\n")
                    f.flush()
                    buffer.clear()
                    last_flush = time.time()
            
            # Final flush
            if buffer:
                for event_dict in buffer:
                    f.write(json.dumps(event_dict, ensure_ascii=False) + "\n")
                f.flush()
    
    def write_event(self, event: Any) -> None:
        """Queue event for writing (non-blocking)."""
        if self._stop_event.is_set():
            raise RuntimeError("AsyncTraceWriter is closed")
        
        # Convert event to dict
        if is_dataclass(event):
            event_dict = asdict(event)
        elif hasattr(event, "to_dict"):
            event_dict = event.to_dict()
        elif isinstance(event, dict):
            event_dict = event
        else:
            raise TypeError(f"Event must be dict, dataclass, or have to_dict(): {type(event)}")
        
        self._queue.put(event_dict)
    
    def flush(self) -> None:
        """Wait for queue to be processed (blocking)."""
        self._queue.join()
    
    def close(self) -> None:
        """Stop worker and wait for queue drain."""
        if self._stop_event.is_set():
            return
        
        # Signal worker to stop
        self._stop_event.set()
        
        # Wait for worker to finish
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10.0)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


__all__ = [
    "TraceWriter",
    "SyncTraceWriter",
    "AsyncTraceWriter",
]
