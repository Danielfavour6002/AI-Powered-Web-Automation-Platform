"""Security utilities for QA Platform."""

import re
import os
import base64
import json
import keyring
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

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


# --- Cryptographic Utilities (PBKDF2 & AES-256-GCM) ---

def derive_key(master_password: str, salt: bytes) -> bytes:
    """
    Derive a 256-bit AES key from master password and salt using PBKDF2 (600,000 iterations).
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,
    )
    return kdf.derive(master_password.encode('utf-8'))


def encrypt_data(key: bytes, plaintext: str) -> str:
    """
    Encrypt a plaintext string using AES-256-GCM.
    Returns nonce and ciphertext joined by a colon, base64-encoded.
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    nonce_b64 = base64.b64encode(nonce).decode('utf-8')
    ct_b64 = base64.b64encode(ciphertext).decode('utf-8')
    return f"{nonce_b64}:{ct_b64}"


def decrypt_data(key: bytes, encrypted_str: str) -> str:
    """
    Decrypt an AES-256-GCM encrypted string.
    """
    try:
        nonce_b64, ct_b64 = encrypted_str.split(":", 1)
        nonce = base64.b64decode(nonce_b64.encode('utf-8'))
        ciphertext = base64.b64decode(ct_b64.encode('utf-8'))
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")


# --- Keyring Wrapper & Fallback secrets ---

FALLBACK_FILE = Path("data/fallback_secrets.bin")


def get_client_password(client_id: str, master_key: Optional[bytes] = None) -> str:
    """
    Retrieve password for a client.
    Checks keyring first, falls back to fallback_secrets.bin if keyring is unavailable.
    """
    try:
        pw = keyring.get_password("qap_client_passwords", client_id)
        if pw is not None:
            return pw
    except Exception:
        pass
        
    if master_key and FALLBACK_FILE.exists():
        try:
            secrets = load_fallback_secrets(master_key)
            return secrets.get(client_id, "")
        except Exception:
            pass
    return ""


def set_client_password(client_id: str, password: str, master_key: Optional[bytes] = None) -> bool:
    """
    Store password for a client.
    Tries OS keyring first. If that fails (headless Linux/no DBus), falls back to fallback_secrets.bin.
    Returns True if saved to keyring, False if saved to fallback.
    """
    keyring_success = False
    try:
        keyring.set_password("qap_client_passwords", client_id, password)
        keyring_success = True
    except Exception:
        pass
        
    if not keyring_success and master_key:
        save_fallback_secret(master_key, client_id, password)
    return keyring_success


def load_fallback_secrets(key: bytes) -> Dict[str, str]:
    """Load and decrypt all fallback secrets from file."""
    if not FALLBACK_FILE.exists():
        return {}
    try:
        content = FALLBACK_FILE.read_text(encoding='utf-8')
        decrypted = decrypt_data(key, content)
        return json.loads(decrypted)
    except Exception:
        return {}


def save_fallback_secret(key: bytes, client_id: str, password: str) -> None:
    """Encrypt and save a fallback secret to file."""
    secrets = load_fallback_secrets(key)
    secrets[client_id] = password
    plaintext = json.dumps(secrets)
    encrypted = encrypt_data(key, plaintext)
    FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    FALLBACK_FILE.write_text(encrypted, encoding='utf-8')


def is_keyring_working() -> bool:
    """Verify if the OS keyring is working properly."""
    try:
        keyring.set_password("qap_test_keyring", "test", "test_pass")
        pw = keyring.get_password("qap_test_keyring", "test")
        keyring.delete_password("qap_test_keyring", "test")
        return pw == "test_pass"
    except Exception:
        return False

