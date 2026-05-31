"""CLI tool to store Fusion password in Windows Credential Manager."""

import argparse
import getpass
import sys
import keyring
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main() -> None:
    """Store the password in the keyring."""
    parser = argparse.ArgumentParser(description="Store Fusion password securely.")
    parser.add_argument("--pod", required=True, help="The Fusion POD name (e.g., TEST, DEV, PROD)")
    parser.add_argument("--user", required=True, help="The Fusion username")
    
    args = parser.parse_args()
    
    service_name = f"qap/{args.pod}"
    
    print(f"Setting password for user '{args.user}' on pod '{args.pod}'")
    password = getpass.getpass("Enter Fusion Password: ")
    
    if not password:
        print("Error: Password cannot be empty.", file=sys.stderr)
        sys.exit(1)
        
    try:
        keyring.set_password(service_name, args.user, password)
        print(f"Successfully stored password in keyring under service '{service_name}'.")
    except Exception as e:
        print(f"Failed to store password: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
