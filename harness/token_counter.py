"""
Token Counter for VRAM Safety
Estimates token usage to prevent context window overflow on local models.
"""


class TokenCounter:
    """
    Token counter for managing context window usage.
    Optimized for Qwen2.5-7B with 32K context window.
    
    Uses simple character-based estimation (1 token ≈ 4 characters)
    which is accurate enough for English text and much faster than
    proper tokenization.
    """

    # Default limits for RTX 4060 8GB
    DEFAULT_MAX_TOKENS = 28000  # Leave headroom below 32K
    DEFAULT_MAX_CHARS = 112000  # 28000 * 4

    def __init__(
        self, 
        max_tokens: int = DEFAULT_MAX_TOKENS,
        compact_threshold: int = 24000  # Start compaction at 75% full
    ):
        """
        Initialize token counter.
        
        Args:
            max_tokens: Maximum tokens allowed in context
            compact_threshold: Token count at which to trigger compaction
        """
        self.max_tokens = max_tokens
        self.compact_threshold = compact_threshold
        self.max_chars = max_tokens * 4

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        return len(text) // 4

    def count_messages(self, messages: list) -> int:
        """
        Count total tokens in a list of messages.
        
        Args:
            messages: List of dicts with 'role' and 'content'
            
        Returns:
            Total estimated tokens
        """
        total = 0
        for msg in messages:
            content = msg.get('content', '')
            total += self.count_tokens(content)
            # Add overhead for role markers
            total += 4  # Approximate overhead per message
        return total

    def should_compact(self, current_tokens: int) -> bool:
        """
        Check if context should be compacted.
        
        Args:
            current_tokens: Current token count
            
        Returns:
            True if compaction is recommended
        """
        return current_tokens >= self.compact_threshold

    def is_context_full(self, current_tokens: int) -> bool:
        """
        Check if context is approaching the limit.
        
        Args:
            current_tokens: Current token count
            
        Returns:
            True if context is too full
        """
        return current_tokens >= self.max_tokens

    def get_available_tokens(self, current_tokens: int) -> int:
        """
        Get remaining token budget.
        
        Args:
            current_tokens: Current token count
            
        Returns:
            Available tokens
        """
        return max(0, self.max_tokens - current_tokens)

    def truncate_to_fit(
        self, 
        text: str, 
        reserved_tokens: int = 1000
    ) -> str:
        """
        Truncate text to fit within available token budget.
        
        Args:
            text: Text to truncate
            reserved_tokens: Tokens to reserve for other content
            
        Returns:
            Truncated text with message if truncated
        """
        available = self.get_available_tokens(reserved_tokens)
        max_chars = available * 4

        if len(text) <= max_chars:
            return text

        truncation_message = "\n\n... [TRUNCATED] ... Use Grep to search specific parts."
        truncate_at = max_chars - len(truncation_message)

        return text[:truncate_at] + truncation_message

    def estimate_file_tokens(self, file_path: str) -> int:
        """
        Estimate token count for a file without loading it entirely.
        
        Args:
            file_path: Path to file
            
        Returns:
            Estimated token count
        """
        import os
        file_size = os.path.getsize(file_path)
        return file_size // 4

    def can_load_file(self, file_path: str, current_tokens: int) -> bool:
        """
        Check if a file can be safely loaded into context.
        
        Args:
            file_path: Path to file
            current_tokens: Current context token count
            
        Returns:
            True if file can be loaded safely
        """
        file_tokens = self.estimate_file_tokens(file_path)
        return (current_tokens + file_tokens) <= self.max_tokens
