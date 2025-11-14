"""Configuration manager for ragcli."""

import yaml
import os
from typing import Dict, Any, Optional
from copy import deepcopy
from .defaults import DEFAULT_CONFIG, REQUIRED_FIELDS
from ..utils.helpers import parse_env_vars
from ..utils.validators import validate_config as validate_config_values

class ConfigValidationError(Exception):
    """Raised when configuration is invalid."""

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
    # Use comprehensive validation from validators module
    try:
        validate_config_values(config)
    except Exception as e:
        raise ConfigValidationError(str(e)) from e

    # Additional config-specific validations
    if 'port' in config.get('ui', {}):
        port = config['ui']['port']
        if not isinstance(port, int) or not (1024 <= port <= 65535):
            raise ConfigValidationError("ui.port must be an integer between 1024 and 65535")

    # Sensitive data check
    oracle = config.get('oracle', {})
    if 'password' in oracle and isinstance(oracle['password'], str) and oracle['password'] and not oracle['password'].startswith('${'):
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
    substituted = parse_env_vars(loaded_config)
    
    # Merge with defaults
    merged_config = merge_dicts(DEFAULT_CONFIG, substituted)
    
    # Validate
    validate_config(merged_config)
    
    return merged_config
