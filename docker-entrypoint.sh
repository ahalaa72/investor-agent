#!/bin/bash
#
# Docker entrypoint for investor-agent with encrypted Questrade token support
#
# If encrypted token exists (.questrade.enc), prompts for password to decrypt.
# Token is re-encrypted when container stops via trap.
#

set -e

ENCRYPTED_FILE="/root/.questrade.enc"
SALT_FILE="/root/.questrade.salt"
TOKEN_FILE="/root/.questrade.json"
PASSWORD_FILE="/tmp/.questrade_password"

# Function to decrypt token
decrypt_token() {
    if [ -f "$ENCRYPTED_FILE" ] && [ -f "$SALT_FILE" ]; then
        echo "Encrypted Questrade token found."

        # Check if password is passed via environment (for automation)
        if [ -n "$QUESTRADE_TOKEN_PASSWORD" ]; then
            echo "$QUESTRADE_TOKEN_PASSWORD" > "$PASSWORD_FILE"
            chmod 600 "$PASSWORD_FILE"
        else
            # Interactive password prompt
            read -s -p "Enter Questrade token password: " PASSWORD
            echo
            echo "$PASSWORD" > "$PASSWORD_FILE"
            chmod 600 "$PASSWORD_FILE"
        fi

        # Decrypt using Python module
        python3 -c "
import sys
sys.path.insert(0, '/app')
from pathlib import Path
from investor_agent.token_security import decrypt_token_file

with open('$PASSWORD_FILE', 'r') as f:
    password = f.read().strip()

if decrypt_token_file(password):
    print('Token decrypted successfully')
else:
    print('Decryption failed - wrong password?', file=sys.stderr)
    sys.exit(1)
"
        if [ $? -ne 0 ]; then
            rm -f "$PASSWORD_FILE"
            exit 1
        fi

        echo "Questrade token ready."
    elif [ -f "$TOKEN_FILE" ]; then
        echo "Warning: Plaintext token found. Consider encrypting with:"
        echo "  python -m investor_agent.token_security encrypt"
    else
        echo "No Questrade token found."
        echo "Set QUESTRADE_REFRESH_TOKEN in .env or use token_security module."
    fi
}

# Function to re-encrypt token on shutdown
encrypt_token() {
    if [ -f "$TOKEN_FILE" ] && [ -f "$PASSWORD_FILE" ] && [ -f "$SALT_FILE" ]; then
        echo "Re-encrypting Questrade token..."
        python3 -c "
import sys
sys.path.insert(0, '/app')
from investor_agent.token_security import encrypt_token_file

with open('$PASSWORD_FILE', 'r') as f:
    password = f.read().strip()

if encrypt_token_file(password):
    print('Token re-encrypted successfully')
else:
    print('Re-encryption failed', file=sys.stderr)
"
        rm -f "$PASSWORD_FILE"
    fi
}

# Trap shutdown signals to re-encrypt token
trap encrypt_token EXIT SIGTERM SIGINT

# Decrypt token if encrypted
decrypt_token

# Execute the command passed to the container
exec "$@"
