"""PkgForge — Multi-package queue manager.

Manages a FIFO queue of package files, processing them one at a time
through the conversion pipeline with per-package status tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)


class QueueItemStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class QueueItem:
    """A single package in the processing queue."""
    file_path: Path
    status: QueueItemStatus = QueueItemStatus.PENDING
    message: str = ""
    result: Any = None  # PipelineResult when done

    @property
    def name(self) -> str:
        return self.file_path.name

    @property
    def pkg_type(self) -> str:
        suffix = self.file_path.suffix.lower()
        return "deb" if suffix == ".deb" else "rpm"


class QueueManager(QObject):
    """Manages a queue of packages for sequential processing.

    Signals:
        queue_changed(list)        – updated list of QueueItems
        item_started(int)          – index of item now processing
        item_finished(int, bool)   – index, success
        all_finished()             – entire queue done
        progress_updated(int, int) – current_index, total_count
    """

    queue_changed = pyqtSignal(list)
    item_started = pyqtSignal(int)
    item_finished = pyqtSignal(int, bool)
    all_finished = pyqtSignal()
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._items: list[QueueItem] = []
        self._current_index: int = -1
        self._processing: bool = False

    @property
    def items(self) -> list[QueueItem]:
        return self._items.copy()

    @property
    def is_processing(self) -> bool:
        return self._processing

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def total(self) -> int:
        return len(self._items)

    @property
    def pending_count(self) -> int:
        return sum(1 for i in self._items if i.status == QueueItemStatus.PENDING)

    def add_files(self, paths: list[Path]) -> None:
        """Add files to the queue."""
        for path in paths:
            if path.is_file() and path.suffix.lower() in (".deb", ".rpm"):
                # Avoid duplicates
                if not any(i.file_path == path for i in self._items):
                    self._items.append(QueueItem(file_path=path))
                    log.info("Kuyruğa eklendi: %s", path.name)

        self.queue_changed.emit(self._items)

    def remove_item(self, index: int) -> None:
        """Remove an item from the queue (only if pending)."""
        if 0 <= index < len(self._items):
            item = self._items[index]
            if item.status == QueueItemStatus.PENDING:
                self._items.pop(index)
                self.queue_changed.emit(self._items)

    def clear(self) -> None:
        """Clear all non-processing items."""
        self._items = [i for i in self._items if i.status == QueueItemStatus.PROCESSING]
        self._current_index = -1
        self.queue_changed.emit(self._items)

    def get_next(self) -> tuple[int, QueueItem] | None:
        """Get the next pending item. Returns (index, item) or None."""
        for i, item in enumerate(self._items):
            if item.status == QueueItemStatus.PENDING:
                return i, item
        return None

    def mark_started(self, index: int) -> None:
        """Mark an item as processing."""
        if 0 <= index < len(self._items):
            self._items[index].status = QueueItemStatus.PROCESSING
            self._current_index = index
            self._processing = True
            self.item_started.emit(index)
            self.progress_updated.emit(index + 1, len(self._items))
            self.queue_changed.emit(self._items)

    def mark_finished(self, index: int, success: bool, message: str = "", result: Any = None) -> None:
        """Mark an item as finished."""
        if 0 <= index < len(self._items):
            self._items[index].status = QueueItemStatus.DONE if success else QueueItemStatus.ERROR
            self._items[index].message = message
            self._items[index].result = result
            self.item_finished.emit(index, success)
            self.queue_changed.emit(self._items)

            # Check if all done
            if not any(i.status == QueueItemStatus.PENDING for i in self._items):
                self._processing = False
                self._current_index = -1
                self.all_finished.emit()

    def get_summary(self) -> dict[str, int]:
        """Return a summary of queue status counts."""
        counts: dict[str, int] = {}
        for item in self._items:
            key = item.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts
