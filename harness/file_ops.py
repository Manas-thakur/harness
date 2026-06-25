"""
File Operations with Atomic Writes and Locking
Ensures safe concurrent access to memory and session files.
"""

import os
import tempfile
import fcntl
from pathlib import Path
from contextlib import contextmanager


class FileLock:
    """
    Simple file locking mechanism using fcntl.
    Prevents race conditions when multiple processes access the same file.
    """

    def __init__(self, lock_file_path: str):
        """
        Initialize file lock.
        
        Args:
            lock_file_path: Path to lock file (can be same as data file + .lock)
        """
        self.lock_path = Path(lock_file_path)
        self._fd = None

    def acquire(self, exclusive: bool = False, blocking: bool = True):
        """
        Acquire the lock.
        
        Args:
            exclusive: If True, acquire exclusive lock; otherwise shared
            blocking: If True, wait for lock; otherwise raise if unavailable
        """
        # Ensure lock file exists
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self.lock_path, 'w')

        lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        if not blocking:
            lock_type |= fcntl.LOCK_NB

        try:
            fcntl.flock(self._fd, lock_type)
        except BlockingIOError:
            self._fd.close()
            self._fd = None
            raise RuntimeError(f"Could not acquire lock on {self.lock_path}")

    def release(self):
        """Release the lock."""
        if self._fd:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            self._fd.close()
            self._fd = None

    def __enter__(self):
        self.acquire(exclusive=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


@contextmanager
def read_locked(path: str, exclusive: bool = False):
    """
    Context manager for reading a file with locking.
    
    Args:
        path: Path to file
        exclusive: If True, acquire exclusive lock
        
    Yields:
        File content as string
    """
    lock_path = Path(str(path) + ".lock")
    lock = FileLock(str(lock_path))

    try:
        lock.acquire(exclusive=exclusive)
        with open(path, 'r') as f:
            content = f.read()
        yield content
    finally:
        lock.release()


def write_atomic(path: str, content: str):
    """
    Write content to file atomically.
    Uses temp file + rename to prevent partial writes.
    
    Args:
        path: Destination file path
        content: Content to write
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory (for atomic rename)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix='.tmp_',
        suffix='.md'
    )

    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)

        # Atomic rename
        os.replace(tmp_path, str(path))
    except Exception:
        # Clean up temp file on error
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def read_file_safe(path: str) -> str:
    """
    Safely read a file with locking.
    
    Args:
        path: Path to file
        
    Returns:
        File content
    """
    with read_locked(path) as content:
        return content


def append_atomic(path: str, content: str):
    """
    Append content to file atomically.
    Reads, appends, and writes back atomically.
    
    Args:
        path: Path to file
        content: Content to append
    """
    path = Path(path)

    # Use lock to prevent concurrent appends
    lock_path = Path(str(path) + ".lock")
    with FileLock(str(lock_path)):
        if path.exists():
            existing = path.read_text()
        else:
            existing = ""

        write_atomic(str(path), existing + content)


def ensure_directory(path: str):
    """
    Ensure directory exists.
    
    Args:
        path: Directory path
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def get_file_size_tokens(path: str) -> int:
    """
    Estimate token count from file size.
    
    Args:
        path: Path to file
        
    Returns:
        Estimated token count
    """
    file_size = Path(path).stat().st_size
    return file_size // 4
