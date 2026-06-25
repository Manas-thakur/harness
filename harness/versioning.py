"""
Versioning System for Memory Audit Trail
Provides immutable snapshots and rollback capabilities using Git.
"""

import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import List


class VersioningSystem:
    """
    Manages versioned snapshots of agent memory.
    Supports creating snapshots, listing versions, and rollback.
    Integrates with Git for long-term audit trail.
    """

    def __init__(self, versions_dir: str = "versions", memory_path: str = "memory.md"):
        """
        Initialize versioning system.
        
        Args:
            versions_dir: Directory to store version snapshots
            memory_path: Path to active memory file
        """
        self.versions_dir = Path(versions_dir)
        self.memory_path = Path(memory_path)
        self.versions_dir.mkdir(parents=True, exist_ok=True)

        # Ensure git is initialized
        self._ensure_git_initialized()

    def _ensure_git_initialized(self):
        """Initialize git repository if not already done."""
        if not (Path(".git") / "HEAD").exists():
            try:
                subprocess.run(
                    ["git", "init"],
                    capture_output=True,
                    check=True
                )
            except subprocess.CalledProcessError:
                pass  # Git might not be available

    def create_snapshot(self, message: str = "Manual snapshot") -> str:
        """
        Creates a timestamped snapshot of the current memory.
        
        Args:
            message: Description of why this snapshot was created
            
        Returns:
            Path to created snapshot file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"v_{timestamp}.md"
        snapshot_path = self.versions_dir / snapshot_name

        # Copy current memory if it exists
        if self.memory_path.exists():
            shutil.copy(str(self.memory_path), str(snapshot_path))
        else:
            # Create empty snapshot
            snapshot_path.touch()

        # Git commit for long-term audit trail
        self._commit_snapshot(snapshot_name, message)

        return str(snapshot_path)

    def _commit_snapshot(self, snapshot_name: str, message: str):
        """Commit snapshot to Git."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            # Add files
            subprocess.run(
                ["git", "add", str(self.memory_path), str(self.versions_dir)],
                capture_output=True,
                check=True
            )

            # Commit
            commit_message = f"[Memory] {message} ({timestamp})"
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                capture_output=True,
                check=True
            )
        except subprocess.CalledProcessError:
            # Git might not be configured or no changes
            pass
        except FileNotFoundError:
            # Git not installed
            pass

    def list_snapshots(self) -> List[Path]:
        """
        Returns a list of available snapshots sorted by date (newest first).
        
        Returns:
            List of snapshot paths
        """
        if not self.versions_dir.exists():
            return []

        snapshots = sorted(
            self.versions_dir.glob("v_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return snapshots

    def rollback(self, snapshot_name: str) -> str:
        """
        Restores memory.md to a previous state.
        Creates a new snapshot before rolling back.
        
        Args:
            snapshot_name: Name of snapshot to restore (e.g., "v_20260625_140000.md")
            
        Returns:
            Path to restored snapshot
        """
        snapshot_path = self.versions_dir / snapshot_name

        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_name}")

        # Create snapshot of current state before rollback
        self.create_snapshot(f"Rollback to {snapshot_name}")

        # Restore the snapshot
        shutil.copy(str(snapshot_path), str(self.memory_path))

        return str(snapshot_path)

    def get_snapshot_info(self, snapshot_name: str) -> dict:
        """
        Get information about a specific snapshot.
        
        Args:
            snapshot_name: Name of snapshot
            
        Returns:
            Dict with snapshot metadata
        """
        snapshot_path = self.versions_dir / snapshot_name

        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_name}")

        stat = snapshot_path.stat()

        from harness.token_counter import TokenCounter
        counter = TokenCounter()

        return {
            "name": snapshot_name,
            "path": str(snapshot_path),
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "token_count": counter.count_tokens(snapshot_path.read_text())
        }

    def diff_snapshots(
        self, 
        snapshot1_name: str, 
        snapshot2_name: str
    ) -> str:
        """
        Show difference between two snapshots.
        
        Args:
            snapshot1_name: First snapshot name
            snapshot2_name: Second snapshot name
            
        Returns:
            Diff output as string
        """
        snapshot1 = self.versions_dir / snapshot1_name
        snapshot2 = self.versions_dir / snapshot2_name

        if not snapshot1.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot1_name}")
        if not snapshot2.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot2_name}")

        try:
            result = subprocess.run(
                ["diff", "-u", str(snapshot1), str(snapshot2)],
                capture_output=True,
                text=True
            )
            return result.stdout
        except FileNotFoundError:
            # diff not available, do simple comparison
            content1 = snapshot1.read_text()
            content2 = snapshot2.read_text()

            if content1 == content2:
                return "No differences"
            else:
                return "Files differ (diff tool not available)"

    def cleanup_old_snapshots(
        self, 
        keep_count: int = 10,
        max_age_days: int = 30
    ) -> List[str]:
        """
        Remove old snapshots to save space.
        
        Args:
            keep_count: Minimum number of recent snapshots to keep
            max_age_days: Maximum age in days for snapshots
            
        Returns:
            List of removed snapshot names
        """
        removed = []
        snapshots = self.list_snapshots()

        cutoff_date = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)

        for i, snapshot in enumerate(snapshots):
            # Always keep the most recent ones up to keep_count
            if i < keep_count:
                continue

            # Remove old snapshots
            if snapshot.stat().st_mtime < cutoff_date:
                snapshot.unlink()
                removed.append(snapshot.name)

        return removed
