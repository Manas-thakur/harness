"""Tests for harness.file_ops module"""
import os
import tempfile
import pytest
from pathlib import Path
from harness.file_ops import (
    FileLock,
    read_locked,
    write_atomic,
    read_file_safe,
    append_atomic,
    ensure_directory,
    get_file_size_tokens
)


class TestFileLock:
    """Test FileLock class"""

    def test_acquire_and_release(self, tmp_path):
        """Test basic lock acquire and release"""
        lock_file = tmp_path / "test.lock"
        lock = FileLock(str(lock_file))
        
        lock.acquire()
        assert lock._fd is not None
        lock.release()
        assert lock._fd is None

    def test_context_manager(self, tmp_path):
        """Test lock as context manager"""
        lock_file = tmp_path / "test.lock"
        with FileLock(str(lock_file)) as lock:
            assert lock._fd is not None
        assert lock._fd is None


class TestReadLocked:
    """Test read_locked context manager"""

    def test_read_file_content(self, tmp_path):
        """Test reading file content"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")
        
        with read_locked(str(test_file)) as content:
            assert content == "Hello World"

    def test_read_empty_file(self, tmp_path):
        """Test reading empty file"""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        
        with read_locked(str(test_file)) as content:
            assert content == ""


class TestWriteAtomic:
    """Test write_atomic function"""

    def test_write_new_file(self, tmp_path):
        """Test writing to a new file"""
        test_file = tmp_path / "new.txt"
        write_atomic(str(test_file), "Test content")
        
        assert test_file.exists()
        assert test_file.read_text() == "Test content"

    def test_overwrite_existing_file(self, tmp_path):
        """Test overwriting existing file"""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("Old content")
        
        write_atomic(str(test_file), "New content")
        assert test_file.read_text() == "New content"

    def test_write_creates_parent_directories(self, tmp_path):
        """Test that write_atomic creates parent directories"""
        test_file = tmp_path / "subdir" / "nested" / "file.txt"
        write_atomic(str(test_file), "Content")
        
        assert test_file.exists()
        assert test_file.read_text() == "Content"


class TestReadFileSafe:
    """Test read_file_safe function"""

    def test_read_existing_file(self, tmp_path):
        """Test reading existing file safely"""
        test_file = tmp_path / "safe.txt"
        test_file.write_text("Safe content")
        
        content = read_file_safe(str(test_file))
        assert content == "Safe content"


class TestAppendAtomic:
    """Test append_atomic function"""

    def test_append_to_existing_file(self, tmp_path):
        """Test appending to existing file"""
        test_file = tmp_path / "append.txt"
        test_file.write_text("Initial ")
        
        append_atomic(str(test_file), "Added")
        assert test_file.read_text() == "Initial Added"

    def test_append_to_nonexistent_file(self, tmp_path):
        """Test appending to file that doesn't exist"""
        test_file = tmp_path / "new_append.txt"
        
        append_atomic(str(test_file), "First content")
        assert test_file.read_text() == "First content"

    def test_multiple_appends(self, tmp_path):
        """Test multiple atomic appends"""
        test_file = tmp_path / "multi.txt"
        
        append_atomic(str(test_file), "A")
        append_atomic(str(test_file), "B")
        append_atomic(str(test_file), "C")
        
        assert test_file.read_text() == "ABC"


class TestEnsureDirectory:
    """Test ensure_directory function"""

    def test_create_new_directory(self, tmp_path):
        """Test creating a new directory"""
        new_dir = tmp_path / "new_dir"
        ensure_directory(str(new_dir))
        
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_create_nested_directories(self, tmp_path):
        """Test creating nested directories"""
        nested_dir = tmp_path / "level1" / "level2" / "level3"
        ensure_directory(str(nested_dir))
        
        assert nested_dir.exists()

    def test_existing_directory(self, tmp_path):
        """Test ensuring existing directory"""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()
        
        ensure_directory(str(existing_dir))
        assert existing_dir.exists()


class TestGetFileSizeTokens:
    """Test get_file_size_tokens function"""

    def test_token_estimation(self, tmp_path):
        """Test token count estimation from file size"""
        test_file = tmp_path / "tokens.txt"
        # Write 100 bytes (approximately 25 tokens)
        test_file.write_text("x" * 100)
        
        tokens = get_file_size_tokens(str(test_file))
        assert tokens == 25  # 100 // 4

    def test_empty_file_tokens(self, tmp_path):
        """Test token count for empty file"""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        
        tokens = get_file_size_tokens(str(test_file))
        assert tokens == 0
