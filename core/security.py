"""Security utilities for QA Platform."""

import re
from typing import Dict, Any

SENSITIVE_PATTERNS = [
    'password', 'passwd', 'pass', 'token', 'secret', 'otp', 'pin',
    'ssn', 'credit', 'card', 'cvv', 'apikey', 'api_key', 'api-key',
    'fusion_pass', 'idcs', 'oracle_key', 'private_key', 'auth'
]


def is_sensitive_field(selector: str, value: str = "") -> bool:
    """
    Determine if a field is sensitive based on its selector or value.
    
    Args:
        selector: The UI selector for the field.
        value: The value being entered.
        
    Returns:
        bool: True if the field is deemed sensitive.
    """
    selector_lower = selector.lower() if selector else ""
    value_lower = value.lower() if value else ""
    
    for pattern in SENSITIVE_PATTERNS:
        # Check selector for sensitive patterns (using word boundaries to avoid matching "passenger" with "pass")
        if re.search(r'\b' + re.escape(pattern) + r'\b', selector_lower):
            return True
            
    # Heuristic for password-like values (length > 6, mixed characters)
    # Exclude values with spaces as they are usually sentences or addresses
    if value and len(value) > 6 and ' ' not in value:
        has_upper = bool(re.search(r'[A-Z]', value))
        has_lower = bool(re.search(r'[a-z]', value))
        has_digit = bool(re.search(r'\d', value))
        has_special = bool(re.search(r'[^A-Za-z0-9]', value))
        
        # If it has at least 3 of these characteristics, treat it as sensitive
        if sum([has_upper, has_lower, has_digit, has_special]) >= 3:
            return True
            
    return False


def redact_value(value: str) -> str:
    """
    Redact a sensitive value.
    
    Args:
        value: The original value.
        
    Returns:
        str: A redacted placeholder.
    """
    return "[REDACTED]"


def sanitize_step(action: str, selector: str, value: str) -> Dict[str, Any]:
    """
    Sanitize a test step, redacting sensitive information.
    
    Args:
        action: The action type.
        selector: The UI selector.
        value: The value being entered.
        
    Returns:
        dict: A sanitized dictionary with action, selector, value, and is_sensitive.
    """
    sensitive = is_sensitive_field(selector, value)
    safe_value = redact_value(value) if sensitive else value
    
    return {
        "action": action,
        "selector": selector,
        "value": safe_value,
        "is_sensitive": sensitive
    }
