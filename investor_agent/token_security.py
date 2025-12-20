"""
Encrypted token storage for Questrade API credentials.

Provides AES-256 encryption for token files with password-based key derivation.
Tokens are encrypted at rest and decrypted only when needed.

Usage:
    # First time setup - encrypt initial token
    encrypt_token_file(password="your_password")

    # At container startup - decrypt for use
    decrypt_token_file(password="your_password")

    # After API calls - re-encrypt updated token
    encrypt_token_file(password="your_password")
"""

import base64
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Try to import cryptography, fall back gracefully if not available
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    InvalidToken = Exception  # Fallback for type hints

logger = logging.getLogger(__name__)

# Default paths
TOKEN_FILE = Path.home() / ".questrade.json"
ENCRYPTED_FILE = Path.home() / ".questrade.enc"
SALT_FILE = Path.home() / ".questrade.salt"


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a Fernet-compatible key from password using PBKDF2."""
    if not CRYPTO_AVAILABLE:
        raise ImportError("cryptography package required. Install with: pip install cryptography")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,  # OWASP recommended minimum
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_token_file(
    password: str,
    token_path: Optional[Path] = None,
    encrypted_path: Optional[Path] = None,
    salt_path: Optional[Path] = None,
    delete_plaintext: bool = True
) -> bool:
    """
    Encrypt the Questrade token file.

    Reads ~/.questrade.json, encrypts it, saves to ~/.questrade.enc,
    and optionally removes the plaintext file.

    Args:
        password: Encryption password
        token_path: Optional custom token file path
        encrypted_path: Optional custom encrypted output path
        salt_path: Optional custom salt file path
        delete_plaintext: Whether to delete plaintext after encryption

    Returns:
        True if successful, False otherwise
    """
    if not CRYPTO_AVAILABLE:
        logger.error("cryptography package not installed")
        return False

    token_file = token_path or TOKEN_FILE
    enc_file = encrypted_path or ENCRYPTED_FILE
    s_file = salt_path or SALT_FILE

    if not token_file.exists():
        logger.error(f"Token file not found: {token_file}")
        return False

    try:
        # Read plaintext token
        with open(token_file, 'r') as f:
            token_data = f.read()

        # Generate or load salt
        if s_file.exists():
            with open(s_file, 'rb') as f:
                salt = f.read()
        else:
            salt = os.urandom(16)
            with open(s_file, 'wb') as f:
                f.write(salt)
            os.chmod(s_file, 0o600)  # Restrict permissions

        # Derive key and encrypt
        key = _derive_key(password, salt)
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(token_data.encode())

        # Save encrypted file
        with open(enc_file, 'wb') as f:
            f.write(encrypted_data)
        os.chmod(enc_file, 0o600)

        # Remove plaintext file
        if delete_plaintext:
            token_file.unlink()

        logger.info(f"Token encrypted and saved to {enc_file}")
        return True

    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return False


def decrypt_token_file(
    password: str,
    token_path: Optional[Path] = None,
    encrypted_path: Optional[Path] = None,
    salt_path: Optional[Path] = None
) -> bool:
    """
    Decrypt the Questrade token file.

    Reads ~/.questrade.enc, decrypts it, and saves to ~/.questrade.json.

    Args:
        password: Decryption password
        token_path: Optional custom output path
        encrypted_path: Optional custom encrypted file path
        salt_path: Optional custom salt file path

    Returns:
        True if successful, False otherwise
    """
    if not CRYPTO_AVAILABLE:
        logger.error("cryptography package not installed")
        return False

    enc_file = encrypted_path or ENCRYPTED_FILE
    s_file = salt_path or SALT_FILE
    token_file = token_path or TOKEN_FILE

    if not enc_file.exists():
        logger.warning(f"No encrypted file found: {enc_file}")
        return False

    if not s_file.exists():
        logger.error(f"Salt file missing: {s_file}")
        return False

    try:
        # Load salt
        with open(s_file, 'rb') as f:
            salt = f.read()

        # Read encrypted data
        with open(enc_file, 'rb') as f:
            encrypted_data = f.read()

        # Derive key and decrypt
        key = _derive_key(password, salt)
        fernet = Fernet(key)
        decrypted_data = fernet.decrypt(encrypted_data)

        # Save plaintext token
        with open(token_file, 'w') as f:
            f.write(decrypted_data.decode())
        os.chmod(token_file, 0o600)

        logger.info(f"Token decrypted to {token_file}")
        return True

    except InvalidToken:
        logger.error("Decryption failed: wrong password")
        return False
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return False


def is_token_encrypted(
    encrypted_path: Optional[Path] = None,
    token_path: Optional[Path] = None
) -> bool:
    """Check if token is currently in encrypted state."""
    enc_file = encrypted_path or ENCRYPTED_FILE
    t_file = token_path or TOKEN_FILE
    return enc_file.exists() and not t_file.exists()


def is_token_decrypted(token_path: Optional[Path] = None) -> bool:
    """Check if token is currently in decrypted state."""
    t_file = token_path or TOKEN_FILE
    return t_file.exists()


def get_token_status(
    token_path: Optional[Path] = None,
    encrypted_path: Optional[Path] = None
) -> str:
    """
    Get current token status.

    Returns:
        'encrypted': Token is encrypted (secure)
        'decrypted': Token is in plaintext
        'both': Both files exist (inconsistent state)
        'none': No token files found
    """
    enc_file = encrypted_path or ENCRYPTED_FILE
    t_file = token_path or TOKEN_FILE

    has_enc = enc_file.exists()
    has_plain = t_file.exists()

    if has_enc and has_plain:
        return 'both'
    elif has_enc:
        return 'encrypted'
    elif has_plain:
        return 'decrypted'
    else:
        return 'none'


class SecureTokenContext:
    """
    Context manager for secure token usage.

    Decrypts token on entry, re-encrypts on exit.

    Usage:
        with SecureTokenContext("password"):
            # Make Questrade API calls here
            # Token is decrypted and available
        # Token is re-encrypted when exiting
    """

    def __init__(
        self,
        password: str,
        token_path: Optional[Path] = None,
        encrypted_path: Optional[Path] = None,
        salt_path: Optional[Path] = None
    ):
        self.password = password
        self.token_path = token_path
        self.encrypted_path = encrypted_path
        self.salt_path = salt_path
        self.was_encrypted = is_token_encrypted(encrypted_path, token_path)

    def __enter__(self):
        if self.was_encrypted:
            if not decrypt_token_file(
                self.password,
                token_path=self.token_path,
                encrypted_path=self.encrypted_path,
                salt_path=self.salt_path
            ):
                raise ValueError("Failed to decrypt token")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if is_token_decrypted(self.token_path):
            encrypt_token_file(
                self.password,
                token_path=self.token_path,
                encrypted_path=self.encrypted_path,
                salt_path=self.salt_path
            )
        return False


def secure_token_cycle(
    password: str,
    token_path: Optional[Path] = None,
    encrypted_path: Optional[Path] = None,
    salt_path: Optional[Path] = None
):
    """
    Create a context manager for secure token usage.

    Decrypts token on entry, re-encrypts on exit.

    Args:
        password: Encryption/decryption password
        token_path: Optional custom token file path
        encrypted_path: Optional custom encrypted file path
        salt_path: Optional custom salt file path

    Returns:
        SecureTokenContext instance
    """
    return SecureTokenContext(password, token_path, encrypted_path, salt_path)


# CLI interface for manual encryption/decryption
if __name__ == "__main__":
    import getpass

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python -m investor_agent.token_security [encrypt|decrypt|status]")
        print()
        print("Commands:")
        print("  encrypt  - Encrypt plaintext token file")
        print("  decrypt  - Decrypt encrypted token file")
        print("  status   - Show current token state")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "status":
        status = get_token_status()
        status_messages = {
            'encrypted': "Token status: ENCRYPTED (secure)",
            'decrypted': "Token status: DECRYPTED (plaintext) - run 'encrypt' to secure",
            'both': "Token status: INCONSISTENT (both files exist) - manual cleanup needed",
            'none': "Token status: NOT FOUND - no token files present"
        }
        print(status_messages.get(status, f"Unknown status: {status}"))

    elif command == "encrypt":
        if not is_token_decrypted():
            print("No plaintext token found to encrypt")
            print(f"Expected: {TOKEN_FILE}")
            sys.exit(1)
        password = getpass.getpass("Enter encryption password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords don't match")
            sys.exit(1)
        if len(password) < 8:
            print("Password must be at least 8 characters")
            sys.exit(1)
        if encrypt_token_file(password):
            print("Token encrypted successfully")
            print(f"Encrypted file: {ENCRYPTED_FILE}")
            print(f"Plaintext file removed: {TOKEN_FILE}")
        else:
            print("Encryption failed")
            sys.exit(1)

    elif command == "decrypt":
        if not is_token_encrypted():
            status = get_token_status()
            if status == 'decrypted':
                print("Token is already decrypted (plaintext)")
            else:
                print("No encrypted token found")
                print(f"Expected: {ENCRYPTED_FILE}")
            sys.exit(1)
        password = getpass.getpass("Enter decryption password: ")
        if decrypt_token_file(password):
            print("Token decrypted successfully")
            print(f"Token file: {TOKEN_FILE}")
        else:
            print("Decryption failed (wrong password?)")
            sys.exit(1)

    else:
        print(f"Unknown command: {command}")
        print("Use: encrypt, decrypt, or status")
        sys.exit(1)
