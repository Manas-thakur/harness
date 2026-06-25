"""
Configuration Manager for Agent Fleet
Supports hierarchical loading: Environment Variables > Config File > Defaults
Uses dataclasses for structured configuration with validation
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from pathlib import Path


@dataclass
class ModelConfig:
    """LLM Model configuration"""
    model_name: str = "qwen2.5:7b"
    context_window: int = 32768
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0

    def validate(self) -> List[str]:
        """Validate model configuration constraints"""
        errors = []
        if self.max_tokens >= self.context_window:
            errors.append(f"max_tokens ({self.max_tokens}) must be less than context_window ({self.context_window})")
        if not 0 <= self.temperature <= 2:
            errors.append(f"temperature must be between 0 and 2, got {self.temperature}")
        if not 0 <= self.top_p <= 1:
            errors.append(f"top_p must be between 0 and 1, got {self.top_p}")
        if self.timeout <= 0:
            errors.append(f"timeout must be positive, got {self.timeout}")
        if self.max_retries < 0:
            errors.append(f"max_retries must be non-negative, got {self.max_retries}")
        return errors


@dataclass
class MemoryConfig:
    """Memory system configuration"""
    use_mesh: bool = True
    memory_dir: str = "./memory"
    legacy_file: str = "memory.md"
    enable_versioning: bool = True
    max_versions: int = 10
    auto_compact: bool = False
    compact_threshold: int = 100  # Compact when entries exceed this

    # Shard permissions (POSIX octal)
    shard_permissions: Dict[str, int] = field(default_factory=lambda: {
        "skills": 0o644,
        "facts": 0o644,
        "episodes": 0o600,  # Private
        "archive": 0o444,   # Read-only
        "logs": 0o600,      # Private
    })

    # Index settings
    auto_index: bool = True
    index_file: str = "_index.md"

    def validate(self) -> List[str]:
        """Validate memory configuration"""
        errors = []
        if self.max_versions < 1:
            errors.append(f"max_versions must be at least 1, got {self.max_versions}")
        if self.compact_threshold < 1:
            errors.append(f"compact_threshold must be positive, got {self.compact_threshold}")

        # Validate permissions are valid octal
        for shard, perm in self.shard_permissions.items():
            if not isinstance(perm, int) or perm < 0 or perm > 0o777:
                errors.append(f"Invalid permission {oct(perm)} for shard '{shard}'")
        return errors


@dataclass
class AgentConfig:
    """Agent behavior configuration"""
    agent_id: str = "agent_001"
    agent_name: str = "DefaultAgent"
    max_iterations: int = 50
    max_execution_time: int = 300  # seconds
    allow_self_modification: bool = False
    sandbox_mode: bool = True
    verbose: bool = False
    log_level: str = "INFO"

    # Tool restrictions
    allowed_tools: List[str] = field(default_factory=lambda: ["all"])
    denied_tools: List[str] = field(default_factory=list)
    max_tool_chars: int = 10000

    # Safety
    confirm_destructive: bool = True
    dry_run: bool = False

    def validate(self) -> List[str]:
        """Validate agent configuration"""
        errors = []
        if self.max_iterations < 1:
            errors.append(f"max_iterations must be at least 1, got {self.max_iterations}")
        if self.max_execution_time < 1:
            errors.append(f"max_execution_time must be positive, got {self.max_execution_time}")
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            errors.append(f"Invalid log_level: {self.log_level}")
        if self.agent_id and not self.agent_id.replace("_", "").replace("-", "").isalnum():
            errors.append(f"agent_id contains invalid characters: {self.agent_id}")
        return errors


@dataclass
class ToolConfig:
    """Tool execution configuration"""
    timeout: int = 30
    max_output_chars: int = 10000
    truncate_indicator: str = "... [truncated]"
    safe_mode: bool = True
    allow_network: bool = False
    allow_filesystem: bool = True
    allowed_paths: List[str] = field(default_factory=lambda: ["./"])
    denied_commands: List[str] = field(default_factory=lambda: ["rm -rf", "sudo", "chmod -R"])

    def validate(self) -> List[str]:
        """Validate tool configuration"""
        errors = []
        if self.timeout < 1:
            errors.append(f"timeout must be positive, got {self.timeout}")
        if self.max_output_chars < 1:
            errors.append(f"max_output_chars must be positive, got {self.max_output_chars}")
        return errors


@dataclass
class FleetConfig:
    """Fleet coordination configuration"""
    fleet_id: str = "fleet_001"
    agent_id: str = "agent_001"
    shard_assignment: str = "default"
    heartbeat_interval: int = 30  # seconds
    heartbeat_timeout: int = 90   # seconds
    coordination_backend: str = "filesystem"  # filesystem, redis, etcd
    coordination_path: str = "./fleet_coordination"
    leader_election: bool = False
    max_agents: int = 100
    load_balancing: str = "round_robin"  # round_robin, least_loaded, hash

    # Communication
    message_queue_path: str = "./messages"
    broadcast_enabled: bool = True

    def validate(self) -> List[str]:
        """Validate fleet configuration"""
        errors = []
        if self.heartbeat_interval < 1:
            errors.append(f"heartbeat_interval must be positive, got {self.heartbeat_interval}")
        if self.heartbeat_timeout <= self.heartbeat_interval:
            errors.append("heartbeat_timeout must be greater than heartbeat_interval")
        if self.max_agents < 1:
            errors.append(f"max_agents must be at least 1, got {self.max_agents}")
        if self.load_balancing not in ["round_robin", "least_loaded", "hash"]:
            errors.append(f"Invalid load_balancing strategy: {self.load_balancing}")
        return errors


@dataclass
class Config:
    """Main configuration container with hierarchical loading"""
    model: ModelConfig = field(default_factory=ModelConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    tool: ToolConfig = field(default_factory=ToolConfig)
    fleet: FleetConfig = field(default_factory=FleetConfig)

    _config_path: Optional[Path] = field(default=None, repr=False)
    _env_prefix: str = field(default="AGENT_", repr=False)

    @classmethod
    def from_file(cls, config_path: str, env_prefix: str = "AGENT_") -> "Config":
        """Load configuration from JSON file with environment overrides"""
        path = Path(config_path)
        config_data = {}

        if path.exists():
            with open(path, 'r') as f:
                config_data = json.load(f)

        config = cls._from_dict(config_data)
        config._config_path = path
        config._env_prefix = env_prefix

        # Apply environment variable overrides
        config._apply_env_overrides()

        return config

    @classmethod
    def from_env(cls, env_prefix: str = "AGENT_") -> "Config":
        """Load configuration purely from environment variables"""
        config = cls()
        config._env_prefix = env_prefix
        config._apply_env_overrides()
        return config

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create Config from nested dictionary"""
        config = cls()

        if "model" in data:
            config.model = ModelConfig(**{k: v for k, v in data["model"].items() 
                                          if k in ModelConfig.__dataclass_fields__})
        if "memory" in data:
            mem_data = data["memory"].copy()
            # Handle shard_permissions separately if needed
            if "shard_permissions" in mem_data:
                # Convert string permissions to int if needed
                perms = {}
                for k, v in mem_data["shard_permissions"].items():
                    if isinstance(v, str):
                        perms[k] = int(v, 8)  # Parse octal string
                    else:
                        perms[k] = v
                mem_data["shard_permissions"] = perms
            config.memory = MemoryConfig(**{k: v for k, v in mem_data.items() 
                                            if k in MemoryConfig.__dataclass_fields__})
        if "agent" in data:
            config.agent = AgentConfig(**{k: v for k, v in data["agent"].items() 
                                          if k in AgentConfig.__dataclass_fields__})
        if "tool" in data:
            config.tool = ToolConfig(**{k: v for k, v in data["tool"].items() 
                                        if k in ToolConfig.__dataclass_fields__})
        if "fleet" in data:
            config.fleet = FleetConfig(**{k: v for k, v in data["fleet"].items() 
                                          if k in FleetConfig.__dataclass_fields__})

        return config

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides using dot notation"""
        env_vars = os.environ.copy()

        for key, value in env_vars.items():
            if not key.startswith(self._env_prefix):
                continue

            # Remove prefix and convert to lowercase dot notation
            config_key = key[len(self._env_prefix):].lower()

            # Parse the nested path
            parts = config_key.split("_")
            self._set_nested_value(parts, value)

    def _set_nested_value(self, parts: List[str], value: str) -> None:
        """Set a nested configuration value from environment variable"""
        if len(parts) < 2:
            return

        section = parts[0]
        field_name = "_".join(parts[1:])

        # Map section names to config objects
        section_map = {
            "model": self.model,
            "memory": self.memory,
            "agent": self.agent,
            "tool": self.tool,
            "fleet": self.fleet,
        }

        if section not in section_map:
            return

        config_obj = section_map[section]

        if not hasattr(config_obj, field_name):
            return

        # Convert value to appropriate type
        current_value = getattr(config_obj, field_name)
        converted_value = self._convert_value(value, type(current_value))

        setattr(config_obj, field_name, converted_value)

    def _convert_value(self, value: str, target_type: type) -> Any:
        """Convert string value to target type"""
        if target_type is bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif target_type is int:
            try:
                return int(value)
            except ValueError:
                return 0
        elif target_type is float:
            try:
                return float(value)
            except ValueError:
                return 0.0
        elif target_type is list:
            # Parse comma-separated list
            return [item.strip() for item in value.split(",")]
        elif target_type is dict:
            # Try to parse as JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}
        else:
            return value

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        Example: config.get("model.context_window")
        """
        parts = path.split(".")

        # Map first part to config object
        section_map = {
            "model": self.model,
            "memory": self.memory,
            "agent": self.agent,
            "tool": self.tool,
            "fleet": self.fleet,
        }

        if not parts or parts[0] not in section_map:
            return default

        obj = section_map[parts[0]]

        # Navigate through remaining parts
        for part in parts[1:]:
            if not hasattr(obj, part):
                return default
            obj = getattr(obj, part)

        return obj

    def set(self, path: str, value: Any) -> bool:
        """
        Set configuration value using dot notation.
        Example: config.set("model.temperature", 0.9)
        Returns True if successful, False if path invalid.
        """
        parts = path.split(".")

        section_map = {
            "model": self.model,
            "memory": self.memory,
            "agent": self.agent,
            "tool": self.tool,
            "fleet": self.fleet,
        }

        if len(parts) < 2 or parts[0] not in section_map:
            return False

        obj = section_map[parts[0]]

        if not hasattr(obj, parts[-1]):
            return False

        setattr(obj, parts[-1], value)
        return True

    def validate(self) -> List[str]:
        """
        Validate all configuration sections.
        Returns list of error messages (empty if valid).
        """
        errors = []
        errors.extend(self.model.validate())
        errors.extend(self.memory.validate())
        errors.extend(self.agent.validate())
        errors.extend(self.tool.validate())
        errors.extend(self.fleet.validate())
        return errors

    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        return len(self.validate()) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to nested dictionary"""
        return {
            "model": asdict(self.model),
            "memory": asdict(self.memory),
            "agent": asdict(self.agent),
            "tool": asdict(self.tool),
            "fleet": asdict(self.fleet),
        }

    def save(self, path: Optional[str] = None) -> None:
        """Save configuration to JSON file"""
        save_path = Path(path) if path else self._config_path
        if not save_path:
            raise ValueError("No path specified for saving configuration")

        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    def __repr__(self) -> str:
        return f"Config(agent_id={self.agent.agent_id}, model={self.model.model_name})"


# Convenience function for quick config loading
def load_config(config_path: Optional[str] = None, env_prefix: str = "AGENT_") -> Config:
    """
    Load configuration with priority: Env Vars > Config File > Defaults
    
    Args:
        config_path: Path to JSON config file (optional)
        env_prefix: Environment variable prefix (default: AGENT_)
    
    Returns:
        Config object with merged settings
    """
    if config_path and Path(config_path).exists():
        return Config.from_file(config_path, env_prefix)
    else:
        return Config.from_env(env_prefix)


if __name__ == "__main__":
    # Example usage and testing
    config = load_config()

    print("Configuration loaded:")
    print(f"  Agent ID: {config.agent.agent_id}")
    print(f"  Model: {config.model.model_name}")
    print(f"  Memory Mesh: {config.memory.use_mesh}")
    print(f"  Context Window: {config.get('model.context_window')}")

    # Test validation
    errors = config.validate()
    if errors:
        print("\nValidation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\n✓ Configuration is valid")
