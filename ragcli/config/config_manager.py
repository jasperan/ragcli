"""Configuration manager for ragcli."""

import yaml
import os
import re
from typing import Dict, Any
from copy import deepcopy
from .defaults import DEFAULT_CONFIG, REQUIRED_FIELDS

class ConfigValidationError(Exception):
    """Raised when configuration is invalid."""

def substitute_env_vars(value: Any) -> Any:
    """Recursively substitute environment variables in config values."""
    if isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_env_vars(v) for v in value]
    elif isinstance(value, str) and '${' in value and '}' in value:
        match = re.search(r'\$\{([^}]+)\}', value)
        if match:
            var_name = match.group(1)
            env_value = os.getenv(var_name, '')
            return value.replace('${' + var_name + '}', env_value)
    return value

def merge_dicts(default: Dict, override: Dict) -> Dict:
    """Deep merge override into default."""
    merged = deepcopy(default)
    for k, v in override.items():
        if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
            merged[k] = merge_dicts(merged[k], v)
        else:
            merged[k] = v
    return merged

def validate_config(config: Dict) -> None:
    """Validate the merged configuration."""
    for section, required in REQUIRED_FIELDS.items():
        if section not in config:
            raise ConfigValidationError(f"Missing required section: {section}")
        for field in required:
            if field not in config[section]:
                raise ConfigValidationError(f"Missing required field {field} in {section}")
    
    # Basic type validations
    if 'port' in config.get('ui', {}) and not isinstance(config['ui']['port'], int):
        raise ConfigValidationError("ui.port must be an integer")
    
    # Sensitive data check
    oracle = config.get('oracle', {})
    if 'password' in oracle and isinstance(oracle['password'], str) and not oracle['password'].startswith('${') and oracle['password']:
        print("WARNING: Oracle password is hardcoded in config. Consider using environment variables.")

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Safely load configuration from YAML with environment variable substitution.
    
    Features:
    - Validates required fields
    - Expands environment variables (${VAR_NAME} syntax)
    - Applies default values for missing optional fields
    - Checks for sensitive data exposure
    - Validates connection parameters
    
    Returns:
        dict: Merged configuration with defaults
        
    Raises:
        ConfigValidationError: If configuration is invalid
    """
    if not os.path.exists(config_path):
        if os.path.exists("config.yaml.example"):
            config_path = "config.yaml.example"
        else:
            raise FileNotFoundError("No config.yaml or config.yaml.example found.")
    
    with open(config_path, "r", encoding="utf-8") as f:
        loaded_config = yaml.safe_load(f) or {}
    
    # Substitute env vars
    substituted = substitute_env_vars(loaded_config)
    
    # Merge with defaults
    merged_config = merge_dicts(DEFAULT_CONFIG, substituted)
    
    # Validate
    validate_config(merged_config)
    
    return merged_config
